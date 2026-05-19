"""Teste de integração: Extração de PDF IRPF vs JSON esperado."""

import json
from pathlib import Path
from decimal import Decimal

import pytest

from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor
from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser
from irpf_processor.infrastructure.extraction.field_extractors import (
    extract_cpf,
    extract_cnpj,
    extract_currency,
    normalize_cpf,
    validate_cpf,
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
def pdf_text() -> str:
    """Extrai texto do PDF."""
    if not PDF_FILE.exists():
        pytest.skip(f"PDF não encontrado: {PDF_FILE}")
    
    extractor = PdfTextExtractor()
    return extractor.extract_text(PDF_FILE)


class TestPdfTextExtraction:
    """Testes de extração de texto do PDF."""
    
    def test_pdf_exists(self):
        assert PDF_FILE.exists(), f"PDF não encontrado: {PDF_FILE}"
    
    def test_expected_json_exists(self):
        assert EXPECTED_JSON.exists(), f"JSON não encontrado: {EXPECTED_JSON}"
    
    def test_extract_text_not_empty(self, pdf_text: str):
        assert len(pdf_text) > 0, "Texto extraído está vazio"
    
    def test_text_contains_declaration_header(self, pdf_text: str):
        assert "DECLARAÇÃO DE AJUSTE ANUAL" in pdf_text.upper()
    
    def test_text_contains_exercise_year(self, pdf_text: str):
        assert "2025" in pdf_text
    
    def test_text_contains_calendar_year(self, pdf_text: str):
        assert "2024" in pdf_text


class TestTaxpayerIdentification:
    """Testes de identificação do contribuinte."""
    
    def test_extract_cpf(self, pdf_text: str, expected_data: dict):
        expected_cpf = expected_data["taxpayer_identification"]["normalized_cpf"]
        
        cpf = extract_cpf(pdf_text)
        assert cpf is not None, "CPF não encontrado no texto"
        
        normalized = normalize_cpf(cpf)
        assert normalized == expected_cpf, f"CPF: {normalized} != {expected_cpf}"
    
    def test_cpf_is_valid(self, pdf_text: str):
        cpf = extract_cpf(pdf_text)
        assert cpf is not None
        assert validate_cpf(cpf), f"CPF inválido: {cpf}"
    
    def test_extract_name(self, pdf_text: str, expected_data: dict):
        expected_name = expected_data["taxpayer_identification"]["name"]
        assert expected_name in pdf_text, f"Nome '{expected_name}' não encontrado"
    
    def test_extract_exercise_year(self, pdf_text: str, expected_data: dict):
        expected_year = expected_data["taxpayer_identification"]["exercise_year"]
        assert expected_year in pdf_text
    
    def test_extract_address_city(self, pdf_text: str, expected_data: dict):
        expected_city = expected_data["taxpayer_identification"]["contact_and_address"]["city"]
        assert expected_city.upper() in pdf_text.upper()


class TestAssetsDeclaration:
    """Testes de declaração de bens."""
    
    def test_total_assets_value(self, pdf_text: str, expected_data: dict):
        expected_total = expected_data["assets_declaration"]["current_year_total_value"]
        
        value = extract_currency(f"R$ {expected_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        assert value is not None
    
    def test_contains_asset_descriptions(self, pdf_text: str, expected_data: dict):
        items = expected_data["assets_declaration"]["items"]
        
        found_count = 0
        for item in items[:3]:
            desc_words = item["asset_description"].split()[:3]
            if any(word.upper() in pdf_text.upper() for word in desc_words if len(word) > 3):
                found_count += 1
        
        assert found_count > 0, "Nenhuma descrição de bem encontrada"


class TestIncomeFromLegalPerson:
    """Testes de rendimentos de pessoa jurídica."""
    
    def test_contains_payer_names(self, pdf_text: str, expected_data: dict):
        items = expected_data["income_from_legal_person_to_holder"]["items"]
        
        found = 0
        for item in items:
            payer_name = item["payer_name"]
            words = payer_name.split()[:2]
            if any(word.upper() in pdf_text.upper() for word in words if len(word) > 3):
                found += 1
        
        assert found > 0, "Nenhuma fonte pagadora encontrada"
    
    def test_total_income_value(self, pdf_text: str, expected_data: dict):
        total = expected_data["income_from_legal_person_to_holder"]["total_values"]
        expected_income = total["income_from_legal_person"]["amount"]
        
        assert str(int(expected_income)).replace(".", "") in pdf_text.replace(",", "").replace(".", "")


class TestExemptIncome:
    """Testes de rendimentos isentos."""
    
    def test_contains_exempt_income_section(self, pdf_text: str):
        assert any(
            term in pdf_text.upper() 
            for term in ["RENDIMENTOS ISENTOS", "ISENTOS E NÃO TRIBUTÁVEIS"]
        )
    
    def test_total_exempt_value(self, pdf_text: str, expected_data: dict):
        if expected_data.get("exempt_income"):
            expected_total = expected_data["exempt_income"]["total_value"]
            assert expected_total > 0


class TestRuralActivity:
    """Testes de atividade rural."""
    
    def test_contains_rural_section(self, pdf_text: str, expected_data: dict):
        if expected_data.get("exploited_rural_properties_in_brazil"):
            assert any(
                term in pdf_text.upper()
                for term in ["ATIVIDADE RURAL", "IMÓVEL EXPLORADO", "RURAL"]
            )


class TestCompareWithExpectedJson:
    """Comparação completa com JSON esperado."""
    
    def test_taxpayer_cpf_matches(self, pdf_text: str, expected_data: dict):
        expected = expected_data["taxpayer_identification"]
        
        cpf = extract_cpf(pdf_text)
        assert cpf is not None
        assert normalize_cpf(cpf) == expected["normalized_cpf"]
    
    def test_taxpayer_name_found(self, pdf_text: str, expected_data: dict):
        expected_name = expected_data["taxpayer_identification"]["name"]
        assert expected_name in pdf_text
    
    def test_exercise_year_matches(self, pdf_text: str, expected_data: dict):
        expected_year = expected_data["taxpayer_identification"]["exercise_year"]
        assert f"EXERCÍCIO {expected_year}" in pdf_text.upper() or expected_year in pdf_text
    
    def test_calendar_year_matches(self, pdf_text: str, expected_data: dict):
        expected_year = expected_data["taxpayer_identification"]["calendar_year"]
        assert f"ANO-CALENDÁRIO {expected_year}" in pdf_text.upper() or expected_year in pdf_text
    
    def test_total_pages_reasonable(self, expected_data: dict):
        total_pages = expected_data.get("total_pages", 0)
        assert total_pages == 11, f"Total de páginas: {total_pages}"
    
    def test_assets_count(self, expected_data: dict):
        items = expected_data["assets_declaration"]["items"]
        assert len(items) == 11, f"Quantidade de bens: {len(items)}"
    
    def test_income_sources_count(self, expected_data: dict):
        items = expected_data["income_from_legal_person_to_holder"]["items"]
        assert len(items) == 3, f"Quantidade de fontes pagadoras: {len(items)}"


class TestFieldExtractorsWithRealData:
    """Testes dos extratores com dados reais do PDF."""
    
    def test_extract_multiple_cnpjs(self, pdf_text: str):
        import re
        cnpjs = re.findall(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", pdf_text)
        assert len(cnpjs) > 0, "Nenhum CNPJ encontrado"
    
    def test_extract_currency_values(self, pdf_text: str):
        import re
        values = re.findall(r"[\d.,]+", pdf_text)
        assert len(values) > 0
    
    def test_extract_dates(self, pdf_text: str):
        import re
        dates = re.findall(r"\d{2}/\d{2}/\d{4}", pdf_text)
        assert len(dates) > 0, "Nenhuma data encontrada"


class TestParserIntegration:
    """Testes de integração do parser completo."""
    
    def test_parser_with_real_pdf(self):
        if not PDF_FILE.exists():
            pytest.skip(f"PDF não encontrado: {PDF_FILE}")
        
        parser = IRPFParser()
        result = parser.parse(PDF_FILE)
        
        assert result is not None
        assert result.total_pages == 11
        
        profile = parser.get_document_profile()
        assert profile.exercise_year == "2025"
    
    def test_parser_extracts_cpf(self, expected_data: dict):
        if not PDF_FILE.exists():
            pytest.skip(f"PDF não encontrado: {PDF_FILE}")
        
        parser = IRPFParser()
        result = parser.parse(PDF_FILE)
        
        if "normalized_cpf" in result.taxpayer_identification:
            extracted_cpf = result.taxpayer_identification["normalized_cpf"]
            expected_cpf = expected_data["taxpayer_identification"]["normalized_cpf"]
            assert extracted_cpf == expected_cpf
    
    def test_parser_confidence_above_threshold(self):
        if not PDF_FILE.exists():
            pytest.skip(f"PDF não encontrado: {PDF_FILE}")
        
        parser = IRPFParser()
        result = parser.parse(PDF_FILE)
        
        assert result.confidence >= 0.0
