from prometheus_client import Counter, Histogram, Gauge, Info, REGISTRY, CollectorRegistry
from prometheus_client.multiprocess import MultiProcessCollector
import os


APP_INFO = Info(
    "irpf_processor",
    "IRPF Processor application information",
)


DOCUMENTS_UPLOADED_TOTAL = Counter(
    "irpf_documents_uploaded_total",
    "Total number of documents uploaded",
    ["tenant_id"],
)


DOCUMENTS_PROCESSED_TOTAL = Counter(
    "irpf_documents_processed_total",
    "Total number of documents processed by final status",
    ["tenant_id", "status", "pdf_type"],
)


DOCUMENTS_BY_STATUS = Counter(
    "irpf_documents_status_transitions_total",
    "Total status transitions",
    ["tenant_id", "from_status", "to_status"],
)


CURRENT_DOCUMENTS_BY_STATUS = Gauge(
    "irpf_documents_current_by_status",
    "Current number of documents in each status",
    ["status"],
)


EXTRACTION_CONFIDENCE = Histogram(
    "irpf_extraction_confidence",
    "Distribution of extraction confidence scores",
    ["tenant_id", "template_version", "pdf_type"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0],
)


PROCESSING_DURATION_SECONDS = Histogram(
    "irpf_processing_duration_seconds",
    "Time spent processing documents end-to-end",
    ["tenant_id", "pdf_type", "template_version"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300, 600],
)


EXTRACTION_DURATION_SECONDS = Histogram(
    "irpf_extraction_duration_seconds",
    "Time spent extracting data from PDF",
    ["tenant_id", "pdf_type", "template_version"],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 30, 60],
)


PDF_SIZE_BYTES = Histogram(
    "irpf_pdf_size_bytes",
    "Size distribution of uploaded PDF files",
    ["tenant_id"],
    buckets=[50000, 100000, 250000, 500000, 1000000, 2500000, 5000000, 10000000, 25000000],
)


PDF_PAGES_COUNT = Histogram(
    "irpf_pdf_pages_count",
    "Number of pages in processed PDFs",
    ["tenant_id", "template_version"],
    buckets=[1, 2, 5, 10, 20, 50, 100, 200, 500],
)


DOCUMENTS_BY_CATEGORY = Counter(
    "irpf_documents_by_category_total",
    "Total documents by category (DECLARACAO or RECIBO)",
    ["tenant_id", "category"],
)


DOCUMENTS_BY_PDF_TYPE = Counter(
    "irpf_documents_by_pdf_type_total",
    "Total documents by PDF type detected",
    ["tenant_id", "pdf_type"],
)


DOCUMENTS_BY_TEMPLATE_VERSION = Counter(
    "irpf_documents_by_template_version_total",
    "Total documents by template version (exercise year)",
    ["tenant_id", "template_version"],
)


EXTRACTION_WARNINGS_TOTAL = Counter(
    "irpf_extraction_warnings_total",
    "Total number of extraction warnings",
    ["tenant_id", "warning_type"],
)


OCR_USAGE_TOTAL = Counter(
    "irpf_ocr_usage_total",
    "Total number of OCR operations performed",
    ["tenant_id", "ocr_engine"],
)


OCR_DURATION_SECONDS = Histogram(
    "irpf_ocr_duration_seconds",
    "Time spent in OCR engine processing",
    ["tenant_id", "ocr_engine"],
    buckets=[1, 5, 10, 20, 30, 60, 120, 180, 300, 600],
)


OCR_CONFIDENCE = Histogram(
    "irpf_ocr_confidence",
    "OCR engine confidence scores",
    ["tenant_id", "ocr_engine"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0],
)


ROUTING_DURATION_SECONDS = Histogram(
    "irpf_routing_duration_seconds",
    "Time spent routing documents to queues",
    ["tenant_id", "pdf_type"],
    buckets=[0.1, 0.25, 0.5, 1, 2, 5, 10, 20],
)


PDF_TYPE_DETECTION_TOTAL = Counter(
    "irpf_pdf_type_detection_total",
    "Total PDF type detections by type",
    ["pdf_type", "confidence_bucket"],
)


