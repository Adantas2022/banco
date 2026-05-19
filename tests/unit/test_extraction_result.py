import pytest
from datetime import datetime

from irpf_processor.domain.entities.extraction_result import ExtractionResult
from irpf_processor.domain.enums import PdfType
from irpf_processor.domain.value_objects import (
    Confidence,
    DocumentId,
    FieldValue,
    TenantId,
)


class TestExtractionResult:

    @pytest.fixture
    def sample_result(self) -> ExtractionResult:
        return ExtractionResult(
            document_id=DocumentId.from_string("doc-123"),
            tenant_id=TenantId.from_string("tenant-abc"),
            pdf_type=PdfType.DIGITAL,
            raw_data={
                "cpf": FieldValue(value="12345678900", confidence=0.99, source="text"),
                "name": FieldValue(value="John Doe", confidence=0.85, source="text"),
            },
            formatted_data={"cpf": "123.456.789-00", "name": "John Doe"},
            confidence=Confidence(overall=0.92, extraction_method="digital"),
        )

    def test_create_extraction_result(self, sample_result: ExtractionResult):
        assert sample_result.document_id.value == "doc-123"
        assert sample_result.tenant_id.value == "tenant-abc"
        assert sample_result.pdf_type == PdfType.DIGITAL

    def test_add_warning(self, sample_result: ExtractionResult):
        sample_result.add_warning("Field X has low confidence")

        assert len(sample_result.warnings) == 1
        assert "Field X" in sample_result.warnings[0]

    def test_add_multiple_warnings(self, sample_result: ExtractionResult):
        sample_result.add_warning("Warning 1")
        sample_result.add_warning("Warning 2")
        sample_result.add_warning("Warning 3")

        assert len(sample_result.warnings) == 3

    def test_is_high_confidence_true(self):
        result = ExtractionResult(
            document_id=DocumentId.from_string("doc-1"),
            tenant_id=TenantId.from_string("tenant-1"),
            pdf_type=PdfType.DIGITAL,
            raw_data={},
            formatted_data={},
            confidence=Confidence(overall=0.98, extraction_method="digital"),
        )

        assert result.is_high_confidence() is True

    def test_is_high_confidence_false(self):
        result = ExtractionResult(
            document_id=DocumentId.from_string("doc-1"),
            tenant_id=TenantId.from_string("tenant-1"),
            pdf_type=PdfType.DIGITAL,
            raw_data={},
            formatted_data={},
            confidence=Confidence(overall=0.80, extraction_method="digital"),
        )

        assert result.is_high_confidence() is False

    def test_is_high_confidence_custom_threshold(self, sample_result: ExtractionResult):
        assert sample_result.is_high_confidence(threshold=0.90) is True
        assert sample_result.is_high_confidence(threshold=0.95) is False

    def test_is_low_confidence_true(self):
        result = ExtractionResult(
            document_id=DocumentId.from_string("doc-1"),
            tenant_id=TenantId.from_string("tenant-1"),
            pdf_type=PdfType.IMAGE,
            raw_data={},
            formatted_data={},
            confidence=Confidence(overall=0.45, extraction_method="ocr"),
        )

        assert result.is_low_confidence() is True

    def test_is_low_confidence_false(self, sample_result: ExtractionResult):
        assert sample_result.is_low_confidence() is False

    def test_is_low_confidence_custom_threshold(self):
        result = ExtractionResult(
            document_id=DocumentId.from_string("doc-1"),
            tenant_id=TenantId.from_string("tenant-1"),
            pdf_type=PdfType.DIGITAL,
            raw_data={},
            formatted_data={},
            confidence=Confidence(overall=0.70, extraction_method="digital"),
        )

        assert result.is_low_confidence(threshold=0.75) is True
        assert result.is_low_confidence(threshold=0.60) is False

    def test_get_field_confidence_existing_field(self, sample_result: ExtractionResult):
        cpf_confidence = sample_result.get_field_confidence("cpf")

        assert cpf_confidence == 0.99

    def test_get_field_confidence_nonexistent_field(self, sample_result: ExtractionResult):
        unknown_confidence = sample_result.get_field_confidence("unknown_field")

        assert unknown_confidence is None

    def test_has_warnings_false(self, sample_result: ExtractionResult):
        assert sample_result.has_warnings() is False

    def test_has_warnings_true(self, sample_result: ExtractionResult):
        sample_result.add_warning("Some warning")

        assert sample_result.has_warnings() is True

    def test_default_values(self):
        result = ExtractionResult(
            document_id=DocumentId.from_string("doc-1"),
            tenant_id=TenantId.from_string("tenant-1"),
            pdf_type=PdfType.DIGITAL,
            raw_data={},
            formatted_data={},
            confidence=Confidence(overall=0.90, extraction_method="digital"),
        )

        assert result.warnings == []
        assert result.processing_time_ms == 0
        assert isinstance(result.created_at, datetime)

    def test_processing_time_ms(self):
        result = ExtractionResult(
            document_id=DocumentId.from_string("doc-1"),
            tenant_id=TenantId.from_string("tenant-1"),
            pdf_type=PdfType.DIGITAL,
            raw_data={},
            formatted_data={},
            confidence=Confidence(overall=0.90, extraction_method="digital"),
            processing_time_ms=1500,
        )

        assert result.processing_time_ms == 1500
