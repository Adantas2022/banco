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

    def test_inline_value_us_format(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00"
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_multiline_value_us_format(self, extractor):
        section_text = _make_section_text(
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
            "3,580.00",
        )
        result = extractor._extract_financial_abroad(section_text)
        assert result is not None
        assert result["total_value"] == 3580.0

    def test_full_extract_us_format(self, extractor):
        page_text = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 30,000.00\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00\n"
            "TOTAL 33,580.00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1,
        )
        result = extractor.extract(context)
        assert result is not None
        assert "financial_investments_and_profits_and_dividends_abroad" in result["subsections"]
        assert result["subsections"]["financial_investments_and_profits_and_dividends_abroad"]["total_value"] == 3580.0

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


class TestNormalizePayerName:

    def test_sa_with_spaces(self, extractor):
        assert extractor._normalize_payer_name("BANCO XYZ S / A") == "BANCO XYZ S/A"

    def test_sa_with_single_space_before_slash(self, extractor):
        assert extractor._normalize_payer_name("BANCO XYZ S /A") == "BANCO XYZ S/A"

    def test_open_paren_space(self, extractor):
        assert extractor._normalize_payer_name("FUNDO ( CREDITO)") == "FUNDO (CREDITO)"

    def test_close_paren_space(self, extractor):
        assert extractor._normalize_payer_name("FUNDO (CREDITO )") == "FUNDO (CREDITO)"

    def test_both_paren_spaces(self, extractor):
        assert extractor._normalize_payer_name("FUNDO ( CREDITO )") == "FUNDO (CREDITO)"

    def test_comma_space(self, extractor):
        assert extractor._normalize_payer_name("FUNDO XYZ , LTDA") == "FUNDO XYZ, LTDA"

    def test_combined_artifacts(self, extractor):
        result = extractor._normalize_payer_name("BANCO S / A ( FIC ) , LTDA")
        assert result == "BANCO S/A (FIC), LTDA"

    def test_no_change_clean_name(self, extractor):
        assert extractor._normalize_payer_name("ITAU UNIBANCO S/A") == "ITAU UNIBANCO S/A"


class TestCollectNameContinuation:

    def _lines(self, *args):
        return list(args)

    def test_single_continuation(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO BRADESCO",
            "PRIME S/A",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "PRIME S/A"

    def test_multiple_continuation_lines(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO",
            "BRADESCO PRIME",
            "FUNDO DE INVESTIMENTO",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "BRADESCO PRIME FUNDO DE INVESTIMENTO"

    def test_stops_at_cnpj(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "CONTINUACAO",
            "98.765.432/0001-10",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "CONTINUACAO"

    def test_stops_at_cpf(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "CONTINUACAO",
            "987.654.321-00",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "CONTINUACAO"

    def test_stops_at_titular(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "Titular 987.654.321-00",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_stops_at_subsection_marker(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "07. Rendimentos recebidos acumuladamente",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_stops_at_total(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "TOTAL 15.000,00",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_stops_at_empty_line(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "",
            "CONTINUACAO",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_skips_page_header(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "Página 3 de 21",
            "PRIME S/A",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "PRIME S/A"

    def test_skips_multiple_page_headers(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "Página 3 de 21",
            "NOME: FULANO DE TAL",
            "PRIME S/A",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "PRIME S/A"

    def test_stops_at_section_end_marker(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "PAGAMENTOS EFETUADOS",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_max_lookahead_respected(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "LINE1", "LINE2", "LINE3", "LINE4",
            "LINE5", "LINE6", "LINE7", "LINE8",
            "LINE9",
        )
        result = extractor._collect_name_continuation(lines, 0, max_lookahead=3)
        assert result == "LINE1 LINE2 LINE3"

    def test_stops_at_standalone_currency(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
            "15.000,00",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_no_continuation_at_end_of_lines(self, extractor):
        lines = self._lines(
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""


class TestConsolidateNamesByCnpj:

    def test_prefix_upgrade(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESCO", "value": 100.0},
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESCO PRIME S/A", "value": 200.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[0]["payer_name"] == "BANCO BRADESCO PRIME S/A"
        assert items[1]["payer_name"] == "BANCO BRADESCO PRIME S/A"

    def test_no_change_different_cnpjs(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO A", "value": 100.0},
            {"payer_cnpj": "98.765.432/0001-10", "payer_name": "BANCO B", "value": 200.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[0]["payer_name"] == "BANCO A"
        assert items[1]["payer_name"] == "BANCO B"

    def test_one_char_diff_frequency(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESCO", "value": 100.0},
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESCO", "value": 200.0},
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESBO", "value": 300.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[2]["payer_name"] == "BANCO BRADESCO"

    def test_one_char_diff_same_frequency_uses_first_seen(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESCO", "value": 100.0},
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESBO", "value": 200.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[0]["payer_name"] == "BANCO BRADESCO"
        assert items[1]["payer_name"] == "BANCO BRADESCO"

    def test_no_merge_short_names(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO A", "value": 100.0},
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO B", "value": 200.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[0]["payer_name"] == "BANCO A"
        assert items[1]["payer_name"] == "BANCO B"

    def test_no_merge_multiple_char_diffs(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO BRADESCO SA", "value": 100.0},
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO ITAU CORP", "value": 200.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[0]["payer_name"] == "BANCO BRADESCO SA"
        assert items[1]["payer_name"] == "BANCO ITAU CORP"

    def test_empty_items(self, extractor):
        items = []
        result = extractor._consolidate_names_by_cnpj(items)
        assert result == []

    def test_items_without_cnpj_unchanged(self, extractor):
        items = [
            {"payer_cnpj": "", "payer_name": "BANCO A", "value": 100.0},
            {"payer_cnpj": "", "payer_name": "BANCO B", "value": 200.0},
        ]
        extractor._consolidate_names_by_cnpj(items)
        assert items[0]["payer_name"] == "BANCO A"
        assert items[1]["payer_name"] == "BANCO B"

    def test_returns_items_list(self, extractor):
        items = [
            {"payer_cnpj": "12.345.678/0001-90", "payer_name": "BANCO X", "value": 100.0},
        ]
        result = extractor._consolidate_names_by_cnpj(items)
        assert result is items
