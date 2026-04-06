#!/bin/bash
set -euo pipefail

# AI Trends Explorer — EC2 Deployment Script
# Usage:
#   ./deploy.sh init       — First-time Terraform init
#   ./deploy.sh plan       — Preview what will be created
#   ./deploy.sh apply      — Create/update the EC2 instance
#   ./deploy.sh output     — Show instance IP and URLs
#   ./deploy.sh ssh        — SSH into the instance
#   ./deploy.sh destroy    — Tear down everything
#   ./deploy.sh logs       — View cloud-init logs on the instance

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

command="${1:-help}"

case "$command" in
  init)
    terraform init
    echo ""
    echo "Next: copy terraform.tfvars.example to terraform.tfvars and fill in your values"
    echo "  cp terraform.tfvars.example terraform.tfvars"
    ;;

  plan)
    terraform plan
    ;;

  apply)
    terraform apply
    echo ""
    echo "Instance is starting. It takes ~3-5 minutes for Docker to build and start."
    echo "Run './deploy.sh output' to see the URLs."
    echo "Run './deploy.sh logs' to watch progress."
    ;;

  output)
    terraform output
    ;;

  ssh)
    IP=$(terraform output -raw instance_public_ip)
    KEY=$(terraform output -raw ssh_command | grep -oP '(?<=-i )\S+')
    ssh -i "$KEY" ubuntu@"$IP"
    ;;

  logs)
    IP=$(terraform output -raw instance_public_ip)
    KEY=$(terraform output -raw ssh_command | grep -oP '(?<=-i )\S+')
    ssh -i "$KEY" ubuntu@"$IP" "tail -f /var/log/user-data.log"
    ;;

  destroy)
    echo "This will destroy all infrastructure. Are you sure? (type 'yes')"
    read -r confirm
    if [ "$confirm" = "yes" ]; then
      terraform destroy
    else
      echo "Cancelled."
    fi
    ;;

  help|*)
    echo "AI Trends Explorer — Deployment"
    echo ""
    echo "Usage: ./deploy.sh <command>"
    echo ""
    echo "Commands:"
    echo "  init      Initialize Terraform"
    echo "  plan      Preview infrastructure changes"
    echo "  apply     Create/update the EC2 instance"
    echo "  output    Show instance IP and URLs"
    echo "  ssh       SSH into the instance"
    echo "  logs      Tail cloud-init logs on the instance"
    echo "  destroy   Tear down everything"
    ;;
esac
