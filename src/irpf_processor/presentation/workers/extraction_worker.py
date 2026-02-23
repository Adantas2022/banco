from __future__ import annotations

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
    record_digital_to_ocr_fallback,
    record_document_category,
    record_document_processed,
    record_extraction_duration,
    record_extraction_warning,
    record_failure,
    record_pages_skipped,
    record_professional_confidence,
    record_section_extraction,
    record_status_transition,
    record_subprocess_timeout,
    record_text_extraction_duration,
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


def detect_category_from_text(full_text: str) -> DocumentCategory:
    """Detecta categoria a partir de texto já extraído (sem re-extrair)."""
    if not full_text or not full_text.strip():
        return DocumentCategory.UNKNOWN
    if is_receipt_document(full_text):
        return DocumentCategory.RECIBO
    return DocumentCategory.DECLARACAO


@dramatiq.actor(max_retries=3, min_backoff=1000, max_backoff=60000, time_limit=1200000)
def process_document(document_id: str, tenant_id: str) -> None:
    start_time = time.perf_counter()
    document_category = DocumentCategory.UNKNOWN
    
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

        with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)

        try:
            from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_all_text

            extraction_start = time.perf_counter()

            pages_text, total_pages, extraction_warnings, extraction_timing = extract_all_text(tmp_path)
            text_extraction_seconds = time.perf_counter() - extraction_start

            full_text = "\n".join(
                pages_text[k] for k in sorted(pages_text.keys())
            )
            has_text = bool(full_text.strip())

            had_timeout = any("TIMEOUT" in w for w in extraction_warnings)
            pages_timed_out = sum(1 for w in extraction_warnings if "PAGE_TIMEOUT" in w)
            pages_with_error = sum(1 for w in extraction_warnings if "PAGE_ERROR" in w)

            record_text_extraction_duration(tenant_id, "pdfplumber_subprocess", text_extraction_seconds)

            if had_timeout:
                if any("PROCESS_TIMEOUT" in w for w in extraction_warnings):
                    record_subprocess_timeout(tenant_id, "process_killed")
                elif any("PDF_OPEN_TIMEOUT" in w for w in extraction_warnings):
                    record_subprocess_timeout(tenant_id, "pdf_open")
                if pages_timed_out > 0:
                    record_pages_skipped(tenant_id, "timeout", pages_timed_out)
            if pages_with_error > 0:
                record_pages_skipped(tenant_id, "error", pages_with_error)

            should_fallback_to_ocr = _should_fallback_to_ocr(
                has_text, had_timeout, extraction_warnings, pages_text, total_pages,
            )

            if should_fallback_to_ocr:
                fallback_reason = _get_fallback_reason(has_text, had_timeout, extraction_warnings)
                _execute_ocr_fallback(
                    db=db,
                    document_id=document_id,
                    tenant_id=tenant_id,
                    reason=fallback_reason,
                    extraction_warnings=extraction_warnings,
                    text_extraction_seconds=text_extraction_seconds,
                    extraction_timing=extraction_timing,
                    had_timeout=had_timeout,
                    total_pages=total_pages,
                    size_bytes=len(pdf_content),
                    start_time=start_time,
                )
                push_metrics_to_gateway()
                return

            document_category = detect_category_from_text(full_text)

            record_document_category(tenant_id, document_category.value)
            logger.info(
                "Document category detected",
                document_id=document_id,
                category=document_category.value,
                has_text=has_text,
                text_extraction_seconds=round(text_extraction_seconds, 2),
                pdf_open_seconds=round(extraction_timing.get("open_s", 0), 2),
                pages_extraction_seconds=round(extraction_timing.get("pages_s", 0), 2),
            )

            pdf_type = PdfType.DIGITAL.value

            parsing_start = time.perf_counter()

            if document_category == DocumentCategory.RECIBO:
                parser = ReceiptParser()
                result = parser.parse_from_text(
                    full_text, total_pages=total_pages,
                )
                template_version = "recibo"
            else:
                parser = IRPFParser()
                result = parser.parse_from_pages_text(
                    pages_text=pages_text,
                    full_text=full_text,
                    total_pages=total_pages,
                    warning_message=(
                        "Documento detectado via extração digital "
                        "(estrutura por página preservada)"
                    ),
                )
                template_version = parser.detected_version or "unknown"

            parsing_seconds = time.perf_counter() - parsing_start

            for w in extraction_warnings:
                result.warnings.insert(0, w)

            extraction_duration = time.perf_counter() - extraction_start

            record_text_extraction_duration(tenant_id, "parsing", parsing_seconds)
            record_extraction_duration(
                tenant_id=tenant_id,
                pdf_type=pdf_type,
                template_version=template_version,
                duration_seconds=extraction_duration,
                document_category=document_category.value,
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

                record_professional_confidence(
                    tenant_id=tenant_id,
                    template_version=template_version,
                    overall=confidence_details.overall,
                    coverage_score=confidence_details.coverage_score,
                    validation_score=confidence_details.validation_score,
                    field_score=confidence_details.details.get("field_score", 0.0),
                    needs_review=confidence_details.needs_review,
                    review_flags=confidence_details.review_flags,
                    validation_results=confidence_details.validation_results,
                    section_scores=confidence_details.section_scores,
                )

            extraction_collection = db["extraction_results"]

            if document_category == DocumentCategory.RECIBO:
                ir_response_data = {
                    "ir_response": {
                        "receipt": result_dict,
                        "declaration": None,
                    }
                }
            else:
                receipt_data = None
                try:
                    receipt_parser = ReceiptParser()
                    receipt_result = receipt_parser.parse_from_text(
                        full_text, total_pages=total_pages,
                    )
                    if receipt_result and receipt_result.receipt_number:
                        receipt_data = receipt_result.to_dict()
                        logger.info(
                            "Receipt also extracted from declaration document",
                            document_id=document_id,
                            receipt_number=receipt_result.receipt_number,
                        )
                except Exception as receipt_error:
                    logger.debug(
                        "No receipt found in declaration document",
                        document_id=document_id,
                        error=str(receipt_error),
                    )

                ir_response_data = {
                    "ir_response": {
                        "receipt": receipt_data,
                        "declaration": result_dict,
                    }
                }

            extraction_doc = {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "document_category": document_category.value,
                "template_version": template_version,
                "confidence": result.confidence,
                "confidence_details": confidence_details.to_dict() if confidence_details else None,
                "total_pages": result.total_pages,
                "warnings": result.warnings,
                "data": ir_response_data,
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
                document_category=document_category.value,
                had_timeout=had_timeout,
            )

            WORKER_JOBS_TOTAL.labels(worker_name="extraction_worker", status="success").inc()

            logger.info(
                "Document processing completed",
                document_id=document_id,
                category=document_category.value,
                status="READY",
                confidence=result.confidence,
                total_pages=result.total_pages,
                template_version=template_version,
                processing_time_seconds=round(processing_duration, 2),
                text_extraction_seconds=round(text_extraction_seconds, 2),
                parsing_seconds=round(parsing_seconds, 2),
                pdf_open_seconds=round(extraction_timing.get("open_s", 0), 2),
                had_timeout=had_timeout,
                pages_timed_out=pages_timed_out,
                pages_with_error=pages_with_error,
                warnings_count=len(result.warnings),
                size_bytes=len(pdf_content),
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

        record_failure(tenant_id, "extraction", "EXTRACTION_ERROR", document_category.value)
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


MIN_USEFUL_TEXT_RATIO = 0.3
MIN_CHARS_FOR_DIGITAL = 200


def _should_fallback_to_ocr(
    has_text: bool,
    had_timeout: bool,
    extraction_warnings: list[str],
    pages_text: dict[int, str],
    total_pages: int,
) -> bool:
    if not has_text:
        return True

    if any("PROCESS_TIMEOUT" in w for w in extraction_warnings):
        return True

    if any("PDF_OPEN_TIMEOUT" in w for w in extraction_warnings):
        return True

    if total_pages == 0:
        return True

    total_chars = sum(len(t.strip()) for t in pages_text.values())
    if total_chars < MIN_CHARS_FOR_DIGITAL:
        return True

    pages_with_text = sum(1 for t in pages_text.values() if len(t.strip()) > 10)
    if total_pages > 0 and pages_with_text / total_pages < MIN_USEFUL_TEXT_RATIO:
        return True

    return False


def _get_fallback_reason(
    has_text: bool,
    had_timeout: bool,
    extraction_warnings: list[str],
) -> str:
    if any("PROCESS_TIMEOUT" in w for w in extraction_warnings):
        return "process_timeout"
    if any("PDF_OPEN_TIMEOUT" in w for w in extraction_warnings):
        return "pdf_open_timeout"
    if not has_text:
        return "no_text_extracted"
    return "insufficient_text"


def _execute_ocr_fallback(
    *,
    db,
    document_id: str,
    tenant_id: str,
    reason: str,
    extraction_warnings: list[str],
    text_extraction_seconds: float,
    extraction_timing: dict,
    had_timeout: bool,
    total_pages: int,
    size_bytes: int,
    start_time: float,
) -> None:
    from irpf_processor.presentation.workers.ocr_worker import process_ocr_document

    logger.info(
        "Digital extraction insufficient, falling back to OCR",
        document_id=document_id,
        tenant_id=tenant_id,
        fallback_reason=reason,
        text_extraction_seconds=round(text_extraction_seconds, 2),
        pdf_open_seconds=round(extraction_timing.get("open_s", 0), 2),
        had_timeout=had_timeout,
        total_pages=total_pages,
        size_bytes=size_bytes,
        warnings=extraction_warnings,
        elapsed_before_fallback=round(time.perf_counter() - start_time, 2),
    )

    record_digital_to_ocr_fallback(tenant_id, reason)

    db["documents"].update_one(
        {"document_id": document_id, "tenant_id": tenant_id},
        {"$set": {
            "pdf_type": "IMAGE",
            "digital_fallback_reason": reason,
            "updated_at": datetime.now(timezone.utc),
        }},
    )

    record_status_transition(tenant_id, "ROUTED", "ROUTED")
    WORKER_JOBS_TOTAL.labels(worker_name="extraction_worker", status="fallback_to_ocr").inc()

    process_ocr_document.send(document_id, tenant_id)

    logger.info(
        "Document re-routed to OCR queue",
        document_id=document_id,
        tenant_id=tenant_id,
        fallback_reason=reason,
    )
