import pytest

from irpf_processor.domain.exceptions import (
    DomainException,
    DocumentNotFoundError,
    DocumentAlreadyExistsError,
    ExtractionFailedError,
    InvalidStateTransitionError,
    LowConfidenceError,
)


class TestDomainException:

    def test_create_with_message_and_code(self):
        exc = DomainException(message="Test error", code="TEST_CODE")

        assert exc.message == "Test error"
        assert exc.code == "TEST_CODE"
        assert str(exc) == "Test error"

    def test_inherits_from_exception(self):
        exc = DomainException(message="Test", code="CODE")

        assert isinstance(exc, Exception)


class TestDocumentNotFoundError:

    def test_create_with_document_id(self):
        exc = DocumentNotFoundError(document_id="doc-123")

        assert exc.document_id == "doc-123"
        assert exc.code == "DOCUMENT_NOT_FOUND"
        assert "doc-123" in exc.message

    def test_message_format(self):
        exc = DocumentNotFoundError(document_id="abc-456")

        assert exc.message == "Document 'abc-456' not found"

    def test_is_domain_exception(self):
        exc = DocumentNotFoundError(document_id="test")

        assert isinstance(exc, DomainException)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(DocumentNotFoundError) as exc_info:
            raise DocumentNotFoundError(document_id="missing-doc")

        assert exc_info.value.document_id == "missing-doc"


class TestDocumentAlreadyExistsError:

    def test_create_with_sha256_and_existing_id(self):
        sha256 = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0"
        exc = DocumentAlreadyExistsError(
            sha256=sha256,
            existing_document_id="existing-doc-456"
        )

        assert exc.sha256 == sha256
        assert exc.existing_document_id == "existing-doc-456"
        assert exc.code == "DOCUMENT_ALREADY_EXISTS"

    def test_message_truncates_sha256(self):
        sha256 = "abcdef1234567890abcdef1234567890abcdef12"
        exc = DocumentAlreadyExistsError(
            sha256=sha256,
            existing_document_id="doc-1"
        )

        assert sha256[:16] in exc.message
        assert sha256 not in exc.message

    def test_is_domain_exception(self):
        exc = DocumentAlreadyExistsError(sha256="hash", existing_document_id="id")

        assert isinstance(exc, DomainException)


class TestExtractionFailedError:

    def test_create_with_document_id_and_reason(self):
        exc = ExtractionFailedError(
            document_id="doc-789",
            reason="OCR timeout after 30s"
        )

        assert exc.document_id == "doc-789"
        assert exc.reason == "OCR timeout after 30s"
        assert exc.code == "EXTRACTION_FAILED"

    def test_message_includes_document_and_reason(self):
        exc = ExtractionFailedError(
            document_id="test-doc",
            reason="Invalid PDF format"
        )

        assert "test-doc" in exc.message
        assert "Invalid PDF format" in exc.message

    def test_is_domain_exception(self):
        exc = ExtractionFailedError(document_id="x", reason="y")

        assert isinstance(exc, DomainException)


class TestInvalidStateTransitionError:

    def test_create_with_transition_details(self):
        exc = InvalidStateTransitionError(
            document_id="doc-001",
            current_status="RECEIVED",
            target_status="READY"
        )

        assert exc.document_id == "doc-001"
        assert exc.current_status == "RECEIVED"
        assert exc.target_status == "READY"
        assert exc.code == "INVALID_STATE_TRANSITION"

    def test_message_shows_transition(self):
        exc = InvalidStateTransitionError(
            document_id="doc-x",
            current_status="FAILED",
            target_status="READY"
        )

        assert "FAILED" in exc.message
        assert "READY" in exc.message
        assert "doc-x" in exc.message

    def test_is_domain_exception(self):
        exc = InvalidStateTransitionError(
            document_id="x",
            current_status="A",
            target_status="B"
        )

        assert isinstance(exc, DomainException)


class TestLowConfidenceError:

    def test_create_with_confidence_details(self):
        exc = LowConfidenceError(
            document_id="doc-low",
            confidence=0.45,
            threshold=0.60
        )

        assert exc.document_id == "doc-low"
        assert exc.confidence == 0.45
        assert exc.threshold == 0.60
        assert exc.code == "LOW_CONFIDENCE"

    def test_message_includes_percentages(self):
        exc = LowConfidenceError(
            document_id="doc-test",
            confidence=0.55,
            threshold=0.70
        )

        assert "55" in exc.message
        assert "70" in exc.message

    def test_is_domain_exception(self):
        exc = LowConfidenceError(
            document_id="x",
            confidence=0.1,
            threshold=0.5
        )

        assert isinstance(exc, DomainException)

    def test_can_be_raised_with_zero_confidence(self):
        exc = LowConfidenceError(
            document_id="zero-doc",
            confidence=0.0,
            threshold=0.5
        )

        assert exc.confidence == 0.0


class TestExceptionHierarchy:

    def test_all_exceptions_inherit_from_domain_exception(self):
        exceptions = [
            DocumentNotFoundError(document_id="x"),
            DocumentAlreadyExistsError(sha256="h", existing_document_id="e"),
            ExtractionFailedError(document_id="x", reason="r"),
            InvalidStateTransitionError(document_id="x", current_status="A", target_status="B"),
            LowConfidenceError(document_id="x", confidence=0.1, threshold=0.5),
        ]

        for exc in exceptions:
            assert isinstance(exc, DomainException)
            assert isinstance(exc, Exception)
            assert hasattr(exc, "message")
            assert hasattr(exc, "code")
