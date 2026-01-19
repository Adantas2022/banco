#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Usage: $0 <environment>"
    echo "  environment: dev, staging, or prod"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_DIR="$ROOT_DIR/environments/$ENVIRONMENT"

echo "Deploying to $ENVIRONMENT environment..."

cd "$ENV_DIR"

echo "Initializing Terraform..."
terraform init -backend-config=backend.tfvars -upgrade

echo "Planning changes..."
terraform plan -out=tfplan

read -p "Apply changes? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo "Applying changes..."
terraform apply tfplan

rm -f tfplan

echo ""
echo "Deployment complete!"
echo ""
terraform output
