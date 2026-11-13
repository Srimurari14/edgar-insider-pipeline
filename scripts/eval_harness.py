# eval_harness.py
#
# Self-updating eval harness for the EDGAR insider-trading agent.
#
# GRADING TIERS (the key design idea):
#   "auto"              -> golden SQL is an INDEPENDENT, trusted reference.
#                          Counts toward the headline score. Safe to re-run
#                          every time you change the agent.
#   "auto_pending_data" -> golden SQL shares a known data-quality blind spot
#                          with the agent. The golden is as likely wrong as the
#                          agent, so a "match" proves nothing. Runs and prints,
#                          but does NOT count toward the trusted score. TEMPORARY
#                          quarantine: once the underlying flag is fixed, move the
#                          case back to "auto". (As of the is_implausible_price
#                          fix, this tier is empty again.)
#   "manual"            -> correct answer is a judgment call. Agent answer is
#                          dumped to JSON for you to read. No auto pass/fail.
#
# How an auto / auto_pending_data case is graded, per run:
#   1. Run golden SQL directly via athena_client.run_query -> true answer NOW
#      (live data, so it doesn't rot when the 6am pipeline adds rows).
#   2. Run agent.ask(question) -> agent prose.
#   3. Check the golden answer appears in the agent prose.
#
# Design notes:
#   - Every golden SQL aliases its output column to "result".
#   - athena_client.run_query trims to 10 rows. All golden SQL here returns a
#     SINGLE row, so the cap never touches ground truth. Do NOT write a golden
#     SQL that depends on more than 10 returned rows.
#   - All questions use ABSOLUTE dates (September 2026), never "last month".
#   - Raw agent answers are written to eval_results.json so you can tell a real
#     failure from a matcher failure WITHOUT re-calling the model (saves quota).

import json
import re
import time
from datetime import datetime, timezone

from scripts.athena_client import run_query

from scripts.agent import ask as agent_ask


def get_agent_answer(question: str) -> str:
    """Single place to adapt if agent.ask returns something other than a str."""
    result = agent_ask(question)
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        for key in ("answer", "response", "text", "output"):
            if key in result:
                return str(result[key])
    return str(result)

WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def numbers_in(text: str):
    """All numbers in text as a set of floats. Handles commas, trailing-zero
    decimals, and spelled-out small numbers.
    '1,307' -> 1307.0, '140,942.00' -> 140942.0, 'two' -> 2.0"""
    found = set()
    for m in re.findall(r"[-+]?[\d,]*\.?\d+", text):
        try:
            found.add(float(m.replace(",", "")))
        except ValueError:
            pass
    low = text.lower()
    for word, val in WORD_NUMBERS.items():
        if re.search(rf"\b{word}\b", low):
            found.add(float(val))
    return found


def match_numeric(golden: str, answer: str) -> bool:
    try:
        gold = float(golden.replace(",", ""))
    except ValueError:
        return False
    return any(abs(gold - n) < 0.01 for n in numbers_in(answer))


def match_text(golden: str, answer: str) -> bool:
    return golden.strip().lower() in answer.lower()


def match_contains(substrings, answer: str) -> bool:
    low = answer.lower()
    return any(s.lower() in low for s in substrings)

