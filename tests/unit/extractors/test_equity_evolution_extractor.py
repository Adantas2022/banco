"""Unit tests for EquityEvolutionExtractor (US-19160) — regex path."""

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.equity_evolution import (
    EquityEvolutionExtractor,
)

SAMPLE_PAGE = (
    "Página 7 de 8\n"
    "EVOLUÇÃO PATRIMONIAL\n"
    " Bens e direitos em 31/12/2023                                250.000,00\n"
    " Bens e direitos em 31/12/2024                                275.500,50\n"
    " Dívidas e ônus reais em 31/12/2023                                10.000,00\n"
    " Dívidas e ônus reais em 31/12/2024                                 5.000,00\n"
    "\n"
    "OUTRAS INFORMAÇÕES\n"
    " Rendimentos isentos e não tributáveis                            80.001,00\n"
)


@pytest.fixture
def extractor() -> EquityEvolutionExtractor:
    return EquityEvolutionExtractor()


@pytest.fixture
def context() -> ExtractionContext:
    return ExtractionContext(
        full_text=SAMPLE_PAGE,
        pages_text={7: SAMPLE_PAGE},
        total_pages=8,
        pdf_path="/tmp/test.pdf",
        document_id="test_doc_equity",
    )


class TestCanExtract:
    def test_detects_section(self, extractor, context):
        assert extractor.can_extract(context) is True

    def test_returns_false_when_marker_absent(self, extractor):
        ctx = ExtractionContext(
            full_text="ALGUMA OUTRA SECAO\nLINHA QUALQUER",
            pages_text={1: "ALGUMA OUTRA SECAO"},
            total_pages=1,
            pdf_path="/tmp/x.pdf",
            document_id="empty",
        )
        assert extractor.can_extract(ctx) is False

    def test_detects_ocr_variant_no_accents(self, extractor):
        text = "EVOLUCAO PATRIMONIAL\n Bens e direitos em 31/12/2024 100,00"
        ctx = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
            pdf_path="/tmp/x.pdf",
            document_id="ocr",
        )
        assert extractor.can_extract(ctx) is True


class TestExtract:
    def test_full_section_extraction(self, extractor, context):
        result = extractor.extract(context)
        assert result is not None
        assert result["section_name"] == "Evolução Patrimonial"
        assert result["assets_last_year"] == 250000.0
        assert result["assets_current_year"] == 275500.5
        assert result["debts_last_year"] == 10000.0
        assert result["debts_current_year"] == 5000.0
        assert result["year_last"] == 2023
        assert result["year_current"] == 2024
        # (275500.5 - 5000) - (250000 - 10000) = 270500.5 - 240000 = 30500.5
        assert result["computed_evolution"] == 30500.5
        assert "id" in result

    def test_section_without_debts_returns_zeros(self, extractor):
        text = (
            "EVOLUÇÃO PATRIMONIAL\n"
            " Bens e direitos em 31/12/2023        100.000,00\n"
            " Bens e direitos em 31/12/2024        150.000,00\n"
            "OUTRAS INFORMAÇÕES\n"
        )
        ctx = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
            pdf_path="/tmp/x.pdf",
            document_id="no_debts",
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert result["assets_current_year"] == 150000.0
        assert result["debts_current_year"] == 0.0
        # (150000 - 0) - (100000 - 0) = 50000.0
        assert result["computed_evolution"] == 50000.0

    def test_returns_none_when_section_absent(self, extractor):
        ctx = ExtractionContext(
            full_text="OUTRA COISA",
            pages_text={1: "OUTRA COISA"},
            total_pages=1,
            pdf_path="/tmp/x.pdf",
            document_id="absent",
        )
        assert extractor.extract(ctx) is None

    def test_returns_none_when_section_empty(self, extractor):
        text = "EVOLUÇÃO PATRIMONIAL\nOUTRAS INFORMAÇÕES"
        ctx = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
            pdf_path="/tmp/x.pdf",
            document_id="empty_section",
        )
        result = extractor.extract(ctx)
        assert result is None

    def test_id_consistent_across_calls(self, extractor, context):
        a = extractor.extract(context)
        b = extractor.extract(context)
        assert a["id"] == b["id"]

    def test_handles_us_locale_value_format(self, extractor):
        # OCR sometimes flips comma/period; parse_currency handles it.
        text = (
            "EVOLUÇÃO PATRIMONIAL\n"
            " Bens e direitos em 31/12/2024        1.234,56\n"
            "OUTRAS INFORMAÇÕES\n"
        )
        ctx = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
            pdf_path="/tmp/x.pdf",
            document_id="us_locale",
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert result["assets_current_year"] == 1234.56
