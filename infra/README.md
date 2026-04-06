# Infrastructure — EC2 Deployment

Single EC2 instance running the full stack via Docker Compose: PostgreSQL (pgvector) + API service + nginx (dashboard).

## Architecture

```
EC2 (t3.small)
├── nginx (:80)          → serves dashboard + proxies API
├── Docker
│   ├── trends-api (:8000)   → FastAPI + LangGraph
│   └── trends-db (:5432)    → PostgreSQL + pgvector
└── Lambda triggers (optional) → EventBridge cron → API
```

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- AWS CLI configured (`aws configure`)
- SSH key pair (`ssh-keygen -t ed25519 -f ~/.ssh/ai-trends-explorer-key`)

## Quick Start

```bash
cd infra

# 1. Initialize Terraform
./deploy.sh init

# 2. Configure variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your SSH key, API keys, and repo URL

# 3. Preview
./deploy.sh plan

# 4. Deploy
./deploy.sh apply

# 5. Wait ~3-5 min for setup, then check
./deploy.sh output
./deploy.sh logs
```

## What Gets Created

| Resource | Purpose |
|----------|---------|
| EC2 instance (t3.small) | Runs Docker Compose (API + Postgres) |
| Security group | Allows ports 22, 80, 8000 |
| Key pair | SSH access |

Uses the default VPC — no networking to manage.

## Estimated Cost

- **t3.small**: ~$15/month (or free-tier eligible with t3.micro, but needs 2GB RAM for sentence-transformers)
- **30GB gp3 EBS**: ~$2.40/month
- **Total**: ~$17/month

## Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh init` | Initialize Terraform |
| `./deploy.sh plan` | Preview changes |
| `./deploy.sh apply` | Create/update infrastructure |
| `./deploy.sh output` | Show IP and URLs |
| `./deploy.sh ssh` | SSH into the instance |
| `./deploy.sh logs` | Tail cloud-init setup logs |
| `./deploy.sh destroy` | Tear down everything |

## After Deployment

The dashboard is available at `http://<instance-ip>` and the API at `http://<instance-ip>:8000`.

To update the code after deployment:
```bash
./deploy.sh ssh
cd app
git pull
docker compose up -d --build
```

## Dashboard API URL

The dashboard `index.html` hardcodes `http://localhost:8000` as the API URL. In production, nginx proxies all API paths from port 80 to port 8000, so the dashboard works without changes when accessed via `http://<instance-ip>`.
