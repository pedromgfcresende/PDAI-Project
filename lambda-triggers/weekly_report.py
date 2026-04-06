"""
AWS Lambda: Weekly Report Pipeline + Email Delivery
EventBridge rule: cron(0 8 ? * FRI *)  →  every Friday at 08:00 UTC

Calls the API to run the weekly pipeline, then sends the report via SES.
"""

import json
import os
import urllib.request

import boto3

API_URL = os.environ.get("API_URL", "http://localhost:8000")
SES_FROM = os.environ.get("SES_FROM_EMAIL", "trends@yourdomain.com")
SES_TO = os.environ.get("SES_TO_EMAIL", "team@yourdomain.com")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")


def send_email(subject: str, html_body: str):
    """Send the report via Amazon SES."""
    ses = boto3.client("ses", region_name=AWS_REGION)
    ses.send_email(
        Source=SES_FROM,
        Destination={"ToAddresses": [SES_TO]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {"Html": {"Data": html_body, "Charset": "UTF-8"}},
        },
    )
    print(f"Email sent to {SES_TO}")


def handler(event, context):
    # 1. Run the weekly pipeline (ingest + filter + signals + report)
    url = f"{API_URL}/pipeline/weekly"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            body = json.loads(resp.read().decode())
    except Exception as e:
        print(f"Weekly pipeline failed: {e}")
        return {"statusCode": 500, "body": str(e)}

    # 2. Extract the report
    report = body.get("report", {})
    title = report.get("title", "Weekly AI Trends Report")
    report_id = report.get("id")
    quality = report.get("quality_score", "N/A")

    # 3. Fetch the styled HTML version
    html_body = report.get("content_html", "")
    if report_id and not html_body:
        try:
            dl_url = f"{API_URL}/reports/{report_id}/download"
            with urllib.request.urlopen(dl_url, timeout=30) as dl_resp:
                html_body = dl_resp.read().decode()
        except Exception:
            html_body = f"<p>Report generated (quality: {quality}) but HTML export failed. View it in the dashboard.</p>"

    # 4. Send via SES
    subject = f"AI Trends Weekly: {title}"
    try:
        send_email(subject, html_body)
    except Exception as e:
        print(f"Email delivery failed: {e}")
        return {"statusCode": 500, "body": f"Report generated but email failed: {e}"}

    print(f"Weekly report delivered: {title} (quality: {quality})")
    return {"statusCode": 200, "body": {"title": title, "quality_score": quality, "emailed": True}}
