#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Usage: $0 <environment>"
    echo "  environment: dev, staging, or prod"
    exit 1
fi

if [ "$ENVIRONMENT" == "prod" ]; then
    echo "WARNING: You are about to destroy PRODUCTION!"
    read -p "Type 'destroy-prod' to confirm: " CONFIRM
    if [ "$CONFIRM" != "destroy-prod" ]; then
        echo "Cancelled."
        exit 0
    fi
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_DIR="$ROOT_DIR/environments/$ENVIRONMENT"

echo "Destroying $ENVIRONMENT environment..."

cd "$ENV_DIR"

terraform init -backend-config=backend.tfvars

terraform destroy

echo "Environment destroyed."
