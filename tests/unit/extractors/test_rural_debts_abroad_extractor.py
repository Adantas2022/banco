import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.rural.debts_abroad import RuralDebtsAbroadExtractor


@pytest.fixture
def extractor():
    return RuralDebtsAbroadExtractor()


def _make_context(pages: dict[int, str]) -> ExtractionContext:
    full_text = "\n".join(pages.values())
    return ExtractionContext(full_text=full_text, pages_text=pages, total_pages=len(pages))


SECTION_HEADER = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR"
ITEM_HEADER = "Item Discriminação Situação em 31/12/2023 Situação em 31/12/2024 Valor Pago em 2024"


class TestMarkerInDescription:

    def test_item_with_marker_in_description_is_not_skipped(self, extractor):
        page_text = "\n".join([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR 50.000,00 40.000,00 10.000,00",
            "TOTAL 50.000,00 40.000,00 10.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) >= 1

    def test_two_items_both_extracted_when_first_contains_marker(self, extractor):
        page_text = "\n".join([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR 50.000,00 40.000,00 10.000,00",
            "2 EMPRÉSTIMO BANCÁRIO INTERNACIONAL 100.000,00 80.000,00 20.000,00",
            "TOTAL 150.000,00 120.000,00 30.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 2
