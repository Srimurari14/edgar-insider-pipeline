import json
from scripts.athena_client import run_query
from scripts.bronze_fetch import fetch_raw_filing, extract_explanation

def handler(event, context):
    path = event.get("path", "")

    if path == "/top-trades":
        data = get_top_trades()
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


def get_top_trades():
    buys_sql = """
    SELECT issuer_name, owner_name, transaction_shares, transaction_price_per_share, dollar_value
    FROM edgar_form4.fct_transactions
    WHERE filing_date = (SELECT MAX(filing_date) FROM edgar_form4.fct_transactions)
      AND dollar_value_unreliable = false
      AND transaction_classification = 'Buy'
    ORDER BY dollar_value DESC
    LIMIT 5
    """

    sells_sql = """
    SELECT issuer_name, owner_name, transaction_shares, transaction_price_per_share, dollar_value
    FROM edgar_form4.fct_transactions
    WHERE filing_date = (SELECT MAX(filing_date) FROM edgar_form4.fct_transactions)
      AND dollar_value_unreliable = false
      AND transaction_classification = 'Sell'
    ORDER BY dollar_value DESC
    LIMIT 5
    """

    buys_result = run_query(buys_sql)
    sells_result = run_query(sells_sql)

    return {
        "buys": buys_result.get("rows", []) if buys_result["success"] else [],
        "sells": sells_result.get("rows", []) if sells_result["success"] else [],
    }

def get_anomalies():
    sql = """
    SELECT filing_date, accession, issuer_name, owner_name, transaction_classification,
           transaction_code, transaction_shares, transaction_price_per_share, dollar_value,
           is_debt_security, is_nonstandard_pricing
    FROM edgar_form4.fct_transactions
    WHERE dollar_value_unreliable = true
    ORDER BY dollar_value DESC
    LIMIT 20
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
    LIMIT 20
    """
    result = run_query(sql)
    return {"companies": result.get("rows", []) if result["success"] else []}