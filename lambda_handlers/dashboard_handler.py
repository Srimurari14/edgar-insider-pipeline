import json
import re
from scripts.athena_client import run_query
from scripts.bronze_fetch import fetch_raw_filing, extract_explanation


def handler(event, context):
    path = event.get("path", "")

    if path == "/top-trades":
        params = event.get("queryStringParameters") or {}
        data = get_top_trades(params.get("date"))
    elif path == "/anomalies":
        data = get_anomalies()
    elif path == "/issuers":
        params = event.get("queryStringParameters") or {}
        data = get_issuers(params.get("search"))
    elif path == "/large-company-activity":
        data = get_large_company_activity()
    else:
        return {
            "statusCode": 404,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Unknown path"})
        }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps(data)
    }


def get_top_trades(date_param=None):
    if date_param and re.match(r'^\d{4}-\d{2}-\d{2}$', date_param):
        target_date = date_param
    else:
        date_result = run_query("SELECT MAX(filing_date) as d FROM edgar_form4.fct_transactions")
        if not date_result["success"] or not date_result["rows"]:
            return {"date": None, "buys": [], "sells": [], "prev_date": None, "next_date": None}
        target_date = date_result["rows"][0]["d"]

    buys_sql = f"""
    SELECT issuer_name, owner_name, transaction_shares, transaction_price_per_share, dollar_value
    FROM edgar_form4.fct_transactions
    WHERE filing_date = '{target_date}'
      AND dollar_value_unreliable = false
      AND transaction_classification = 'Buy'
    ORDER BY dollar_value DESC
    LIMIT 5
    """
    sells_sql = f"""
    SELECT issuer_name, owner_name, transaction_shares, transaction_price_per_share, dollar_value
    FROM edgar_form4.fct_transactions
    WHERE filing_date = '{target_date}'
      AND dollar_value_unreliable = false
      AND transaction_classification = 'Sell'
    ORDER BY dollar_value DESC
    LIMIT 5
    """
    prev_sql = f"SELECT MAX(filing_date) as d FROM edgar_form4.fct_transactions WHERE filing_date < '{target_date}'"
    next_sql = f"SELECT MIN(filing_date) as d FROM edgar_form4.fct_transactions WHERE filing_date > '{target_date}'"

    buys_result = run_query(buys_sql)
    sells_result = run_query(sells_sql)
    prev_result = run_query(prev_sql)
    next_result = run_query(next_sql)

    def first_date(result):
        if result["success"] and result["rows"] and result["rows"][0].get("d"):
            return result["rows"][0]["d"]
        return None

    return {
        "date": target_date,
        "buys": buys_result.get("rows", []) if buys_result["success"] else [],
        "sells": sells_result.get("rows", []) if sells_result["success"] else [],
        "prev_date": first_date(prev_result),
        "next_date": first_date(next_result),
    }


def get_anomalies():
    sql = """
    SELECT filing_date, accession, issuer_name, owner_name, transaction_classification,
           transaction_code, transaction_shares, transaction_price_per_share, dollar_value,
           is_debt_security, is_nonstandard_pricing
    FROM edgar_form4.fct_transactions
    WHERE dollar_value_unreliable = true
    ORDER BY dollar_value DESC
    LIMIT 18
    """
    result = run_query(sql)
    rows = result.get("rows", []) if result["success"] else []

    enriched = []
    for row in rows:
        filing = fetch_raw_filing(row["accession"], row["filing_date"])
        explanation = extract_explanation(filing["xml"]) if filing["success"] else {"remarks": None, "footnotes": {}}
        enriched.append({**row, "explanation": explanation})

    return {"anomalies": enriched}


def get_issuers(search_term=None):
    if search_term:
        safe_term = search_term.replace("'", "''")
        sql = f"""
        SELECT issuer_cik, issuer_name, issuer_trading_symbol
        FROM edgar_form4.dim_issuers
        WHERE lower(issuer_name) LIKE lower('%{safe_term}%')
        ORDER BY issuer_name
        LIMIT 50
        """
    else:
        sql = """
        SELECT issuer_cik, issuer_name, issuer_trading_symbol
        FROM edgar_form4.dim_issuers
        ORDER BY issuer_name
        LIMIT 50
        """
    result = run_query(sql)
    return {"issuers": result.get("rows", []) if result["success"] else []}


def get_large_company_activity():
    sql = """
    SELECT issuer_cik, issuer_name, total_owner_count, last_transaction_date,
           total_buy_value, total_buy_count, total_sell_value, total_sell_count
    FROM edgar_form4.agg_issuer_activity
    ORDER BY total_owner_count DESC
    LIMIT 12
    """
    result = run_query(sql)
    return {"companies": result.get("rows", []) if result["success"] else []}