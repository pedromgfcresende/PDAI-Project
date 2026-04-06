# Deployment Instructions

Step-by-step guide to deploy AI Trends Explorer on AWS EC2.

## Prerequisites

- [ ] AWS CLI installed and configured (`aws configure`)
- [ ] Terraform installed (`brew install terraform`)
- [ ] Your AWS `.pem` key file on your machine (e.g., `~/.ssh/my-key.pem`)
- [ ] The key pair name as shown in AWS Console → EC2 → Key Pairs
- [ ] API keys: Anthropic, Groq (required), Google AI + GitHub (optional)

## Step 1 — Configure Variables

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region    = "eu-west-1"             # Your preferred region
instance_type = "t3.small"              # Needs 2GB RAM for sentence-transformers
key_pair_name = "your-key-name"         # Exact name from AWS Console
ssh_cidr      = "0.0.0.0/0"            # Or restrict to your IP: "1.2.3.4/32"
repo_url      = "https://github.com/your-org/PDAI-Project.git"

anthropic_api_key = "sk-ant-..."
groq_api_key      = "gsk_..."
google_ai_api_key = ""                  # Optional
github_token      = ""                  # Optional
langchain_api_key = ""                  # Optional
db_password       = "a-strong-password"
```

## Step 2 — Initialize Terraform

```bash
cd infra
terraform init
```

## Step 3 — Preview What Will Be Created

```bash
terraform plan
```

You should see: 1 EC2 instance + 1 security group. Uses your default VPC.

## Step 4 — Deploy

```bash
terraform apply
```

Type `yes` when prompted. Takes ~30 seconds to create the instance.

## Step 5 — Wait for Setup (~3-5 minutes)

The EC2 instance runs a bootstrap script that:
1. Installs Docker + Docker Compose + nginx
2. Clones your repo
3. Creates the `.env` file with your API keys
4. Builds the Docker image and starts PostgreSQL + API
5. Configures nginx to serve the dashboard

Watch the progress:

```bash
# Get your instance IP
terraform output

# SSH in and watch the setup log
ssh -i ~/.ssh/your-key-name.pem ec2-user@<INSTANCE_IP>
tail -f /var/log/user-data.log
```

Wait until you see `=== Setup complete ===`.

## Step 6 — Verify

```bash
# Check the API
curl http://<INSTANCE_IP>:8000/health

# Open the dashboard in your browser
open http://<INSTANCE_IP>
```

The dashboard should load and show connection status "Connected".

## Step 7 — Run the Pipeline

From the dashboard (or via curl):

```bash
# Ingest data
curl -X POST http://<INSTANCE_IP>:8000/ingest

# Score items
curl -X POST http://<INSTANCE_IP>:8000/filter?limit=50

# Detect signals
curl -X POST http://<INSTANCE_IP>:8000/signals/detect

# Generate a report
curl -X POST "http://<INSTANCE_IP>:8000/reports/generate?report_type=weekly"
```

Or just use the dashboard buttons — they work the same way.

## Updating After Deployment

```bash
ssh -i ~/.ssh/your-key-name.pem ec2-user@<INSTANCE_IP>
cd app
git pull
docker compose up -d --build
```

## Tearing Down

```bash
cd infra
terraform destroy
```

Type `yes`. This deletes the EC2 instance and security group. Data in PostgreSQL is lost (it's on the instance's EBS volume).

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `terraform plan` fails with credentials | Run `aws configure` and check your access key |
| Can't SSH into the instance | Check security group allows port 22, and you're using the right `.pem` file |
| Dashboard loads but shows "Unreachable" | API container may still be starting — wait 1-2 min, check `docker compose logs api` |
| API returns 500 errors | Check logs: `ssh in → cd app → docker compose logs api` |
| Setup script never completes | SSH in and check: `cat /var/log/user-data.log` |
| Port 8000 not accessible | Check security group in AWS Console → must allow inbound on 8000 |

## Cost

| Resource | Monthly Cost |
|----------|-------------|
| t3.small EC2 (24/7) | ~$15 |
| 30GB gp3 EBS | ~$2.40 |
| Data transfer (minimal) | ~$0.50 |
| **Total** | **~$18/month** |

To save money: stop the instance when not in use (`aws ec2 stop-instances --instance-ids <ID>`). EBS storage still costs $2.40/month but compute stops billing.
