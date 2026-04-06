# Lambda Triggers

AWS Lambda functions that replace n8n for production scheduling. Each function is triggered by an EventBridge cron rule and calls the FastAPI backend.

## Functions

| Function | Schedule | What it does |
|----------|----------|-------------|
| `daily_ingest.py` | Every day 06:00 UTC | Ingest + filter + detect signals |
| `weekly_report.py` | Every Friday 08:00 UTC | Daily pipeline + generate weekly report + email via SES |
| `monthly_report.py` | 1st of month 08:00 UTC | Daily pipeline + generate monthly report + email via SES |

## Environment Variables

Set these in each Lambda's configuration:

| Variable | Description |
|----------|-------------|
| `API_URL` | URL of the FastAPI backend (e.g., `https://api.yourdomain.com`) |
| `SES_FROM_EMAIL` | Verified SES sender address |
| `SES_TO_EMAIL` | Report recipient email |
| `AWS_REGION` | SES region (default: `eu-west-1`) |

## EventBridge Rules (AWS CLI)

```bash
# Daily ingestion (06:00 UTC)
aws events put-rule \
  --name ai-trends-daily \
  --schedule-expression "cron(0 6 * * ? *)"

# Weekly report (Friday 08:00 UTC)
aws events put-rule \
  --name ai-trends-weekly \
  --schedule-expression "cron(0 8 ? * FRI *)"

# Monthly report (1st of month 08:00 UTC)
aws events put-rule \
  --name ai-trends-monthly \
  --schedule-expression "cron(0 8 1 * ? *)"
```

## Deployment

Each function uses only `boto3` (pre-installed in Lambda) and `urllib` (stdlib) — no additional dependencies needed. Deploy as a single `.py` file per function.

```bash
# Package and deploy (example for weekly)
zip weekly_report.zip weekly_report.py
aws lambda create-function \
  --function-name ai-trends-weekly \
  --runtime python3.12 \
  --handler weekly_report.handler \
  --zip-file fileb://weekly_report.zip \
  --role arn:aws:iam::ACCOUNT:role/lambda-ses-role \
  --timeout 600 \
  --environment "Variables={API_URL=https://api.yourdomain.com,SES_FROM_EMAIL=trends@yourdomain.com,SES_TO_EMAIL=team@yourdomain.com}"
```

## IAM Role

The Lambda execution role needs:
- `ses:SendEmail` permission
- Network access to the API (VPC config if API is in a private subnet)
