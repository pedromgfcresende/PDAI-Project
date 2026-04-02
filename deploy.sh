#!/usr/bin/env bash
set -euo pipefail

# ─── AI Trends Explorer — Deploy Script (CloudFormation) ──
# Usage:
#   ./deploy.sh infra      — Create/update CloudFormation stack
#   ./deploy.sh build      — Build & push Docker image to ECR
#   ./deploy.sh deploy     — Update stack with image + force new ECS deployment
#   ./deploy.sh dashboard  — Upload dashboard to S3 + invalidate CloudFront
#   ./deploy.sh db-init    — Instructions for initializing the DB schema
#   ./deploy.sh all        — Run infra + build + deploy + dashboard
#   ./deploy.sh destroy    — Delete the CloudFormation stack
#   ./deploy.sh status     — Show stack outputs

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/infra/template.yaml"

AWS_REGION="${AWS_REGION:-eu-west-1}"
STACK_NAME="${STACK_NAME:-ai-trends-prod}"

# ─── Helpers ─────────────────────────────────────────────

get_output() {
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" \
    --output text --region "$AWS_REGION" 2>/dev/null
}

# ─── Commands ────────────────────────────────────────────

cmd_infra() {
  echo "==> Validating template..."
  aws cloudformation validate-template \
    --template-body "file://$TEMPLATE" \
    --region "$AWS_REGION" --no-cli-pager

  echo "==> Creating/updating CloudFormation stack: $STACK_NAME"
  echo "    (This takes ~15-20 minutes for RDS + NAT Gateway + CloudFront)"

  # Check if stack exists
  if aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$AWS_REGION" &>/dev/null; then
    echo "    Stack exists — updating..."
    aws cloudformation update-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://$TEMPLATE" \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameters file://"$SCRIPT_DIR/infra/parameters.json" \
      --region "$AWS_REGION" \
      --no-cli-pager || echo "    (No updates needed)"

    echo "==> Waiting for update to complete..."
    aws cloudformation wait stack-update-complete \
      --stack-name "$STACK_NAME" --region "$AWS_REGION"
  else
    echo "    Creating new stack..."
    aws cloudformation create-stack \
      --stack-name "$STACK_NAME" \
      --template-body "file://$TEMPLATE" \
      --capabilities CAPABILITY_NAMED_IAM \
      --parameters file://"$SCRIPT_DIR/infra/parameters.json" \
      --region "$AWS_REGION" \
      --no-cli-pager

    echo "==> Waiting for stack creation (~15-20 min)..."
    aws cloudformation wait stack-create-complete \
      --stack-name "$STACK_NAME" --region "$AWS_REGION"
  fi

  echo "==> Stack ready!"
  cmd_status
}

cmd_build() {
  echo "==> Building and pushing Docker image..."
  ECR_URL=$(get_output ECRRepositoryURL)
  ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

  # Authenticate Docker with ECR
  aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"

  # Build image (linux/amd64 for Fargate)
  cd "$SCRIPT_DIR"
  docker build --platform linux/amd64 -t ai-trends-agent-service .

  # Tag and push
  docker tag ai-trends-agent-service:latest "$ECR_URL:latest"
  docker push "$ECR_URL:latest"

  echo "==> Image pushed to $ECR_URL:latest"
}

cmd_deploy() {
  echo "==> Updating stack with container image and forcing new deployment..."
  ECR_URL=$(get_output ECRRepositoryURL)

  # Update the ContainerImage parameter in parameters.json
  # Then update the stack to pick up the new image
  PARAMS_FILE="$SCRIPT_DIR/infra/parameters.json"

  # Read current params, update ContainerImage
  python3 -c "
import json, sys
with open('$PARAMS_FILE') as f:
    params = json.load(f)
for p in params:
    if p['ParameterKey'] == 'ContainerImage':
        p['ParameterValue'] = '${ECR_URL}:latest'
        break
else:
    params.append({'ParameterKey': 'ContainerImage', 'ParameterValue': '${ECR_URL}:latest'})
with open('$PARAMS_FILE', 'w') as f:
    json.dump(params, f, indent=2)
print('Updated ContainerImage in parameters.json')
"

  # Update the stack
  aws cloudformation update-stack \
    --stack-name "$STACK_NAME" \
    --template-body "file://$TEMPLATE" \
    --capabilities CAPABILITY_NAMED_IAM \
    --parameters file://"$PARAMS_FILE" \
    --region "$AWS_REGION" \
    --no-cli-pager || true

  # Also force a new deployment on the ECS service
  CLUSTER=$(get_output ECSClusterName)
  SERVICE_NAME="${STACK_NAME%-*}-agent-service"

  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$SERVICE_NAME" \
    --force-new-deployment \
    --region "$AWS_REGION" \
    --no-cli-pager 2>/dev/null || echo "    (ECS service not yet running — will start after stack update)"

  echo "==> Deployment triggered. Check progress with: ./deploy.sh status"
}

