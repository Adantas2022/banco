import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from irpf_processor.domain.enums import DocumentStatus


class TestGetSyncDb:

    def test_get_sync_db_is_callable(self):
        from irpf_processor.presentation.workers.router_worker import get_sync_db
        assert callable(get_sync_db)

    @patch("irpf_processor.presentation.workers.router_worker.MongoClient")
    @patch("irpf_processor.presentation.workers.router_worker.get_settings")
    def test_get_sync_db_connects_to_mongo(self, mock_settings, mock_client):
        mock_settings.return_value = MagicMock(
            mongo_uri="mongodb://localhost:27017",
            mongo_db="test_db"
        )
        mock_db = MagicMock()
        mock_client.return_value.__getitem__.return_value = mock_db

        from irpf_processor.presentation.workers.router_worker import get_sync_db
        result = get_sync_db()

        mock_client.assert_called_once_with("mongodb://localhost:27017")


class TestUpdateDocumentPdfType:

    def test_update_document_pdf_type_is_callable(self):
        from irpf_processor.presentation.workers.router_worker import update_document_pdf_type
        assert callable(update_document_pdf_type)

    def test_updates_document_with_pdf_type_and_status(self):
        from irpf_processor.presentation.workers.router_worker import update_document_pdf_type

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        update_document_pdf_type(mock_db, "doc-123", "tenant-456", "DIGITAL")

        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        assert call_args[0][0] == {"document_id": "doc-123", "tenant_id": "tenant-456"}
        update_set = call_args[0][1]["$set"]
        assert update_set["pdf_type"] == "DIGITAL"
        assert update_set["status"] == DocumentStatus.ROUTED.value
        assert "updated_at" in update_set

    def test_updates_document_with_image_type(self):
        from irpf_processor.presentation.workers.router_worker import update_document_pdf_type

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        update_document_pdf_type(mock_db, "doc-123", "tenant-456", "IMAGE")

        call_args = mock_collection.update_one.call_args
        assert call_args[0][1]["$set"]["pdf_type"] == "IMAGE"

    def test_updates_document_with_mixed_type(self):
        from irpf_processor.presentation.workers.router_worker import update_document_pdf_type

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_db.__getitem__.return_value = mock_collection

        update_document_pdf_type(mock_db, "doc-123", "tenant-456", "MIXED")

        call_args = mock_collection.update_one.call_args
        assert call_args[0][1]["$set"]["pdf_type"] == "MIXED"


class TestPushMetricsToGateway:

    def test_push_metrics_is_callable(self):
        from irpf_processor.presentation.workers.router_worker import push_metrics_to_gateway
        assert callable(push_metrics_to_gateway)

    @patch("irpf_processor.presentation.workers.router_worker.os.environ.get")
    def test_uses_default_pushgateway_url(self, mock_env_get):
        mock_env_get.return_value = "pushgateway:9091"

        from irpf_processor.presentation.workers.router_worker import push_metrics_to_gateway

        try:
            push_metrics_to_gateway()
        except Exception:
            pass

    @patch("irpf_processor.presentation.workers.router_worker.os.environ.get")
    def test_handles_push_error_gracefully(self, mock_env_get):
        mock_env_get.side_effect = Exception("Connection refused")

        from irpf_processor.presentation.workers.router_worker import push_metrics_to_gateway

        push_metrics_to_gateway()


class TestRouteDocument:

    def test_route_document_is_dramatiq_actor(self):
        from irpf_processor.presentation.workers.router_worker import route_document
        assert hasattr(route_document, "send")
        assert hasattr(route_document, "fn")

    def test_route_document_has_queue_name(self):
        from irpf_processor.presentation.workers.router_worker import route_document
        assert hasattr(route_document, "options")

    @patch("irpf_processor.presentation.workers.router_worker.get_sync_db")
    @patch("irpf_processor.presentation.workers.router_worker.MinioStorageService")
    @patch("irpf_processor.presentation.workers.router_worker.PdfTypeDetector")
    @patch("irpf_processor.presentation.workers.router_worker.push_metrics_to_gateway")
    @patch("irpf_processor.presentation.workers.router_worker.WORKER_JOBS_TOTAL")
    def test_handles_missing_document(
        self, mock_jobs_total, mock_push, mock_detector, mock_storage, mock_get_db
    ):
        from irpf_processor.presentation.workers.router_worker import route_document

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = None
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        route_document.fn("nonexistent", "tenant-456")

        mock_jobs_total.labels.assert_called_with(worker_name="router_worker", status="not_found")


    @patch("irpf_processor.presentation.workers.router_worker.get_sync_db")
    @patch("irpf_processor.presentation.workers.router_worker.MinioStorageService")
    @patch("irpf_processor.presentation.workers.router_worker.push_metrics_to_gateway")
    @patch("irpf_processor.presentation.workers.router_worker.WORKER_JOBS_TOTAL")
    def test_handles_routing_error(
        self, mock_jobs_total, mock_push, mock_storage, mock_get_db
    ):
        from irpf_processor.presentation.workers.router_worker import route_document

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one.return_value = {
            "document_id": "doc-123",
            "tenant_id": "tenant-456",
            "storage_uri": "s3://documents/tenant-456/doc.pdf",
            "status": "RECEIVED"
        }
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        mock_storage_instance = MagicMock()
        mock_storage_instance.download_sync.side_effect = Exception("Storage error")
        mock_storage.return_value = mock_storage_instance

        with pytest.raises(Exception, match="Storage error"):
            route_document.fn("doc-123", "tenant-456")

        mock_jobs_total.labels.assert_called_with(worker_name="router_worker", status="failed")
        mock_collection.update_one.assert_called()


class TestDocumentStatusEnum:

    def test_received_value(self):
        assert DocumentStatus.RECEIVED.value == "RECEIVED"

    def test_routed_value(self):
        assert DocumentStatus.ROUTED.value == "ROUTED"

    def test_failed_value(self):
        assert DocumentStatus.FAILED.value == "FAILED"
