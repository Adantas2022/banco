#!/bin/bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Stopping observability stack..."
docker compose stop prometheus pushgateway grafana

echo "Removing containers..."
docker compose rm -f prometheus pushgateway grafana

echo "Removing data volumes..."
docker volume rm -f irpf-processor-prometheus-data 2>/dev/null || true
docker volume rm -f irpf-processor-grafana-data 2>/dev/null || true

echo "Restarting observability stack..."
docker compose up -d prometheus pushgateway grafana

echo "Waiting for services to be healthy..."
sleep 5

echo "Clearing MongoDB test data..."
docker exec irpf-processor-mongo mongosh --quiet irpf_processor --eval '
db.documents.deleteMany({});
db.extraction_results.deleteMany({});
print("MongoDB collections cleared");
' 2>/dev/null || echo "MongoDB not available, skipping..."

echo "Restarting workers to clear in-memory metrics..."
docker compose restart api worker-router worker-digital worker-ocr

echo "Waiting for workers to be ready..."
sleep 5

echo "Verifying Prometheus is clean..."

METRICS_TO_CHECK=(
    "irpf_documents_uploaded_total"
    "irpf_documents_processed_total"
    "irpf_storage_operations_total"
    "irpf_database_operations_total"
    "irpf_extraction_confidence_bucket"
    "irpf_ocr_processing_total"
)

ALL_CLEAN=true
for metric in "${METRICS_TO_CHECK[@]}"; do
    RESULT=$(curl -s "http://localhost:9095/api/v1/query?query=$metric" | grep -o '"result":\[\]' || true)
    if [ "$RESULT" != '"result":[]' ]; then
        echo "  - $metric: still has data"
        ALL_CLEAN=false
    fi
done

if [ "$ALL_CLEAN" = true ]; then
    echo "SUCCESS: All metrics have been reset"
else
    echo "WARNING: Some metrics may still have data (Prometheus scrape interval is 15s)"
fi

echo ""
echo "Grafana: http://localhost:3000 (admin/admin)"
echo "Prometheus: http://localhost:9095"
echo ""
echo "Done!"
