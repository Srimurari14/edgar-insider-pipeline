# agent.py

import json
import os
import re

from groq import Groq

from scripts.athena_client import run_query
from scripts.bronze_fetch import fetch_raw_filing
from scripts.schema import SCHEMA_DESCRIPTION

MODEL = "openai/gpt-oss-120b"
MAX_ITERATIONS = 4

client = Groq(api_key=os.environ["GROQ_API_KEY"])

# The model ignores character-level formatting rules often enough that these are
# fixed in code instead. This runs locally and costs nothing against the token budget.
CHARACTER_REPLACEMENTS = {
    "\u2014": ", ",   # em dash
    "\u2013": "-",    # en dash
    "\u2010": "-",    # hyphen
    "\u2011": "-",    # non-breaking hyphen
    "\u2012": "-",    # figure dash
    "\u2018": "'",    # left single quote
    "\u2019": "'",    # right single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2026": "...",  # ellipsis
    "\u00a0": " ",    # non-breaking space
    "\u202f": " ",    # narrow no-break space
    "\u2009": " ",    # thin space
    "\u200b": "",     # zero width space
}


def sanitize(text: str) -> str:
    """Normalizes the model's output: plain punctuation, no bullets, no italics."""
    if not text:
        return text

    for bad, good in CHARACTER_REPLACEMENTS.items():
        text = text.replace(bad, good)

    # Strip a leading bullet marker from any line, keeping the text after it.
    # The model already writes full sentences, so the line reads fine without it.
    text = re.sub(r"^[ \t]*[-*\u2022\u00b7][ \t]+", "", text, flags=re.M)

    # Remove single-asterisk italics while leaving **bold** intact. The negative
    # lookarounds make sure neither asterisk of a bold pair is matched.
    text = re.sub(r"(?<!\*)\*(?!\*)([^*\n]+?)(?<!\*)\*(?!\*)", r"\1", text)

    # Collapse runs of spaces left behind by the replacements above. Line breaks
    # are untouched, so paragraph structure survives.
    text = re.sub(r" {2,}", " ", text)

    return text


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_sql_query",
            "description": (
                "Run a read-only SQL query against the edgar_form4 Athena database "
                "and return the results. Use this whenever you need real data to "
                "answer the user's question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "A valid Athena SQL query (Presto/Trino syntax).",
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_raw_filing",
            "description": (
                "Fetches the raw SEC XML for one specific Form 4 filing, given its "
                "accession number and filing_date. This is expensive, so use it only "
                "when a value looks wrong or unexplained and the answer is not "
                "available from the tables."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "accession": {
                        "type": "string",
                        "description": "The filing's accession number, e.g. '0000905148-26-003232'.",
                    },
                    "filing_date": {
                        "type": "string",
                        "description": "The filing's filing_date, e.g. '2026-08-18'.",
                    },
                },
                "required": ["accession", "filing_date"],
            },
        },
    },
]

FORMATTING_RULES = """Write your answer as plain prose in full sentences. No markdown
tables, no bullet lists, no numbered lists. You may use **bold** for a key number or
name, and nothing else."""

HONESTY_RULES = """Only describe data you have actually seen in a tool result. Never
describe rows as empty, missing, blank, or lacking detail unless a tool result showed
them that way. If a result was trimmed, the rows you cannot see were removed to save
space, not absent from the database, so do not describe them at all. If you did not
query something, say that you did not look at it.

Remember what your own query asked for. If you filtered with a WHERE clause, the
result describes only the rows that passed that filter, not the whole table. A count
from a filtered query is a count of matching rows, so never present it as a total,
and never conclude that the rest of the table shares the property you filtered on.

Keep separate results separate. A name, date, or figure that came from one query or
one filing must not be attached to a different filing. If you are not certain which
result a detail came from, leave it out."""