CASES = [
    {
        "id": "sep_purchases_count",
        "tier": "auto",
        "question": "How many purchase transactions by officers or directors happened in September 2026?",
        "golden_sql": """
            SELECT count(*) AS result
            FROM fct_transactions
            WHERE transaction_code = 'P'
              AND transaction_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'
              AND (is_officer = true OR is_director = true)
        """,
        "match": "numeric",
    },
    {
        "id": "total_rows",
        "tier": "auto",
        "question": "How many transactions are in the dataset in total?",
        "golden_sql": "SELECT count(*) AS result FROM fct_transactions",
        "match": "numeric",
    },
    {
        "id": "distinct_issuers",
        "tier": "auto",
        "question": "How many different companies have filings in the dataset?",
        "golden_sql": "SELECT count(DISTINCT issuer_cik) AS result FROM fct_transactions",
        "match": "numeric",
    },
    {
        "id": "rb_global_total",
        "tier": "auto",
        "question": "What is the total dollar value of real insider purchases at RB Global (CIK 0001046102)?",
        "golden_sql": """
            SELECT sum(dollar_value) AS result
            FROM fct_transactions
            WHERE issuer_cik = '0001046102'
              AND transaction_code = 'P'
              AND is_empty_transaction = false
              AND dollar_value_unreliable = false
        """,
        "match": "numeric",
    },
    {
        "id": "rb_global_traders",
        "tier": "auto",
        "question": "How many distinct insiders actually traded at RB Global (CIK 0001046102)?",
        "golden_sql": """
            SELECT count(DISTINCT owner_cik) AS result
            FROM fct_transactions
            WHERE issuer_cik = '0001046102'
              AND is_empty_transaction = false
        """,
        "match": "numeric",
    },

    # Name-order entity resolution regression guard (Bug B).
    # Emily Ellis is stored surname-first ("Ellis Emily") and filed a
    # derivative-only Form 4, so she has 0 real (non-empty) transactions but
    # DOES exist. Before the owner_name_search fix the agent answered
    # "no record of Emily Ellis". The golden resolves her through
    # owner_name_search exactly as the agent should, and returns 0. The agent
    # passes only if it finds her and reports 0.
    # Caveat: a regressed "not found" answer could also contain "0" and
    # false-pass this numeric check, so the manual amd_ellis_real_trades case
    # below is kept as the human backstop that reads whether she was actually
    # found.
    {
        "id": "name_order_lookup_ellis",
        "tier": "auto",
        "question": "How many actual stock trades did Emily Ellis make?",
        "golden_sql": """
            SELECT count(*) AS result
            FROM fct_transactions
            WHERE owner_cik = (
                SELECT owner_cik FROM dim_owners
                WHERE owner_name_search LIKE '%ellis%'
                  AND owner_name_search LIKE '%emily%'
                LIMIT 1
            )
            AND is_empty_transaction = false
        """,
        "match": "numeric",
    },

    {
        "id": "top_issuer_by_purchase_value_sep",
        "tier": "auto",
        "question": "Which company had the highest total insider purchase value in September 2026, excluding unreliable dollar values?",
        "golden_sql": """
            SELECT issuer_name AS result
            FROM fct_transactions
            WHERE transaction_code = 'P'
              AND transaction_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'
              AND dollar_value_unreliable = false
            GROUP BY issuer_name
            ORDER BY sum(dollar_value) DESC, issuer_name
            LIMIT 1
        """,
        "match": "text",
    },
    {
        "id": "largest_single_purchase_reliable",
        "tier": "auto",
        "question": "What was the single largest reliable insider stock purchase in September 2026, and who made it?",
        "golden_sql": """
            SELECT owner_name AS result
            FROM fct_transactions
            WHERE transaction_code = 'P'
              AND transaction_date BETWEEN DATE '2026-09-01' AND DATE '2026-09-30'
              AND dollar_value_unreliable = false
            ORDER BY dollar_value DESC, owner_name
            LIMIT 1
        """,
        "match": "text",
    },

    # ---- MANUAL: correct answer is a judgment, read the JSON dump ----
    {
        "id": "tech_exec_bought_sep",
        "tier": "manual",
        "question": "Did any technology company executives buy stock in September 2026?",
        "must_contain": ["yes"],
        "note": "Regression test for over-constraint false negative. Truth = YES (Uber, GameStop, etc). VERIFY named people/titles against Athena; agent has mislabeled CEOs before.",
    },
    {
        "id": "amd_ellis_real_trades",
        "tier": "manual",
        "question": "How many actual stock purchases or sales did AMD insider Emily Ellis report on her August 2026 Form 4?",
        "must_contain": ["0", "zero", "none"],
        "note": "Human backstop for the name_order_lookup_ellis auto case. Truth = 0 non-derivative trades, but she DOES exist (CIK 0002102463). 'Could not find her' is WRONG even if it says 0. Read the answer to confirm she was actually FOUND, not just that a 0 appeared.",
    },
    {
        "id": "anomaly_detection",
        "tier": "manual",
        "question": "What is the most extreme dollar value in the dataset, and should it be trusted?",
        "must_contain": ["unreliable", "not"],
        "note": "Should surface ~1.6 quadrillion AND flag it unreliable. Agent should now cite is_implausible_price as one reason.",
    },
]

