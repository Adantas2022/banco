from datetime import datetime

import pytest

from irpf_processor.domain.events import (
    DocumentEvent,
    DocumentUploaded,
    DocumentRouted,
    DocumentExtracted,
    DocumentReady,
    DocumentFailed,
    DocumentQuarantined,
)


class TestDocumentEvent:

    def test_create_base_event(self):
        event = DocumentEvent(
            document_id="doc-123",
            tenant_id="tenant-abc"
        )

        assert event.document_id == "doc-123"
        assert event.tenant_id == "tenant-abc"

    def test_timestamp_auto_generated(self):
        before = datetime.utcnow()
        event = DocumentEvent(document_id="doc", tenant_id="tenant")
        after = datetime.utcnow()

        assert before <= event.timestamp <= after

    def test_event_type_returns_class_name(self):
        event = DocumentEvent(document_id="doc", tenant_id="tenant")

        assert event.event_type == "DocumentEvent"

    def test_is_frozen_dataclass(self):
        event = DocumentEvent(document_id="doc", tenant_id="tenant")

        with pytest.raises(Exception):
            event.document_id = "new-id"


class TestDocumentUploaded:

    def test_create_with_all_fields(self):
        event = DocumentUploaded(
            document_id="doc-upload",
            tenant_id="tenant-1",
            storage_uri="s3://bucket/key",
            media_type="application/pdf",
            sha256="abc123def456"
        )

        assert event.document_id == "doc-upload"
        assert event.storage_uri == "s3://bucket/key"
        assert event.media_type == "application/pdf"
        assert event.sha256 == "abc123def456"

    def test_event_type(self):
        event = DocumentUploaded(
            document_id="doc",
            tenant_id="tenant"
        )

        assert event.event_type == "DocumentUploaded"

    def test_default_values(self):
        event = DocumentUploaded(
            document_id="doc",
            tenant_id="tenant"
        )

        assert event.storage_uri == ""
        assert event.media_type == ""
        assert event.sha256 == ""

    def test_inherits_from_document_event(self):
        event = DocumentUploaded(document_id="doc", tenant_id="tenant")

        assert isinstance(event, DocumentEvent)


class TestDocumentRouted:

    def test_create_with_pdf_type(self):
        event = DocumentRouted(
            document_id="doc-routed",
            tenant_id="tenant-1",
            pdf_type="DIGITAL",
            message="Document routed successfully"
        )

        assert event.pdf_type == "DIGITAL"
        assert event.message == "Document routed successfully"

    def test_event_type(self):
        event = DocumentRouted(document_id="doc", tenant_id="tenant")

        assert event.event_type == "DocumentRouted"

    def test_default_values(self):
        event = DocumentRouted(document_id="doc", tenant_id="tenant")

        assert event.pdf_type == ""
        assert event.message == ""


class TestDocumentExtracted:

    def test_create_with_extraction_details(self):
        event = DocumentExtracted(
            document_id="doc-extracted",
            tenant_id="tenant-1",
            confidence=0.95,
            extraction_method="digital",
            fields_extracted=42,
            warnings_count=2
        )

        assert event.confidence == 0.95
        assert event.extraction_method == "digital"
        assert event.fields_extracted == 42
        assert event.warnings_count == 2

    def test_event_type(self):
        event = DocumentExtracted(document_id="doc", tenant_id="tenant")

        assert event.event_type == "DocumentExtracted"

    def test_default_values(self):
        event = DocumentExtracted(document_id="doc", tenant_id="tenant")

        assert event.confidence == 0.0
        assert event.extraction_method == ""
        assert event.fields_extracted == 0
        assert event.warnings_count == 0


class TestDocumentReady:

    def test_create_with_ready_details(self):
        event = DocumentReady(
            document_id="doc-ready",
            tenant_id="tenant-1",
            confidence=0.98,
            processing_time_ms=1500
        )

        assert event.confidence == 0.98
        assert event.processing_time_ms == 1500

    def test_event_type(self):
        event = DocumentReady(document_id="doc", tenant_id="tenant")

        assert event.event_type == "DocumentReady"

    def test_default_values(self):
        event = DocumentReady(document_id="doc", tenant_id="tenant")

        assert event.confidence == 0.0
        assert event.processing_time_ms == 0


class TestDocumentFailed:

    def test_create_with_failure_details(self):
        event = DocumentFailed(
            document_id="doc-failed",
            tenant_id="tenant-1",
            step="extraction",
            error_code="OCR_TIMEOUT",
            error_message="OCR process timed out after 60s",
            attempt=2
        )

        assert event.step == "extraction"
        assert event.error_code == "OCR_TIMEOUT"
        assert event.error_message == "OCR process timed out after 60s"
        assert event.attempt == 2

    def test_event_type(self):
        event = DocumentFailed(document_id="doc", tenant_id="tenant")

        assert event.event_type == "DocumentFailed"

    def test_default_values(self):
        event = DocumentFailed(document_id="doc", tenant_id="tenant")

        assert event.step == ""
        assert event.error_code == ""
        assert event.error_message == ""
        assert event.attempt == 0


class TestDocumentQuarantined:

    def test_create_with_quarantine_details(self):
        event = DocumentQuarantined(
            document_id="doc-quarantine",
            tenant_id="tenant-1",
            reason="Low confidence below threshold",
            confidence=0.45
        )

        assert event.reason == "Low confidence below threshold"
        assert event.confidence == 0.45

    def test_event_type(self):
        event = DocumentQuarantined(document_id="doc", tenant_id="tenant")

        assert event.event_type == "DocumentQuarantined"

    def test_default_values(self):
        event = DocumentQuarantined(document_id="doc", tenant_id="tenant")

        assert event.reason == ""
        assert event.confidence is None

    def test_confidence_can_be_none(self):
        event = DocumentQuarantined(
            document_id="doc",
            tenant_id="tenant",
            reason="Manual quarantine",
            confidence=None
        )

        assert event.confidence is None


class TestEventImmutability:

    def test_all_events_are_frozen(self):
        events = [
            DocumentUploaded(document_id="doc", tenant_id="tenant"),
            DocumentRouted(document_id="doc", tenant_id="tenant"),
            DocumentExtracted(document_id="doc", tenant_id="tenant"),
            DocumentReady(document_id="doc", tenant_id="tenant"),
            DocumentFailed(document_id="doc", tenant_id="tenant"),
            DocumentQuarantined(document_id="doc", tenant_id="tenant"),
        ]

        for event in events:
            with pytest.raises(Exception):
                event.document_id = "modified"


class TestEventInheritance:

    def test_all_events_inherit_from_document_event(self):
        events = [
            DocumentUploaded(document_id="doc", tenant_id="tenant"),
            DocumentRouted(document_id="doc", tenant_id="tenant"),
            DocumentExtracted(document_id="doc", tenant_id="tenant"),
            DocumentReady(document_id="doc", tenant_id="tenant"),
            DocumentFailed(document_id="doc", tenant_id="tenant"),
            DocumentQuarantined(document_id="doc", tenant_id="tenant"),
        ]

        for event in events:
            assert isinstance(event, DocumentEvent)
            assert hasattr(event, "document_id")
            assert hasattr(event, "tenant_id")
            assert hasattr(event, "timestamp")
            assert hasattr(event, "event_type")
