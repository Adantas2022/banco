"""Unit tests for ExclusiveIncomeExtractor LLM integration (US-19159).

Tests the new LLM extraction methods (extract_with_llm, _normalize_llm_item)
without requiring actual Azure OpenAI connectivity. Mirrors the
test_rural_properties_llm.py pattern.

CPF/CNPJ values used here come from the gitleaks allowlist (dev dummies);
no real PII appears in this file.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.exclusive_income import (
    ExclusiveIncomeExtractor,
)

CPF_A = "111.111.111-11"
CPF_B = "222.222.222-22"
CNPJ_A = "11.111.111/0001-11"
CNPJ_B = "22.222.222/0001-22"


@pytest.fixture
def extractor() -> ExclusiveIncomeExtractor:
    return ExclusiveIncomeExtractor()


@pytest.fixture
def context() -> ExtractionContext:
    page_text = (
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA\n"
        "01. 13o salário\n"
        f"Titular {CPF_A} {CNPJ_A} ACME LTDA 5.000,00\n"
        "TOTAL 5.000,00\n"
    )
    return ExtractionContext(
        full_text=page_text,
        pages_text={4: page_text},
        total_pages=10,
        pdf_path="/tmp/test.pdf",
        document_id="test_doc_exclusive",
    )


class TestParseLLMCurrency:
    def test_none_returns_zero(self, extractor):
        assert extractor._parse_llm_currency(None) == 0.0

    def test_empty_string_returns_zero(self, extractor):
        assert extractor._parse_llm_currency("") == 0.0

    def test_number_passthrough(self, extractor):
        assert extractor._parse_llm_currency(5000.0) == 5000.0
        assert extractor._parse_llm_currency(0) == 0.0

    def test_br_format_string(self, extractor):
        assert extractor._parse_llm_currency("5.000,00") == 5000.0

    def test_us_format_string(self, extractor):
        assert extractor._parse_llm_currency("5000.50") == 5000.5


class TestNormalizeLLMItem:
    """_normalize_llm_item routes by subsection_key into the correct schema."""

    def test_thirteenth_salary_default_schema(self, extractor):
        raw = {
            "subsection_key": "thirteenth_salary",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "ACME LTDA",
            "value": 5000.0,
            "page": 4,
        }
        key, item = extractor._normalize_llm_item(raw)
        assert key == "thirteenth_salary"
        assert item["beneficiary"] == "Titular"
        assert item["payer_cpf_cnpj"] == CNPJ_A
        assert item["value"] == 5000.0
        assert item["thirteenth_salary"] == 0.0
        assert "id" in item

    def test_financial_income_subsection(self, extractor):
        raw = {
            "subsection_key": "income_from_financial_investments",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_B,
            "payer_name": "BANCO Y",
            "value": 1234.56,
            "page": 5,
        }
        key, item = extractor._normalize_llm_item(raw)
        assert key == "income_from_financial_investments"
        assert item["payer_cpf_cnpj"] == CNPJ_B
        assert item["value"] == 1234.56
        assert "thirteenth_salary" not in item

    def test_interest_on_capital_subsection(self, extractor):
        raw = {
            "subsection_key": "interest_on_own_capital",
            "beneficiary": "Titular",
            "cpf": CPF_B,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "EMPRESA X",
            "value": 800.0,
            "page": 6,
        }
        key, item = extractor._normalize_llm_item(raw)
        assert key == "interest_on_own_capital"
        assert item["value"] == 800.0
        assert item["payer_name"] == "EMPRESA X"

    def test_financial_abroad_subsection(self, extractor):
        raw = {
            "subsection_key": "financial_investments_and_profits_and_dividends_abroad",
            "description": "Aplicação no exterior — fundo de investimento",
            "value": 2500.0,
            "page": 7,
        }
        key, item = extractor._normalize_llm_item(raw)
        assert key == "financial_investments_and_profits_and_dividends_abroad"
        assert item["description"] == "Aplicação no exterior — fundo de investimento"
        assert item["value"] == 2500.0
        assert "id" in item

    def test_others_subsection_with_description(self, extractor):
        raw = {
            "subsection_key": "others",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "FONTE W",
            "description": "Indenização espontânea",
            "value": 350.0,
            "page": 8,
        }
        key, item = extractor._normalize_llm_item(raw)
        assert key == "others"
        assert item["description"] == "Indenização espontânea"
        assert item["payer_name"] == "FONTE W"

    def test_invalid_subsection_key_rejected(self, extractor):
        raw = {
            "subsection_key": "made_up_section",
            "value": 100,
            "page": 1,
        }
        key, item = extractor._normalize_llm_item(raw)
        assert key == ""
        assert item == {}

    def test_missing_subsection_key_rejected(self, extractor):
        key, item = extractor._normalize_llm_item({})
        assert key == ""
        assert item == {}

    def test_id_generated_consistently(self, extractor):
        raw = {
            "subsection_key": "thirteenth_salary",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "TEST",
            "value": 100.0,
            "page": 1,
        }
        _, r1 = extractor._normalize_llm_item(raw)
        _, r2 = extractor._normalize_llm_item(raw)
        assert r1["id"] == r2["id"]

    def test_string_value_parsed_br(self, extractor):
        raw = {
            "subsection_key": "thirteenth_salary",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "TEST",
            "value": "12.345,67",
            "page": 1,
        }
        _, item = extractor._normalize_llm_item(raw)
        assert item["value"] == 12345.67


class TestExtractWithLLM:
    """extract_with_llm orchestration with mocked get_llm_extraction_data."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_chunks(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await extractor.extract_with_llm(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_empty_items(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [{"items": [], "subsection_totals": {}}]
            result = await extractor.extract_with_llm(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_single_chunk_single_subsection(self, extractor, context):
        chunk = {
            "items": [
                {
                    "subsection_key": "thirteenth_salary",
                    "beneficiary": "Titular",
                    "cpf": CPF_A,
                    "payer_cpf_cnpj": CNPJ_A,
                    "payer_name": "ACME LTDA",
                    "value": 5000.0,
                    "page": 4,
                }
            ],
            "subsection_totals": {"thirteenth_salary": 5000.0},
            "total_value": 5000.0,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["section_name"] == "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva"
        assert result["extraction_method"] == "llm"
        assert result["total_value"] == 5000.0
        assert "thirteenth_salary" in result["subsections"]

    @pytest.mark.asyncio
    async def test_multi_chunk_multi_subsection(self, extractor, context):
        chunk1 = {
            "items": [
                {
                    "subsection_key": "thirteenth_salary",
                    "beneficiary": "Titular",
                    "cpf": CPF_A,
                    "payer_cpf_cnpj": CNPJ_A,
                    "payer_name": "EMPRESA X",
                    "value": 5000.0,
                    "page": 4,
                }
            ],
            "subsection_totals": {
                "thirteenth_salary": 5000.0,
                "income_from_financial_investments": 1234.56,
            },
            "total_value": 6234.56,
        }
        chunk2 = {
            "items": [
                {
                    "subsection_key": "income_from_financial_investments",
                    "beneficiary": "Titular",
                    "cpf": CPF_A,
                    "payer_cpf_cnpj": CNPJ_B,
                    "payer_name": "BANCO Y",
                    "value": 1234.56,
                    "page": 5,
                }
            ],
            "subsection_totals": {},
            "total_value": 0,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk1, chunk2]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["total_value"] == 6234.56
        assert set(result["subsections"].keys()) == {
            "thirteenth_salary",
            "income_from_financial_investments",
        }

    @pytest.mark.asyncio
    async def test_duplicate_id_deduped(self, extractor, context):
        item = {
            "subsection_key": "thirteenth_salary",
            "beneficiary": "Titular",
            "cpf": CPF_B,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "DUP",
            "value": 100.0,
            "page": 1,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [
                {
                    "items": [item],
                    "subsection_totals": {"thirteenth_salary": 100.0},
                    "total_value": 100.0,
                },
                {"items": [item], "subsection_totals": {}, "total_value": 0},
            ]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert len(result["subsections"]["thirteenth_salary"]["items"]) == 1

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("Azure connection failed")
            result = await extractor.extract_with_llm(context)
        assert result is None


class TestLLMExtractionEnabled:
    """Settings toggle for exclusive_taxation_income LLM path."""

    def test_property_reads_from_settings_true(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_exclusive_taxation_income = True
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is True

    def test_property_defaults_false(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_exclusive_taxation_income = False
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is False
