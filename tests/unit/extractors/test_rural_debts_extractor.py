import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.rural.debts import RuralDebtsExtractor


@pytest.fixture
def extractor():
    return RuralDebtsExtractor()


def _make_page(lines: list[str]) -> str:
    return "\n".join(lines)


def _make_context(pages: dict[int, str]) -> ExtractionContext:
    full_text = "\n".join(pages.values())
    return ExtractionContext(
        full_text=full_text,
        pages_text=pages,
        total_pages=len(pages),
    )


SECTION_HEADER = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - Brasil"
ITEM_HEADER = "Item Discriminação Situação em 31/12/2023 Situação em 31/12/2024 Valor Pago em 2024"


class TestExtractsItemWithMarkerInDescription:

    def test_item_whose_description_contains_marker_is_not_skipped(self, extractor):
        page_text = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100.000,00 120.000,00 20.000,00",
            "TOTAL 100.000,00 120.000,00 20.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["item"] == 1
        assert result["items"][0]["year_before_last_value"] == 100000.0
        assert result["items"][0]["last_year_value"] == 120000.0
        assert result["items"][0]["paid_value_in_last_year"] == 20000.0


class TestExtractsMultipleItemsIncludingMarkerDescription:

    def test_both_items_extracted_with_correct_totals(self, extractor):
        page_text = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100.000,00 120.000,00 20.000,00",
            "2 FINANCIAMENTO BANCÁRIO SAFRA 2023 400.000,00 200.000,00 200.000,00",
            "TOTAL 500.000,00 320.000,00 220.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 2
        assert result["items"][0]["item"] == 1
        assert result["items"][0]["year_before_last_value"] == 100000.0
        assert result["items"][1]["item"] == 2
        assert result["items"][1]["year_before_last_value"] == 400000.0

    def test_totals_validate_correctly(self, extractor):
        page_text = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100.000,00 120.000,00 20.000,00",
            "2 FINANCIAMENTO BANCÁRIO SAFRA 2023 400.000,00 200.000,00 200.000,00",
            "TOTAL 500.000,00 320.000,00 220.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        totals = result["total_values"]
        assert totals["year_before_last_value"]["valid"] is True
        assert totals["last_year_value"]["valid"] is True
        assert totals["paid_value_in_last_year"]["valid"] is True


class TestSectionHeaderStillDetected:

    def test_section_marker_on_header_line_enters_section_mode(self, extractor):
        page_text = _make_page([
            "RENDIMENTOS TRIBUTÁVEIS",
            "Algum conteudo anterior",
            SECTION_HEADER,
            ITEM_HEADER,
            "1 FINANCIAMENTO RURAL 50.000,00 40.000,00 10.000,00",
            "TOTAL 50.000,00 40.000,00 10.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["year_before_last_value"] == 50000.0

    def test_returns_none_when_marker_absent(self, extractor):
        page_text = _make_page([
            "RENDIMENTOS TRIBUTÁVEIS",
            "1 ITEM QUALQUER 10.000,00 10.000,00 5.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is None


class TestBrasilVsExteriorDisambiguation:

    def test_brasil_items_stay_in_brasil_section(self, extractor):
        page_text = _make_page([
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - Brasil",
            ITEM_HEADER,
            "1 FINANCIAMENTO RURAL BRASIL 100.000,00 80.000,00 20.000,00",
            "TOTAL 100.000,00 80.000,00 20.000,00",
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - Exterior",
            "1 FINANCIAMENTO EXTERIOR 200.000,00 150.000,00 50.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert "BRASIL" in result["items"][0]["description"]

    def test_exterior_only_page_is_skipped(self, extractor):
        page_text = _make_page([
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - Exterior",
            ITEM_HEADER,
            "1 LOAN FROM FOREIGN BANK 300.000,00 250.000,00 50.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is None


class TestTotalLineEndsSection:

    def test_items_after_total_are_not_extracted(self, extractor):
        page_text = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 FINANCIAMENTO A 50.000,00 40.000,00 10.000,00",
            "TOTAL 50.000,00 40.000,00 10.000,00",
            "2 ESTE ITEM NÃO DEVE APARECER 99.000,00 99.000,00 99.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["item"] == 1

    def test_total_line_with_values_is_detected(self, extractor):
        page_text = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 EMPRÉSTIMO RURAL 200.000,00 180.000,00 20.000,00",
            "TOTAL 200.000,00 180.000,00 20.000,00",
        ])
        ctx = _make_context({1: page_text})

        result = extractor.extract(ctx)

        assert result is not None
        totals = result["total_values"]
        assert totals["year_before_last_value"]["amount"] == 200000.0


class TestMultiPageExtraction:

    def test_items_from_separate_pages_are_collected(self, extractor):
        page1 = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100.000,00 120.000,00 20.000,00",
            "TOTAL 500.000,00 320.000,00 220.000,00",
        ])
        page2 = _make_page([
            SECTION_HEADER,
            ITEM_HEADER,
            "2 FINANCIAMENTO BANCÁRIO SAFRA 2023 400.000,00 200.000,00 200.000,00",
        ])
        ctx = _make_context({1: page1, 2: page2})

        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 2
        assert result["items"][0]["item"] == 1
        assert result["items"][1]["item"] == 2
