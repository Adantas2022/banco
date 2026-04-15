"""Unit tests for RuralPropertiesExtractor LLM integration.

Tests the new LLM extraction methods (extract_with_llm, _normalize_llm_item)
without requiring actual Azure OpenAI connectivity.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from irpf_processor.infrastructure.extraction.extractors.rural.properties import (
    RuralPropertiesExtractor,
)
from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext


@pytest.fixture
def extractor():
    return RuralPropertiesExtractor()


@pytest.fixture
def context():
    page_text = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "10 100,00 1 FAZENDA LAMBARI, CAMPOS DE JULIO/MT 1.200,0 4.695.449-0\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )
    return ExtractionContext(
        full_text=page_text,
        pages_text={5: page_text},
        total_pages=12,
        pdf_path="/tmp/test.pdf",
        document_id="test_doc_123",
    )


class TestNormalizeLLMItem:
    """Tests for _normalize_llm_item() — transforms raw LLM output into
    the same dict format the regex extract() method produces."""

    def test_basic_item_normalization(self, extractor):
        raw = {
            "code": 10,
            "participation": 100.0,
            "exploration_condition": 1,
            "name_and_location": "FAZENDA LAMBARI, CAMPOS DE JULIO/MT",
            "area": 1200.0,
            "cib": "4.695.449-0",
            "participants": None,
            "page": 5,
        }
        result = extractor._normalize_llm_item(raw)

        assert result["code"] == 10
        assert result["participation"] == 100.0
        assert result["exploration_condition"] == 1
        assert result["name_and_location"] == "FAZENDA LAMBARI, CAMPOS DE JULIO/MT"
        assert result["area"] == 1200.0
        assert result["cib"] == "4.695.449-0"
        assert result["participants"] is None
        assert result["page"] == 5
        assert "id" in result

    def test_string_code_converted_to_int(self, extractor):
        raw = {"code": "10", "participation": 0, "exploration_condition": "1",
               "name_and_location": "TEST", "area": 0, "cib": "", "page": 1}
        result = extractor._normalize_llm_item(raw)
        assert result["code"] == 10
        assert result["exploration_condition"] == 1

    def test_br_currency_area_parsed(self, extractor):
        raw = {"code": 10, "participation": "15,00", "exploration_condition": 1,
               "name_and_location": "FAZENDA", "area": "1.200,0", "cib": "", "page": 1}
        result = extractor._normalize_llm_item(raw)
        assert result["participation"] == 15.0
        assert result["area"] == 1200.0

    def test_name_whitespace_normalized(self, extractor):
        raw = {"code": 10, "participation": 100, "exploration_condition": 1,
               "name_and_location": "FAZENDA   BOA    VISTA", "area": 0, "cib": "", "page": 1}
        result = extractor._normalize_llm_item(raw)
        assert result["name_and_location"] == "FAZENDA BOA VISTA"

    def test_cib_none_becomes_empty_string(self, extractor):
        raw = {"code": 10, "participation": 100, "exploration_condition": 1,
               "name_and_location": "TEST", "area": 0, "cib": None, "page": 1}
        result = extractor._normalize_llm_item(raw)
        assert result["cib"] == ""

    def test_participants_normalized(self, extractor):
        raw = {
            "code": 10, "participation": 15.0, "exploration_condition": 3,
            "name_and_location": "FAZENDA LAMBARI", "area": 1200.0, "cib": "4.695.449-0",
            "participants": {
                "items": [
                    {
                        "participant_name": "JOAO DA SILVA (175.474.448-65)",
                        "cpf": "175.474.448-65",
                        "cnpj": None,
                        "foreigner": False,
                    },
                    {
                        "participant_name": "EMPRESA XYZ (12.345.678/0001-90)",
                        "cnpj": "12.345.678/0001-90",
                        "cpf": None,
                        "foreigner": False,
                    },
                ]
            },
            "page": 5,
        }
        result = extractor._normalize_llm_item(raw)

        assert result["participants"] is not None
        parts = result["participants"]["items"]
        assert len(parts) == 2

        assert parts[0]["cpf"] == "175.474.448-65"
        assert "cnpj" not in parts[0]
        assert parts[0]["foreigner"] is False
        assert "id" in parts[0]

        assert parts[1]["cnpj"] == "12.345.678/0001-90"
        assert "cpf" not in parts[1]

    def test_empty_participants_becomes_none(self, extractor):
        raw = {"code": 10, "participation": 100, "exploration_condition": 1,
               "name_and_location": "TEST", "area": 0, "cib": "",
               "participants": {"items": []}, "page": 1}
        result = extractor._normalize_llm_item(raw)
        assert result["participants"] is None

    def test_missing_fields_use_defaults(self, extractor):
        raw = {}
        result = extractor._normalize_llm_item(raw)
        assert result["code"] == 0
        assert result["participation"] == 0.0
        assert result["exploration_condition"] == 0
        assert result["name_and_location"] == ""
        assert result["area"] == 0.0
        assert result["cib"] == ""
        assert result["participants"] is None
        assert result["page"] == 0

    def test_id_generated_consistently(self, extractor):
        raw = {"code": 10, "participation": 100, "exploration_condition": 1,
               "name_and_location": "FAZENDA X", "area": 500.0, "cib": "1.234.567-8", "page": 1}
        r1 = extractor._normalize_llm_item(raw)
        r2 = extractor._normalize_llm_item(raw)
        assert r1["id"] == r2["id"]


class TestExtractWithLLM:
    """Tests for extract_with_llm() — mocks LLM calls to verify
    chunk merging, overlap removal, and result structure."""

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
                    "code": 10, "participation": 100.0, "exploration_condition": 1,
                    "name_and_location": "FAZENDA LAMBARI", "area": 1200.0,
                    "cib": "4.695.449-0", "participants": None, "page": 5,
                },
            ],
            "total_properties": 1,
            "total_area": 1200.0,
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)

        assert result is not None
        assert result["total_properties"] == 1
        assert result["total_area"] == 1200.0
        assert result["extraction_method"] == "llm"
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == 10

    @pytest.mark.asyncio
    async def test_multi_chunk_merge(self, extractor, context):
        chunk1 = {
            "items": [
                {"code": 10, "participation": 100, "exploration_condition": 1,
                 "name_and_location": "FAZENDA A", "area": 500, "cib": "1.111.111-1",
                 "participants": None, "page": 5},
                {"code": 11, "participation": 50, "exploration_condition": 3,
                 "name_and_location": "FAZENDA B", "area": 300, "cib": "2.222.222-2",
                 "participants": None, "page": 6},
            ],
        }
        chunk2 = {
            "items": [
                # Overlap: page 6 item repeated
                {"code": 11, "participation": 50, "exploration_condition": 3,
                 "name_and_location": "FAZENDA B", "area": 300, "cib": "2.222.222-2",
                 "participants": None, "page": 6},
                {"code": 13, "participation": 100, "exploration_condition": 1,
                 "name_and_location": "FAZENDA C", "area": 800, "cib": "3.333.333-3",
                 "participants": None, "page": 7},
            ],
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk1, chunk2]
            result = await extractor.extract_with_llm(context)

        assert result is not None
        # After overlap removal: A(p5) + B(p6 from chunk2) + C(p7)
        assert result["total_properties"] == 3
        assert result["total_area"] == 1600.0

    @pytest.mark.asyncio
    async def test_section_name_correct(self, extractor, context):
        chunk = {
            "items": [
                {"code": 10, "participation": 100, "exploration_condition": 1,
                 "name_and_location": "TEST", "area": 100, "cib": "", "participants": None, "page": 1},
            ],
        }
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.return_value = [chunk]
            result = await extractor.extract_with_llm(context)

        assert result["section_name"] == "Dados e Identificação do Imóvel Explorado - Brasil"

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, extractor, context):
        with patch.object(extractor, "get_llm_extraction_data", new_callable=AsyncMock) as mock:
            mock.side_effect = RuntimeError("Azure connection failed")
            result = await extractor.extract_with_llm(context)
            assert result is None


class TestLLMExtractionEnabled:
    """Tests that the config toggle is correctly resolved."""

    def test_property_reads_from_settings(self, extractor):
        with patch("irpf_processor.infrastructure.extraction.extractors.base.get_settings") as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_exploited_rural_properties_in_brazil = True
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is True

    def test_property_defaults_false(self, extractor):
        with patch("irpf_processor.infrastructure.extraction.extractors.base.get_settings") as mock_settings:
            settings = MagicMock()
            settings.llm_extraction_exploited_rural_properties_in_brazil = False
            mock_settings.return_value = settings
            assert extractor.llm_extraction_enabled is False


class TestInitState:
    """Tests that __init__ properly initializes section tracking state."""

    def test_section_started_false(self, extractor):
        assert extractor._section_started is False

    def test_section_start_page_minus_one(self, extractor):
        assert extractor._section_start_page == -1


class TestRegexRegressionWithInit:
    """Regression: ensure __init__ addition doesn't break existing regex extract()."""

    PAGE_TEXT = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "10 15,00 3 FAZENDA LAMBARI, CAMPOS DE JULIO/MT 1.200,0 4.695.449-0\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )

    def test_extract_still_works(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={10: self.PAGE_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert result["total_properties"] == 1
        assert result["items"][0]["code"] == 10
        assert result["items"][0]["area"] == 1200.0
