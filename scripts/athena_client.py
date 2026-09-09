# athena_client.py

import time
import boto3

DATABASE = "edgar_form4"
OUTPUT_LOCATION = "s3://edgar-form4-sri/athena-query-results/"
MAX_WAIT_SECONDS = 60  # give up if a query takes longer than this

client = boto3.client("athena", region_name="us-east-1")


def run_query(sql: str) -> dict:
    try:
        response = client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={"Database": DATABASE},
            ResultConfiguration={"OutputLocation": OUTPUT_LOCATION},
        )
    except Exception as e:
        return {"success": False, "error": f"Failed to start query: {e}"}

    query_id = response["QueryExecutionId"]

    waited = 0
    while waited < MAX_WAIT_SECONDS:
        status = client.get_query_execution(QueryExecutionId=query_id)
        state = status["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        elif state in ("FAILED", "CANCELLED"):
            reason = status["QueryExecution"]["Status"].get(
                "StateChangeReason", "Unknown error"
            )
            return {"success": False, "error": reason}

        time.sleep(1)
        waited += 1
    else:
        return {"success": False, "error": "Query timed out after 60 seconds"}

    try:
        result = client.get_query_results(QueryExecutionId=query_id)
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch results: {e}"}

    rows = result["ResultSet"]["Rows"]
    if not rows:
        return {"success": True, "rows": []}

    headers = [col["VarCharValue"] for col in rows[0]["Data"]]
    data_rows = []
    for row in rows[1:]:
        values = [col.get("VarCharValue", "") for col in row["Data"]]
        data_rows.append(dict(zip(headers, values)))

    return {"success": True, "rows": data_rows}