def run_golden(sql: str):
    """Run trusted SQL, return the single 'result' value as a string, or raise."""
    res = run_query(sql)
    if not res.get("success"):
        raise RuntimeError(f"Golden SQL failed: {res.get('error')}")
    rows = res.get("rows", [])
    if not rows:
        raise RuntimeError("Golden SQL returned no rows")
    row = rows[0]
    if "result" not in row:
        raise RuntimeError(f"Golden SQL must alias its column to 'result'. Got: {list(row.keys())}")
    return row["result"]


def grade_golden(case, answer, record):
    """Shared grading for auto and auto_pending_data. Returns True/False/None.
    None means the golden itself errored."""
    try:
        golden = run_golden(case["golden_sql"])
        record["golden"] = golden
        if case["match"] == "numeric":
            ok = match_numeric(golden, answer)
        else:
            ok = match_text(golden, answer)
        record["pass"] = ok
        return ok
    except Exception as e:
        record["pass"] = False
        record["golden_error"] = str(e)
        return None

def run(cases=CASES, outfile="eval_results.json"):
    results = []
    auto_passed = auto_total = 0
    pending_passed = pending_total = 0

    for case in cases:
        cid = case["id"]
        tier = case["tier"]
        q = case["question"]
        print(f"\n=== {cid}  [{tier}] ===")
        print(f"Q: {q}")

        record = {"id": cid, "tier": tier, "question": q}
        t0 = time.time()
        try:
            answer = get_agent_answer(q)
        except Exception as e:
            answer = f"<AGENT ERROR: {e}>"
        record["agent_answer"] = answer
        record["latency_sec"] = round(time.time() - t0, 1)
        if "note" in case:
            record["note"] = case["note"]

        if tier == "auto":
            auto_total += 1
            ok = grade_golden(case, answer, record)
            if ok is None:
                print(f"GOLDEN ERROR: {record.get('golden_error')}  -> FAIL")
            else:
                auto_passed += int(ok)
                print(f"golden={record.get('golden')}  ->  {'PASS' if ok else 'FAIL'}  ({record['latency_sec']}s)")

        elif tier == "auto_pending_data":
            pending_total += 1
            ok = grade_golden(case, answer, record)
            if ok is None:
                print(f"GOLDEN ERROR: {record.get('golden_error')}  (not counted)")
            else:
                pending_passed += int(ok)
                print(f"golden={record.get('golden')}  ->  {'match' if ok else 'mismatch'}  "
                      f"[GOLDEN UNVERIFIED, not counted]  ({record['latency_sec']}s)")

        else:  # manual
            weak = match_contains(case.get("must_contain", []), answer)
            record["weak_signal_pass"] = weak
            print(f"[manual review] weak-signal {'hit' if weak else 'miss'}  ({record['latency_sec']}s)")

        print(f"A: {answer[:300]}{'...' if len(answer) > 300 else ''}")
        results.append(record)

    print("\n" + "=" * 55)
    if auto_total:
        pct = round(100 * auto_passed / auto_total)
        print(f"AUTO (trusted):        {auto_passed}/{auto_total} passed  ({pct}%)")
    if pending_total:
        print(f"AUTO_PENDING_DATA:     {pending_passed}/{pending_total} golden-agent agree  "
              f"[golden unverified, NOT a real score]")
    manual = [r for r in results if r["tier"] == "manual"]
    if manual:
        print(f"MANUAL:                {len(manual)} cases, read eval_results.json")
        for r in manual:
            print(f"   {r['id']}: weak-signal {'hit' if r.get('weak_signal_pass') else 'miss'}")

    payload = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "auto_passed": auto_passed,
        "auto_total": auto_total,
        "pending_passed": pending_passed,
        "pending_total": pending_total,
        "results": results,
    }
    with open(outfile, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nFull results written to {outfile}")
    return payload


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        selected = [c for c in CASES if c["id"] in wanted]
        if not selected:
            print(f"No cases matched {wanted}. Available: {[c['id'] for c in CASES]}")
            sys.exit(1)
        run(selected)
    else:
        run()