"""Unit tests for ExemptIncomeExtractor LLM integration (US-19157).

Tests the new LLM extraction methods (extract_with_llm, _normalize_llm_item)
without requiring actual Azure OpenAI connectivity. Mirrors the
test_rural_properties_llm.py pattern.

CPF/CNPJ values used here come from the gitleaks allowlist (dev dummies);
no real PII appears in this file.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.exempt_income import (
    ExemptIncomeExtractor,
)

# Dev-dummy identifiers (allowlisted in .claude/config/gitleaks.toml).
CPF_A = "111.111.111-11"
CPF_B = "222.222.222-22"
CPF_NULL = "000.000.000-00"
CNPJ_A = "11.111.111/0001-11"
CNPJ_B = "22.222.222/0001-22"


@pytest.fixture
def extractor() -> ExemptIncomeExtractor:
    return ExemptIncomeExtractor()


@pytest.fixture
def context() -> ExtractionContext:
    page_text = (
        "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS\n"
        "01. Bolsas de estudo e de pesquisa\n"
        f"Titular {CPF_A} {CNPJ_A} ACME LTDA 1.500,00\n"
        "TOTAL 1.500,00\n"
    )
    return ExtractionContext(
        full_text=page_text,
        pages_text={3: page_text},
        total_pages=12,
        pdf_path="/tmp/test.pdf",
        document_id="test_doc_exempt",
    )


class TestParseLLMCurrency:
    """parse_llm_currency must accept BR/US strings, numbers, None, empties."""

    def test_none_returns_zero(self, extractor):
        assert extractor._parse_llm_currency(None) == 0.0

    def test_empty_string_returns_zero(self, extractor):
        assert extractor._parse_llm_currency("") == 0.0

    def test_number_passthrough(self, extractor):
        assert extractor._parse_llm_currency(1500.5) == 1500.5
        assert extractor._parse_llm_currency(0) == 0.0

    def test_br_format_string(self, extractor):
        assert extractor._parse_llm_currency("1.500,00") == 1500.0

    def test_us_format_string(self, extractor):
        assert extractor._parse_llm_currency("1500.50") == 1500.5


class TestNormalizeLLMItem:
    """_normalize_llm_item routes by subsection_code into the correct schema."""

    def test_default_standard_format(self, extractor):
        raw = {
            "subsection_code": "01",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "ACME LTDA",
            "value": 1500.0,
            "page": 3,
        }
        code, item = extractor._normalize_llm_item(raw)
        assert code == "01"
        assert item["beneficiary"] == "Titular"
        assert item["payer_cnpj"] == CNPJ_A
        assert item["payer_name"] == "ACME LTDA"
        assert item["value"] == 1500.0
        assert item["page"] == 3
        assert "id" in item

    def test_subsection_04_termination_no_beneficiary(self, extractor):
        raw = {
            "subsection_code": "04",
            "cpf": CPF_B,
            "payer_cpf_cnpj": CNPJ_B,
            "payer_name": "EMPRESA Y",
            "value": 50000.0,
            "page": 2,
        }
        code, item = extractor._normalize_llm_item(raw)
        assert code == "04"
        assert "beneficiary" not in item
        assert item["payer_cpf_cnpj"] == CNPJ_B
        assert item["value"] == 50000.0
        assert "id" in item

    def test_subsection_10_retirement_thirteenth_salary(self, extractor):
        raw = {
            "subsection_code": "10",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "INSS",
            "value": 24000.0,
            "thirteenth_salary": 2000.0,
            "page": 4,
        }
        code, item = extractor._normalize_llm_item(raw)
        assert code == "10"
        assert item["payer_cnpj"] == CNPJ_A
        assert item["thirteenth_salary"] == 2000.0
        assert item["value"] == 24000.0

    def test_subsection_11_illness_five_numeric_fields(self, extractor):
        raw = {
            "subsection_code": "11",
            "beneficiary": "Dependente",
            "cpf": CPF_B,
            "payer_cpf_cnpj": CNPJ_B,
            "payer_name": "BANCO Z",
            "value": 12000.0,
            "income": 12000.0,
            "irrf": 800.0,
            "thirteenth_salary": 1000.0,
            "irrf_on_thirteenth_salary": 80.0,
            "official_social_security_contribution": 200.0,
            "page": 5,
        }
        code, item = extractor._normalize_llm_item(raw)
        assert code == "11"
        assert item["income"] == 12000.0
        assert item["irrf"] == 800.0
        assert item["thirteenth_salary"] == 1000.0
        assert item["irrf_on_thirteenth_salary"] == 80.0
        assert item["official_social_security_contribution"] == 200.0
        assert item["payer_cpf_cnpj"] == CNPJ_B

    def test_subsection_99_others_with_description(self, extractor):
        raw = {
            "subsection_code": "99",
            "beneficiary": "Titular",
            "cpf": CPF_NULL,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "FONTE W",
            "description": "Restituição IRPF",
            "value": 350.0,
            "page": 6,
        }
        code, item = extractor._normalize_llm_item(raw)
        assert code == "99"
        assert item["description"] == "Restituição IRPF"
        assert item["payer_cpf_cnpj"] == CNPJ_A
        assert item["value"] == 350.0

    def test_missing_fields_use_defaults(self, extractor):
        code, item = extractor._normalize_llm_item({})
        assert code == ""
        assert item == {}

    def test_id_generated_consistently(self, extractor):
        raw = {
            "subsection_code": "01",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_B,
            "payer_name": "TEST",
            "value": 100.0,
            "page": 1,
        }
        _, r1 = extractor._normalize_llm_item(raw)
        _, r2 = extractor._normalize_llm_item(raw)
        assert r1["id"] == r2["id"]

    def test_string_value_parsed_br(self, extractor):
        raw = {
            "subsection_code": "01",
            "beneficiary": "Titular",
            "cpf": CPF_A,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "TEST",
            "value": "2.500,75",
            "page": 1,
        }
        _, item = extractor._normalize_llm_item(raw)
        assert item["value"] == 2500.75


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
                    "subsection_code": "01",
                    "beneficiary": "Titular",
                    "cpf": CPF_A,
                    "payer_cpf_cnpj": CNPJ_A,
                    "payer_name": "ACME LTDA",
                    "value": 1500.0,
                    "page": 3,
                }
            ],
            "subsection_totals": {"01": 1500.0},
            "total_value": 1500.0,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["section_name"] == "Rendimentos Isentos e Não Tributáveis"
        assert result["extraction_method"] == "llm"
        assert result["total_value"] == 1500.0
        assert result["items_count"] == 1
        assert "scholarships_and_grants_without_donor_compensation" in result["subsections"]
        sub = result["subsections"]["scholarships_and_grants_without_donor_compensation"]
        assert sub["code"] == "01"
        assert sub["total_value"] == 1500.0
        assert len(sub["items"]) == 1

    @pytest.mark.asyncio
    async def test_multi_chunk_multi_subsection(self, extractor, context):
        chunk1 = {
            "items": [
                {
                    "subsection_code": "01",
                    "beneficiary": "Titular",
                    "cpf": CPF_A,
                    "payer_cpf_cnpj": CNPJ_B,
                    "payer_name": "BOLSA X",
                    "value": 5000.0,
                    "page": 3,
                }
            ],
            "subsection_totals": {"01": 5000.0, "10": 24000.0},
            "total_value": 29000.0,
        }
        chunk2 = {
            "items": [
                {
                    "subsection_code": "10",
                    "beneficiary": "Titular",
                    "cpf": CPF_A,
                    "payer_cpf_cnpj": CNPJ_A,
                    "payer_name": "INSS",
                    "value": 24000.0,
                    "thirteenth_salary": 2000.0,
                    "page": 4,
                }
            ],
            "subsection_totals": {},
            "total_value": 0,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk1, chunk2]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["items_count"] == 2
        # Total honours the LLM-reported PDF total from chunk1
        assert result["total_value"] == 29000.0
        codes = {s["code"] for s in result["subsections"].values()}
        assert codes == {"01", "10"}

    @pytest.mark.asyncio
    async def test_duplicate_id_deduped(self, extractor, context):
        item = {
            "subsection_code": "01",
            "beneficiary": "Titular",
            "cpf": CPF_B,
            "payer_cpf_cnpj": CNPJ_A,
            "payer_name": "DUP",
            "value": 100.0,
            "page": 1,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [
                {"items": [item], "subsection_totals": {"01": 100.0}, "total_value": 100.0},
                {"items": [item], "subsection_totals": {}, "total_value": 0},
            ]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["items_count"] == 1

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("Azure connection failed")
            result = await extractor.extract_with_llm(context)
        assert result is None


class TestLLMExtractionEnabled:
    """Settings toggle for exempt_income LLM path."""

    def test_property_reads_from_settings_true(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_exempt_income = True
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is True

    def test_property_defaults_false(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_exempt_income = False
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is False
