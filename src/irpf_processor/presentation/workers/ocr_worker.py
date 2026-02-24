import os
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import dramatiq
from pymongo import MongoClient

from irpf_processor.config import get_settings
from irpf_processor.domain.enums import DocumentStatus, DocumentCategory
from irpf_processor.infrastructure.extraction import IRPFParser, ReceiptParser, is_receipt_document
from irpf_processor.infrastructure.extraction.ocr import (
    DocumentAIEngine,
    OcrOrchestrator,
    OcrToPdfplumberAdapter,
    PostProcessor,
    TesseractEngine,
)
from irpf_processor.infrastructure.storage import get_storage_service, extract_storage_key
from irpf_processor.shared.logging import get_logger
from irpf_processor.shared.metrics import (
    WORKER_JOBS_TOTAL,
    record_confidence_details,
    record_document_category,
    record_document_processed,
    record_extraction_duration,
    record_extraction_warning,
    record_failure,
    record_ocr_confidence,
    record_ocr_duration,
    record_ocr_professional_confidence,
    record_ocr_usage,
    record_professional_confidence,
    record_section_extraction,
    record_status_transition,
)

logger = get_logger(__name__)


def push_metrics_to_gateway():
    try:
        from prometheus_client import pushadd_to_gateway, REGISTRY
        pushgateway_url = os.environ.get("PUSHGATEWAY_URL", "pushgateway:9091")
        instance_id = f"ocr-{os.getpid()}"
        pushadd_to_gateway(pushgateway_url, job="irpf-ocr-worker", registry=REGISTRY, grouping_key={"instance": instance_id})
        logger.info("Metrics pushed to gateway", pushgateway_url=pushgateway_url, instance=instance_id)
    except Exception as e:
        logger.warning("Failed to push metrics to gateway", error=str(e))


def get_sync_db():
    settings = get_settings()
    client = MongoClient(settings.mongo_uri)
    return client[settings.mongo_db]


def create_ocr_orchestrator() -> OcrOrchestrator:
    settings = get_settings()
    engines = []

    def _build_documentai():
        engine = DocumentAIEngine(timeout=300)
        if engine.is_available():
            logger.info("Document AI engine available")
            return engine
        return None

    def _build_tesseract():
        engine = TesseractEngine(lang="por", timeout=180)
        if engine.is_available():
            logger.info("Tesseract engine available")
            return engine
        return None

    def _build_docling():
        try:
            from irpf_processor.infrastructure.extraction.ocr import DoclingEngine

            engine = DoclingEngine(timeout=300, vision_model="default")
            if engine.is_available():
                logger.info("Docling engine available")
                return engine
            return None
        except ImportError:
            logger.info("Docling not installed")
            return None

    builders = {
        "documentai": _build_documentai,
        "tesseract": _build_tesseract,
        "docling": _build_docling,
    }
    preferred = settings.ocr_engine
    order = [preferred] + [name for name in builders.keys() if name != preferred]

    for name in order:
        engine = builders[name]()
        if engine:
            engines.append(engine)

    if not engines:
        raise RuntimeError("No OCR engines available")

    return OcrOrchestrator(engines=engines, min_confidence=0.5)


