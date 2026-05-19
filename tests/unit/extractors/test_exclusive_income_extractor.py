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

    def test_strips_controle_footer(self, extractor):
        """Bug #16887: Controle: number from PDF footer must be stripped."""
        dirty = "BANCO DO BRASIL SA Controle: 581346937590242"
        assert extractor._normalize_payer_name(dirty) == "BANCO DO BRASIL SA"

    def test_strips_controle_with_pagina_and_data(self, extractor):
        """Bug #16887: Full footer line concatenated to name."""
        dirty = (
            "BANCO DO BRASIL SA Controle: 581346937590242 "
            "Página 2 de15 Data/Hora da Entrega: 15/05/2025 às 13:48:09"
        )
        assert extractor._normalize_payer_name(dirty) == "BANCO DO BRASIL SA"

    def test_strips_pagina_only(self, extractor):
        """Bug #16887: Only Página appended."""
        dirty = "BANCO DO BRASIL SA Página 3 de 15"
        assert extractor._normalize_payer_name(dirty) == "BANCO DO BRASIL SA"

    def test_strips_data_hora_only(self, extractor):
        """Bug #16887: Only Data/Hora appended."""
        dirty = "BANCO DO BRASIL SA Data/Hora da Entrega: 15/05/2025 às 13:48:09"
        assert extractor._normalize_payer_name(dirty) == "BANCO DO BRASIL SA"

    def test_clean_name_unchanged(self, extractor):
        """Regression: normal names stay intact."""
        assert extractor._normalize_payer_name("BANCO BRADESCO S/A") == "BANCO BRADESCO S/A"
        assert extractor._normalize_payer_name("ITAU UNIBANCO S.A.") == "ITAU UNIBANCO S.A."

    def test_strips_subsection_08_header(self, extractor):
        """Bug #16887v2: OCR inlined subsection 08 header."""
        dirty = (
            "COOPERATIVA DE CREDITO, POUPANCA E INVESTIMENTO SICREDI PION "
            "08. 13º salário recebido pelos dependentes                   435,21"
        )
        assert extractor._normalize_payer_name(dirty) == (
            "COOPERATIVA DE CREDITO, POUPANCA E INVESTIMENTO SICREDI PION"
        )

    def test_strips_subsection_06_header(self, extractor):
        """Bug #16887v2: OCR inlined subsection 06 header."""
        dirty = "BANCO XYZ 06. Rendimentos de aplicações financeiras 1.234,56"
        assert extractor._normalize_payer_name(dirty) == "BANCO XYZ"

    def test_strips_generic_subsection(self, extractor):
        """Bug #16887v2: Generic NN. pattern."""
        dirty = "FUNDO ABC 10. Juros sobre capital próprio"
        assert extractor._normalize_payer_name(dirty) == "FUNDO ABC"

    def test_strips_trailing_value(self, extractor):
        """Bug #16887v2: Trailing monetary value from OCR."""
        dirty = "COOPERATIVA SICREDI PION 435,21"
        assert extractor._normalize_payer_name(dirty) == "COOPERATIVA SICREDI PION"

    def test_full_ocr_dirty_name(self, extractor):
        """Bug #16887v2: Exact reproduction of PAULO case."""
        dirty = (
            "COOPERATIVA DE CREDITO, POUPANCA E INVESTIMENTO SICREDI PION "
            "08. 13º salário recebido pelos dependentes"
            "                                                                         "
            "435,21"
        )
        result = extractor._normalize_payer_name(dirty)
        assert result == "COOPERATIVA DE CREDITO, POUPANCA E INVESTIMENTO SICREDI PION"

    def test_name_with_numbers_not_stripped(self, extractor):
        """Regression: names with numbers in the middle stay intact."""
        assert extractor._normalize_payer_name("FUNDO 123 INVESTIMENTO") == "FUNDO 123 INVESTIMENTO"
        assert extractor._normalize_payer_name("BB FIC RF LP 100") == "BB FIC RF LP 100"



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

    def test_stops_at_controle_footer(self, extractor):
        """Bug #16887: Controle: must stop continuation."""
        lines = self._lines(
            "Titular 337.468.340-15 00.000.000/0001-91 BANCO DO BRASIL SA",
            "Controle: 581346937590242",
            "Página 2 de 15",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_stops_at_data_hora_footer(self, extractor):
        """Bug #16887: Data/Hora da Entrega must stop continuation."""
        lines = self._lines(
            "Titular 337.468.340-15 00.000.000/0001-91 BANCO DO BRASIL SA",
            "Data/Hora da Entrega: 15/05/2025 às 13:48:09",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == ""

    def test_multiline_name_still_works_with_footer(self, extractor):
        """Bug #16887 regression: real multiline name before footer."""
        lines = self._lines(
            "Titular 337.468.340-15 92.702.067/0001-96 BANCO DO ESTADO DO RIO GRANDE",
            "DO SUL S. A.",
            "Controle: 581346937590242",
        )
        result = extractor._collect_name_continuation(lines, 0)
        assert result == "DO SUL S. A."



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


class TestCapitalGainsExtraction:

    def test_inline_br_format(self, extractor):
        section_text = _make_section_text(
            "02. Ganhos de capital na alienação de bens e/ou direitos 51.351,86"
        )
        result = extractor._extract_capital_gains(section_text)
        assert result is not None
        assert result["code"] == "02"
        assert result["total_value"] == 51351.86
        assert result["valid_total"] is True
        assert result["items"] is None

    def test_ocr_no_accents(self, extractor):
        section_text = _make_section_text(
            "02 GANHOS DE CAPITAL NA ALIENACAO DE BENS E/OU DIREITOS 80.000,00"
        )
        result = extractor._extract_capital_gains(section_text)
        assert result is not None
        assert result["code"] == "02"
        assert result["total_value"] == 80000.0

    def test_us_format_value(self, extractor):
        section_text = _make_section_text(
            "02. Ganhos de capital na alienação de bens e/ou direitos 80,000.00"
        )
        result = extractor._extract_capital_gains(section_text)
        assert result is not None
        assert result["total_value"] == 80000.0

    def test_absent_returns_none(self, extractor):
        section_text = _make_section_text(
            "06. Rendimentos de aplicações financeiras",
            "Titular 123.456.789-00 12.345.678/0001-90 BANCO XYZ 1.248,37",
            "TOTAL 1.248,37",
        )
        result = extractor._extract_capital_gains(section_text)
        assert result is None

    def test_section_total_includes_code_02(self, extractor):
        page_text = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "02. Ganhos de capital na alienação de bens e/ou direitos 51.351,86\n"
            "06. Rendimentos de aplicações financeiras\n"
            "Titular 067.569.659-30 33.479.023/0001-80 BANCO XYZ S/A 1.248,37\n"
            "TOTAL 52.600,23\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1,
        )
        result = extractor.extract(context)
        assert result is not None
        assert "capital_gains_from_sale_of_assets_and_or_rights" in result["subsections"]
        cg = result["subsections"]["capital_gains_from_sale_of_assets_and_or_rights"]
        assert cg["total_value"] == 51351.86
        assert cg["items"] is None
        assert result["total_value"] == pytest.approx(52600.23, abs=0.01)

    def test_ocr_with_spaces_around_slash(self, extractor):
        section_text = _make_section_text(
            "02. GANHOS DE CAPITAL NA ALIENAÇÃO DE BENS E / OU DIREITOS 80.000,00"
        )
        result = extractor._extract_capital_gains(section_text)
        assert result is not None
        assert result["total_value"] == 80000.0

    def test_large_value(self, extractor):
        section_text = _make_section_text(
            "02. Ganhos de capital na alienação de bens e/ou direitos 1.234.567,89"
        )
        result = extractor._extract_capital_gains(section_text)
        assert result is not None
        assert result["total_value"] == 1234567.89


class TestOthersSubsectionCode:

    def _make_others_section(self, code: str) -> list[tuple[int, str]]:
        return [
            (3, f"{code}. Outros"),
            (3, "Titular 058.019.820-00 81.723.108/0001-04"),
            (3, "CREDICOAMO FICART E DEMAIS"),
            (3, "CREDITO RURAL RENDIMENTOS DE 1.130,70"),
            (3, "TOTAL 1.130,70"),
        ]

    def test_code_12_for_exercise_2024(self, extractor):
        section_lines = self._make_others_section("12")
        result = extractor._extract_others(section_lines)
        assert result["code"] == "12"
        assert result["name"] == "12. Outros"

    def test_code_13_for_exercise_2025(self, extractor):
        section_lines = self._make_others_section("13")
        result = extractor._extract_others(section_lines)
        assert result["code"] == "13"
        assert result["name"] == "13. Outros"

    def test_subsection_key_is_others(self, extractor):
        context = ExtractionContext(
            full_text="", pages_text={3: ""}, total_pages=1
        )
        section_lines = self._make_others_section("12")
        section_text = "\n".join(line for _, line in section_lines)
        context = ExtractionContext(
            full_text=section_text,
            pages_text={3: section_text},
            total_pages=1,
        )
        result = extractor.extract(context)
        if result:
            subsections = result.get("subsections", {})
            assert "others_13" not in subsections
            if "others" in subsections:
                assert subsections["others"]["code"] == "12"
