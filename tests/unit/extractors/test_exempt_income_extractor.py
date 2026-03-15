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
        context = ExtractionContext(full_text=text, pages_text={1: text}, total_pages=1)
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
        context = ExtractionContext(full_text=text, pages_text={1: text}, total_pages=1)
        result = extractor.extract(context)
        if result:
            assert "exempt_portion_from_rural_activity" not in result.get("subsections", {})

    def test_exempt_income_total_includes_code_15(self, extractor, context_with_code_15):
        result = extractor.extract(context_with_code_15)
        assert result is not None
        assert result["total_value"] == 58572.01

    def test_other_subsections_unchanged_with_code_15(
        self, extractor, context_with_code_15, context_without_code_15
    ):
        result_with = extractor.extract(context_with_code_15)
        result_without = extractor.extract(context_without_code_15)
        assert result_with is not None
        assert result_without is not None
        if (
            "profits_and_dividends" in result_with["subsections"]
            and "profits_and_dividends" in result_without["subsections"]
        ):
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
        context = ExtractionContext(full_text=text, pages_text={1: text}, total_pages=1)
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
                        "items": [{"description": "Resultado", "value": 8572.01, "id": "x1"}],
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
        assert (
            result.exempt_income["subsections"]["exempt_portion_from_rural_activity"]["total_value"]
            == 8572.01
        )

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


