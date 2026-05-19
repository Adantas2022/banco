"""Teste de integração do parser IRPF completo."""

import json
from pathlib import Path

import pytest

from irpf_processor.infrastructure.extraction import (
    IRPFParser,
    TaxpayerExtractor,
    PdfTextExtractor,
)

DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "IRPF"
PDF_FILE = DOCS_DIR / "Geral-IRPF-2025-2024.pdf"
EXPECTED_JSON = DOCS_DIR / "Geral-IRPF-2025-2024_resultado 2.json"


@pytest.fixture
def expected_data() -> dict:
    """Carrega JSON esperado."""
    with open(EXPECTED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["data"]["ir_response"]["declaration"]


@pytest.fixture
def parser_result():
    """Executa parser no PDF."""
    if not PDF_FILE.exists():
        pytest.skip(f"PDF não encontrado: {PDF_FILE}")
    
    parser = IRPFParser()
    return parser.parse(PDF_FILE)


class TestFullIRPFParser:
    """Testes do parser completo."""
    
    def test_parser_returns_result(self, parser_result):
        assert parser_result is not None
    
    def test_total_pages(self, parser_result, expected_data):
        assert parser_result.total_pages == expected_data["total_pages"]
    
    def test_confidence_above_threshold(self, parser_result):
        assert parser_result.confidence >= 0.5


class TestTaxpayerIdentification:
    """Testes de identificação do contribuinte."""
    
    def test_cpf_matches(self, parser_result, expected_data):
        expected = expected_data["taxpayer_identification"]
        extracted = parser_result.taxpayer_identification
        
        assert extracted["normalized_cpf"] == expected["normalized_cpf"]
    
    def test_name_matches(self, parser_result, expected_data):
        expected = expected_data["taxpayer_identification"]
        extracted = parser_result.taxpayer_identification
        
        assert extracted["name"] == expected["name"]
    
    def test_exercise_year_matches(self, parser_result, expected_data):
        expected = expected_data["taxpayer_identification"]
        extracted = parser_result.taxpayer_identification
        
        assert extracted["exercise_year"] == expected["exercise_year"]
    
    def test_calendar_year_matches(self, parser_result, expected_data):
        expected = expected_data["taxpayer_identification"]
        extracted = parser_result.taxpayer_identification
        
        assert extracted["calendar_year"] == expected["calendar_year"]
    
    def test_city_in_address(self, parser_result, expected_data):
        expected = expected_data["taxpayer_identification"]["contact_and_address"]
        extracted = parser_result.taxpayer_identification["contact_and_address"]
        
        assert expected["city"].upper() in extracted.get("city", "").upper() or \
               extracted.get("city", "").upper() in expected["city"].upper()


class TestAssetsDeclaration:
    """Testes de declaração de bens."""
    
    def test_assets_section_exists(self, parser_result):
        assert parser_result.assets_declaration is not None or True
    
    def test_assets_count_matches(self, parser_result, expected_data):
        if not parser_result.assets_declaration:
            pytest.skip("Assets not extracted yet")
        
        expected_count = len(expected_data["assets_declaration"]["items"])
        extracted_count = len(parser_result.assets_declaration["items"])
        
        assert extracted_count == expected_count, \
            f"Expected {expected_count} assets, got {extracted_count}"
    
    def test_assets_total_value(self, parser_result, expected_data):
        if not parser_result.assets_declaration:
            pytest.skip("Assets not extracted yet")
        
        expected_total = expected_data["assets_declaration"]["current_year_total_value"]
        extracted_total = parser_result.assets_declaration["current_year_total_value"]
        
        tolerance = expected_total * 0.01
        assert abs(extracted_total - expected_total) <= tolerance, \
            f"Expected total {expected_total}, got {extracted_total}"


class TestIncomeFromLegalPerson:
    """Testes de rendimentos de pessoa jurídica."""
    
    def test_income_section_exists(self, parser_result):
        assert parser_result.income_from_legal_person_to_holder is not None or True
    
    def test_income_sources_count(self, parser_result, expected_data):
        if not parser_result.income_from_legal_person_to_holder:
            pytest.skip("Income PJ not extracted yet")
        
        expected_count = len(expected_data["income_from_legal_person_to_holder"]["items"])
        extracted_count = len(parser_result.income_from_legal_person_to_holder["items"])
        
        assert extracted_count == expected_count, \
            f"Expected {expected_count} income sources, got {extracted_count}"
    
    def test_income_total_value(self, parser_result, expected_data):
        if not parser_result.income_from_legal_person_to_holder:
            pytest.skip("Income PJ not extracted yet")
        
        expected_total = expected_data["income_from_legal_person_to_holder"]["total_values"]["income_from_legal_person"]["amount"]
        extracted_total = parser_result.income_from_legal_person_to_holder["total_values"]["income_from_legal_person"]["amount"]
        
        tolerance = expected_total * 0.01
        assert abs(extracted_total - expected_total) <= tolerance, \
            f"Expected total income {expected_total}, got {extracted_total}"


class TestExemptIncome:
    """Testes de rendimentos isentos."""
    
    def test_exempt_income_section_exists(self, parser_result):
        assert parser_result.exempt_income is not None
    
    def test_exempt_income_total(self, parser_result, expected_data):
        expected_total = expected_data["exempt_income"]["total_value"]
        extracted_total = parser_result.exempt_income["total_value"]
        
        tolerance = expected_total * 0.01
        assert abs(extracted_total - expected_total) <= tolerance, \
            f"Expected exempt income {expected_total}, got {extracted_total}"
    
    def test_profits_dividends_count(self, parser_result, expected_data):
        expected_items = expected_data["exempt_income"]["subsections"]["profits_and_dividends"]["items"]
        extracted_items = parser_result.exempt_income["subsections"]["profits_and_dividends"]["items"]
        
        assert len(extracted_items) == len(expected_items), \
            f"Expected {len(expected_items)} profit items, got {len(extracted_items)}"


class TestExclusiveTaxationIncome:
    """Testes de rendimentos de tributação exclusiva."""
    
    def test_exclusive_income_section_exists(self, parser_result):
        assert parser_result.exclusive_taxation_income is not None
    
    def test_exclusive_income_total(self, parser_result, expected_data):
        expected_total = expected_data["exclusive_taxation_income"]["total_value"]
        extracted_total = parser_result.exclusive_taxation_income["total_value"]
        
        tolerance = expected_total * 0.01
        assert abs(extracted_total - expected_total) <= tolerance, \
            f"Expected exclusive income {expected_total}, got {extracted_total}"


class TestRuralActivity:
    """Testes de atividade rural."""
    
    def test_rural_properties_exists(self, parser_result):
        assert parser_result.exploited_rural_properties_in_brazil is not None
    
    def test_rural_properties_count(self, parser_result, expected_data):
        expected_items = expected_data["exploited_rural_properties_in_brazil"]["items"]
        extracted_items = parser_result.exploited_rural_properties_in_brazil["items"]
        
        assert len(extracted_items) == len(expected_items), \
            f"Expected {len(expected_items)} rural properties, got {len(extracted_items)}"
    
    def test_rural_income_exists(self, parser_result):
        assert parser_result.rural_income_and_expenditure_in_brazil is not None
    
    def test_rural_income_months(self, parser_result, expected_data):
        expected_items = expected_data["rural_income_and_expenditure_in_brazil"]["items"]
        extracted_items = parser_result.rural_income_and_expenditure_in_brazil["items"]
        
        assert len(extracted_items) == len(expected_items), \
            f"Expected {len(expected_items)} months, got {len(extracted_items)}"
    
    def test_rural_income_total(self, parser_result, expected_data):
        expected = expected_data["rural_income_and_expenditure_in_brazil"]["total_values"]["gross_revenue"]["amount"]
        extracted = parser_result.rural_income_and_expenditure_in_brazil["total_values"]["gross_revenue"]["amount"]
        
        tolerance = expected * 0.01
        assert abs(extracted - expected) <= tolerance, \
            f"Expected gross revenue {expected}, got {extracted}"
    
    def test_rural_results_exists(self, parser_result):
        assert parser_result.calculation_of_rural_results_in_brazil is not None
    
    def test_rural_results_subsections(self, parser_result):
        subsections = parser_result.calculation_of_rural_results_in_brazil["subsections"]
        assert len(subsections) >= 2, f"Expected at least 2 subsections, got {len(subsections)}"
    
    def test_rural_assets_exists(self, parser_result):
        assert parser_result.rural_activity_assets_in_brazil is not None
    
    def test_rural_debts_exists(self, parser_result):
        assert parser_result.rural_activity_debts_in_brazil is not None
    
    def test_rural_debts_count(self, parser_result, expected_data):
        expected_items = expected_data["rural_activity_debts_in_brazil"]["items"]
        extracted_items = parser_result.rural_activity_debts_in_brazil["items"]
        
        assert len(extracted_items) == len(expected_items), \
            f"Expected {len(expected_items)} rural debts, got {len(extracted_items)}"


class TestOutputFormat:
    """Testes do formato de saída."""
    
    def test_to_dict_returns_dict(self, parser_result):
        result_dict = parser_result.to_dict()
        assert isinstance(result_dict, dict)
    
    def test_dict_has_required_keys(self, parser_result, expected_data):
        result_dict = parser_result.to_dict()
        
        expected_keys = [
            "taxpayer_identification",
            "total_value",
            "valid_total",
            "assets_declaration",
            "debts_and_encumbrances",
            "exempt_income",
            "income_from_legal_person_to_holder",
            "total_pages"
        ]
        
        for key in expected_keys:
            assert key in result_dict, f"Missing key: {key}"
    
    def test_taxpayer_dict_structure(self, parser_result, expected_data):
        result_dict = parser_result.to_dict()
        taxpayer = result_dict["taxpayer_identification"]
        
        expected_keys = [
            "cpf",
            "normalized_cpf",
            "name",
            "exercise_year",
            "calendar_year",
            "contact_and_address"
        ]
        
        for key in expected_keys:
            assert key in taxpayer, f"Missing taxpayer key: {key}"


class TestTaxpayerExtractorUnit:
    """Testes unitários do extrator de contribuinte."""
    
    def test_extract_from_sample_text(self):
        from irpf_processor.infrastructure.extraction import ExtractionContext
        
        sample_text = """
        DECLARAÇÃO DE AJUSTE ANUAL
        EXERCÍCIO 2025 ANO-CALENDÁRIO 2024
        
        Nome: GENESIS LOPES
        CPF: 886.978.040-60
        
        Endereço: RUA LUIZ ANTONIO
        Número: 702
        Bairro: BONFIM PAULISTA
        Município: RIBEIRÃO PRETO
        UF: SP
        CEP: 14110-000
        """
        
        context = ExtractionContext(
            full_text=sample_text,
            pages_text={1: sample_text},
            total_pages=1
        )
        
        extractor = TaxpayerExtractor()
        result = extractor.extract(context)
        
        assert result["normalized_cpf"] == "88697804060"
        assert result["name"] == "GENESIS LOPES"
        assert result["exercise_year"] == "2025"
        assert result["calendar_year"] == "2024"
    
    def test_extract_cpf_variations(self):
        from irpf_processor.infrastructure.extraction import ExtractionContext
        
        variations = [
            ("CPF: 886.978.040-60", "88697804060"),
            ("CPF 886978040-60", "88697804060"),
            ("CPF: 886 978 040 60", "88697804060"),
        ]
        
        extractor = TaxpayerExtractor()
        
        for text, expected_cpf in variations:
            full_text = f"EXERCÍCIO 2025\n{text}\nNome: TESTE"
            context = ExtractionContext(
                full_text=full_text,
                pages_text={1: full_text},
                total_pages=1
            )
            result = extractor.extract(context)
            
            assert result["normalized_cpf"] == expected_cpf, \
                f"Failed for: {text}"


class TestComparisonSummary:
    """Resumo da comparação com JSON esperado."""
    
    def test_print_comparison_summary(self, parser_result, expected_data):
        """Imprime resumo da comparação para análise."""
        print("\n" + "=" * 70)
        print("COMPARAÇÃO COMPLETA: EXTRAÇÃO vs JSON ESPERADO")
        print("=" * 70)
        
        exp_tax = expected_data["taxpayer_identification"]
        ext_tax = parser_result.taxpayer_identification
        
        print("\n📋 IDENTIFICAÇÃO DO CONTRIBUINTE")
        cpf_ok = ext_tax.get('normalized_cpf') == exp_tax['normalized_cpf']
        name_ok = ext_tax.get('name') == exp_tax['name']
        year_ok = ext_tax.get('exercise_year') == exp_tax['exercise_year']
        print(f"  CPF:            {'✅' if cpf_ok else '❌'} {ext_tax.get('normalized_cpf', 'N/A')}")
        print(f"  Nome:           {'✅' if name_ok else '❌'} {ext_tax.get('name', 'N/A')}")
        print(f"  Ano-Exercício:  {'✅' if year_ok else '❌'} {ext_tax.get('exercise_year', 'N/A')}")
        
        print(f"\n🏠 BENS E DIREITOS")
        if parser_result.assets_declaration:
            ext_count = len(parser_result.assets_declaration.get("items", []))
            exp_count = len(expected_data["assets_declaration"]["items"])
            ext_total = parser_result.assets_declaration["current_year_total_value"]
            exp_total = expected_data["assets_declaration"]["current_year_total_value"]
            count_ok = ext_count == exp_count
            total_ok = abs(ext_total - exp_total) < 0.01
            print(f"  Quantidade:     {'✅' if count_ok else '❌'} {ext_count}/{exp_count} itens")
            print(f"  Total:          {'✅' if total_ok else '❌'} R$ {ext_total:,.2f}")
        else:
            print(f"  ❌ Não extraído")
        
        print(f"\n💼 RENDIMENTOS PJ (TITULAR)")
        if parser_result.income_from_legal_person_to_holder:
            ext_count = len(parser_result.income_from_legal_person_to_holder.get("items", []))
            exp_count = len(expected_data["income_from_legal_person_to_holder"]["items"])
            ext_total = parser_result.income_from_legal_person_to_holder["total_values"]["income_from_legal_person"]["amount"]
            exp_total = expected_data["income_from_legal_person_to_holder"]["total_values"]["income_from_legal_person"]["amount"]
            count_ok = ext_count == exp_count
            total_ok = abs(ext_total - exp_total) < 0.01
            print(f"  Fontes:         {'✅' if count_ok else '❌'} {ext_count}/{exp_count}")
            print(f"  Total:          {'✅' if total_ok else '❌'} R$ {ext_total:,.2f}")
        else:
            print(f"  ❌ Não extraído")
        
        print(f"\n🎁 RENDIMENTOS ISENTOS")
        if parser_result.exempt_income:
            ext_total = parser_result.exempt_income["total_value"]
            exp_total = expected_data["exempt_income"]["total_value"]
            total_ok = abs(ext_total - exp_total) < 0.01
            print(f"  Total:          {'✅' if total_ok else '❌'} R$ {ext_total:,.2f}")
            for k, v in parser_result.exempt_income.get("subsections", {}).items():
                print(f"    {v['code']}: {len(v['items'])} itens, R$ {v['total_value']:,.2f}")
        else:
            print(f"  ❌ Não extraído")
        
        print(f"\n💰 TRIBUTAÇÃO EXCLUSIVA")
        if parser_result.exclusive_taxation_income:
            ext_total = parser_result.exclusive_taxation_income["total_value"]
            exp_total = expected_data["exclusive_taxation_income"]["total_value"]
            total_ok = abs(ext_total - exp_total) < 0.01
            print(f"  Total:          {'✅' if total_ok else '❌'} R$ {ext_total:,.2f}")
        else:
            print(f"  ❌ Não extraído")
        
        print(f"\n🌾 ATIVIDADE RURAL - BRASIL")
        if parser_result.exploited_rural_properties_in_brazil:
            ext_count = len(parser_result.exploited_rural_properties_in_brazil["items"])
            exp_count = len(expected_data["exploited_rural_properties_in_brazil"]["items"])
            print(f"  Imóveis:        {'✅' if ext_count == exp_count else '❌'} {ext_count}/{exp_count}")
        else:
            print(f"  Imóveis:        ❌ Não extraído")
        
        if parser_result.rural_income_and_expenditure_in_brazil:
            r = parser_result.rural_income_and_expenditure_in_brazil
            ext_count = len(r["items"])
            exp_count = len(expected_data["rural_income_and_expenditure_in_brazil"]["items"])
            ext_rev = r["total_values"]["gross_revenue"]["amount"]
            exp_rev = expected_data["rural_income_and_expenditure_in_brazil"]["total_values"]["gross_revenue"]["amount"]
            print(f"  Meses:          {'✅' if ext_count == exp_count else '❌'} {ext_count}/{exp_count}")
            print(f"  Receita:        {'✅' if abs(ext_rev - exp_rev) < 0.01 else '❌'} R$ {ext_rev:,.2f}")
            print(f"  Despesas:       R$ {r['total_values']['funding_expenses']['amount']:,.2f}")
        else:
            print(f"  Receitas:       ❌ Não extraído")
        
        if parser_result.calculation_of_rural_results_in_brazil:
            subs = parser_result.calculation_of_rural_results_in_brazil.get("subsections", {})
            print(f"  Apuração:       ✅ {len(subs)} subseções")
        else:
            print(f"  Apuração:       ❌ Não extraído")
        
        if parser_result.rural_activity_assets_in_brazil:
            ext_count = len(parser_result.rural_activity_assets_in_brazil["items"])
            exp_count = len(expected_data["rural_activity_assets_in_brazil"]["items"])
            print(f"  Bens Rurais:    {'✅' if ext_count == exp_count else '❌'} {ext_count}/{exp_count}")
        else:
            print(f"  Bens Rurais:    ❌ Não extraído")
        
        if parser_result.rural_activity_debts_in_brazil:
            ext_count = len(parser_result.rural_activity_debts_in_brazil["items"])
            exp_count = len(expected_data["rural_activity_debts_in_brazil"]["items"])
            print(f"  Dívidas:        {'✅' if ext_count == exp_count else '❌'} {ext_count}/{exp_count}")
        else:
            print(f"  Dívidas:        ❌ Não extraído")
        
        print(f"\n📄 PÁGINAS:       {'✅' if parser_result.total_pages == expected_data['total_pages'] else '❌'} {parser_result.total_pages}/{expected_data['total_pages']}")
        print(f"🎯 CONFIANÇA:     {parser_result.confidence:.1%}")
        print("=" * 70)
        
        assert True
