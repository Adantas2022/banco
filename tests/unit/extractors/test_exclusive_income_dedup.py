"""Tests for deduplication key behavior in ExclusiveIncomeExtractor and ExemptIncomeExtractor.

Validates that items with identical (CNPJ, CPF, value) on DIFFERENT pages are kept,
while items with identical (CNPJ, CPF, value) on the SAME page are deduplicated.

Issue: #82491 — declaration 0258 drops 17 financial investment items due to
cross-page dedup key collision.
"""

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.exclusive_income import (
    ExclusiveIncomeExtractor,
)
from irpf_processor.infrastructure.extraction.extractors.exempt_income import (
    ExemptIncomeExtractor,
)


@pytest.fixture
def exclusive_extractor():
    return ExclusiveIncomeExtractor()


@pytest.fixture
def exempt_extractor():
    return ExemptIncomeExtractor()


def _make_context(pages_text: dict[int, str]) -> ExtractionContext:
    full_text = "\n".join(pages_text[k] for k in sorted(pages_text))
    return ExtractionContext(
        full_text=full_text,
        pages_text=pages_text,
        total_pages=max(pages_text.keys()),
    )


class TestFinancialIncomeDedup:

    def test_cross_page_items_with_same_cnpj_cpf_value_are_not_deduplicated(
        self, exclusive_extractor
    ):
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "06. Rendimentos de aplicações financeiras\n"
            "Beneficiário CPF CNPJ Fonte Pagadora Valor\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 38.204,65\n"
        )
        page6 = (
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 38.204,65\n"
            "TOTAL 76.409,30\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5, 6: page6})
        result = exclusive_extractor.extract(context)

        assert result is not None
        financial = result["subsections"].get("income_from_financial_investments")
        assert financial is not None
        assert len(financial["items"]) == 2
        assert financial["total_value"] == pytest.approx(76409.30, abs=0.01)

    def test_same_page_items_with_same_cnpj_cpf_value_are_preserved(
        self, exclusive_extractor
    ):
        """Bug #88514: legitimate duplicate items (same CNPJ/CPF/value/page)
        must be preserved — they represent distinct entries in the declaration."""
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "06. Rendimentos de aplicações financeiras\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 38.204,65\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 38.204,65\n"
            "TOTAL 76.409,30\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        financial = result["subsections"].get("income_from_financial_investments")
        assert financial is not None
        assert len(financial["items"]) == 2

    def test_items_with_same_cnpj_different_values_always_kept(
        self, exclusive_extractor
    ):
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "06. Rendimentos de aplicações financeiras\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 38.204,65\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 12.500,00\n"
            "TOTAL 50.704,65\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        financial = result["subsections"].get("income_from_financial_investments")
        assert financial is not None
        assert len(financial["items"]) == 2
        values = sorted(i["value"] for i in financial["items"])
        assert values == pytest.approx([12500.0, 38204.65], abs=0.01)

    def test_financial_income_subsection_dedup_with_page(
        self, exclusive_extractor
    ):
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "06. Rendimentos de aplicações financeiras\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 1.000,00\n"
            "Titular 169.407.738-19 11.222.333/0001-81 BRADESCO FI RF 2.000,00\n"
        )
        page6 = (
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 1.000,00\n"
            "Titular 169.407.738-19 33.444.555/0001-66 CAIXA FI RF 3.000,00\n"
            "TOTAL 7.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5, 6: page6})
        result = exclusive_extractor.extract(context)

        assert result is not None
        financial = result["subsections"].get("income_from_financial_investments")
        assert financial is not None
        assert len(financial["items"]) == 4
        assert financial["total_value"] == pytest.approx(7000.0, abs=0.01)


class TestProfitSharingDedup:

    def test_plr_cross_page_not_deduplicated(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "11. Participação nos lucros ou resultados\n"
            "Titular 169.407.738-19 40.498.539/0001-37 EMPRESA ABC SA 5.000,00\n"
        )
        page6 = (
            "Titular 169.407.738-19 40.498.539/0001-37 EMPRESA ABC SA 5.000,00\n"
            "TOTAL 10.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5, 6: page6})
        result = exclusive_extractor.extract(context)

        assert result is not None
        plr = result["subsections"].get("profit_or_results_sharing")
        assert plr is not None
        assert len(plr["items"]) == 2


class TestInterestOnCapitalDedup:

    def test_interest_cross_page_not_deduplicated(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "10. Juros sobre capital próprio\n"
            "Titular 169.407.738-19 40.498.539/0001-37 EMPRESA ABC SA 5.000,00\n"
        )
        page6 = (
            "Titular 169.407.738-19 40.498.539/0001-37 EMPRESA ABC SA 5.000,00\n"
            "TOTAL 10.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5, 6: page6})
        result = exclusive_extractor.extract(context)

        assert result is not None
        interest = result["subsections"].get("interest_on_own_capital")
        assert interest is not None
        assert len(interest["items"]) == 2


class TestExemptIncomeStandardSubsectionDedup:

    def test_exempt_income_standard_subsection_cross_page_dedup(
        self, exempt_extractor
    ):
        page3 = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU HOLDING SA 10.000,00\n"
        )
        page4 = (
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU HOLDING SA 10.000,00\n"
            "TOTAL 20.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO\n"
        )
        context = _make_context({3: page3, 4: page4})
        result = exempt_extractor.extract(context)

        assert result is not None
        dividends = result["subsections"].get("profits_and_dividends")
        assert dividends is not None
        assert len(dividends["items"]) == 2
        assert dividends["total_value"] == pytest.approx(20000.0, abs=0.01)


class TestDocumentAISplitHeader:

    def test_split_header_across_lines(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS À\n"
            "TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 5.000,00\n"
            "TOTAL 5.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        assert result["subsections"]["thirteenth_salary"]["total_value"] == 5000.0

    def test_split_header_with_unaccented_variant(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS A\n"
            "TRIBUTACAO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 8.000,00\n"
            "TOTAL 8.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        assert result["subsections"]["thirteenth_salary"]["total_value"] == 8000.0

    def test_split_header_with_garbled_c_variant(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS A\n"
            "TRIBUTAGAO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 3.000,00\n"
            "TOTAL 3.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        assert result["subsections"]["thirteenth_salary"]["total_value"] == 3000.0

    def test_split_header_no_false_positive_from_description(self, exclusive_extractor):
        page5 = (
            "09. Lucros e dividendos recebidos\n"
            "Titular 169.407.738-19 51.572.102/0001-12 FINANCEIRA XYZ TRIBUTAÇÃO EXCLUSIVA 11.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is None

    def test_single_line_header_still_works(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 10.000,00\n"
            "TOTAL 10.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        assert result["subsections"]["thirteenth_salary"]["total_value"] == 10000.0

    def test_split_header_with_single_space_items(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS À\n"
            "TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "06. Rendimentos de aplicações financeiras\n"
            "Titular 169.407.738-19 40.498.539/0001-37 ITAU OPTIMUS RF LP FIC 38.204,65\n"
            "TOTAL 38.204,65\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is not None
        financial = result["subsections"].get("income_from_financial_investments")
        assert financial is not None
        assert len(financial["items"]) == 1
        assert financial["total_value"] == pytest.approx(38204.65, abs=0.01)

    def test_split_header_pending_resets_between_lines(self, exclusive_extractor):
        page5 = (
            "RENDIMENTOS SUJEITOS À\n"
            "SOME UNRELATED LINE\n"
            "TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
            "01. 13º salário 5.000,00\n"
            "PAGAMENTOS EFETUADOS\n"
        )
        context = _make_context({5: page5})
        result = exclusive_extractor.extract(context)

        assert result is None