class TestSectionMarkerDetection:
    @pytest.fixture
    def extractor(self):
        return ExemptIncomeExtractor()

    def test_rejects_marker_substring_in_criteria_line(self, extractor):
        text_page3 = (
            "2 - Recebeu rendimentos isentos, não tributáveis ou tributados "
            "exclusivamente na fonte, cuja soma foi superior a R$ 200.000,00.\n"
        )
        text_page6 = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS (Valores em Reais)\n"
            "09. Lucros e dividendos recebidos 385.000,00\n"
            "Titular 383.952.658-24 13.670.228/0001-30 ALINE DE FATIMA MARQUES LTDA 385.000,00\n"
            "TOTAL 385.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )
        context = ExtractionContext(
            full_text=text_page3 + text_page6,
            pages_text={3: text_page3, 6: text_page6},
            total_pages=6,
        )
        lines = extractor._get_section_lines(context)
        assert len(lines) > 0
        assert lines[0][0] == 6

    def test_rejects_end_marker_substring_in_other_section(self, extractor):
        text_page3 = (
            "2 - Recebeu rendimentos isentos, não tributáveis ou tributados "
            "exclusivamente na fonte, cuja soma foi superior a R$ 200.000,00.\n"
        )
        text_page4 = (
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR\n"
            "Some taxable income data\n"
        )
        text_page6 = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS (Valores em Reais)\n"
            "09. Lucros e dividendos recebidos 50.000,00\n"
            "Titular 123.456.789-00 12.345.678/0001-90 EMPRESA ABC 50.000,00\n"
            "TOTAL 50.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )
        context = ExtractionContext(
            full_text=text_page3 + text_page4 + text_page6,
            pages_text={3: text_page3, 4: text_page4, 6: text_page6},
            total_pages=6,
        )
        lines = extractor._get_section_lines(context)
        assert len(lines) > 0
        assert all(pn == 6 for pn, _ in lines)

    def test_accepts_marker_at_line_start(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos 10.000,00\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        lines = extractor._get_section_lines(context)
        assert len(lines) == 1
        assert "09." in lines[0][1]

    def test_accepts_marker_with_valores_suffix(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS (Valores em Reais)\n"
            "09. Lucros e dividendos recebidos 10.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        lines = extractor._get_section_lines(context)
        assert len(lines) == 1

    def test_full_digital_pdf_scenario(self, extractor):
        text_page3 = (
            "2 - Recebeu rendimentos isentos, não tributáveis ou tributados "
            "exclusivamente na fonte, cuja soma foi superior a R$ 200.000,00.\n"
        )
        text_page4 = (
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR\n"
            "Taxable income line 1\n"
        )
        text_page6 = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS (Valores em Reais)\n"
            "09. Lucros e dividendos recebidos 385.000,00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome da Fonte Pagadora Valor\n"
            "Titular 383.952.658-24 13.670.228/0001-30 ALINE DE FATIMA MARQUES LTDA 385.000,00\n"
            "TOTAL 385.000,00\n"
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA\n"
        )
        context = ExtractionContext(
            full_text=text_page3 + text_page4 + text_page6,
            pages_text={3: text_page3, 4: text_page4, 6: text_page6},
            total_pages=6,
        )
        result = extractor.extract(context)
        assert result is not None
        assert result["items_count"] == 1
        assert result["total_value"] == 385000.0
        subs = result["subsections"]
        assert "profits_and_dividends" in subs
        items = subs["profits_and_dividends"]["items"]
        assert len(items) == 1
        assert items[0]["value"] == 385000.0
        assert items[0]["payer_name"] == "ALINE DE FATIMA MARQUES LTDA"


class TestIsSectionHeader:
    def test_marker_at_line_start(self):
        assert ExemptIncomeExtractor._is_section_header(
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS",
            ["RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS"],
        )

    def test_marker_with_suffix(self):
        assert ExemptIncomeExtractor._is_section_header(
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS (VALORES EM REAIS)",
            ["RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS"],
        )

    def test_marker_with_numeric_prefix(self):
        assert ExemptIncomeExtractor._is_section_header(
            "3. RENDIMENTOS TRIBUTÁVEIS",
            ["RENDIMENTOS TRIBUTÁVEIS"],
        )

    def test_rejects_marker_in_sentence(self):
        assert not ExemptIncomeExtractor._is_section_header(
            "2 - RECEBEU RENDIMENTOS ISENTOS, NÃO TRIBUTÁVEIS OU TRIBUTADOS",
            ["RENDIMENTOS ISENTOS"],
        )

    def test_rejects_marker_mid_text(self):
        assert not ExemptIncomeExtractor._is_section_header(
            "CUJA SOMA DE RENDIMENTOS TRIBUTÁVEIS FOI SUPERIOR",
            ["RENDIMENTOS TRIBUTÁVEIS"],
        )

    def test_accepts_marker_with_leading_whitespace(self):
        assert ExemptIncomeExtractor._is_section_header(
            "   RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS",
            ["RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS"],
        )

    def test_short_marker_not_matched_as_substring(self):
        assert not ExemptIncomeExtractor._is_section_header(
            "RECEBEU RENDIMENTOS ISENTOS NÃO TRIBUTÁVEIS",
            ["RENDIMENTOS ISENTOS"],
        )

    def test_accepts_marker_with_dash_prefix(self):
        assert ExemptIncomeExtractor._is_section_header(
            "1 - RENDIMENTOS TRIBUTÁVEIS",
            ["RENDIMENTOS TRIBUTÁVEIS"],
        )


class TestOCRStandardItemParsing:
    @pytest.fixture
    def extractor(self):
        return ExemptIncomeExtractor()

    def test_parses_ocr_item_with_multi_space_gaps(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos                                    140.161,93\n"
            "Beneficiário            CPF          CNPJ da Fonte Pagadora         Nome da Fonte Pagadora                    Valor\n"
            "Titular           252.500.728-01       12.331.388/0001-92              EMA AGRICOLA SA                   140.161,93\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={4: text},
            total_pages=4,
        )
        result = extractor.extract(context)
        assert result is not None
        subs = result["subsections"]
        assert "profits_and_dividends" in subs
        items = subs["profits_and_dividends"]["items"]
        assert items is not None
        assert len(items) == 1
        assert items[0]["value"] == 140161.93
        assert items[0]["cpf"] == "252.500.728-01"
        assert items[0]["payer_cnpj"] == "12.331.388/0001-92"

    def test_skips_ocr_noise_artifact(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "09. Lucros e dividendos recebidos 50.000,00\n"
            "AL\n"
            "Titular 123.456.789-00 12.345.678/0001-90 EMPRESA XYZ 50.000,00\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        result = extractor.extract(context)
        subs = result["subsections"]
        assert "profits_and_dividends" in subs
        items = subs["profits_and_dividends"]["items"]
        assert len(items) == 1
        assert items[0]["value"] == 50000.0

    def test_parses_dependente_item(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "12. Rendimentos de cadernetas de poupança\n"
            "Dependente         041.228.356-58      00.000.000/2433-37     BANCO DO BRASIL MORRO AGUDO SP            1.115,02\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        result = extractor.extract(context)
        subs = result["subsections"]
        key = "savings_accounts_mortgage_lci_lca_cra_cri"
        assert key in subs
        items = subs[key]["items"]
        assert len(items) == 1
        assert items[0]["beneficiary"] == "Dependente"
        assert items[0]["cpf"] == "041.228.356-58"
        assert items[0]["value"] == 1115.02


class TestOthersSubsectionParsing:
    @pytest.fixture
    def extractor(self):
        return ExemptIncomeExtractor()

    def test_parses_others_with_name_and_description(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "99. Outros                                                    5.000,00\n"
            "Titular 123.456.789-00 71.328.769/0001-81     SICOOB COCRED      DISTRIBUICAO DE           2.500,00\n"
            "Titular 123.456.789-00 53.935.029/0001-21     CC COOCRELIVRE     DISTRIBUICAO DE           2.500,00\n"
            "TOTAL 5.000,00\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        result = extractor.extract(context)
        subs = result["subsections"]
        assert "others_99" in subs
        items = subs["others_99"]["items"]
        assert len(items) == 2
        assert items[0]["payer_cpf_cnpj"] == "71.328.769/0001-81"
        assert items[0]["payer_name"] == "SICOOB COCRED"
        assert items[0]["description"] == "DISTRIBUICAO DE"
        assert items[0]["value"] == 2500.0

    def test_merges_continuation_lines_into_payer_name(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "99. Outros                                                    2.725,70\n"
            "Titular 123.456.789-00 71.328.769/0001-81     SICOOB COCRED      DISTRIBUICAO DE           2.725,70\n"
            "COOPERATIVA DE          SOBRAS\n"
            "CREDITO\n"
            "TOTAL 2.725,70\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        result = extractor.extract(context)
        subs = result["subsections"]
        items = subs["others_99"]["items"]
        assert len(items) == 1
        assert "SICOOB COCRED" in items[0]["payer_name"]
        assert "COOPERATIVA DE" in items[0]["payer_name"]
        assert "CREDITO" in items[0]["payer_name"]
        assert items[0]["value"] == 2725.7

    def test_ignores_header_lines_as_continuation(self, extractor):
        text = (
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
            "99. Outros                                                    1.000,00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome Descrição Valor\n"
            "Pagadora\n"
            "Titular 123.456.789-00 71.328.769/0001-81     EMPRESA ABC      DESCRICAO           1.000,00\n"
            "TOTAL 1.000,00\n"
            "RENDIMENTOS TRIBUTÁVEIS\n"
        )
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=1,
        )
        result = extractor.extract(context)
        items = result["subsections"]["others_99"]["items"]
        assert len(items) == 1
        assert items[0]["payer_name"] == "EMPRESA ABC"

    def test_short_noise_lines_not_merged(self):
        assert not ExemptIncomeExtractor._is_others_continuation("AL")
        assert not ExemptIncomeExtractor._is_others_continuation("X")
        assert not ExemptIncomeExtractor._is_others_continuation("")


class TestSplitNameDescription:
    def test_splits_on_multi_space_gap(self):
        name, desc = ExemptIncomeExtractor._split_name_description(
            "SICOOB COCRED      DISTRIBUICAO DE"
        )
        assert name == "SICOOB COCRED"
        assert desc == "DISTRIBUICAO DE"

    def test_no_split_without_gap(self):
        name, desc = ExemptIncomeExtractor._split_name_description("EMPRESA ABC LTDA")
        assert name == "EMPRESA ABC LTDA"
        assert desc == ""

    def test_multiple_gaps(self):
        name, desc = ExemptIncomeExtractor._split_name_description(
            "COOPERATIVA DE      DISTRIBUICAO DE      SOBRAS"
        )
        assert name == "COOPERATIVA DE"
        assert desc == "DISTRIBUICAO DE SOBRAS"

    def test_empty_string(self):
        name, desc = ExemptIncomeExtractor._split_name_description("")
        assert name == ""
        assert desc == ""
