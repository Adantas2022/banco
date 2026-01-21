import os
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import dramatiq
from pymongo import MongoClient

from irpf_processor.config import get_settings
from irpf_processor.infrastructure.extraction import IRPFParser, ReceiptParser, is_receipt_document
from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor
from irpf_processor.infrastructure.storage import get_storage_service, extract_storage_key
from irpf_processor.domain.enums import DocumentStatus, DocumentCategory, PdfType
from irpf_processor.shared.logging import get_logger
from irpf_processor.shared.metrics import (
    record_confidence_details,
    record_document_category,
    record_document_processed,
    record_extraction_duration,
    record_extraction_warning,
    record_failure,
    record_section_extraction,
    record_status_transition,
    WORKER_JOBS_TOTAL,
    get_registry,
)

logger = get_logger(__name__)


def push_metrics_to_gateway():
    try:
        from prometheus_client import pushadd_to_gateway, REGISTRY
        pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "pushgateway:9091")
        instance_id = f"extraction-{os.getpid()}"
        
        metrics_count = sum(1 for m in REGISTRY.collect() for s in m.samples if 'irpf' in s.name and s.value > 0)
        logger.info("Pushing metrics", metrics_with_values=metrics_count, instance=instance_id)
        
        pushadd_to_gateway(pushgateway_url, job="irpf-worker", registry=REGISTRY, grouping_key={"instance": instance_id})
        logger.info("Metrics pushed to gateway", pushgateway_url=pushgateway_url, instance=instance_id)
    except Exception as e:
        logger.warning("Failed to push metrics to gateway", error=str(e))


def get_sync_db():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def get_document_sync(db, document_id: str, tenant_id: str) -> dict | None:
    return db["documents"].find_one({
        "document_id": document_id,
        "tenant_id": tenant_id,
    })


def update_status_sync(
    db, 
    document_id: str, 
    tenant_id: str, 
    status: DocumentStatus, 
    pdf_type: str | None = None,
    confidence: float | None = None,
    error_message: str | None = None,
):
    update_doc = {
        "status": status.value,
        "updated_at": datetime.now(timezone.utc),
    }
    if pdf_type:
        update_doc["pdf_type"] = pdf_type
    if confidence is not None:
        update_doc["confidence"] = confidence
    if error_message:
        update_doc["error_message"] = error_message
    
    db["documents"].update_one(
        {"document_id": document_id, "tenant_id": tenant_id},
        {"$set": update_doc},
    )


