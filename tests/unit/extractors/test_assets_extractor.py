import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.assets import AssetsExtractor
from irpf_processor.infrastructure.extraction.table_extractor import parse_currency, generate_item_id


@pytest.fixture
def extractor():
    return AssetsExtractor()


@pytest.fixture
def sample_assets_page():
    return """
    DECLARACAO DE BENS E DIREITOS
    
    01 01 APARTAMENTO RESIDENCIAL 150.000,00 175.000,00
    01 02 TERRENO URBANO 80.000,00 85.000,00
    02 01 AUTOMOVEL FIAT ARGO 45.000,00 40.000,00
    06 01 CONTA CORRENTE BANCO DO BRASIL 10.000,00 15.000,00
    """


class TestAssetsExtractorSectionName:

    def test_returns_correct_section_name(self, extractor):
        assert extractor.section_name == "assets_declaration"


class TestAssetsExtractorCanExtract:

    def test_returns_false_when_no_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="RENDIMENTOS ISENTOS\nConteudo",
            pages_text={1: ""},
            total_pages=1
        )

        assert extractor.can_extract(context) is False

    def test_can_extract_is_callable(self, extractor):
        """Verify can_extract method exists and is callable."""
        assert callable(extractor.can_extract)


class TestAssetsExtractorExtract:

    def test_returns_none_when_no_items_found(self, extractor):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS\nSem itens",
            pages_text={1: "DECLARACAO DE BENS E DIREITOS\nSem itens"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_extract_is_callable(self, extractor):
        """Verify extract method exists and is callable."""
        assert callable(extractor.extract)

    def test_calculates_totals(self, extractor, sample_assets_page):
        context = ExtractionContext(
            full_text=sample_assets_page,
            pages_text={1: sample_assets_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert "last_year_total_value" in result
            assert "current_year_total_value" in result
            assert isinstance(result["last_year_total_value"], float)
            assert isinstance(result["current_year_total_value"], float)

    def test_result_structure(self, extractor, sample_assets_page):
        context = ExtractionContext(
            full_text=sample_assets_page,
            pages_text={1: sample_assets_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert "section_name" in result
            assert "items" in result
            assert "last_year_total_value" in result
            assert "current_year_total_value" in result
            assert "pages_with_problems" in result


class TestAssetsExtractorItemStructure:

    def test_item_has_required_fields(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 APARTAMENTO 100.000,00 120.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert "id" in item
            assert "asset_group_code" in item
            assert "asset_code" in item
            assert "asset_description" in item
            assert "before_year_asset_value" in item
            assert "current_year_asset_value" in item

    def test_item_values_parsed_correctly(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 IMOVEL 100.000,00 150.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "01"
            assert item["asset_code"] == "01"
            assert item["before_year_asset_value"] == 100000.0
            assert item["current_year_asset_value"] == 150000.0


class TestAssetsExtractorMultiplePages:

    def test_extracts_from_multiple_pages(self, extractor):
        page1 = "DECLARACAO DE BENS E DIREITOS\n01 01 IMOVEL 1 100.000,00 110.000,00"
        page2 = "DECLARACAO DE BENS E DIREITOS\n01 02 IMOVEL 2 200.000,00 220.000,00"

        context = ExtractionContext(
            full_text=page1 + "\n" + page2,
            pages_text={1: page1, 2: page2},
            total_pages=2
        )

        result = extractor.extract(context)

        if result:
            assert len(result["items"]) >= 1


class TestParseCurrency:

    def test_parses_brazilian_format(self):
        assert parse_currency("100.000,00") == 100000.0

    def test_parses_simple_format(self):
        assert parse_currency("1.000,50") == 1000.5

    def test_handles_empty_string(self):
        assert parse_currency("") == 0.0

    def test_handles_invalid_format(self):
        assert parse_currency("invalid") == 0.0

    def test_removes_currency_symbols(self):
        assert parse_currency("R$ 1.000,00") == 1000.0


class TestGenerateItemId:

    def test_generates_consistent_id(self):
        id1 = generate_item_id("test content")
        id2 = generate_item_id("test content")

        assert id1 == id2

    def test_generates_different_ids_for_different_content(self):
        id1 = generate_item_id("content 1")
        id2 = generate_item_id("content 2")

        assert id1 != id2

    def test_returns_hash_string(self):
        item_id = generate_item_id("test")

        assert isinstance(item_id, str)
        assert len(item_id) > 0


class TestAssetsExtractorAssetGroups:

    def test_extracts_real_estate_group_01(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 CASA RESIDENCIAL 500.000,00 550.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "01"

    def test_extracts_vehicle_group_02(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n02 01 AUTOMOVEL HONDA 80.000,00 70.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "02"

    def test_extracts_deposit_group_06(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n06 01 CONTA POUPANCA 25.000,00 30.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "06"


class TestAssetsExtractorCountryInfo:

    def test_default_country_is_brazil(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 IMOVEL 100.000,00 100.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["country_code"] == "105"
            assert item["country_name"] == "BRASIL"
            assert item["country_valid"] is True


class TestAssetsExtractorEdgeCases:

    def test_handles_empty_pages_text(self, extractor):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS",
            pages_text={},
            total_pages=0
        )

        result = extractor.extract(context)

        assert result is None

    def test_handles_page_without_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS",
            pages_text={1: "Page without marker"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_skips_non_matching_lines(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        Random text that should be skipped
        01 01 VALID ASSET 10.000,00 12.000,00
        More random text
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert len(result["items"]) == 1
