"""Unit tests for DebtsExtractor LLM integration (US-19158).

Tests the new LLM extraction methods (extract_with_llm, _normalize_llm_item)
without requiring actual Azure OpenAI connectivity. Mirrors the
test_rural_properties_llm.py pattern.

CPF/CNPJ values used here come from the gitleaks allowlist (dev dummies);
no real PII appears in this file.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.debts import DebtsExtractor


@pytest.fixture
def extractor() -> DebtsExtractor:
    return DebtsExtractor()


@pytest.fixture
def context() -> ExtractionContext:
    page_text = (
        "DÍVIDAS E ÔNUS REAIS\n"
        "11 EMPRESTIMO BANCO X 50.000,00 30.000,00 0,00\n"
        "TOTAL 50.000,00 30.000,00 0,00\n"
    )
    return ExtractionContext(
        full_text=page_text,
        pages_text={5: page_text},
        total_pages=8,
        pdf_path="/tmp/test.pdf",
        document_id="test_doc_debts",
    )


class TestParseLLMCurrency:
    def test_none_returns_zero(self, extractor):
        assert extractor._parse_llm_currency(None) == 0.0

    def test_empty_string_returns_zero(self, extractor):
        assert extractor._parse_llm_currency("") == 0.0

    def test_number_passthrough(self, extractor):
        assert extractor._parse_llm_currency(50000.0) == 50000.0
        assert extractor._parse_llm_currency(0) == 0.0

    def test_br_format_string(self, extractor):
        assert extractor._parse_llm_currency("50.000,00") == 50000.0

    def test_us_format_string(self, extractor):
        assert extractor._parse_llm_currency("50000.00") == 50000.0


class TestNormalizeLLMItem:
    """_normalize_llm_item validates code + description and parses values."""

    def test_valid_item_normalized(self, extractor):
        raw = {
            "debt_code": "11",
            "debt_description": "EMPRESTIMO BANCO X",
            "year_before_last_value": 50000.0,
            "last_year_value": 30000.0,
            "current_year_value": 0,
            "page": 5,
        }
        item = extractor._normalize_llm_item(raw)
        assert item is not None
        assert item["debt_code"] == "11"
        assert item["debt_description"] == "EMPRESTIMO BANCO X"
        assert item["year_before_last_value"] == 50000.0
        assert item["last_year_value"] == 30000.0
        assert item["current_year_value"] == 0.0
        assert item["page"] == 5
        assert "id" in item

    def test_invalid_code_rejected(self, extractor):
        raw = {
            "debt_code": "99",
            "debt_description": "FAKE",
            "year_before_last_value": 1,
            "last_year_value": 1,
            "current_year_value": 1,
            "page": 1,
        }
        assert extractor._normalize_llm_item(raw) is None

    def test_empty_description_rejected(self, extractor):
        raw = {
            "debt_code": "11",
            "debt_description": "",
            "year_before_last_value": 1,
            "last_year_value": 1,
            "current_year_value": 1,
            "page": 1,
        }
        assert extractor._normalize_llm_item(raw) is None

    def test_string_code_padded(self, extractor):
        raw = {
            "debt_code": "1",
            "debt_description": "TEST",
            "year_before_last_value": 0,
            "last_year_value": 0,
            "current_year_value": 0,
            "page": 1,
        }
        # "01" not in VALID_DEBT_CODES — must reject
        assert extractor._normalize_llm_item(raw) is None

    def test_string_value_parsed_br(self, extractor):
        raw = {
            "debt_code": "12",
            "debt_description": "FINANCIAMENTO",
            "year_before_last_value": "1.234.567,89",
            "last_year_value": "987.654,32",
            "current_year_value": "0,00",
            "page": 2,
        }
        item = extractor._normalize_llm_item(raw)
        assert item is not None
        assert item["year_before_last_value"] == 1234567.89
        assert item["last_year_value"] == 987654.32
        assert item["current_year_value"] == 0.0

    def test_id_generated_consistently(self, extractor):
        raw = {
            "debt_code": "13",
            "debt_description": "BANCO Y",
            "year_before_last_value": 100,
            "last_year_value": 50,
            "current_year_value": 0,
            "page": 3,
        }
        r1 = extractor._normalize_llm_item(raw)
        r2 = extractor._normalize_llm_item(raw)
        assert r1["id"] == r2["id"]

    def test_non_dict_rejected(self, extractor):
        assert extractor._normalize_llm_item(None) is None
        assert extractor._normalize_llm_item("not a dict") is None


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
            mock.return_value = [{"items": []}]
            result = await extractor.extract_with_llm(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_single_chunk_extraction(self, extractor, context):
        chunk = {
            "items": [
                {
                    "debt_code": "11",
                    "debt_description": "EMPRESTIMO BANCO X",
                    "year_before_last_value": 50000.0,
                    "last_year_value": 30000.0,
                    "current_year_value": 0.0,
                    "page": 5,
                }
            ],
            "year_before_last_total_value": 50000.0,
            "last_year_total_value": 30000.0,
            "current_year_total_value": 0.0,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["section_name"] == "Dívidas e Ônus Reais"
        assert result["extraction_method"] == "llm"
        assert len(result["items"]) == 1
        assert result["items"][0]["debt_code"] == "11"
        assert result["year_before_last_total_value"] == 50000.0
        assert result["last_year_total_value"] == 30000.0
        assert result["current_year_total_value"] == 0.0
        assert result["pages_with_problems"] == []

    @pytest.mark.asyncio
    async def test_multi_chunk_merge_with_dedup(self, extractor, context):
        item_a = {
            "debt_code": "11",
            "debt_description": "EMPRESTIMO X",
            "year_before_last_value": 100.0,
            "last_year_value": 50.0,
            "current_year_value": 0.0,
            "page": 5,
        }
        item_b = {
            "debt_code": "12",
            "debt_description": "FINANCIAMENTO Y",
            "year_before_last_value": 1000.0,
            "last_year_value": 800.0,
            "current_year_value": 200.0,
            "page": 6,
        }
        chunk1 = {"items": [item_a]}
        chunk2 = {"items": [item_a, item_b]}  # item_a duplicated
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk1, chunk2]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert len(result["items"]) == 2
        codes = sorted(i["debt_code"] for i in result["items"])
        assert codes == ["11", "12"]

    @pytest.mark.asyncio
    async def test_invalid_code_filtered_out(self, extractor, context):
        chunk = {
            "items": [
                {
                    "debt_code": "99",  # invalid
                    "debt_description": "FAKE",
                    "year_before_last_value": 1,
                    "last_year_value": 1,
                    "current_year_value": 1,
                    "page": 1,
                },
                {
                    "debt_code": "13",
                    "debt_description": "VALID",
                    "year_before_last_value": 100,
                    "last_year_value": 50,
                    "current_year_value": 0,
                    "page": 2,
                },
            ],
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["debt_code"] == "13"

    @pytest.mark.asyncio
    async def test_section_name_correct(self, extractor, context):
        chunk = {
            "items": [
                {
                    "debt_code": "11",
                    "debt_description": "TEST",
                    "year_before_last_value": 100,
                    "last_year_value": 50,
                    "current_year_value": 0,
                    "page": 1,
                }
            ],
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)
        assert result["section_name"] == "Dívidas e Ônus Reais"

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("Azure connection failed")
            result = await extractor.extract_with_llm(context)
        assert result is None


class TestLLMExtractionEnabled:
    """Settings toggle for debts_and_encumbrances LLM path."""

    def test_property_reads_from_settings_true(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_debts_and_encumbrances = True
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is True

    def test_property_defaults_false(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_debts_and_encumbrances = False
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is False