@dramatiq.actor(queue_name="extraction-ocr", max_retries=2, min_backoff=5000, max_backoff=120000, time_limit=1800000)
def process_ocr_document(document_id: str, tenant_id: str) -> None:
    start_time = time.perf_counter()
    document_category = DocumentCategory.UNKNOWN
    
    logger.info(
        "Starting OCR document processing",
        document_id=document_id,
        tenant_id=tenant_id,
    )

    db = get_sync_db()
    storage = get_storage_service()

    document = db["documents"].find_one({
        "document_id": document_id,
        "tenant_id": tenant_id,
    })

    if not document:
        logger.error("Document not found for OCR", document_id=document_id)
        WORKER_JOBS_TOTAL.labels(worker_name="ocr_worker", status="not_found").inc()
        return

    try:
        orchestrator = create_ocr_orchestrator()
        post_processor = PostProcessor(lang="pt-BR")
        parser = IRPFParser()

        storage_key = extract_storage_key(document["storage_uri"])
        pdf_content = storage.download_sync(storage_key)

        logger.info(
            "PDF downloaded for OCR",
            document_id=document_id,
            size_bytes=len(pdf_content),
        )

        with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(pdf_content)
            tmp_path = Path(tmp_file.name)

        try:
            ocr_start = time.perf_counter()
            ocr_result = orchestrator.process(tmp_path, timeout=900)  # 15 min para Granite Vision
            ocr_duration = time.perf_counter() - ocr_start

            logger.info(
                "OCR extraction completed",
                document_id=document_id,
                engine_used=ocr_result.engine_used,
                confidence=ocr_result.confidence,
                pages=ocr_result.total_pages,
                ocr_duration_seconds=ocr_duration,
            )

            processed_text = post_processor.process(ocr_result.text)
            ocr_adapter = OcrToPdfplumberAdapter(post_processor=post_processor)
            pages_text, structured_text = ocr_adapter.convert(ocr_result)
            normalized_ocr_text = structured_text or processed_text

            record_ocr_usage(tenant_id, ocr_result.engine_used)
            record_ocr_duration(tenant_id, ocr_result.engine_used, ocr_duration)
            record_ocr_confidence(tenant_id, ocr_result.engine_used, ocr_result.confidence)
            record_extraction_duration(
                tenant_id=tenant_id,
                pdf_type="IMAGE",
                template_version="ocr",
                duration_seconds=ocr_duration,
            )

            document_category = (
                DocumentCategory.RECIBO
                if is_receipt_document(normalized_ocr_text)
                else DocumentCategory.DECLARACAO
            )
            record_document_category(tenant_id, document_category.value)
            
            logger.info(
                "Document category detected (OCR)",
                document_id=document_id,
                category=document_category.value,
            )

            extraction_start = time.perf_counter()
            
            if document_category == DocumentCategory.RECIBO:
                receipt_parser = ReceiptParser()
                irpf_result = receipt_parser.parse_from_text(
                    normalized_ocr_text,
                    ocr_result.total_pages,
                    ocr_confidence=ocr_result.confidence,
                )
                template_version = "recibo-ocr"
            else:
                irpf_result = parser.parse_from_pages_text(
                    pages_text=pages_text,
                    full_text=normalized_ocr_text,
                    total_pages=ocr_result.total_pages,
                    ocr_confidence=ocr_result.confidence,
                )
                template_version = parser.detected_version or "ocr"
            
            extraction_duration = time.perf_counter() - extraction_start

            final_confidence = min(irpf_result.confidence, ocr_result.confidence)

            result_dict = irpf_result.to_dict()

            for warning in irpf_result.warnings:
                warning_type = warning.split(":")[0] if ":" in warning else "general"
                record_extraction_warning(tenant_id, warning_type)

            if document_category == DocumentCategory.DECLARACAO:
                for section_name in ["taxpayer_identification", "assets_declaration", 
                                    "income_from_legal_person_to_holder", "exempt_income",
                                    "exclusive_taxation_income", "exploited_rural_properties_in_brazil"]:
                    has_section = section_name in result_dict and result_dict[section_name]
                    record_section_extraction(section_name, template_version, has_section)
            else:
                record_section_extraction("receipt", template_version, True)

            if document_category == DocumentCategory.RECIBO:
                confidence_details = receipt_parser.get_confidence_details()
            else:
                confidence_details = parser.get_confidence_details()
            
            if confidence_details:
                record_confidence_details(
                    tenant_id=tenant_id,
                    document_category=document_category.value,
                    confidence_level=confidence_details.level,
                    fields_found=confidence_details.details.get("fields_found", 0),
                    penalties=confidence_details.penalties,
                    bonuses=confidence_details.bonuses,
                )
                
                fallback_used = len(ocr_result.metadata.get("attempts", [])) > 1
                record_ocr_professional_confidence(
                    tenant_id=tenant_id,
                    ocr_engine=ocr_result.engine_used,
                    overall=confidence_details.overall,
                    ocr_confidence=ocr_result.confidence,
                    coverage_score=confidence_details.coverage_score,
                    validation_score=confidence_details.validation_score,
                    needs_review=confidence_details.needs_review,
                    review_flags=confidence_details.review_flags,
                    fallback_used=fallback_used,
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
            
            # Estruturar dados no mesmo formato do extraction_worker (ir_response wrapper)
            if document_category == DocumentCategory.RECIBO:
                ir_response_data = {
                    "ir_response": {
                        "receipt": result_dict,
                        "declaration": None,
                    }
                }
            else:
                # Quando é DECLARAÇÃO, também tentar extrair o recibo se presente
                receipt_data = None
                try:
                    receipt_parser_for_receipt = ReceiptParser()
                    receipt_result = receipt_parser_for_receipt.parse_from_text(
                        normalized_ocr_text,
                        ocr_result.total_pages,
                        ocr_confidence=ocr_result.confidence,
                    )
                    if receipt_result and receipt_result.receipt_number:
                        receipt_data = receipt_result.to_dict()
                        logger.info(
                            "Receipt also extracted from OCR declaration",
                            document_id=document_id,
                            receipt_number=receipt_result.receipt_number,
                        )
                except Exception as receipt_error:
                    logger.debug(
                        "No receipt found in OCR declaration",
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
                "confidence": final_confidence,
                "confidence_details": confidence_details.to_dict() if confidence_details else None,
                "total_pages": ocr_result.total_pages,
                "warnings": irpf_result.warnings + ocr_result.warnings,
                "data": ir_response_data,
                "ocr_engine": ocr_result.engine_used,
                "ocr_confidence": ocr_result.confidence,
                "extraction_method": "ocr",
                "updated_at": datetime.now(timezone.utc),
            }
            extraction_collection.update_one(
                {"document_id": document_id, "tenant_id": tenant_id},
                {"$set": extraction_doc, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
                upsert=True,
            )

            record_status_transition(tenant_id, "ROUTED", "READY")

            db["documents"].update_one(
                {"document_id": document_id, "tenant_id": tenant_id},
                {"$set": {
                    "status": DocumentStatus.READY.value,
                    "document_category": document_category.value,
                    "confidence": final_confidence,
                    "ocr_engine": ocr_result.engine_used,
                    "updated_at": datetime.now(timezone.utc),
                }},
            )

            total_duration = time.perf_counter() - start_time
            record_document_processed(
                tenant_id=tenant_id,
                status="READY",
                pdf_type="IMAGE",
                template_version="ocr",
                confidence=final_confidence,
                processing_time_seconds=total_duration,
                total_pages=ocr_result.total_pages,
                document_category=document_category.value,
            )

            WORKER_JOBS_TOTAL.labels(worker_name="ocr_worker", status="success").inc()

            logger.info(
                "OCR document processing completed",
                document_id=document_id,
                status="READY",
                confidence=final_confidence,
                ocr_engine=ocr_result.engine_used,
                total_duration_seconds=total_duration,
            )

            push_metrics_to_gateway()

        finally:
            tmp_path.unlink(missing_ok=True)

    except Exception as e:
        logger.error(
            "OCR document processing failed",
            document_id=document_id,
            error=str(e),
        )

        record_failure(tenant_id, "ocr_extraction", "OCR_ERROR", document_category.value)
        record_status_transition(tenant_id, "ROUTED", "FAILED")
        WORKER_JOBS_TOTAL.labels(worker_name="ocr_worker", status="failed").inc()

        db["documents"].update_one(
            {"document_id": document_id, "tenant_id": tenant_id},
            {"$set": {
                "status": DocumentStatus.FAILED.value,
                "error_message": f"OCR failed: {e}",
                "updated_at": datetime.now(timezone.utc),
            }},
        )

        push_metrics_to_gateway()
        raise
