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

REGISTRY_URL=$(terraform output -raw artifact_registry_url 2>/dev/null || echo "")
PROJECT_ID=$(terraform output -raw project_id 2>/dev/null || echo "")

if [ -z "$REGISTRY_URL" ]; then
    echo "Error: Could not get Artifact Registry URL. Make sure infrastructure is deployed."
    exit 1
fi

echo "Configuring Docker for Artifact Registry..."
gcloud auth configure-docker southamerica-east1-docker.pkg.dev --quiet

cd "$PROJECT_ROOT"

echo "Building API image..."
docker build -t $REGISTRY_URL/irpf-processor-api:$VERSION --target api .

echo "Building Worker image..."
docker build -t $REGISTRY_URL/irpf-processor-worker:$VERSION --target worker .

echo "Building Worker OCR image..."
docker build -t $REGISTRY_URL/irpf-processor-worker-ocr:$VERSION --target worker-ocr .

echo "Pushing images..."
docker push $REGISTRY_URL/irpf-processor-api:$VERSION
docker push $REGISTRY_URL/irpf-processor-worker:$VERSION
docker push $REGISTRY_URL/irpf-processor-worker-ocr:$VERSION

echo ""
echo "Images pushed successfully!"
echo "  - $REGISTRY_URL/irpf-processor-api:$VERSION"
echo "  - $REGISTRY_URL/irpf-processor-worker:$VERSION"
echo "  - $REGISTRY_URL/irpf-processor-worker-ocr:$VERSION"