def detect_document_category(pdf_content: bytes) -> DocumentCategory:
    """Detecta se o PDF é uma declaração ou recibo."""
    try:
        text_extractor = PdfTextExtractor()
        text = text_extractor.extract_text(pdf_content)
        if is_receipt_document(text):
            return DocumentCategory.RECIBO
        return DocumentCategory.DECLARACAO
    except Exception:
        return DocumentCategory.UNKNOWN


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=60000)
def process_document(document_id: str, tenant_id: str) -> None:
    start_time = time.perf_counter()
    logger.info(
        "Starting document processing",
        document_id=document_id,
        tenant_id=tenant_id,
    )

    db = get_sync_db()
    storage = get_storage_service()

    document = get_document_sync(db, document_id, tenant_id)
    if not document:
        logger.error("Document not found", document_id=document_id)
        WORKER_JOBS_TOTAL.labels(worker_name="extraction_worker", status="not_found").inc()
        return

    try:
        record_status_transition(tenant_id, "RECEIVED", "ROUTED")
        update_status_sync(
            db=db,
            document_id=document_id,
            tenant_id=tenant_id,
            status=DocumentStatus.ROUTED,
            pdf_type=PdfType.DIGITAL.value,
        )

        storage_key = extract_storage_key(document["storage_uri"])
        pdf_content = storage.download_sync(storage_key)

        logger.info(
            "PDF downloaded",
            document_id=document_id,
            size_bytes=len(pdf_content),
        )

        document_category = detect_document_category(pdf_content)
        record_document_category(tenant_id, document_category.value)
        logger.info(
            "Document category detected",
            document_id=document_id,
            category=document_category.value,
        )

        with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)

        try:
            extraction_start = time.perf_counter()
            
            if document_category == DocumentCategory.RECIBO:
                parser = ReceiptParser()
                result = parser.parse(tmp_path)
                template_version = "recibo"
            else:
                parser = IRPFParser()
                result = parser.parse(tmp_path)
                template_version = parser.detected_version or "unknown"
            
            extraction_duration = time.perf_counter() - extraction_start
            pdf_type = PdfType.DIGITAL.value

            record_extraction_duration(
                tenant_id=tenant_id,
                pdf_type=pdf_type,
                template_version=template_version,
                duration_seconds=extraction_duration,
            )

            for warning in result.warnings:
                warning_type = warning.split(":")[0] if ":" in warning else "general"
                record_extraction_warning(tenant_id, warning_type)

            result_dict = result.to_dict()
            
            if document_category == DocumentCategory.DECLARACAO:
                for section_name in ["taxpayer_identification", "assets_declaration", 
                                    "income_from_legal_person_to_holder", "exempt_income",
                                    "exclusive_taxation_income", "exploited_rural_properties_in_brazil"]:
                    has_section = section_name in result_dict and result_dict[section_name]
                    record_section_extraction(section_name, template_version, has_section)
            else:
                record_section_extraction("receipt", template_version, True)

            confidence_details = parser.get_confidence_details()
            logger.info(
                "Document parsed",
                document_id=document_id,
                category=document_category.value,
                version=template_version,
                confidence=result.confidence,
                confidence_level=confidence_details.level if confidence_details else "unknown",
            )

            if confidence_details:
                record_confidence_details(
                    tenant_id=tenant_id,
                    document_category=document_category.value,
                    confidence_level=confidence_details.level,
                    fields_found=confidence_details.details.get("fields_found", 0),
                    penalties=confidence_details.penalties,
                    bonuses=confidence_details.bonuses,
                )

            extraction_collection = db["extraction_results"]
            extraction_doc = {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "document_category": document_category.value,
                "template_version": template_version,
                "confidence": result.confidence,
                "confidence_details": confidence_details.to_dict() if confidence_details else None,
                "total_pages": result.total_pages,
                "warnings": result.warnings,
                "data": result_dict,
                "updated_at": datetime.now(timezone.utc),
            }
            extraction_collection.update_one(
                {"document_id": document_id, "tenant_id": tenant_id},
                {"$set": extraction_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )

            db["documents"].update_one(
                {"document_id": document_id, "tenant_id": tenant_id},
                {"$set": {"document_category": document_category.value}},
            )

            record_status_transition(tenant_id, "ROUTED", "READY")
            update_status_sync(
                db=db,
                document_id=document_id,
                tenant_id=tenant_id,
                status=DocumentStatus.READY,
                confidence=result.confidence,
            )

            processing_duration = time.perf_counter() - start_time
            record_document_processed(
                tenant_id=tenant_id,
                status="READY",
                pdf_type=pdf_type,
                template_version=template_version,
                confidence=result.confidence,
                processing_time_seconds=processing_duration,
                total_pages=result.total_pages,
            )

            WORKER_JOBS_TOTAL.labels(worker_name="extraction_worker", status="success").inc()

            logger.info(
                "Document processing completed",
                document_id=document_id,
                category=document_category.value,
                status="READY",
                processing_time_seconds=processing_duration,
            )

            push_metrics_to_gateway()

        finally:
            tmp_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(
            "Document processing failed",
            document_id=document_id,
            error=str(e),
        )

        record_failure(tenant_id, "extraction", "EXTRACTION_ERROR")
        record_status_transition(tenant_id, "ROUTED", "FAILED")
        WORKER_JOBS_TOTAL.labels(worker_name="extraction_worker", status="failed").inc()

        push_metrics_to_gateway()

        update_status_sync(
            db=db,
            document_id=document_id,
            tenant_id=tenant_id,
            status=DocumentStatus.FAILED,
            error_message=str(e),
        )

        raise
