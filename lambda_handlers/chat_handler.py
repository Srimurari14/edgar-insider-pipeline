# chat_handler.py

import json
from scripts.agent import ask

def handler(event, context):
    params = event.get("queryStringParameters") or {}
    question = params.get("q")

    if not question:
        return {
            "statusCode": 400,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "Missing 'q' query parameter"})
        }

    try:
        answer = ask(question)
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": f"Agent failed: {e}"})
        }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({"question": question, "answer": answer})
    }