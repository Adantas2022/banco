import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.rural.livestock_abroad import LivestockMovementAbroadExtractor


@pytest.fixture
def extractor():
    return LivestockMovementAbroadExtractor()


def _make_context(pages: dict[int, str]) -> ExtractionContext:
    full_text = "\n".join(pages.values())
    return ExtractionContext(full_text=full_text, pages_text=pages, total_pages=len(pages))


SECTION_HEADER = "MOVIMENTAÇÃO DO REBANHO - EXTERIOR"
COL_HEADER = "Espécie Estoque Inicial Aquisições Nascimentos Perdas Vendas Estoque Final"


class TestMarkerInDescription:

    def test_item_with_marker_in_description_is_not_skipped(self, extractor):
        page_text = "\n".join([
            SECTION_HEADER,
            COL_HEADER,
            "Movimentação do Rebanho Bovinos 100,00 50,00 30,00 10,00 20,00 150,00",
            "TOTAL 100,00 50,00 30,00 10,00 20,00 150,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) >= 1
