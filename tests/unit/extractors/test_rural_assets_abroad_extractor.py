import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.rural.assets_abroad import RuralAssetsAbroadExtractor


@pytest.fixture
def extractor():
    return RuralAssetsAbroadExtractor()


def _make_context(pages: dict[int, str]) -> ExtractionContext:
    full_text = "\n".join(pages.values())
    return ExtractionContext(full_text=full_text, pages_text=pages, total_pages=len(pages))


SECTION_HEADER = "BENS DA ATIVIDADE RURAL - EXTERIOR"
ITEM_HEADER = "Cód Descrição Situação em 31/12/2023 Situação em 31/12/2024"


class TestMarkerInDescription:

    def test_item_with_marker_in_description_is_not_skipped(self, extractor):
        page_text = "\n".join([
            SECTION_HEADER,
            ITEM_HEADER,
            "16 BENS DA ATIVIDADE RURAL - EXTERIOR 149 CANADÁ 200.000,00 190.000,00",
            "TOTAL 200.000,00 190.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) >= 1

    def test_two_items_both_extracted_when_first_contains_marker(self, extractor):
        page_text = "\n".join([
            SECTION_HEADER,
            ITEM_HEADER,
            "16 BENS DA ATIVIDADE RURAL - EXTERIOR 149 CANADÁ 200.000,00 190.000,00",
            "17 TRATOR JOHN DEERE 149 CANADÁ 100.000,00 95.000,00",
            "TOTAL 300.000,00 285.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 2
