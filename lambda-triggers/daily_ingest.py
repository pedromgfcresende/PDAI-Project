"""
AWS Lambda: Daily Ingestion Pipeline
EventBridge rule: cron(0 6 * * ? *)  →  every day at 06:00 UTC

Calls the API to ingest from all sources, score items, and detect signals.
"""

import json
import os
import urllib.request

API_URL = os.environ.get("API_URL", "http://localhost:8000")


def handler(event, context):
    url = f"{API_URL}/pipeline/daily"

    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode())
            print(f"Daily pipeline complete: {json.dumps(body, default=str)}")
            return {"statusCode": 200, "body": body}
    except Exception as e:
        print(f"Daily pipeline failed: {e}")
        return {"statusCode": 500, "body": str(e)}
