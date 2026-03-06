"""Testes unitários para RuralDebtsExtractor.

Bug #87044 - Corrigir colisão entre section marker e descrição de item.
"""

import pytest
from irpf_processor.infrastructure.extraction.extractors.rural.debts import (
    RuralDebtsExtractor,
)
from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext


@pytest.fixture
def extractor():
    return RuralDebtsExtractor()


class TestIsHeaderLine:
    """Testa _is_section_header_line — distingue header real de item."""

    def test_real_header_with_brasil(self, extractor):
        line = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)"
        assert extractor._is_section_header_line(line) is True

    def test_real_header_without_suffix(self, extractor):
        line = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL"
        assert extractor._is_section_header_line(line) is True

    def test_real_header_exterior(self, extractor):
        line = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR"
        assert extractor._is_section_header_line(line) is True

    def test_item_with_marker_text_is_not_header(self, extractor):
        """Bug #87044: item 1 com descrição = section marker NÃO deve ser header."""
        line = "1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100,000.00 120,000.00 20,000.00"
        assert extractor._is_section_header_line(line) is False

    def test_item_with_marker_text_two_digits(self, extractor):
        line = "12 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 0,00 500.000,00 0,00"
        assert extractor._is_section_header_line(line) is False

    def test_unrelated_line_is_not_header(self, extractor):
        line = "2 RECEITA DE VENDA DE BOVINOS 400,000.00 200,000.00 200,000.00"
        assert extractor._is_section_header_line(line) is False

    def test_total_line_is_not_header(self, extractor):
        line = "TOTAL 500,000.00 320,000.00 220,000.00"
        assert extractor._is_section_header_line(line) is False

    def test_empty_line_is_not_header(self, extractor):
        assert extractor._is_section_header_line("") is False


class TestBug87044SectionMarkerCollision:
    """Bug #87044: Item com descrição idêntica ao section marker era perdido."""

    PAGE_TEXT = """DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)
ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024
31/12/2023 31/12/2024

1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100,000.00 120,000.00 20,000.00
2 RECEITA DE VENDA DE BOVINOS 400,000.00 200,000.00 200,000.00
TOTAL 500,000.00 320,000.00 220,000.00

Página 17 de 23"""

    def test_finds_both_items(self, extractor):
        """Deve encontrar 2 itens, não 1."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 17)
        assert len(items) == 2

    def test_item1_description(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 17)
        assert items[0]["description"] == "DÍVIDAS VINCULADAS À ATIVIDADE RURAL"

    def test_item1_values(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 17)
        assert items[0]["year_before_last_value"] == 100000.0
        assert items[0]["last_year_value"] == 120000.0
        assert items[0]["paid_value_in_last_year"] == 20000.0

    def test_item2_description(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 17)
        assert items[1]["description"] == "RECEITA DE VENDA DE BOVINOS"

    def test_item2_values(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 17)
        assert items[1]["year_before_last_value"] == 400000.0
        assert items[1]["last_year_value"] == 200000.0
        assert items[1]["paid_value_in_last_year"] == 200000.0

    def test_totals_extracted(self, extractor):
        totals = extractor._extract_section_total(self.PAGE_TEXT)
        assert len(totals) == 3
        assert totals[0] == 500000.0
        assert totals[1] == 320000.0
        assert totals[2] == 220000.0

    def test_full_extract_via_context(self, extractor):
        """Pipeline completo via ExtractionContext."""
        ctx = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={17: self.PAGE_TEXT},
            total_pages=23,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 2
        tv = result["total_values"]
        assert tv["year_before_last_value"]["amount"] == 500000.0
        assert tv["year_before_last_value"]["valid"] is True
        assert tv["last_year_value"]["amount"] == 320000.0
        assert tv["last_year_value"]["valid"] is True
        assert tv["paid_value_in_last_year"]["amount"] == 220000.0
        assert tv["paid_value_in_last_year"]["valid"] is True


class TestExteriorSectionNotMixed:
    """Garante que seção EXTERIOR com item similar não interfere."""

    PAGE_TEXT = """DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR (Valores em Reais)
ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024
31/12/2023 31/12/2024

1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL (EXTERIOR) 300,000.00 250,000.00 0.00
TOTAL 300,000.00 250,000.00 0.00"""

    def test_exterior_section_not_captured_by_brasil(self, extractor):
        """Seção EXTERIOR não deve ser capturada pelo extractor de BRASIL."""
        ctx = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={18: self.PAGE_TEXT},
            total_pages=23,
        )
        result = extractor.extract(ctx)
        assert result is None
