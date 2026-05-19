import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from irpf_processor.domain.enums import DocumentStatus, DocumentCategory


class TestGetSyncDb:

    def test_get_sync_db_is_callable(self):
        from irpf_processor.presentation.workers.ocr_worker import get_sync_db
        assert callable(get_sync_db)

    @patch("irpf_processor.presentation.workers.ocr_worker.MongoClient")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_settings")
    def test_get_sync_db_connects_to_mongo(self, mock_settings, mock_client):
        mock_settings.return_value = MagicMock(
            mongo_uri="mongodb://localhost:27017",
            mongo_db="test_db"
        )
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db

        from irpf_processor.presentation.workers.ocr_worker import get_sync_db
        result = get_sync_db()

        mock_client.assert_called_once_with("mongodb://localhost:27017")


class TestCreateOcrOrchestrator:

    @patch("irpf_processor.infrastructure.extraction.ocr.DoclingEngine")
    @patch("irpf_processor.presentation.workers.ocr_worker.DocumentAIEngine")
    @patch("irpf_processor.presentation.workers.ocr_worker.TesseractEngine")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_settings")
    def test_creates_orchestrator_with_tesseract(
        self, mock_get_settings, mock_tesseract, mock_documentai, mock_docling
    ):
        from irpf_processor.presentation.workers.ocr_worker import create_ocr_orchestrator

        mock_get_settings.return_value = MagicMock(ocr_engine="tesseract")

        mock_documentai_instance = MagicMock()
        mock_documentai_instance.is_available.return_value = False
        mock_documentai.return_value = mock_documentai_instance

        mock_docling_instance = MagicMock()
        mock_docling_instance.is_available.return_value = False
        mock_docling.return_value = mock_docling_instance

        mock_tesseract_instance = MagicMock()
        mock_tesseract_instance.is_available.return_value = True
        mock_tesseract.return_value = mock_tesseract_instance

        result = create_ocr_orchestrator()

        assert result is not None
        mock_tesseract.assert_called_once_with(lang="por", timeout=180)

    @patch("irpf_processor.infrastructure.extraction.ocr.DoclingEngine")
    @patch("irpf_processor.presentation.workers.ocr_worker.DocumentAIEngine")
    @patch("irpf_processor.presentation.workers.ocr_worker.TesseractEngine")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_settings")
    def test_raises_when_no_engines_available(
        self, mock_get_settings, mock_tesseract, mock_documentai, mock_docling
    ):
        from irpf_processor.presentation.workers.ocr_worker import create_ocr_orchestrator

        mock_get_settings.return_value = MagicMock(ocr_engine="documentai")

        mock_documentai_instance = MagicMock()
        mock_documentai_instance.is_available.return_value = False
        mock_documentai.return_value = mock_documentai_instance

        mock_tesseract_instance = MagicMock()
        mock_tesseract_instance.is_available.return_value = False
        mock_tesseract.return_value = mock_tesseract_instance

        mock_docling_instance = MagicMock()
        mock_docling_instance.is_available.return_value = False
        mock_docling.return_value = mock_docling_instance

        with pytest.raises(RuntimeError, match="No OCR engines available"):
            create_ocr_orchestrator()



class TestPushMetricsToGateway:

    def test_push_metrics_is_callable(self):
        from irpf_processor.presentation.workers.ocr_worker import push_metrics_to_gateway
        assert callable(push_metrics_to_gateway)

    @patch("irpf_processor.presentation.workers.ocr_worker.os.environ.get")
    def test_handles_push_error_gracefully(self, mock_env_get):
        mock_env_get.side_effect = Exception("Connection refused")

        from irpf_processor.presentation.workers.ocr_worker import push_metrics_to_gateway

        push_metrics_to_gateway()


