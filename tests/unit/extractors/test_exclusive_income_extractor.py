import unicodedata

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.exclusive_income import (
    ExclusiveIncomeExtractor,
)


@pytest.fixture
def extractor():
    return ExclusiveIncomeExtractor()


def _make_section_text(*lines: str) -> str:
    return "\n".join(lines)


class TestExtractFinancialAbroad:

    def test_inline_value_br_format(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["code"] == "12"
        assert result["total_value"] == 3580.0
        assert result["valid_total"] is True

    def test_inline_value_no_law_ref(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior 1.234,56"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 1234.56

    def test_multiline_value(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "3.580,00",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0
        assert result["code"] == "12"

    def test_multiline_value_with_blank_line(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "",
            "3.580,00",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_no_match_returns_none(self, extractor):
        section_text = _make_section_text(
            "01. 13º salário 5.000,00"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is None

    def test_zero_value_returns_none(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 0,00"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is None

    def test_does_not_capture_law_number(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "13. Outros",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is None

    def test_stops_at_next_subsection(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "13. Outros",
            "3.580,00",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is None

    def test_stops_at_total(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "TOTAL 50.000,00",
            "3.580,00",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is None

    def test_disambiguate_12_abroad_vs_12_outros(self, extractor):
        page_text = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00\n"
            "12. Outros\n"
            "Titular 171.955.328-95 51.572.102/0001-12 FINANCEIRA XYZ OUTROS RENDIMENTOS 11.000,00\n"
            "TOTAL 14.580,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1,
        )
        result = extractor.extract(context)
        assert result is not None
        subsections = result["subsections"]
        assert "financial_investments_and_profits_and_dividends_abroad" in subsections
        abroad = subsections["financial_investments_and_profits_and_dividends_abroad"]
        assert abroad["total_value"] == 3580.0
        assert abroad["code"] == "12"

    def test_total_includes_abroad_subsection(self, extractor):
        page_text = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 5.000,00\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00\n"
            "TOTAL 8.580,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1,
        )
        result = extractor.extract(context)
        assert result is not None
        assert result["total_value"] == 8580.0
        assert "financial_investments_and_profits_and_dividends_abroad" in result["subsections"]

    def test_ocr_no_accents(self, extractor):
        section_text = _make_section_text(
            "12. Aplicacoes Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_ocr_garbled_c(self, extractor):
        section_text = _make_section_text(
            "12. Aplicagoes Financeiras e Lucros e Dividendos no Exterior 3.580,00"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_ocr_multiline_no_accents(self, extractor):
        section_text = _make_section_text(
            "12. Aplicacoes Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "3.580,00",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_nfd_inline_value(self, extractor):
        nfc_text = "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00"
        nfd_text = unicodedata.normalize("NFD", nfc_text)
        assert nfd_text != nfc_text
        normalized = unicodedata.normalize("NFC", nfd_text)
        result = extractor._extract_financial_abroad(normalized)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_nfd_multiline_value(self, extractor):
        nfc_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "3.580,00",
        )
        nfd_text = unicodedata.normalize("NFD", nfc_text)
        normalized = unicodedata.normalize("NFC", nfd_text)
        result = extractor._extract_financial_abroad(normalized)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_nfd_full_extract_with_nfc_normalization(self, extractor):
        nfc_page = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 5.000,00\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00\n"
            "TOTAL 8.580,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        nfd_page = unicodedata.normalize("NFD", nfc_page)
        normalized_page = unicodedata.normalize("NFC", nfd_page)
        context = ExtractionContext(
            full_text=normalized_page,
            pages_text={1: normalized_page},
            total_pages=1,
        )
        result = extractor.extract(context)
        assert result is not None
        assert "financial_investments_and_profits_and_dividends_abroad" in result["subsections"]
        assert result["subsections"]["financial_investments_and_profits_and_dividends_abroad"]["total_value"] == 3580.0
