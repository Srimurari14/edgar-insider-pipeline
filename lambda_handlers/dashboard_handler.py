import json
from scripts.athena_client import run_query

def handler(event, context):
    path = event.get("path", "")

    if path == "/top-trades":
        data = get_top_trades()
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