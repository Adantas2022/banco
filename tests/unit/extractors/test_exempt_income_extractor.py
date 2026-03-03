"""Testes unitarios para ExemptIncomeExtractor — codigo 15."""

import pytest
from irpf_processor.infrastructure.extraction.extractors import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.exempt_income import (
    ExemptIncomeExtractor,
)
from irpf_processor.infrastructure.extraction.irpf_parser import (
    IRPFDeclarationResult,
    IRPFParser,
)


class TestExemptIncomeCode15:

    @pytest.fixture
    def extractor(self):
        return ExemptIncomeExtractor()

    @pytest.fixture
    def text_with_code_15(self):
        return (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos 50.000,00\n"
            "Titular 123.456.789-00 12.345.678/0001-90 EMPRESA XYZ 50.000,00\n"
            "15. Parcela não tributável correspondente à atividade rural 8.572,01\n"
            "TOTAL 58.572,01\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )

    @pytest.fixture
    def text_without_code_15(self):
        return (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos 50.000,00\n"
            "Titular 123.456.789-00 12.345.678/0001-90 EMPRESA XYZ 50.000,00\n"
            "TOTAL 50.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )

    @pytest.fixture
    def context_with_code_15(self, text_with_code_15):
        return ExtractionContext(
            full_text=text_with_code_15,
            pages_text={1: text_with_code_15},
            total_pages=1,
        )

    @pytest.fixture
    def context_without_code_15(self, text_without_code_15):
        return ExtractionContext(
            full_text=text_without_code_15,
            pages_text={1: text_without_code_15},
            total_pages=1,
        )

    def test_code_15_extracted_from_pdf_text(self, extractor, context_with_code_15):
        result = extractor.extract(context_with_code_15)
        assert result is not None
        subsections = result["subsections"]
        assert "exempt_portion_from_rural_activity" in subsections
        assert subsections["exempt_portion_from_rural_activity"]["total_value"] == 8572.01

    def test_code_15_has_correct_metadata(self, extractor, context_with_code_15):
        result = extractor.extract(context_with_code_15)
        code_15 = result["subsections"]["exempt_portion_from_rural_activity"]
        assert code_15["code"] == "15"
        assert code_15["valid_total"] is True
        assert code_15["items"] is None

    def test_code_15_absent_when_not_in_text(self, extractor, context_without_code_15):
        result = extractor.extract(context_without_code_15)
        assert result is not None
        assert "exempt_portion_from_rural_activity" not in result["subsections"]

    def test_code_15_value_on_next_line(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "15. Parcela não tributável correspondente à atividade rural\n"
            "8.572,01\n"
            "TOTAL 8.572,01\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )
        context = ExtractionContext(
            full_text=text, pages_text={1: text}, total_pages=1
        )
        result = extractor.extract(context)
        assert result is not None
        assert "exempt_portion_from_rural_activity" in result["subsections"]
        assert result["subsections"]["exempt_portion_from_rural_activity"]["total_value"] == 8572.01

    def test_code_15_zero_value_not_included(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "15. Parcela não tributável correspondente à atividade rural 0,00\n"
            "TOTAL 0,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )
        context = ExtractionContext(
            full_text=text, pages_text={1: text}, total_pages=1
        )
        result = extractor.extract(context)
        if result:
            assert "exempt_portion_from_rural_activity" not in result.get("subsections", {})

    def test_exempt_income_total_includes_code_15(self, extractor, context_with_code_15):
        result = extractor.extract(context_with_code_15)
        assert result is not None
        assert result["total_value"] == 58572.01

    def test_other_subsections_unchanged_with_code_15(self, extractor, context_with_code_15, context_without_code_15):
        result_with = extractor.extract(context_with_code_15)
        result_without = extractor.extract(context_without_code_15)
        assert result_with is not None
        assert result_without is not None
        if "profits_and_dividends" in result_with["subsections"] and "profits_and_dividends" in result_without["subsections"]:
            assert (
                result_with["subsections"]["profits_and_dividends"]["total_value"]
                == result_without["subsections"]["profits_and_dividends"]["total_value"]
            )

    def test_code_15_does_not_appear_when_no_rural_activity(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos 30.000,00\n"
            "Titular 111.222.333-44 99.888.777/0001-66 EMPRESA ABC 30.000,00\n"
            "TOTAL 30.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )
        context = ExtractionContext(
            full_text=text, pages_text={1: text}, total_pages=1
        )
        result = extractor.extract(context)
        assert result is not None
        assert "exempt_portion_from_rural_activity" not in result["subsections"]


class TestRuralExemptFallback:

    def _make_result(self, exempt_income=None, rural_results=None):
        result = IRPFDeclarationResult(total_pages=1)
        result.exempt_income = exempt_income
        result.calculation_of_rural_results_in_brazil = rural_results
        return result

    def _make_parser(self):
        return IRPFParser.__new__(IRPFParser)

    def test_fallback_propagates_rural_value(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income={
                "section_name": "Rendimentos Isentos e Não Tributáveis",
                "total_value": 50000.0,
                "valid_total": True,
                "subsections": {
                    "profits_and_dividends": {
                        "name": "09. Lucros e dividendos",
                        "code": "09",
                        "total_value": 50000.0,
                        "valid_total": True,
                        "items": [],
                    }
                },
            },
            rural_results={
                "section_name": "Apuração do Resultado - Brasil",
                "subsections": {
                    "calculation_of_exempt_result": {
                        "subsection_name": "APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL",
                        "items": [
                            {"description": "Resultado", "value": 8572.01, "id": "x1"}
                        ],
                        "page": 15,
                    }
                },
            },
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        code_15 = result.exempt_income["subsections"]["exempt_portion_from_rural_activity"]
        assert code_15["total_value"] == 8572.01
        assert code_15["code"] == "15"
        assert code_15["valid_total"] is True
        assert code_15["items"] is None

    def test_no_fallback_when_code_15_already_extracted(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income={
                "total_value": 58572.01,
                "subsections": {
                    "exempt_portion_from_rural_activity": {
                        "name": "15. Parcela",
                        "code": "15",
                        "total_value": 8572.01,
                        "valid_total": True,
                        "items": None,
                    }
                },
            },
            rural_results={
                "subsections": {
                    "calculation_of_exempt_result": {
                        "items": [{"description": "Resultado", "value": 99999.99}],
                    }
                },
            },
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        assert result.exempt_income["subsections"]["exempt_portion_from_rural_activity"]["total_value"] == 8572.01

    def test_no_fallback_when_rural_results_absent(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income={
                "total_value": 50000.0,
                "subsections": {},
            },
            rural_results=None,
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        assert "exempt_portion_from_rural_activity" not in result.exempt_income["subsections"]

    def test_no_fallback_when_exempt_income_absent(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income=None,
            rural_results={
                "subsections": {
                    "calculation_of_exempt_result": {
                        "items": [{"description": "Resultado", "value": 8572.01}],
                    }
                },
            },
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        assert result.exempt_income is None

    def test_fallback_recalculates_total(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income={
                "total_value": 50000.0,
                "subsections": {
                    "profits_and_dividends": {
                        "code": "09",
                        "total_value": 50000.0,
                        "valid_total": True,
                        "items": [],
                    }
                },
            },
            rural_results={
                "subsections": {
                    "calculation_of_exempt_result": {
                        "items": [{"description": "Resultado", "value": 8572.01}],
                    }
                },
            },
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        assert result.exempt_income["total_value"] == 58572.01

    def test_no_fallback_when_rural_value_zero(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income={
                "total_value": 50000.0,
                "subsections": {},
            },
            rural_results={
                "subsections": {
                    "calculation_of_exempt_result": {
                        "items": [{"description": "Resultado", "value": 0.0}],
                    }
                },
            },
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        assert "exempt_portion_from_rural_activity" not in result.exempt_income["subsections"]

    def test_no_fallback_when_rural_value_negative(self):
        parser = self._make_parser()
        result = self._make_result(
            exempt_income={
                "total_value": 50000.0,
                "subsections": {},
            },
            rural_results={
                "subsections": {
                    "calculation_of_exempt_result": {
                        "items": [{"description": "Resultado", "value": -500.0}],
                    }
                },
            },
        )
        parser._propagate_rural_exempt_to_exempt_income(result)
        assert "exempt_portion_from_rural_activity" not in result.exempt_income["subsections"]
