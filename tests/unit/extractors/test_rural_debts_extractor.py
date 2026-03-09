"""Testes unitários para RuralDebtsExtractor.

Bug #87044 - Corrigir colisão entre section marker e descrição de item.
Bug #82852 - year_before_last_value incorreto (fallback trailing 3val).
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


class TestBug82852TrailingValues:
    """Bug #82852: Itens com descrição contendo dígitos/vírgulas (ex: 16,66%)
    falham no _ITEM_3VAL_RE e caem no _ITEM_2VAL_RE com year_before=0."""

    PAGE_TEXT = (
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "1 CEDULA RURAL 19000368 37.905,24 0,00 39.654,62\n"
        "2 CONTRATOS BCO SANTANDER 160.380,29 671.977,30 59.223,92\n"
        "3 16,66% CONTRATO C 106213047 COOP DE 2.298,16 0,00 2.298,16\n"
        "4 CPR SANTANDER 23002357 03/23 CNCTO 204.272,50 1.245.672,40 32.337,69\n"
        "TOTAL 405.056,19 1.917.649,70 133.574,85\n"
    )

    def test_finds_all_4_items(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        assert len(items) == 4

    def test_item3_year_before_not_zero(self, extractor):
        """Bug #82852: item 3 year_before deve ser 2298.16, não 0.0."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item3 = [it for it in items if it["item"] == 3][0]
        assert item3["year_before_last_value"] == 2298.16

    def test_item3_all_values(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item3 = [it for it in items if it["item"] == 3][0]
        assert item3["year_before_last_value"] == 2298.16
        assert item3["last_year_value"] == 0.0
        assert item3["paid_value_in_last_year"] == 2298.16

    def test_item4_year_before_not_zero(self, extractor):
        """Bug #82852: item 4 year_before deve ser 204272.50, não 0.0."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item4 = [it for it in items if it["item"] == 4][0]
        assert item4["year_before_last_value"] == 204272.50

    def test_item4_all_values(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item4 = [it for it in items if it["item"] == 4][0]
        assert item4["year_before_last_value"] == 204272.50
        assert item4["last_year_value"] == 1245672.40
        assert item4["paid_value_in_last_year"] == 32337.69

    def test_sum_year_before_matches(self, extractor):
        """Soma de year_before deve bater com o total."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        total = sum(it["year_before_last_value"] for it in items)
        expected = 37905.24 + 160380.29 + 2298.16 + 204272.50
        assert abs(total - expected) < 0.01

    def test_item3_description(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item3 = [it for it in items if it["item"] == 3][0]
        assert "CONTRATO C 106213047" in item3["description"]


class TestIsSectionTotalLine:
    """Testa _is_section_total_line — distingue total real de descrição."""

    def test_real_total_3_values(self, extractor):
        assert extractor._is_section_total_line(
            "TOTAL 2.579.166,74 22.391.052,36 2.109.050,28"
        ) is True

    def test_description_total_1_value(self, extractor):
        """Bug #82852: 'TOTAL 830.317,36' em descrição NÃO é total de seção."""
        assert extractor._is_section_total_line("TOTAL 830.317,36") is False

    def test_description_total_2_values(self, extractor):
        assert extractor._is_section_total_line("TOTAL 0,00 7.728.433,93") is False

    def test_total_with_text_after(self, extractor):
        assert extractor._is_section_total_line(
            "TOTAL $ 830.317,36 LIQUIDADO EM 2024"
        ) is False

    def test_total_alone(self, extractor):
        assert extractor._is_section_total_line("TOTAL") is True

    def test_empty_line(self, extractor):
        assert extractor._is_section_total_line("") is False


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


class TestBug82852RealWorldOCR:
    """Bug #82852: OCR real com 15 itens e descrição contendo 'TOTAL 830.317,36'.

    A linha 'TOTAL 830.317,36' dentro da descrição do item 3 era falsamente
    detectada como total da seção, causando perda dos itens 4-15.
    """

    PAGE_TEXT = (
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "1 CEDULA RURAL 19000368 CONTRAIDA JUNTO 37.905,24 0,00 39.654,62\n"
        "AO BANCO SANTANDER\n"
        "2 CONTRATOS BCO SANTANDER NRS 21001317 160.380,29 671.977,30 59.223,92\n"
        "LIBERACOES 02, 03 E 04/2021 TOTAL\n"
        "LIBERADO R$ 2.700.000,00 CUSTEIO RURAL\n"
        "2021 TENDO ASSUMIDO SALDO DO MESMO\n"
        "P/FINAL PARCERIA\n"
        "3 16,66% CONTRATO C 106213047 COOP DE 2.298,16 0,00 2.298,16\n"
        "CREDITO SICREDI CONTRAIDO 04/2021\n"
        "TOTAL 830.317,36\n"
        "4 CPR SANTANDER 23002357 03/23 CNCTO 204.272,50 1.245.672,40 32.337,69\n"
        "FINAL 2025 TENDO ASSUMIDO SALDO P/CTA\n"
        "FINAL PARCERIA\n"
        "5 1/6 CREDITO RURAL SICREDI BNDS C10010219 101.808,84 509.200,56 26.723,13\n"
        "6 BB CUSTEIO AGROP 7538 731.605,92 457.822,22 273.788,70\n"
        "7 CPR BCO BRASIL 520575 804.451,73 0,00 946.172,80\n"
        "8 CPR BCO DO BRASIL 614744 536.444,06 0,00 628.080,85\n"
        "9 CONTRAIU CPR 24006218 BCO SANTANDER EM 0,00 454.624,10 0,00\n"
        "EM 06/24\n"
        "10 CONTRAIU CPR 24011767 BCO SANTANDER 0,00 358.550,20 0,00\n"
        "11/24\n"
        "11 CONTRAIU CUSTEIO PECUARIO SICREDI C 0,00 978.780,56 0,00\n"
        "4000078476 03/24\n"
        "12 CONTRAIU CPR BB 715634 0,00 668.263,11 0,00\n"
        "13 FINANCIAMENTO CEF P/CTA CONSTRUÇÃO 0,00 1.415.651,98 0,00\n"
        "BARRACAO, SILO E MAQUINÁRIOS CONTRATO\n"
        "1841873\n"
        "14 FINANCIAMENTO CEF P/CTA CONSTRUÇÃO 0,00 391.368,63 0,00\n"
        "BARRACAO, SILO E MAQUINÁRIOS CONTRATO\n"
        "1907544\n"
        "15 FINANCIAMENTO CEF P/CTA CONSTRUÇÃO 0,00 828.947,39 0,00\n"
        "BARRACAO, SILO E MAQUINÁRIOS CONTRATO\n"
        "1907545\n"
        "TOTAL 2.579.166,74 22.391.052,36 2.109.050,28\n"
    )

    def test_finds_all_15_items(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        assert len(items) == 15

    def test_item3_description_includes_total_text(self, extractor):
        """Descrição do item 3 deve incluir 'TOTAL 830.317,36' como parte do texto."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item3 = [it for it in items if it["item"] == 3][0]
        assert "CONTRATO C 106213047" in item3["description"]

    def test_item4_exists_and_correct(self, extractor):
        """Item 4 NÃO deve ser perdido pelo falso TOTAL."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item4 = [it for it in items if it["item"] == 4][0]
        assert item4["year_before_last_value"] == 204272.50
        assert item4["last_year_value"] == 1245672.40
        assert item4["paid_value_in_last_year"] == 32337.69

    def test_items_9_to_12_zero_before(self, extractor):
        """Itens 9-12 devem ter year_before_last_value = 0."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        for num in [9, 10, 11, 12]:
            item = [it for it in items if it["item"] == num][0]
            assert item["year_before_last_value"] == 0.0, f"item {num}"

    def test_item15_values(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item15 = [it for it in items if it["item"] == 15][0]
        assert item15["year_before_last_value"] == 0.0
        assert item15["last_year_value"] == 828947.39
        assert item15["paid_value_in_last_year"] == 0.0

    def test_section_total_extracted(self, extractor):
        totals = extractor._extract_section_total(self.PAGE_TEXT)
        assert len(totals) == 3
        assert abs(totals[0] - 2579166.74) < 0.01
        assert abs(totals[1] - 22391052.36) < 0.01
        assert abs(totals[2] - 2109050.28) < 0.01

    def test_sum_year_before_matches_total(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        total = sum(it["year_before_last_value"] for it in items)
        expected = 37905.24 + 160380.29 + 2298.16 + 204272.50 + 101808.84 + 731605.92 + 804451.73 + 536444.06
        assert abs(total - expected) < 0.01
