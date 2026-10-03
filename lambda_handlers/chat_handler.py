# chat_handler.py

import json
import os
import uuid
from datetime import datetime, timezone

import boto3

from scripts.storage import write_bytes

WORKER_FUNCTION = os.environ.get("WORKER_FUNCTION", "edgar-chat-worker")
JOB_PREFIX = "jobs/"

lambda_client = boto3.client("lambda")

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    question = (params.get("q") or "").strip()

    if not question:
        return {
            "statusCode": 400,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Missing 'q' query parameter"}),
        }

    job_id = str(uuid.uuid4())

    record = {
        "status": "pending",
        "question": question,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        write_bytes(f"{JOB_PREFIX}{job_id}.json", json.dumps(record).encode("utf-8"))
    except Exception as e:
        print(f"[chat] failed to create job record: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Could not start that question."}),
        }

    try:
        # InvocationType Event means fire and forget: this call returns as soon
        # as Lambda accepts the request, it does not wait for the work.
        lambda_client.invoke(
            FunctionName=WORKER_FUNCTION,
            InvocationType="Event",
            Payload=json.dumps({"job_id": job_id, "question": question}).encode("utf-8"),
        )
    except Exception as e:
        print(f"[chat] failed to invoke worker for job {job_id}: {e}")
        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": "Could not start that question."}),
        }

    print(f"[chat] queued job {job_id}: {question}")

    return {
        "statusCode": 202,
        "headers": CORS_HEADERS,
        "body": json.dumps({"job_id": job_id, "status": "pending"}),
    }