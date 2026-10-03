# chat_worker_handler.py

import json
import traceback
from datetime import datetime, timezone

from scripts.agent import ask
from scripts.storage import write_bytes, read_bytes

JOB_PREFIX = "jobs/"


def _job_key(job_id):
    return f"{JOB_PREFIX}{job_id}.json"


def _write_job(job_id, record):
    write_bytes(_job_key(job_id), json.dumps(record).encode("utf-8"))


def handler(event, context):
    job_id = event.get("job_id")
    question = event.get("question")

    if not job_id or not question:
        print(f"[worker] bad event, missing job_id or question: {event}")
        return {"ok": False}

    print(f"[worker] starting job {job_id}: {question}")

    # Keep whatever the creating Lambda wrote (question, created_at) so the
    # finished record still carries it.
    try:
        record = json.loads(read_bytes(_job_key(job_id)).decode("utf-8"))
    except Exception:
        record = {"question": question}

    try:
        answer = ask(question)
        record["status"] = "done"
        record["answer"] = answer
    except Exception as e:
        # The user never sees this text, only "something went wrong", but it
        # needs to be in the logs to be debuggable.
        print(f"[worker] job {job_id} failed:\n{traceback.format_exc()}")
        record["status"] = "error"
        record["error"] = str(e)

    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_job(job_id, record)
    print(f"[worker] job {job_id} finished with status {record['status']}")

    return {"ok": True, "job_id": job_id, "status": record["status"]}