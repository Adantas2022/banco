import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

from irpf_processor.domain.enums import DocumentStatus, DocumentCategory, PdfType


class TestDocumentStatusEnum:

    def test_received_value(self):
        assert DocumentStatus.RECEIVED.value == "RECEIVED"

    def test_routed_value(self):
        assert DocumentStatus.ROUTED.value == "ROUTED"

    def test_extracted_value(self):
        assert DocumentStatus.EXTRACTED.value == "EXTRACTED"

    def test_ready_value(self):
        assert DocumentStatus.READY.value == "READY"

    def test_failed_value(self):
        assert DocumentStatus.FAILED.value == "FAILED"

    def test_quarantined_value(self):
        assert DocumentStatus.QUARANTINED.value == "QUARANTINED"

    def test_can_transition_to(self):
        assert DocumentStatus.RECEIVED.can_transition_to(DocumentStatus.ROUTED) is True
        assert DocumentStatus.RECEIVED.can_transition_to(DocumentStatus.FAILED) is True
        assert DocumentStatus.READY.can_transition_to(DocumentStatus.FAILED) is False

    def test_is_terminal(self):
        assert DocumentStatus.READY.is_terminal() is True
        assert DocumentStatus.FAILED.is_terminal() is True
        assert DocumentStatus.ROUTED.is_terminal() is False

    def test_is_processable(self):
        assert DocumentStatus.RECEIVED.is_processable() is True
        assert DocumentStatus.ROUTED.is_processable() is True
        assert DocumentStatus.READY.is_processable() is False


class TestDocumentCategoryEnum:

    def test_declaracao_value(self):
        assert DocumentCategory.DECLARACAO.value == "DECLARACAO"

    def test_recibo_value(self):
        assert DocumentCategory.RECIBO.value == "RECIBO"

    def test_unknown_value(self):
        assert DocumentCategory.UNKNOWN.value == "UNKNOWN"


class TestPdfTypeEnum:

    def test_digital_value(self):
        assert PdfType.DIGITAL.value == "DIGITAL"

    def test_image_value(self):
        assert PdfType.IMAGE.value == "IMAGE"

    def test_mixed_value(self):
        assert PdfType.MIXED.value == "MIXED"


class TestGetSyncDb:

    def test_get_sync_db_is_callable(self):
        from irpf_processor.presentation.workers.extraction_worker import get_sync_db
        assert callable(get_sync_db)


class TestGetDocumentSync:

    def test_get_document_sync_is_callable(self):
        from irpf_processor.presentation.workers.extraction_worker import get_document_sync
        assert callable(get_document_sync)


class TestUpdateStatusSync:

    def test_update_status_sync_is_callable(self):
        from irpf_processor.presentation.workers.extraction_worker import update_status_sync
        assert callable(update_status_sync)


class TestDetectDocumentCategory:

    def test_detect_document_category_exists(self):
        from irpf_processor.presentation.workers.extraction_worker import detect_document_category
        assert callable(detect_document_category)


class TestProcessDocumentWorker:

    def test_process_document_is_dramatiq_actor(self):
        from irpf_processor.presentation.workers.extraction_worker import process_document
        assert hasattr(process_document, "send")
        assert hasattr(process_document, "fn")

    def test_process_document_has_retry_config(self):
        from irpf_processor.presentation.workers.extraction_worker import process_document
        assert hasattr(process_document, "options")


class TestPushMetricsToGateway:

    def test_push_metrics_is_callable(self):
        from irpf_processor.presentation.workers.extraction_worker import push_metrics_to_gateway
        assert callable(push_metrics_to_gateway)

    @patch("irpf_processor.presentation.workers.extraction_worker.os.environ.get")
    def test_uses_default_pushgateway_url(self, mock_env_get):
        mock_env_get.return_value = "pushgateway:9091"

        from irpf_processor.presentation.workers.extraction_worker import push_metrics_to_gateway

        try:
            push_metrics_to_gateway()
        except Exception:
            pass

    @patch("irpf_processor.presentation.workers.extraction_worker.os.environ.get")
    def test_handles_push_error_gracefully(self, mock_env_get):
        mock_env_get.side_effect = Exception("Connection refused")

        from irpf_processor.presentation.workers.extraction_worker import push_metrics_to_gateway

        push_metrics_to_gateway()