DATA_PREFERENCE_RULES = """Always reach for the smallest source that can answer the
question, and move to a larger one only when the question genuinely needs it. In
order, cheapest first:

First, agg_issuer_activity and agg_owner_activity. These hold one row per company or
person, already totalled, and are never trimmed. For a broad question about a company
or an insider ("tell me about X", "how active is X", "what has X been doing"), start
here. Use dim_issuers and dim_owners the same way for a name or ticker lookup. When a
question is about a company's or a person's activity, the user almost always wants to
know who was involved, so include owner names in your answer rather than leaving them
out.

Second, fct_transactions with an aggregate such as count(), sum(), min() or max().
These return a single row no matter how many rows they scan, so they are cheap and
never trimmed.

Third, fct_transactions detail rows. These get trimmed and cost a lot, so query them
only when the question names something specific: one filing, one person, one date, or
a ranking like the largest trades.

Last, fetch_raw_filing. This returns a whole XML document and is the most expensive
thing you can do. Use it only when a value in the tables looks wrong or unexplained,
or the user asks why something happened. Never use it just to gather more background.

If a question is broader than your remaining steps allow, answer it at the aggregate
level and say which specific thing the user could ask about next. Do not try to walk
through every filing one by one."""

SYSTEM_PROMPT = f"""You are a data analyst assistant for an insider-trading database.
You answer questions by writing SQL queries against the schema below and
reasoning over the real results. Never guess at numbers, always query for them.

The schema below lists every column that exists. Do not reference any column
that is not in it. In particular, the explanatory text that some filings carry
(remarks and footnotes) exists only inside the raw filing XML returned by the
fetch_raw_filing tool. It is not a column in any table, so never put it in a SQL
query.

If a query fails, read the error message and try a corrected query.

Query results are trimmed to the first few rows to save space. A result with
"truncated" set to true means you are seeing a sample. Describe what the sample
shows and say plainly that it is a sample. Do not run more queries trying to
retrieve everything. If you need a total, use count(*), which returns a single
row and is never trimmed.

You have very few steps available, so plan efficiently. Select only the columns
you need rather than using SELECT *, and prefer one well-aimed query over several
exploratory ones.

{DATA_PREFERENCE_RULES}

{HONESTY_RULES}

{SCHEMA_DESCRIPTION}

When you have enough information, give your final answer and stop calling tools.

{FORMATTING_RULES}
"""

FINAL_ANSWER_NUDGE = f"""You have no more steps available. Answer the question now
using only what you have already found. Do not call any tools.

{HONESTY_RULES}

{FORMATTING_RULES}"""


def ask(question: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    for step in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            reasoning_effort="low",
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return sanitize(message.content)  # model is done, this is the final answer

        # The assistant's own message (with its tool_calls) must be added
        # to history BEFORE the tool results, or the next API call fails.
        messages.append(
            {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ],
            }
        )

        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            tool_name = tool_call.function.name

            if tool_name == "run_sql_query":
                print(f"\n[step {step}] running SQL:\n{args['sql']}\n")
                result = run_query(args["sql"])

            elif tool_name == "fetch_raw_filing":
                print(
                    f"\n[step {step}] fetching raw filing: "
                    f"{args['accession']} ({args['filing_date']})\n"
                )
                result = fetch_raw_filing(args["accession"], args["filing_date"])

            else:
                result = {"success": False, "error": f"Unknown tool: {tool_name}"}

            print(f"[step {step}] result: {json.dumps(result)[:300]}\n")

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    # Out of steps. Rather than discarding everything gathered, make one final
    # call with tools switched off, forcing a prose answer from what we have.
    print("\n[final] step limit reached, forcing an answer from what was found\n")
    messages.append({"role": "user", "content": FINAL_ANSWER_NUDGE})

    final = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tool_choice="none",
    )

    return sanitize(final.choices[0].message.content) or (
        "I could not put together an answer to that one. Try a narrower question."
    )


if __name__ == "__main__":
    question = input("Ask a question: ")
    print("\n" + ask(question))