class TestProcessOcrDocument:

    def test_process_ocr_document_is_dramatiq_actor(self):
        from irpf_processor.presentation.workers.ocr_worker import process_ocr_document
        assert hasattr(process_ocr_document, "send")
        assert hasattr(process_ocr_document, "fn")

    def test_process_ocr_document_has_queue_name(self):
        from irpf_processor.presentation.workers.ocr_worker import process_ocr_document
        assert hasattr(process_ocr_document, "options")

    @patch("irpf_processor.presentation.workers.ocr_worker.get_sync_db")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_storage_service")
    @patch("irpf_processor.presentation.workers.ocr_worker.WORKER_JOBS_TOTAL")
    def test_handles_missing_document(self, mock_jobs_total, mock_storage_factory, mock_get_db):
        from irpf_processor.presentation.workers.ocr_worker import process_ocr_document

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        process_ocr_document.fn("nonexistent", "tenant-456")

        mock_jobs_total.labels.assert_called_with(worker_name="ocr_worker", status="not_found")

    @patch("irpf_processor.presentation.workers.ocr_worker.get_sync_db")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_storage_service")
    @patch("irpf_processor.presentation.workers.ocr_worker.create_ocr_orchestrator")
    @patch("irpf_processor.presentation.workers.ocr_worker.PostProcessor")
    @patch("irpf_processor.presentation.workers.ocr_worker.OcrToPdfplumberAdapter")
    @patch("irpf_processor.presentation.workers.ocr_worker.IRPFParser")
    @patch("irpf_processor.presentation.workers.ocr_worker.is_receipt_document")
    @patch("irpf_processor.presentation.workers.ocr_worker.push_metrics_to_gateway")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_ocr_usage")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_ocr_duration")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_ocr_confidence")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_extraction_duration")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_document_category")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_status_transition")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_document_processed")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_section_extraction")
    @patch("irpf_processor.presentation.workers.ocr_worker.WORKER_JOBS_TOTAL")
    def test_processes_declaration_with_ocr(
        self, mock_jobs_total, mock_record_section, mock_record_processed,
        mock_record_status, mock_record_category, mock_record_duration,
        mock_record_conf, mock_record_dur, mock_record_usage, mock_push,
        mock_is_receipt, mock_parser, mock_adapter, mock_postproc,
        mock_orchestrator, mock_storage_factory, mock_get_db
    ):
        from irpf_processor.presentation.workers.ocr_worker import process_ocr_document

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_extraction_collection = MagicMock()
        mock_db.__getitem__.side_effect = lambda x: {
            "documents": mock_collection,
            "extraction_results": mock_extraction_collection
        }.get(x, MagicMock())

        mock_collection.find_one.return_value = {
            "document_id": "doc-123",
            "tenant_id": "tenant-456",
            "storage_uri": "s3://documents/tenant-456/doc.pdf",
            "status": "ROUTED",
            "pdf_type": "IMAGE"
        }
        mock_get_db.return_value = mock_db

        mock_storage_instance = MagicMock()
        mock_storage_instance.download_sync.return_value = b"PDF content"
        mock_storage_factory.return_value = mock_storage_instance

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "DECLARACAO DE AJUSTE ANUAL"
        mock_ocr_result.engine_used = "tesseract"
        mock_ocr_result.confidence = 0.85
        mock_ocr_result.total_pages = 5
        mock_ocr_result.pages = []
        mock_ocr_result.warnings = []

        mock_orchestrator_instance = MagicMock()
        mock_orchestrator_instance.process.return_value = mock_ocr_result
        mock_orchestrator.return_value = mock_orchestrator_instance

        mock_postproc_instance = MagicMock()
        mock_postproc_instance.process.return_value = "DECLARACAO DE AJUSTE ANUAL"
        mock_postproc.return_value = mock_postproc_instance

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.convert.return_value = (
            {1: "DECLARACAO DE AJUSTE ANUAL"},
            "DECLARACAO DE AJUSTE ANUAL",
        )
        mock_adapter.return_value = mock_adapter_instance

        mock_is_receipt.return_value = False

        mock_irpf_result = MagicMock()
        mock_irpf_result.to_dict.return_value = {"taxpayer_identification": {"cpf": "12345678900"}}
        mock_irpf_result.confidence = 0.90
        mock_irpf_result.warnings = []
        mock_irpf_result.total_pages = 5

        mock_parser_instance = MagicMock()
        mock_parser_instance.parse_from_pages_text.return_value = mock_irpf_result
        mock_parser_instance.detected_version = "2025"
        mock_parser_instance.get_confidence_details.return_value = None
        mock_parser.return_value = mock_parser_instance

        process_ocr_document.fn("doc-123", "tenant-456")

        mock_orchestrator_instance.process.assert_called_once()
        mock_parser_instance.parse_from_pages_text.assert_called_once()
        mock_collection.update_one.assert_called()

    @patch("irpf_processor.presentation.workers.ocr_worker.get_sync_db")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_storage_service")
    @patch("irpf_processor.presentation.workers.ocr_worker.create_ocr_orchestrator")
    @patch("irpf_processor.presentation.workers.ocr_worker.PostProcessor")
    @patch("irpf_processor.presentation.workers.ocr_worker.OcrToPdfplumberAdapter")
    @patch("irpf_processor.presentation.workers.ocr_worker.ReceiptParser")
    @patch("irpf_processor.presentation.workers.ocr_worker.IRPFParser")
    @patch("irpf_processor.presentation.workers.ocr_worker.is_receipt_document")
    @patch("irpf_processor.presentation.workers.ocr_worker.push_metrics_to_gateway")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_ocr_usage")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_ocr_duration")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_ocr_confidence")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_extraction_duration")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_document_category")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_status_transition")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_document_processed")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_section_extraction")
    @patch("irpf_processor.presentation.workers.ocr_worker.WORKER_JOBS_TOTAL")
    def test_processes_receipt_with_ocr(
        self, mock_jobs_total, mock_record_section, mock_record_processed,
        mock_record_status, mock_record_category, mock_record_duration,
        mock_record_conf, mock_record_dur, mock_record_usage, mock_push,
        mock_is_receipt, mock_irpf_parser, mock_receipt_parser,
        mock_adapter, mock_postproc, mock_orchestrator,
        mock_storage_factory, mock_get_db
    ):
        from irpf_processor.presentation.workers.ocr_worker import process_ocr_document

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_extraction_collection = MagicMock()
        mock_db.__getitem__.side_effect = lambda x: {
            "documents": mock_collection,
            "extraction_results": mock_extraction_collection
        }.get(x, MagicMock())

        mock_collection.find_one.return_value = {
            "document_id": "doc-123",
            "tenant_id": "tenant-456",
            "storage_uri": "s3://documents/tenant-456/doc.pdf",
            "status": "ROUTED",
            "pdf_type": "IMAGE"
        }
        mock_get_db.return_value = mock_db

        mock_storage_instance = MagicMock()
        mock_storage_instance.download_sync.return_value = b"PDF content"
        mock_storage_factory.return_value = mock_storage_instance

        mock_ocr_result = MagicMock()
        mock_ocr_result.text = "RECIBO DE ENTREGA"
        mock_ocr_result.engine_used = "tesseract"
        mock_ocr_result.confidence = 0.80
        mock_ocr_result.total_pages = 1
        mock_ocr_result.pages = []
        mock_ocr_result.warnings = []

        mock_orchestrator_instance = MagicMock()
        mock_orchestrator_instance.process.return_value = mock_ocr_result
        mock_orchestrator.return_value = mock_orchestrator_instance

        mock_postproc_instance = MagicMock()
        mock_postproc_instance.process.return_value = "RECIBO DE ENTREGA"
        mock_postproc.return_value = mock_postproc_instance

        mock_adapter_instance = MagicMock()
        mock_adapter_instance.convert.return_value = (
            {1: "RECIBO DE ENTREGA"},
            "RECIBO DE ENTREGA",
        )
        mock_adapter.return_value = mock_adapter_instance

        mock_is_receipt.return_value = True

        mock_receipt_result = MagicMock()
        mock_receipt_result.to_dict.return_value = {"receipt_number": "12345"}
        mock_receipt_result.confidence = 0.85
        mock_receipt_result.warnings = []
        mock_receipt_result.total_pages = 1

        mock_receipt_parser_instance = MagicMock()
        mock_receipt_parser_instance.parse_from_text.return_value = mock_receipt_result
        mock_receipt_parser_instance.get_confidence_details.return_value = None
        mock_receipt_parser.return_value = mock_receipt_parser_instance

        process_ocr_document.fn("doc-123", "tenant-456")

        mock_is_receipt.assert_called_once()
        mock_receipt_parser_instance.parse_from_text.assert_called_once()

    @patch("irpf_processor.presentation.workers.ocr_worker.get_sync_db")
    @patch("irpf_processor.presentation.workers.ocr_worker.get_storage_service")
    @patch("irpf_processor.presentation.workers.ocr_worker.create_ocr_orchestrator")
    @patch("irpf_processor.presentation.workers.ocr_worker.push_metrics_to_gateway")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_failure")
    @patch("irpf_processor.presentation.workers.ocr_worker.record_status_transition")
    @patch("irpf_processor.presentation.workers.ocr_worker.WORKER_JOBS_TOTAL")
    def test_handles_ocr_error(
        self, mock_jobs_total, mock_record_status, mock_record_failure,
        mock_push, mock_orchestrator, mock_storage_factory, mock_get_db
    ):
        from irpf_processor.presentation.workers.ocr_worker import process_ocr_document

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        mock_collection.find_one.return_value = {
            "document_id": "doc-123",
            "tenant_id": "tenant-456",
            "storage_uri": "s3://documents/tenant-456/doc.pdf",
            "status": "ROUTED",
            "pdf_type": "IMAGE"
        }
        mock_get_db.return_value = mock_db

        mock_storage_instance = MagicMock()
        mock_storage_instance.download_sync.return_value = b"PDF content"
        mock_storage_factory.return_value = mock_storage_instance

        mock_orchestrator.side_effect = RuntimeError("No OCR engines available")

        with pytest.raises(RuntimeError):
            process_ocr_document.fn("doc-123", "tenant-456")

        mock_record_failure.assert_called()
        mock_jobs_total.labels.assert_called_with(worker_name="ocr_worker", status="failed")


class TestDocumentCategoryEnum:

    def test_declaracao_value(self):
        assert DocumentCategory.DECLARACAO.value == "DECLARACAO"

    def test_recibo_value(self):
        assert DocumentCategory.RECIBO.value == "RECIBO"

    def test_unknown_value(self):
        assert DocumentCategory.UNKNOWN.value == "UNKNOWN"


class TestDocumentStatusEnum:

    def test_routed_value(self):
        assert DocumentStatus.ROUTED.value == "ROUTED"

    def test_ready_value(self):
        assert DocumentStatus.READY.value == "READY"

    def test_failed_value(self):
        assert DocumentStatus.FAILED.value == "FAILED"
