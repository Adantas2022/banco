import pytest
from unittest.mock import patch, MagicMock

from irpf_processor.shared import metrics


class TestMetricsExist:

    def test_app_info_exists(self):
        assert hasattr(metrics, "APP_INFO")

    def test_documents_uploaded_total_exists(self):
        assert hasattr(metrics, "DOCUMENTS_UPLOADED_TOTAL")

    def test_documents_processed_total_exists(self):
        assert hasattr(metrics, "DOCUMENTS_PROCESSED_TOTAL")

    def test_extraction_confidence_exists(self):
        assert hasattr(metrics, "EXTRACTION_CONFIDENCE")

    def test_processing_duration_seconds_exists(self):
        assert hasattr(metrics, "PROCESSING_DURATION_SECONDS")

    def test_worker_jobs_total_exists(self):
        assert hasattr(metrics, "WORKER_JOBS_TOTAL")


class TestSetAppInfo:

    def test_set_app_info(self):
        metrics.set_app_info("1.0.0", "test")


class TestRecordDocumentUpload:

    def test_record_document_upload(self):
        metrics.record_document_upload("tenant-123", 1024000)


class TestRecordDocumentCategory:

    def test_record_document_category_declaracao(self):
        metrics.record_document_category("tenant-123", "DECLARACAO")

    def test_record_document_category_recibo(self):
        metrics.record_document_category("tenant-123", "RECIBO")


class TestRecordDocumentProcessed:

    def test_record_document_processed(self):
        metrics.record_document_processed(
            tenant_id="tenant-123",
            status="READY",
            pdf_type="DIGITAL",
            template_version="2025",
            confidence=0.95,
            processing_time_seconds=5.0,
            total_pages=10
        )


class TestRecordStatusTransition:

    def test_record_status_transition(self):
        metrics.record_status_transition("tenant-123", "RECEIVED", "ROUTED")


class TestRecordExtractionDuration:

    def test_record_extraction_duration(self):
        metrics.record_extraction_duration(
            tenant_id="tenant-123",
            pdf_type="DIGITAL",
            template_version="2025",
            duration_seconds=2.5
        )


class TestRecordExtractionWarning:

    def test_record_extraction_warning(self):
        metrics.record_extraction_warning("tenant-123", "missing_field")


class TestRecordOcrUsage:

    def test_record_ocr_usage(self):
        metrics.record_ocr_usage("tenant-123", "tesseract")


class TestRecordOcrDuration:

    def test_record_ocr_duration(self):
        metrics.record_ocr_duration("tenant-123", "tesseract", 30.0)


class TestRecordOcrConfidence:

    def test_record_ocr_confidence(self):
        metrics.record_ocr_confidence("tenant-123", "tesseract", 0.85)


class TestRecordRoutingDuration:

    def test_record_routing_duration(self):
        metrics.record_routing_duration("tenant-123", "IMAGE", 1.5)


class TestRecordPdfTypeDetection:

    def test_record_pdf_type_detection_high_confidence(self):
        metrics.record_pdf_type_detection("DIGITAL", 0.95)

    def test_record_pdf_type_detection_medium_confidence(self):
        metrics.record_pdf_type_detection("IMAGE", 0.75)

    def test_record_pdf_type_detection_low_confidence(self):
        metrics.record_pdf_type_detection("MIXED", 0.50)


class TestRecordQuarantine:

    def test_record_quarantine(self):
        metrics.record_quarantine("tenant-123", "low_confidence")


class TestRecordFailure:

    def test_record_failure(self):
        metrics.record_failure("tenant-123", "extraction", "EXTRACTION_ERROR")


class TestRecordRetry:

    def test_record_retry(self):
        metrics.record_retry("tenant-123", "extraction")


class TestRecordApiRequest:

    def test_record_api_request(self):
        metrics.record_api_request("POST", "/v1/documents", 202, 0.5)


class TestRecordStorageOperation:

    def test_record_storage_operation(self):
        metrics.record_storage_operation("upload", "success", 0.25)


class TestRecordDatabaseOperation:

    def test_record_database_operation(self):
        metrics.record_database_operation("documents", "insert", "success", 0.01)


class TestRecordSectionExtraction:

    def test_record_section_extraction_success(self):
        metrics.record_section_extraction("taxpayer_identification", "2025", True)

    def test_record_section_extraction_failure(self):
        metrics.record_section_extraction("assets_declaration", "2025", False)


class TestRecordFieldConfidence:

    def test_record_field_confidence(self):
        metrics.record_field_confidence("cpf", "taxpayer_identification", 0.99)


class TestRecordTaxpayerProfile:

    def test_record_taxpayer_profile(self):
        metrics.record_taxpayer_profile("individual")


class TestRecordEventPublished:

    def test_record_event_published(self):
        metrics.record_event_published("document_ready")


class TestSetWorkerJobsInQueue:

    def test_set_worker_jobs_in_queue(self):
        metrics.set_worker_jobs_in_queue("extraction", 10)


class TestSetCurrentDocumentsByStatus:

    def test_set_current_documents_by_status(self):
        metrics.set_current_documents_by_status("RECEIVED", 5)


class TestRecordConfidenceDetails:

    def test_record_confidence_details_basic(self):
        metrics.record_confidence_details(
            tenant_id="tenant-123",
            document_category="DECLARACAO",
            confidence_level="HIGH",
            fields_found=8
        )

    def test_record_confidence_details_with_penalties(self):
        metrics.record_confidence_details(
            tenant_id="tenant-123",
            document_category="DECLARACAO",
            confidence_level="MEDIUM",
            fields_found=5,
            penalties={"missing_cpf": 0.1, "missing_name": 0.05}
        )

    def test_record_confidence_details_with_bonuses(self):
        metrics.record_confidence_details(
            tenant_id="tenant-123",
            document_category="RECIBO",
            confidence_level="HIGH",
            fields_found=10,
            bonuses={"all_fields_found": 0.05}
        )

    def test_record_confidence_details_with_both(self):
        metrics.record_confidence_details(
            tenant_id="tenant-123",
            document_category="DECLARACAO",
            confidence_level="MEDIUM",
            fields_found=6,
            penalties={"missing_field": 0.05},
            bonuses={"good_structure": 0.02}
        )


class TestGetRegistry:

    def test_get_registry_returns_default_registry(self):
        result = metrics.get_registry()
        assert result is not None

    @patch.dict("os.environ", {"prometheus_multiproc_dir": "/tmp/metrics"})
    @patch("irpf_processor.shared.metrics.MultiProcessCollector")
    @patch("irpf_processor.shared.metrics.CollectorRegistry")
    def test_get_registry_returns_multiprocess_registry(self, mock_registry, mock_collector):
        mock_registry_instance = MagicMock()
        mock_registry.return_value = mock_registry_instance

        result = metrics.get_registry()

        mock_registry.assert_called_once()
        mock_collector.assert_called_once_with(mock_registry_instance)
