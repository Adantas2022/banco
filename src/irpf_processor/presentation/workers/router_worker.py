import os
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import dramatiq
from pymongo import MongoClient

from irpf_processor.config import get_settings
from irpf_processor.domain.enums import DocumentStatus
from irpf_processor.infrastructure.extraction.ocr import PdfTypeDetector
from irpf_processor.infrastructure.extraction.ocr.models import PdfType as OcrPdfType
from irpf_processor.infrastructure.storage import get_storage_service, extract_storage_key
from irpf_processor.shared.logging import get_logger
from irpf_processor.shared.metrics import (
    WORKER_JOBS_TOTAL,
    get_registry,
    record_status_transition,
    record_routing_duration,
    record_pdf_type_detection,
)

logger = get_logger(__name__)


def push_metrics_to_gateway():
    try:
        from prometheus_client import pushadd_to_gateway, REGISTRY
        pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "pushgateway:9091")
        instance_id = f"router-{os.getpid()}"
        pushadd_to_gateway(pushgateway_url, job="irpf-router", registry=REGISTRY, grouping_key={"instance": instance_id})
        logger.info("Metrics pushed to gateway", pushgateway_url=pushgateway_url, instance=instance_id)
    except Exception as e:
        logger.warning("Failed to push metrics to gateway", error=str(e))


def get_sync_db():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def update_document_pdf_type(db, document_id: str, tenant_id: str, pdf_type: str):
    db["documents"].update_one(
        {"document_id": document_id, "tenant_id": tenant_id},
        {"$set": {
            "pdf_type": pdf_type,
            "status": DocumentStatus.ROUTED.value,
            "updated_at": datetime.now(timezone.utc),
        }},
    )


@dramatiq.actor(queue_name="extraction-router", max_retries=2, min_backoff=500, max_backoff=5000, time_limit=1800000)
def route_document(document_id: str, tenant_id: str) -> None:
    """Route document to appropriate extraction queue.
    
    time_limit=1800000 (30 minutes) - PDF type detection can be slow for large/complex PDFs
    """
    start_time = time.perf_counter()
    logger.info(
        "Routing document",
        document_id=document_id,
        tenant_id=tenant_id,
    )

    db = get_sync_db()
    storage = get_storage_service()
    detector = PdfTypeDetector()

    document = db["documents"].find_one({
        "document_id": document_id,
        "tenant_id": tenant_id,
    })

    if not document:
        logger.error("Document not found for routing", document_id=document_id)
        WORKER_JOBS_TOTAL.labels(worker_name="router_worker", status="not_found").inc()
        return

    try:
        storage_key = extract_storage_key(document["storage_uri"])
        pdf_content = storage.download_sync(storage_key)

        with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)

        try:
            detection_result = detector.detect_with_confidence(tmp_path)
            pdf_type = detection_result.pdf_type

            logger.info(
                "PDF type detected",
                document_id=document_id,
                pdf_type=pdf_type.value,
                confidence=detection_result.confidence,
                total_pages=detection_result.total_pages,
            )

            record_pdf_type_detection(pdf_type.value, detection_result.confidence)

            # ---------- idempotency guard ----------
            # Atomically mark as ROUTED only if still RECEIVED.
            # If a retry fires after .send() already succeeded,
            # this prevents sending the message a second time.
            claimed = db["documents"].find_one_and_update(
                {
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                    "status": DocumentStatus.RECEIVED.value,
                },
                {"$set": {
                    "status": DocumentStatus.ROUTED.value,
                    "pdf_type": pdf_type.value,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )
            if claimed is None:
                logger.info(
                    "Document already routed, skipping duplicate send",
                    document_id=document_id,
                )
                return

            record_status_transition(tenant_id, "RECEIVED", "ROUTED")

            if pdf_type in (OcrPdfType.IMAGE, OcrPdfType.MIXED):
                from irpf_processor.presentation.workers.ocr_worker import process_ocr_document
                process_ocr_document.send(document_id, tenant_id)
                logger.info("Document routed to OCR queue", document_id=document_id, pdf_type=pdf_type.value)
            else:
                from irpf_processor.presentation.workers.extraction_worker import process_document
                process_document.send(document_id, tenant_id)
                logger.info("Document routed to digital queue", document_id=document_id)

            routing_time = time.perf_counter() - start_time
            record_routing_duration(tenant_id, pdf_type.value, routing_time)
            WORKER_JOBS_TOTAL.labels(worker_name="router_worker", status="success").inc()

            logger.info(
                "Document routing completed",
                document_id=document_id,
                pdf_type=pdf_type.value,
                routing_time_seconds=routing_time,
            )

            push_metrics_to_gateway()

        finally:
            tmp_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(
            "Document routing failed",
            document_id=document_id,
            error=str(e),
        )
        WORKER_JOBS_TOTAL.labels(worker_name="router_worker", status="failed").inc()

        db["documents"].update_one(
            {"document_id": document_id, "tenant_id": tenant_id},
            {"$set": {
                "status": DocumentStatus.FAILED.value,
                "error_message": f"Routing failed: {e}",
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        push_metrics_to_gateway()
        raise
