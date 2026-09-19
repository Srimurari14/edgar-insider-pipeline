# agent.py

import json
import os

from groq import Groq

from scripts.athena_client import run_query
from scripts.bronze_fetch import fetch_raw_filing
from scripts.schema import SCHEMA_DESCRIPTION

MODEL = "openai/gpt-oss-120b"
MAX_ITERATIONS = 8

client = Groq(api_key=os.environ["GROQ_API_KEY"])

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
                "accession number and filing_date. Use this when a SQL result looks "
                "wrong, unusual, or unexplained (e.g. an implausible dollar_value or "
                "price_per_share), to check what the original filing actually says "
                "before concluding it's an error."
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

SYSTEM_PROMPT = f"""You are a data analyst assistant for an insider-trading database.
You answer questions by writing SQL queries against the schema below and
reasoning over the real results. Never guess at numbers, always query for them.

If a SQL result contains an unusually large, small, or otherwise implausible
value, use the fetch_raw_filing tool to check the original SEC filing before
concluding it's real or explaining why. Some anomalies have a plain-English
explanation in the filing's <remarks> field; others may be genuine filer
errors with no explanation available.

If a query fails, read the error message and try a corrected query. If a
result looks wrong or incomplete, you may run another query to check it
before answering.

{SCHEMA_DESCRIPTION}

When you have enough information to answer the user's question, respond in
plain English with your final answer. Do not call any more tools once you
are ready to answer.
"""


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
        )

        message = response.choices[0].message

        if not message.tool_calls:
            return message.content  # model is done, this is the final answer

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

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )

    return "Gave up after too many steps without a final answer."


if __name__ == "__main__":
    question = input("Ask a question: ")
    print("\n" + ask(question))