QUARANTINED_DOCUMENTS_TOTAL = Counter(
    "irpf_quarantined_documents_total",
    "Total documents sent to quarantine",
    ["tenant_id", "reason"],
)


FAILED_DOCUMENTS_TOTAL = Counter(
    "irpf_failed_documents_total",
    "Total documents that failed processing",
    ["tenant_id", "error_step", "error_code"],
)


RETRY_ATTEMPTS_TOTAL = Counter(
    "irpf_retry_attempts_total",
    "Total retry attempts for failed documents",
    ["tenant_id", "step"],
)


API_REQUEST_DURATION_SECONDS = Histogram(
    "irpf_api_request_duration_seconds",
    "API request latency",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)


API_REQUESTS_TOTAL = Counter(
    "irpf_api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)


API_REQUESTS_IN_PROGRESS = Gauge(
    "irpf_api_requests_in_progress",
    "Number of API requests currently being processed",
    ["method", "endpoint"],
)


WORKER_JOBS_IN_QUEUE = Gauge(
    "irpf_worker_jobs_in_queue",
    "Number of jobs waiting in queue",
    ["queue_name"],
)


WORKER_JOBS_PROCESSING = Gauge(
    "irpf_worker_jobs_processing",
    "Number of jobs currently being processed",
    ["worker_name"],
)


WORKER_JOBS_TOTAL = Counter(
    "irpf_worker_jobs_total",
    "Total worker jobs processed",
    ["worker_name", "status"],
)


SSE_CONNECTIONS_ACTIVE = Gauge(
    "irpf_sse_connections_active",
    "Number of active SSE connections",
)


EVENTS_PUBLISHED_TOTAL = Counter(
    "irpf_events_published_total",
    "Total events published to Redis Streams",
    ["event_type"],
)


QUEUE_SEND_FAILURES_TOTAL = Counter(
    "irpf_queue_send_failures_total",
    "Total failures when sending messages to processing queue",
    ["tenant_id", "queue_name"],
)


STORAGE_OPERATIONS_TOTAL = Counter(
    "irpf_storage_operations_total",
    "Total storage operations (MinIO)",
    ["operation", "status"],
)


STORAGE_OPERATION_DURATION_SECONDS = Histogram(
    "irpf_storage_operation_duration_seconds",
    "Storage operation latency",
    ["operation"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)


DATABASE_OPERATIONS_TOTAL = Counter(
    "irpf_database_operations_total",
    "Total database operations (MongoDB)",
    ["collection", "operation", "status"],
)


DATABASE_OPERATION_DURATION_SECONDS = Histogram(
    "irpf_database_operation_duration_seconds",
    "Database operation latency",
    ["collection", "operation"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5],
)


FIELD_EXTRACTION_CONFIDENCE = Histogram(
    "irpf_field_extraction_confidence",
    "Confidence score per extracted field",
    ["field_name", "section"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0],
)


SECTIONS_EXTRACTED_TOTAL = Counter(
    "irpf_sections_extracted_total",
    "Total sections successfully extracted",
    ["section_name", "template_version"],
)


SECTIONS_MISSING_TOTAL = Counter(
    "irpf_sections_missing_total",
    "Total sections that could not be extracted",
    ["section_name", "template_version"],
)


TAXPAYER_PROFILES_TOTAL = Counter(
    "irpf_taxpayer_profiles_total",
    "Distribution of taxpayer profiles detected",
    ["profile_type"],
)


CONFIDENCE_BY_LEVEL = Counter(
    "irpf_confidence_by_level_total",
    "Total documents by confidence level",
    ["tenant_id", "document_category", "confidence_level"],
)


CONFIDENCE_FIELDS_FOUND = Histogram(
    "irpf_confidence_fields_found",
    "Number of fields found during extraction",
    ["tenant_id", "document_category"],
    buckets=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 20],
)


CONFIDENCE_PENALTIES_APPLIED = Counter(
    "irpf_confidence_penalties_applied_total",
    "Total penalties applied during confidence calculation",
    ["tenant_id", "penalty_type"],
)


CONFIDENCE_BONUSES_APPLIED = Counter(
    "irpf_confidence_bonuses_applied_total",
    "Total bonuses applied during confidence calculation",
    ["tenant_id", "bonus_type"],
)


def set_app_info(version: str, environment: str) -> None:
    APP_INFO.info({
        "version": version,
        "environment": environment,
        "service": "irpf-processor",
    })


def record_document_upload(tenant_id: str, pdf_size_bytes: int) -> None:
    DOCUMENTS_UPLOADED_TOTAL.labels(tenant_id=tenant_id).inc()
    PDF_SIZE_BYTES.labels(tenant_id=tenant_id).observe(pdf_size_bytes)


def record_document_category(tenant_id: str, category: str) -> None:
    DOCUMENTS_BY_CATEGORY.labels(
        tenant_id=tenant_id,
        category=category,
    ).inc()


def record_document_processed(
    tenant_id: str,
    status: str,
    pdf_type: str,
    template_version: str,
    confidence: float,
    processing_time_seconds: float,
    total_pages: int,
) -> None:
    DOCUMENTS_PROCESSED_TOTAL.labels(
        tenant_id=tenant_id,
        status=status,
        pdf_type=pdf_type,
    ).inc()
    
    EXTRACTION_CONFIDENCE.labels(
        tenant_id=tenant_id,
        template_version=template_version,
        pdf_type=pdf_type,
    ).observe(confidence)
    
    PROCESSING_DURATION_SECONDS.labels(
        tenant_id=tenant_id,
        pdf_type=pdf_type,
        template_version=template_version,
    ).observe(processing_time_seconds)
    
    PDF_PAGES_COUNT.labels(
        tenant_id=tenant_id,
        template_version=template_version,
    ).observe(total_pages)
    
    DOCUMENTS_BY_PDF_TYPE.labels(
        tenant_id=tenant_id,
        pdf_type=pdf_type,
    ).inc()
    
    DOCUMENTS_BY_TEMPLATE_VERSION.labels(
        tenant_id=tenant_id,
        template_version=template_version,
    ).inc()


def record_status_transition(tenant_id: str, from_status: str, to_status: str) -> None:
    DOCUMENTS_BY_STATUS.labels(
        tenant_id=tenant_id,
        from_status=from_status,
        to_status=to_status,
    ).inc()


def record_extraction_duration(
    tenant_id: str,
    pdf_type: str,
    template_version: str,
    duration_seconds: float,
) -> None:
    EXTRACTION_DURATION_SECONDS.labels(
        tenant_id=tenant_id,
        pdf_type=pdf_type,
        template_version=template_version,
    ).observe(duration_seconds)


def record_extraction_warning(tenant_id: str, warning_type: str) -> None:
    EXTRACTION_WARNINGS_TOTAL.labels(
        tenant_id=tenant_id,
        warning_type=warning_type,
    ).inc()


def record_ocr_usage(tenant_id: str, ocr_engine: str) -> None:
    OCR_USAGE_TOTAL.labels(
        tenant_id=tenant_id,
        ocr_engine=ocr_engine,
    ).inc()


def record_ocr_duration(tenant_id: str, ocr_engine: str, duration_seconds: float) -> None:
    OCR_DURATION_SECONDS.labels(
        tenant_id=tenant_id,
        ocr_engine=ocr_engine,
    ).observe(duration_seconds)


def record_ocr_confidence(tenant_id: str, ocr_engine: str, confidence: float) -> None:
    OCR_CONFIDENCE.labels(
        tenant_id=tenant_id,
        ocr_engine=ocr_engine,
    ).observe(confidence)


def record_routing_duration(tenant_id: str, pdf_type: str, duration_seconds: float) -> None:
    ROUTING_DURATION_SECONDS.labels(
        tenant_id=tenant_id,
        pdf_type=pdf_type,
    ).observe(duration_seconds)


def record_pdf_type_detection(pdf_type: str, confidence: float) -> None:
    if confidence >= 0.9:
        bucket = "high"
    elif confidence >= 0.7:
        bucket = "medium"
    else:
        bucket = "low"
    PDF_TYPE_DETECTION_TOTAL.labels(
        pdf_type=pdf_type,
        confidence_bucket=bucket,
    ).inc()


def record_quarantine(tenant_id: str, reason: str) -> None:
    QUARANTINED_DOCUMENTS_TOTAL.labels(
        tenant_id=tenant_id,
        reason=reason,
    ).inc()


def record_failure(tenant_id: str, error_step: str, error_code: str) -> None:
    FAILED_DOCUMENTS_TOTAL.labels(
        tenant_id=tenant_id,
        error_step=error_step,
        error_code=error_code,
    ).inc()


def record_retry(tenant_id: str, step: str) -> None:
    RETRY_ATTEMPTS_TOTAL.labels(
        tenant_id=tenant_id,
        step=step,
    ).inc()


def record_api_request(method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
    API_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).observe(duration_seconds)
    
    API_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()


def record_storage_operation(operation: str, status: str, duration_seconds: float) -> None:
    STORAGE_OPERATIONS_TOTAL.labels(operation=operation, status=status).inc()
    STORAGE_OPERATION_DURATION_SECONDS.labels(operation=operation).observe(duration_seconds)


def record_database_operation(collection: str, operation: str, status: str, duration_seconds: float) -> None:
    DATABASE_OPERATIONS_TOTAL.labels(collection=collection, operation=operation, status=status).inc()
    DATABASE_OPERATION_DURATION_SECONDS.labels(collection=collection, operation=operation).observe(duration_seconds)


def record_section_extraction(section_name: str, template_version: str, success: bool) -> None:
    if success:
        SECTIONS_EXTRACTED_TOTAL.labels(
            section_name=section_name,
            template_version=template_version,
        ).inc()
    else:
        SECTIONS_MISSING_TOTAL.labels(
            section_name=section_name,
            template_version=template_version,
        ).inc()


def record_field_confidence(field_name: str, section: str, confidence: float) -> None:
    FIELD_EXTRACTION_CONFIDENCE.labels(
        field_name=field_name,
        section=section,
    ).observe(confidence)


def record_taxpayer_profile(profile_type: str) -> None:
    TAXPAYER_PROFILES_TOTAL.labels(profile_type=profile_type).inc()


def record_event_published(event_type: str) -> None:
    EVENTS_PUBLISHED_TOTAL.labels(event_type=event_type).inc()


def record_queue_send_failure(tenant_id: str, queue_name: str) -> None:
    QUEUE_SEND_FAILURES_TOTAL.labels(
        tenant_id=tenant_id,
        queue_name=queue_name,
    ).inc()


def set_worker_jobs_in_queue(queue_name: str, count: int) -> None:
    WORKER_JOBS_IN_QUEUE.labels(queue_name=queue_name).set(count)


def set_current_documents_by_status(status: str, count: int) -> None:
    CURRENT_DOCUMENTS_BY_STATUS.labels(status=status).set(count)


def record_confidence_details(
    tenant_id: str,
    document_category: str,
    confidence_level: str,
    fields_found: int,
    penalties: dict[str, float] | None = None,
    bonuses: dict[str, float] | None = None,
) -> None:
    CONFIDENCE_BY_LEVEL.labels(
        tenant_id=tenant_id,
        document_category=document_category,
        confidence_level=confidence_level,
    ).inc()
    
    CONFIDENCE_FIELDS_FOUND.labels(
        tenant_id=tenant_id,
        document_category=document_category,
    ).observe(fields_found)
    
    if penalties:
        for penalty_type in penalties:
            CONFIDENCE_PENALTIES_APPLIED.labels(
                tenant_id=tenant_id,
                penalty_type=penalty_type,
            ).inc()
    
    if bonuses:
        for bonus_type in bonuses:
            CONFIDENCE_BONUSES_APPLIED.labels(
                tenant_id=tenant_id,
                bonus_type=bonus_type,
            ).inc()


def get_registry() -> CollectorRegistry:
    if "prometheus_multiproc_dir" in os.environ:
        registry = CollectorRegistry()
        MultiProcessCollector(registry)
        return registry
    return REGISTRY