cmd_dashboard() {
  echo "==> Uploading dashboard to S3..."
  BUCKET=$(get_output DashboardBucketName)
  CDN_URL=$(get_output DashboardURL)
  API_URL=$(get_output APIURL)

  # Inject the ALB URL into the dashboard HTML
  sed "s|http://localhost:8000|$API_URL|g" "$SCRIPT_DIR/dashboard/index.html" > /tmp/index.html

  aws s3 cp /tmp/index.html "s3://$BUCKET/index.html" \
    --content-type "text/html" \
    --region "$AWS_REGION"

  # Invalidate CloudFront cache
  DIST_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Comment=='AI Trends Explorer Dashboard'].Id" \
    --output text --region "$AWS_REGION" 2>/dev/null || echo "")

  if [[ -n "$DIST_ID" && "$DIST_ID" != "None" ]]; then
    aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths "/*" --no-cli-pager
    echo "==> CloudFront cache invalidated"
  fi

  echo "==> Dashboard live at: $CDN_URL"
}

cmd_db_init() {
  echo "==> Database initialization instructions"
  echo ""
  RDS_ENDPOINT=$(get_output RDSEndpoint)
  RDS_PORT=$(get_output RDSPort)
  echo "RDS endpoint: $RDS_ENDPOINT:$RDS_PORT"
  echo ""
  echo "Since RDS is in a private subnet, you have two options:"
  echo ""
  echo "Option 1 — ECS Exec (recommended):"
  echo "  CLUSTER=$(get_output ECSClusterName)"
  echo "  TASK_ID=\$(aws ecs list-tasks --cluster \$CLUSTER --query 'taskArns[0]' --output text --region $AWS_REGION)"
  echo "  aws ecs execute-command --cluster \$CLUSTER --task \$TASK_ID \\"
  echo "    --container agent-service --interactive --command '/bin/sh'"
  echo "  # Then inside the container:"
  echo "  psql \"postgresql://trends:<password>@$RDS_ENDPOINT:$RDS_PORT/ai_trends\" -f /app/init-db.sql"
  echo ""
  echo "Option 2 — Bastion / Cloud9 / SSM Session Manager:"
  echo "  psql \"postgresql://trends:<password>@$RDS_ENDPOINT:$RDS_PORT/ai_trends\" -f init-db.sql"
}

cmd_status() {
  echo "==> Stack: $STACK_NAME"
  echo ""
  echo "Outputs:"
  aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[*].[OutputKey,OutputValue]" \
    --output table --region "$AWS_REGION" 2>/dev/null || echo "Stack not found."
}

cmd_all() {
  cmd_infra
  cmd_build
  cmd_deploy
  cmd_dashboard
  echo ""
  echo "==> All done!"
  cmd_status
}

cmd_destroy() {
  echo "==> WARNING: This will delete the ENTIRE CloudFormation stack: $STACK_NAME"
  echo "    All resources (ECS, RDS, S3, CloudFront, etc.) will be destroyed."
  read -p "Type the stack name to confirm: " confirm
  if [[ "$confirm" == "$STACK_NAME" ]]; then
    # Empty the S3 bucket first (CloudFormation can't delete non-empty buckets)
    BUCKET=$(get_output DashboardBucketName 2>/dev/null || echo "")
    if [[ -n "$BUCKET" ]]; then
      echo "==> Emptying S3 bucket: $BUCKET"
      aws s3 rm "s3://$BUCKET" --recursive --region "$AWS_REGION"
    fi

    aws cloudformation delete-stack \
      --stack-name "$STACK_NAME" --region "$AWS_REGION"

    echo "==> Stack deletion initiated. Monitor with:"
    echo "    aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $AWS_REGION"
  else
    echo "Aborted."
  fi
}

# ─── Main ────────────────────────────────────────────────

case "${1:-}" in
  infra)     cmd_infra ;;
  build)     cmd_build ;;
  deploy)    cmd_deploy ;;
  dashboard) cmd_dashboard ;;
  db-init)   cmd_db_init ;;
  status)    cmd_status ;;
  all)       cmd_all ;;
  destroy)   cmd_destroy ;;
  *)
    echo "AI Trends Explorer — Deployment Script"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  infra      Create/update CloudFormation stack (~15-20 min first time)"
    echo "  build      Build & push Docker image to ECR"
    echo "  deploy     Update stack with image + force new ECS deployment"
    echo "  dashboard  Upload dashboard to S3 + invalidate CloudFront"
    echo "  db-init    Show instructions for initializing the DB schema"
    echo "  status     Show stack outputs (URLs, endpoints)"
    echo "  all        Run infra + build + deploy + dashboard"
    echo "  destroy    Delete the entire stack"
    exit 1
    ;;
esac
