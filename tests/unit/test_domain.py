"""Testes de domínio - entidades, value objects, enums."""

import pytest
from datetime import datetime

from irpf_processor.domain.entities import Document
from irpf_processor.domain.enums import DocumentStatus, PdfType
from irpf_processor.domain.value_objects import (
    Confidence,
    DocumentId,
    FieldValue,
    TenantId,
)


class TestDocumentId:
    """Testes para DocumentId value object."""

    def test_generate_creates_unique_ids(self) -> None:
        id1 = DocumentId.generate()
        id2 = DocumentId.generate()
        assert id1 != id2

    def test_from_string_valid(self) -> None:
        doc_id = DocumentId.from_string("abc-123")
        assert doc_id.value == "abc-123"

    def test_from_string_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            DocumentId.from_string("")

    def test_str_returns_value(self) -> None:
        doc_id = DocumentId(value="test-id")
        assert str(doc_id) == "test-id"


class TestFieldValue:
    """Testes para FieldValue value object."""

    def test_valid_confidence(self) -> None:
        fv = FieldValue(value="test", confidence=0.95, source="text")
        assert fv.confidence == 0.95

    def test_invalid_confidence_raises(self) -> None:
        with pytest.raises(ValueError):
            FieldValue(value="test", confidence=1.5, source="text")

    def test_is_high_confidence(self) -> None:
        fv = FieldValue(value="test", confidence=0.99, source="text")
        assert fv.is_high_confidence()

    def test_is_from_ocr(self) -> None:
        fv = FieldValue(value="test", confidence=0.8, source="ocr")
        assert fv.is_from_ocr()


class TestDocumentStatus:
    """Testes para DocumentStatus enum."""

    def test_valid_transitions_from_received(self) -> None:
        status = DocumentStatus.RECEIVED
        assert status.can_transition_to(DocumentStatus.ROUTED)
        assert status.can_transition_to(DocumentStatus.FAILED)
        assert not status.can_transition_to(DocumentStatus.READY)

    def test_terminal_states(self) -> None:
        assert DocumentStatus.READY.is_terminal()
        assert DocumentStatus.FAILED.is_terminal()
        assert not DocumentStatus.RECEIVED.is_terminal()


class TestDocument:
    """Testes para Document entity."""

    def test_mark_as_routed(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
            sha256="abc123",
        )

        doc.mark_as_routed(PdfType.DIGITAL)

        assert doc.status == DocumentStatus.ROUTED
        assert doc.pdf_type == PdfType.DIGITAL

    def test_mark_as_failed(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
            sha256="abc123",
        )

        doc.mark_as_failed("extraction", "OCR_FAILED", "OCR timeout")

        assert doc.status == DocumentStatus.FAILED
        assert doc.error_step == "extraction"
        assert doc.attempts == 1

    def test_can_retry(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
            sha256="abc123",
        )
        doc.attempts = 2

        assert doc.can_retry(max_attempts=3)
        assert not doc.can_retry(max_attempts=2)

    def test_calculate_sha256(self) -> None:
        content = b"test content"
        sha256 = Document.calculate_sha256(content)
        assert len(sha256) == 64

    def test_document_id_is_generated(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
        )

        assert doc.document_id is not None
        assert len(doc.document_id) == 36

    def test_mark_as_extracted(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
        )
        doc.mark_as_routed(PdfType.DIGITAL)

        doc.mark_as_extracted(confidence=0.95)

        assert doc.status == DocumentStatus.EXTRACTED
        assert doc.confidence == 0.95

    def test_mark_as_ready(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
        )

        doc.mark_as_ready()

        assert doc.status == DocumentStatus.READY

    def test_mark_as_quarantined(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
        )

        doc.mark_as_quarantined(reason="Low confidence")

        assert doc.status == DocumentStatus.QUARANTINED
        assert doc.error_message == "Low confidence"

    def test_is_ready(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
        )

        assert doc.is_ready() is False

        doc.mark_as_ready()

        assert doc.is_ready() is True

    def test_is_extractable(self) -> None:
        doc = Document(
            tenant_id="tenant-1",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/key",
        )

        assert doc.is_extractable() is False

        doc.mark_as_routed(PdfType.DIGITAL)

        assert doc.is_extractable() is True


class TestPdfType:

    def test_requires_ocr_image(self) -> None:
        assert PdfType.IMAGE.requires_ocr() is True

    def test_requires_ocr_mixed(self) -> None:
        assert PdfType.MIXED.requires_ocr() is True

    def test_requires_ocr_digital(self) -> None:
        assert PdfType.DIGITAL.requires_ocr() is False

    def test_is_extractable_digital(self) -> None:
        assert PdfType.DIGITAL.is_extractable() is True

    def test_is_extractable_image(self) -> None:
        assert PdfType.IMAGE.is_extractable() is True

    def test_is_extractable_unknown(self) -> None:
        assert PdfType.UNKNOWN.is_extractable() is False


class TestDocumentStatusExtended:

    def test_is_processable_received(self) -> None:
        assert DocumentStatus.RECEIVED.is_processable() is True

    def test_is_processable_routed(self) -> None:
        assert DocumentStatus.ROUTED.is_processable() is True

    def test_is_processable_extracted(self) -> None:
        assert DocumentStatus.EXTRACTED.is_processable() is True

    def test_is_processable_ready(self) -> None:
        assert DocumentStatus.READY.is_processable() is False

    def test_is_processable_failed(self) -> None:
        assert DocumentStatus.FAILED.is_processable() is False

    def test_is_terminal_quarantined(self) -> None:
        assert DocumentStatus.QUARANTINED.is_terminal() is True

    def test_transitions_from_routed(self) -> None:
        assert DocumentStatus.ROUTED.can_transition_to(DocumentStatus.EXTRACTED) is True
        assert DocumentStatus.ROUTED.can_transition_to(DocumentStatus.FAILED) is True
        assert DocumentStatus.ROUTED.can_transition_to(DocumentStatus.QUARANTINED) is True
        assert DocumentStatus.ROUTED.can_transition_to(DocumentStatus.READY) is False

    def test_transitions_from_extracted(self) -> None:
        assert DocumentStatus.EXTRACTED.can_transition_to(DocumentStatus.READY) is True
        assert DocumentStatus.EXTRACTED.can_transition_to(DocumentStatus.FAILED) is True
