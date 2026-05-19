# Observability Stack - IRPF Processor

## Quick Start

```bash
docker-compose up -d
```

## Access Points

| Service    | URL                     | Credentials      |
|------------|-------------------------|------------------|
| Grafana    | http://localhost:3000   | admin / admin    |
| Prometheus | http://localhost:9095   | -                |
| API        | http://localhost:8000   | -                |
| MinIO      | http://localhost:9001   | minioadmin       |

## Dashboards

### IRPF Processor - Analytics Dashboard
Main operational dashboard with:
- KPIs (uploads, processed, failures, success rate)
- Volume and throughput over time
- Processing latency percentiles (p50, p90, p99)
- Extraction confidence distribution
- Breakdown by PDF type, template version, tenant
- Section extraction success/failure
- Errors and warnings tracking
- API and infrastructure metrics
- Storage and database operations

### IRPF Processor - SLO & Alertas
Service level objectives monitoring:
- Success rate SLO (target: 99%)
- Confidence SLO (target: 85%)
- Latency p95 SLO (target: 30s)
- API latency p95 SLO (target: 500ms)
- Error budget tracking
- Apdex score (user satisfaction)
- Alert indicators
- Period comparison (today vs yesterday, this week vs last week)

## Metrics Reference

### Document Processing Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `irpf_documents_uploaded_total` | Counter | Total documents uploaded |
| `irpf_documents_processed_total` | Counter | Documents by final status |
| `irpf_processing_duration_seconds` | Histogram | End-to-end processing time |
| `irpf_extraction_duration_seconds` | Histogram | PDF extraction time |
| `irpf_extraction_confidence` | Histogram | Confidence score distribution |

### Quality Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `irpf_sections_extracted_total` | Counter | Sections successfully extracted |
| `irpf_sections_missing_total` | Counter | Sections not found |
| `irpf_extraction_warnings_total` | Counter | Extraction warnings by type |
| `irpf_field_extraction_confidence` | Histogram | Per-field confidence |

### Error Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `irpf_failed_documents_total` | Counter | Failures by step/code |
| `irpf_quarantined_documents_total` | Counter | Quarantined documents |
| `irpf_retry_attempts_total` | Counter | Retry attempts |

### API Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `irpf_api_requests_total` | Counter | API requests by endpoint |
| `irpf_api_request_duration_seconds` | Histogram | API latency |
| `irpf_api_requests_in_progress` | Gauge | In-flight requests |

### Infrastructure Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `irpf_worker_jobs_in_queue` | Gauge | Pending jobs |
| `irpf_storage_operations_total` | Counter | MinIO operations |
| `irpf_database_operations_total` | Counter | MongoDB operations |

## SLO Definitions

| SLO | Target | Alert Threshold |
|-----|--------|-----------------|
| Success Rate | 99% | < 95% |
| Avg Confidence | 85% | < 70% |
| Processing p95 | < 30s | > 60s |
| API Latency p95 | < 500ms | > 1s |

## Apdex Score Interpretation

The Apdex score measures user satisfaction based on processing time:

| Score Range | Rating | Description |
|-------------|--------|-------------|
| 0.94 - 1.00 | Excellent | Users very satisfied |
| 0.85 - 0.93 | Good | Users satisfied |
| 0.70 - 0.84 | Fair | Some users frustrated |
| 0.50 - 0.69 | Poor | Many users frustrated |
| 0.00 - 0.49 | Unacceptable | Most users frustrated |

Threshold (T) = 30 seconds
- Satisfied: response <= T (30s)
- Tolerating: T < response <= 4T (120s)
- Frustrated: response > 4T

## Adding Custom Alerts

Edit the Prometheus configuration to add alerting rules:

```yaml
groups:
  - name: irpf-alerts
    rules:
      - alert: HighFailureRate
        expr: (sum(irpf_documents_processed_total{status="FAILED"}) / sum(irpf_documents_processed_total)) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High document failure rate"
          
      - alert: LowConfidence
        expr: avg(irpf_extraction_confidence_sum / irpf_extraction_confidence_count) < 0.7
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low average extraction confidence"
```

## Retention

- Prometheus: 30 days (configurable via `--storage.tsdb.retention.time`)
- Grafana: Persistent volume for dashboards and settings
