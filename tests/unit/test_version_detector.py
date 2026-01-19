import pytest

from irpf_processor.infrastructure.extraction.version_detector import (
    VersionDetector,
    DocumentProfile,
)
from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.domain.enums import DocumentCategory


@pytest.fixture
def detector():
    return VersionDetector()


@pytest.fixture
def sample_declaration_context():
    text = """
    DECLARACAO DE AJUSTE ANUAL
    EXERCICIO 2025
    ANO-CALENDARIO 2024
    CPF: 886.978.040-60
    Nome: GENESIS LOPES
    
    DECLARACAO DE BENS E DIREITOS
    RENDIMENTOS TRIBUTAVEIS
    """
    return ExtractionContext(
        full_text=text,
        pages_text={1: text},
        total_pages=1
    )


@pytest.fixture
def sample_receipt_context():
    text = """
    RECIBO DE ENTREGA
    EXERCICIO 2025
    ANO-CALENDARIO 2024
    CPF: 886.978.040-60
    Nome: GENESIS LOPES
    """
    return ExtractionContext(
        full_text=text,
        pages_text={1: text},
        total_pages=1
    )


class TestDocumentProfile:

    def test_default_values(self):
        profile = DocumentProfile()

        assert profile.exercise_year == ""
        assert profile.calendar_year == ""
        assert profile.taxpayer_cpf == ""
        assert profile.taxpayer_name == ""
        assert profile.document_category == DocumentCategory.UNKNOWN
        assert profile.detected_sections == []
        assert profile.confidence == 0.0

    def test_is_receipt_returns_true_for_receipt(self):
        profile = DocumentProfile(document_category=DocumentCategory.RECIBO)

        assert profile.is_receipt() is True
        assert profile.is_declaration() is False

    def test_is_declaration_returns_true_for_declaration(self):
        profile = DocumentProfile(document_category=DocumentCategory.DECLARACAO)

        assert profile.is_declaration() is True
        assert profile.is_receipt() is False

    def test_is_receipt_and_declaration_false_for_unknown(self):
        profile = DocumentProfile(document_category=DocumentCategory.UNKNOWN)

        assert profile.is_receipt() is False
        assert profile.is_declaration() is False

    def test_to_dict_contains_all_fields(self):
        profile = DocumentProfile(
            exercise_year="2025",
            calendar_year="2024",
            taxpayer_cpf="12345678900",
            taxpayer_name="TEST USER",
            document_category=DocumentCategory.DECLARACAO,
            detected_sections=["assets_declaration", "exempt_income"],
            confidence=0.95
        )

        result = profile.to_dict()

        assert result["exercise_year"] == "2025"
        assert result["calendar_year"] == "2024"
        assert result["taxpayer_cpf"] == "12345678900"
        assert result["taxpayer_name"] == "TEST USER"
        assert "document_category" in result
        assert result["detected_sections"] == ["assets_declaration", "exempt_income"]
        assert result["confidence"] == 0.95

    def test_has_section_returns_true_when_present(self):
        profile = DocumentProfile(detected_sections=["assets_declaration"])

        assert profile.has_section("assets_declaration") is True
        assert profile.has_section("exempt_income") is False


class TestVersionDetectorReceiptMarkers:

    def test_receipt_markers_defined(self, detector):
        assert len(detector.RECEIPT_MARKERS) > 0
        assert "RECIBO DE ENTREGA" in detector.RECEIPT_MARKERS


class TestVersionDetectorSectionMarkers:

    def test_section_markers_defined(self, detector):
        assert len(detector.SECTION_MARKERS) > 0
        assert "taxpayer_identification" in detector.SECTION_MARKERS
        assert "assets_declaration" in detector.SECTION_MARKERS


class TestVersionDetectorDetect:

    def test_detect_returns_document_profile(self, detector, sample_declaration_context):
        result = detector.detect(sample_declaration_context)

        assert isinstance(result, DocumentProfile)

    def test_detect_exercise_year(self, detector):
        context = ExtractionContext(
            full_text="EXERCICIO 2025\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert result.exercise_year == "2025"

    def test_detect_calendar_year(self, detector):
        context = ExtractionContext(
            full_text="ANO-CALENDARIO 2024\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert result.calendar_year == "2024"

    def test_detect_both_years(self, detector, sample_declaration_context):
        result = detector.detect(sample_declaration_context)

        assert result.exercise_year == "2025"
        assert result.calendar_year == "2024"


class TestVersionDetectorDetectCategory:

    def test_detect_receipt_category(self, detector, sample_receipt_context):
        result = detector.detect(sample_receipt_context)

        assert result.document_category == DocumentCategory.RECIBO

    def test_unknown_category_for_unrecognized_document(self, detector):
        context = ExtractionContext(
            full_text="Random document without markers",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert result.document_category == DocumentCategory.UNKNOWN

    def test_detect_returns_valid_category(self, detector, sample_declaration_context):
        result = detector.detect(sample_declaration_context)

        assert result.document_category in [
            DocumentCategory.DECLARACAO,
            DocumentCategory.RECIBO,
            DocumentCategory.UNKNOWN
        ]


class TestVersionDetectorDetectSections:

    def test_detect_taxpayer_identification_section(self, detector):
        context = ExtractionContext(
            full_text="DECLARAÇÃO DE AJUSTE ANUAL\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert "taxpayer_identification" in result.detected_sections

    def test_detect_assets_declaration_section(self, detector):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert "assets_declaration" in result.detected_sections

    def test_detect_exempt_income_section(self, detector):
        context = ExtractionContext(
            full_text="RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert "exempt_income" in result.detected_sections

    def test_detect_exclusive_taxation_section(self, detector):
        context = ExtractionContext(
            full_text="RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = detector.detect(context)

        assert "exclusive_taxation_income" in result.detected_sections


class TestVersionDetectorGetRecommendedExtractors:

    def test_returns_detected_sections_as_extractors(self, detector, sample_declaration_context):
        result = detector.detect(sample_declaration_context)
        extractors = detector.get_recommended_extractors(result)

        assert isinstance(extractors, list)

    def test_returns_empty_list_when_no_sections(self, detector):
        context = ExtractionContext(
            full_text="Random text",
            pages_text={1: ""},
            total_pages=1
        )
        result = detector.detect(context)
        extractors = detector.get_recommended_extractors(result)

        assert isinstance(extractors, list)


class TestExtractionContext:

    def test_add_warning(self):
        context = ExtractionContext(
            full_text="",
            pages_text={},
            total_pages=0
        )

        context.add_warning("Test warning")

        assert "Test warning" in context.warnings

    def test_get_page_text(self):
        context = ExtractionContext(
            full_text="Full text",
            pages_text={1: "Page 1", 2: "Page 2"},
            total_pages=2
        )

        assert context.get_page_text(1) == "Page 1"
        assert context.get_page_text(2) == "Page 2"
        assert context.get_page_text(3) == ""

    def test_find_pages_containing(self):
        context = ExtractionContext(
            full_text="Full text",
            pages_text={1: "Page with CPF", 2: "Page without", 3: "Another CPF page"},
            total_pages=3
        )

        result = context.find_pages_containing("CPF")

        assert 1 in result
        assert 3 in result
        assert 2 not in result
