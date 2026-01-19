#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
VERSION=${2:-latest}

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Usage: $0 <environment> [version]"
    echo "  environment: dev, staging, or prod"
    echo "  version: image tag (default: latest)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$ROOT_DIR")")"
ENV_DIR="$ROOT_DIR/environments/$ENVIRONMENT"

cd "$ENV_DIR"

ACR_NAME=$(terraform output -raw acr_login_server 2>/dev/null || echo "")

if [ -z "$ACR_NAME" ]; then
    echo "Error: Could not get ACR name. Make sure infrastructure is deployed."
    exit 1
fi

echo "Logging into ACR: $ACR_NAME"
az acr login --name ${ACR_NAME%%.*}

cd "$PROJECT_ROOT"

echo "Building API image..."
docker build -t $ACR_NAME/irpf-processor-api:$VERSION --target api .

echo "Building Worker image..."
docker build -t $ACR_NAME/irpf-processor-worker:$VERSION --target worker .

echo "Building Worker OCR image..."
docker build -t $ACR_NAME/irpf-processor-worker-ocr:$VERSION --target worker-ocr .

echo "Pushing images..."
docker push $ACR_NAME/irpf-processor-api:$VERSION
docker push $ACR_NAME/irpf-processor-worker:$VERSION
docker push $ACR_NAME/irpf-processor-worker-ocr:$VERSION

echo ""
echo "Images pushed successfully!"
echo "  - $ACR_NAME/irpf-processor-api:$VERSION"
echo "  - $ACR_NAME/irpf-processor-worker:$VERSION"
echo "  - $ACR_NAME/irpf-processor-worker-ocr:$VERSION"
