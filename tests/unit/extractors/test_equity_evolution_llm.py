"""Unit tests for EquityEvolutionExtractor LLM integration (US-19160)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.equity_evolution import (
    EquityEvolutionExtractor,
)


@pytest.fixture
def extractor() -> EquityEvolutionExtractor:
    return EquityEvolutionExtractor()


@pytest.fixture
def context() -> ExtractionContext:
    page_text = (
        "EVOLUÇÃO PATRIMONIAL\n"
        " Bens e direitos em 31/12/2023        250.000,00\n"
        " Bens e direitos em 31/12/2024        275.000,00\n"
        " Dívidas e ônus reais em 31/12/2023        10.000,00\n"
        " Dívidas e ônus reais em 31/12/2024         5.000,00\n"
        "OUTRAS INFORMAÇÕES\n"
    )
    return ExtractionContext(
        full_text=page_text,
        pages_text={7: page_text},
        total_pages=8,
        pdf_path="/tmp/test.pdf",
        document_id="test_doc_equity_llm",
    )


class TestParseLLMCurrency:
    def test_none_returns_zero(self, extractor):
        assert extractor._parse_llm_currency(None) == 0.0

    def test_empty_string_returns_zero(self, extractor):
        assert extractor._parse_llm_currency("") == 0.0

    def test_number_passthrough(self, extractor):
        assert extractor._parse_llm_currency(250000.0) == 250000.0
        assert extractor._parse_llm_currency(0) == 0.0

    def test_br_format_string(self, extractor):
        assert extractor._parse_llm_currency("250.000,00") == 250000.0

    def test_us_format_string(self, extractor):
        assert extractor._parse_llm_currency("250000.50") == 250000.5


class TestParseYear:
    def test_int_passthrough(self, extractor):
        assert extractor._parse_year(2024) == 2024

    def test_string_4_digits(self, extractor):
        assert extractor._parse_year("2023") == 2023

    def test_invalid_returns_none(self, extractor):
        assert extractor._parse_year("abc") is None
        assert extractor._parse_year("12") is None
        assert extractor._parse_year(None) is None


class TestNormalizeLLMChunk:
    def test_full_chunk_normalized(self, extractor):
        chunk = {
            "assets_last_year": 250000.0,
            "assets_current_year": 275500.5,
            "debts_last_year": 10000.0,
            "debts_current_year": 5000.0,
            "year_last": 2023,
            "year_current": 2024,
        }
        result = extractor._normalize_llm_chunk(chunk)
        assert result is not None
        assert result["section_name"] == "Evolução Patrimonial"
        assert result["assets_current_year"] == 275500.5
        assert result["debts_current_year"] == 5000.0
        assert result["year_last"] == 2023
        assert result["year_current"] == 2024
        # (275500.5 - 5000) - (250000 - 10000) = 30500.5
        assert result["computed_evolution"] == 30500.5
        assert "id" in result

    def test_string_values_parsed_br(self, extractor):
        chunk = {
            "assets_last_year": "100.000,00",
            "assets_current_year": "150.000,00",
            "debts_last_year": "0,00",
            "debts_current_year": "0,00",
            "year_last": "2023",
            "year_current": "2024",
        }
        result = extractor._normalize_llm_chunk(chunk)
        assert result is not None
        assert result["assets_current_year"] == 150000.0
        assert result["computed_evolution"] == 50000.0

    def test_only_year_current_infers_year_last(self, extractor):
        chunk = {
            "assets_current_year": 100.0,
            "year_current": 2024,
        }
        result = extractor._normalize_llm_chunk(chunk)
        assert result is not None
        assert result["year_last"] == 2023
        assert result["year_current"] == 2024

    def test_all_zeros_rejected(self, extractor):
        chunk = {
            "assets_last_year": 0,
            "assets_current_year": 0,
            "debts_last_year": 0,
            "debts_current_year": 0,
            "year_current": 2024,
        }
        assert extractor._normalize_llm_chunk(chunk) is None

    def test_no_year_rejected(self, extractor):
        chunk = {"assets_current_year": 100.0}
        assert extractor._normalize_llm_chunk(chunk) is None

    def test_non_dict_rejected(self, extractor):
        assert extractor._normalize_llm_chunk(None) is None
        assert extractor._normalize_llm_chunk("not a dict") is None


class TestExtractWithLLM:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_chunks(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = None
            result = await extractor.extract_with_llm(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_chunk_unusable(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [{}]
            result = await extractor.extract_with_llm(context)
        assert result is None

    @pytest.mark.asyncio
    async def test_first_valid_chunk_wins(self, extractor, context):
        chunk = {
            "assets_last_year": 250000.0,
            "assets_current_year": 275000.0,
            "debts_last_year": 10000.0,
            "debts_current_year": 5000.0,
            "year_last": 2023,
            "year_current": 2024,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["extraction_method"] == "llm"
        # (275000 - 5000) - (250000 - 10000) = 30000.0
        assert result["computed_evolution"] == 30000.0

    @pytest.mark.asyncio
    async def test_skips_unusable_first_chunk(self, extractor, context):
        good = {
            "assets_current_year": 100.0,
            "debts_current_year": 0.0,
            "assets_last_year": 50.0,
            "debts_last_year": 0.0,
            "year_current": 2024,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [{}, good]
            result = await extractor.extract_with_llm(context)
        assert result is not None
        assert result["computed_evolution"] == 50.0

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("Azure connection failed")
            result = await extractor.extract_with_llm(context)
        assert result is None


class TestLLMExtractionEnabled:
    def test_property_reads_from_settings_true(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_equity_evolution_section = True
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is True

    def test_property_defaults_false(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_equity_evolution_section = False
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is False
