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
        """TOTAL com 2 valores monetários É total de seção (Document AI pode perder 1 valor)."""
        assert extractor._is_section_total_line("TOTAL 0,00 7.728.433,93") is True

    def test_total_with_text_after(self, extractor):
        assert extractor._is_section_total_line(
            "TOTAL $ 830.317,36 LIQUIDADO EM 2024"
        ) is False

    def test_total_alone(self, extractor):
        """Bug #82852: TOTAL sozinho NÃO é total de seção (pode ser OCR de descrição)."""
        assert extractor._is_section_total_line("TOTAL") is False
        assert extractor._is_section_total_line("TOTAL  ") is False

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


class TestBug82852BareTotalInDescription:
    """Bug #82852 v2: OCR splits 'TOTAL' to its own line inside description.

    Quando o OCR quebra a descrição de um item que contém a palavra TOTAL
    (ex: 'LIBERACOES 02, 03 E 04/2021 TOTAL LIBERADO R$ 2.700.000,00'),
    a palavra 'TOTAL' pode aparecer sozinha em uma linha. Anteriormente,
    _is_section_total_line("TOTAL") retornava True, causando break no
    loop de parsing e perda de todos os itens subsequentes.
    """

    PAGE_TEXT = (
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "1 CEDULA RURAL 19000368 CONTRAIDA JUNTO 37.905,24 0,00 39.654,62\n"
        "AO BANCO SANTANDER\n"
        "2 CONTRATOS BCO SANTANDER NRS 21001317 160.380,29 671.977,30 59.223,92\n"
        "LIBERACOES 02, 03 E 04/2021\n"
        "TOTAL\n"
        "LIBERADO R$ 2.700.000,00 CUSTEIO RURAL\n"
        "2021 TENDO ASSUMIDO SALDO DO MESMO\n"
        "P/FINAL PARCERIA\n"
        "3 16,66% CONTRATO C 106213047 COOP DE 2.298,16 0,00 2.298,16\n"
        "CREDITO SICREDI CONTRAIDO 04/2021 VALOR\n"
        "TOTAL $ 830.317,36 LIQUIDADO EM 2024\n"
        "4 CPR SANTANDER 23002357 03/23 C/VCTO 204.272,50 1.245.672,40 32.337,69\n"
        "FINAL 2025 TENDO ASSUMIDO SALDO P/CTA\n"
        "FINAL PARCERIA\n"
        "5 1/6 CREDITO RURAL SICREDI BNDS C10010219 101.808,84 509.200,56 26.723,13\n"
        "6 BB CUSTEIO AGROP 7538 731.605,92 457.822,22 273.788,70\n"
        "7 CPR BCO BRASIL 520575 804.451,73 0,00 946.172,80\n"
        "TOTAL 2.042.722,18 2.884.872,18 1.369.433,32\n"
    )

    def test_bare_total_does_not_stop_parsing(self, extractor):
        """TOTAL sozinho na descrição NÃO deve interromper o parsing."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        assert len(items) == 7

    def test_item3_not_lost(self, extractor):
        """Item 3 (após TOTAL sozinho) deve ser extraído."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item3 = [it for it in items if it["item"] == 3][0]
        assert item3["year_before_last_value"] == 2298.16
        assert item3["last_year_value"] == 0.0
        assert item3["paid_value_in_last_year"] == 2298.16

    def test_item4_not_lost(self, extractor):
        """Item 4 (após 'TOTAL $ 830.317,36' na descrição) deve ser extraído."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item4 = [it for it in items if it["item"] == 4][0]
        assert item4["year_before_last_value"] == 204272.50
        assert item4["last_year_value"] == 1245672.40
        assert item4["paid_value_in_last_year"] == 32337.69

    def test_item7_extracted(self, extractor):
        """Último item deve ser extraído corretamente."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item7 = [it for it in items if it["item"] == 7][0]
        assert item7["year_before_last_value"] == 804451.73
        assert item7["last_year_value"] == 0.0
        assert item7["paid_value_in_last_year"] == 946172.80

    def test_section_total_extracted(self, extractor):
        """Total da seção (3 valores) deve ser extraído corretamente."""
        totals = extractor._extract_section_total(self.PAGE_TEXT)
        assert len(totals) == 3
        assert abs(totals[0] - 2042722.18) < 0.01
        assert abs(totals[1] - 2884872.18) < 0.01
        assert abs(totals[2] - 1369433.32) < 0.01

    def test_description_includes_total_text(self, extractor):
        """Descrição do item 2 deve incluir TOTAL como parte do texto."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 16)
        item2 = [it for it in items if it["item"] == 2][0]
        assert "CONTRATOS BCO SANTANDER" in item2["description"]


class TestBug82852MultilineSectionTotal:
    """Testa extração de total quando TOTAL aparece sozinho e valores na próxima linha."""

    PAGE_TEXT = (
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)\n"
        "1 ITEM A 100,00 200,00 300,00\n"
        "TOTAL\n"
        "500,00 600,00 700,00\n"
    )

    def test_multiline_total_extracted(self, extractor):
        """Total em linha separada do TOTAL deve ser extraído via fallback."""
        totals = extractor._extract_section_total(self.PAGE_TEXT)
        assert len(totals) == 3
        assert totals[0] == 500.0
        assert totals[1] == 600.0
        assert totals[2] == 700.0

    def test_bare_total_with_2_values_extracted(self, extractor):
        """TOTAL + próxima linha com 2 valores DEVE ser extraído (Document AI pode perder 1 valor)."""
        text = (
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL\n"
            "1 ITEM A 100,00 200,00 300,00\n"
            "TOTAL\n"
            "500,00 600,00\n"
        )
        totals = extractor._extract_section_total(text)
        assert len(totals) == 2
        assert totals[0] == 500.0
        assert totals[1] == 600.0


class TestBug82852RealOCRIntegration:
    """Teste de integração com texto OCR REAL extraído via Tesseract do PDF do bug #82852.

    Este teste usa o texto EXATO que o Tesseract produz ao processar o PDF
    '0215_IRPF_LOVIS - IRPF 2025 DECLARACAO.pdf' (pages 16-17).
    Verifica todos os 17 itens e totais contra o gabarito.
    """

    PAGE_16_TEXT = (
        "NOME: CLOVIS FELIX DE PAULA\n"
        "\n"
        "CPF: 604.382.581-34 IMPOSTO SOBRE A RENDA - PESSOA FÍSICA\n"
        "DECLARAÇÃO DE AJUSTE ANUAL EXERCÍCIO 2025 ANO-CALENDÁRIO 2024\n"
        "16 VEICULO CAMIONETE TOYOTA HILUZ CD 4X4 RENAVAM 0,00 80.000,00\n"
        "00341795623 ANO 2011/11\n"
        "16 MOTOCICLETA YAMAHA/CROSSER Z ABS RENAVAM 01347164496 0,00 10.000,00\n"
        "2023/23\n"
        "16 VEICULO CAMINHONETE VW SAVEIRO CE RENAVAM 0,00 50.000,00\n"
        "00995046581 ANO 2013/14\n"
        "16 CAMINHAO M.BENS /ACTROS 2651 S6X4 RENAVAM 01 151933292 0,00 200.000,00\n"
        "ANO 2018/18\n"
        "11 GALPAO EQUIPAPADO COM SILO E MAQUINAS PARA USO NA 0,00 7.308.433,93\n"
        "AGROPECUARIA\n"
        "TOTAL 0,00 7.728.433,93\n"
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 81/12/2024\n"
        "1 CEDULA RURAL 19000368 CONTRAIDA JUNTO 37.905,24 0,00 39.654,62\n"
        "\n"
        "AO BANCO SANTANDER\n"
        "\n"
        "2 CONTRATOS BCO SANTANDER NRS 21001317 160.380,29 671.977,30 59.223,92\n"
        "LIBERACOES 02, 03 E 04/2021 TOTAL\n"
        "LIBERADO R$ 2.700.000,00 CUSTEIO RURAL\n"
        "2021 TENDO ASSUMIDO SALDO DO MESMO\n"
        "P/FINAL PARCERIA\n"
        "\n"
        "3 16,66% CONTRATO C 106213047 COOP DE 2.298,16 0,00 2.298,16\n"
        "CREDITO SICREDI CONTRAIDO 04/2021 VALOR\n"
        "TOTAL $ 830.317,36 LIQUIDADO EM 2024\n"
        "\n"
        "4 CPR SANTANDER 23002357 03/23 CNCTO 204.272,50 1.245.672,40 32.337,69\n"
        "FINAL 2025 TENDO ASSUMIDO SALDO P/CTA\n"
        "FINAL PARCERIA\n"
        "\n"
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
        "\n"
        "Página 16 de 21\n"
    )

    PAGE_17_TEXT = (
        "NOME: CLOVIS FELIX DE PAULA\n"
        "CPF: 604.382.581-34 IMPOSTO SOBRE A RENDA - PESSOA FÍSICA\n"
        "\n"
        "DECLARAÇÃO DE AJUSTE ANUAL EXERCÍCIO 2025 ANO-CALENDÁRIO 2024\n"
        "\n"
        "(Valores em Reais)\n"
        "\n"
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL\n"
        "\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "\n"
        "1 FINANCIAMENTO CEF P/CTA CONSTRUÇÃO 0,00 827.493,51 100.775,41\n"
        "BARRACAO, SILO E MAQUINÁRIOS CONTRATO\n"
        "2080556\n"
        "\n"
        "2 FINANCIAMENTO CEF P/CTA CONSTRUÇÃO 0,00 13.582.700,40 0,00\n"
        "BARRACAO, SILO E MAQUINÁRIOS CONTRATO\n"
        "2188715\n"
        "\n"
        "TOTAL 2.579.166,74 22.391.052,36 2.109.050,28\n"
        "\n"
        "Página 17 de 21\n"
    )

    # Gabarito: valores esperados para cada item (17 total)
    EXPECTED_ITEMS = [
        # Page 16 items (1-15)
        (1, 37905.24, 0.0, 39654.62),
        (2, 160380.29, 671977.3, 59223.92),
        (3, 2298.16, 0.0, 2298.16),
        (4, 204272.5, 1245672.4, 32337.69),
        (5, 101808.84, 509200.56, 26723.13),
        (6, 731605.92, 457822.22, 273788.7),
        (7, 804451.73, 0.0, 946172.8),
        (8, 536444.06, 0.0, 628080.85),
        (9, 0.0, 454624.1, 0.0),
        (10, 0.0, 358550.2, 0.0),
        (11, 0.0, 978780.56, 0.0),
        (12, 0.0, 668263.11, 0.0),
        (13, 0.0, 1415651.98, 0.0),
        (14, 0.0, 391368.63, 0.0),
        (15, 0.0, 828947.39, 0.0),
        # Page 17 items (1-2, continuation)
        (1, 0.0, 827493.51, 100775.41),
        (2, 0.0, 13582700.4, 0.0),
    ]

    def test_page16_extracts_15_items(self, extractor):
        """Página 16: deve extrair 15 itens (todos, incluindo 4-15)."""
        items = extractor._extract_from_page(self.PAGE_16_TEXT, 16)
        assert len(items) == 15, f"Esperado 15 itens, encontrou {len(items)}"

    def test_page17_extracts_2_items(self, extractor):
        """Página 17: deve extrair 2 itens."""
        items = extractor._extract_from_page(self.PAGE_17_TEXT, 17)
        assert len(items) == 2, f"Esperado 2 itens, encontrou {len(items)}"

    def test_full_extraction_17_items(self, extractor):
        """Pipeline completo: deve extrair 17 itens de ambas as páginas."""
        full_text = self.PAGE_16_TEXT + "\n" + self.PAGE_17_TEXT
        ctx = ExtractionContext(
            full_text=full_text,
            pages_text={16: self.PAGE_16_TEXT, 17: self.PAGE_17_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 17, (
            f"Esperado 17 itens, encontrou {len(result['items'])}"
        )

    def test_all_item_values_match_gabarito(self, extractor):
        """Verifica CADA valor de CADA item contra o gabarito."""
        full_text = self.PAGE_16_TEXT + "\n" + self.PAGE_17_TEXT
        ctx = ExtractionContext(
            full_text=full_text,
            pages_text={16: self.PAGE_16_TEXT, 17: self.PAGE_17_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        items = result["items"]

        for i, (exp_num, exp_before, exp_last, exp_paid) in enumerate(self.EXPECTED_ITEMS):
            item = items[i]
            assert item["item"] == exp_num, (
                f"Position {i}: esperado item {exp_num}, encontrou {item['item']}"
            )
            assert abs(item["year_before_last_value"] - exp_before) < 0.01, (
                f"Item {exp_num} pos {i}: year_before {item['year_before_last_value']} != {exp_before}"
            )
            assert abs(item["last_year_value"] - exp_last) < 0.01, (
                f"Item {exp_num} pos {i}: last_year {item['last_year_value']} != {exp_last}"
            )
            assert abs(item["paid_value_in_last_year"] - exp_paid) < 0.01, (
                f"Item {exp_num} pos {i}: paid {item['paid_value_in_last_year']} != {exp_paid}"
            )

    def test_section_totals_match(self, extractor):
        """Totais da seção devem bater com o gabarito."""
        full_text = self.PAGE_16_TEXT + "\n" + self.PAGE_17_TEXT
        ctx = ExtractionContext(
            full_text=full_text,
            pages_text={16: self.PAGE_16_TEXT, 17: self.PAGE_17_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        tv = result["total_values"]
        assert abs(tv["year_before_last_value"]["pdf_total"] - 2579166.74) < 0.01
        assert abs(tv["last_year_value"]["pdf_total"] - 22391052.36) < 0.01
        assert abs(tv["paid_value_in_last_year"]["pdf_total"] - 2109050.28) < 0.01

    def test_year_before_validated(self, extractor):
        """year_before_last_value deve estar validado (soma == pdf_total)."""
        full_text = self.PAGE_16_TEXT + "\n" + self.PAGE_17_TEXT
        ctx = ExtractionContext(
            full_text=full_text,
            pages_text={16: self.PAGE_16_TEXT, 17: self.PAGE_17_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        tv = result["total_values"]["year_before_last_value"]
        assert tv["valid"] is True, (
            f"year_before should be valid: amount={tv['amount']}, pdf_total={tv['pdf_total']}"
        )

    def test_last_year_validated(self, extractor):
        """last_year_value deve estar validado (soma == pdf_total)."""
        full_text = self.PAGE_16_TEXT + "\n" + self.PAGE_17_TEXT
        ctx = ExtractionContext(
            full_text=full_text,
            pages_text={16: self.PAGE_16_TEXT, 17: self.PAGE_17_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        tv = result["total_values"]["last_year_value"]
        assert tv["valid"] is True, (
            f"last_year should be valid: amount={tv['amount']}, pdf_total={tv['pdf_total']}"
        )

    def test_item2_description_has_total_in_text(self, extractor):
        """Item 2 deve ter TOTAL na descrição (parte do texto original)."""
        items = extractor._extract_from_page(self.PAGE_16_TEXT, 16)
        item2 = items[1]  # segundo item
        assert "TOTAL" in item2["description"]
        assert "LIBERACOES" in item2["description"]

    def test_item3_description_has_total_value(self, extractor):
        """Item 3 deve ter 'TOTAL $ 830.317,36' na descrição."""
        items = extractor._extract_from_page(self.PAGE_16_TEXT, 16)
        item3 = items[2]  # terceiro item
        assert "CONTRATO C 106213047" in item3["description"]

    def test_no_false_total_on_page16(self, extractor):
        """Página 16 NÃO deve ter total de seção (só tem na 17)."""
        totals = extractor._extract_section_total(self.PAGE_16_TEXT)
        assert totals == [], f"Page 16 should have no section total, got: {totals}"

    def test_real_total_on_page17(self, extractor):
        """Página 17 deve ter o total real com 3 valores."""
        totals = extractor._extract_section_total(self.PAGE_17_TEXT)
        assert len(totals) == 3
        assert abs(totals[0] - 2579166.74) < 0.01
        assert abs(totals[1] - 22391052.36) < 0.01
        assert abs(totals[2] - 2109050.28) < 0.01


class TestMatchTotalsToColumns:
    """Testes para _match_totals_to_columns — matching inteligente de totais parciais."""

    @pytest.fixture
    def extractor(self):
        return RuralDebtsExtractor()

    def test_3_values_positional(self, extractor):
        result = extractor._match_totals_to_columns(
            [100.0, 200.0, 300.0], 100.0, 200.0, 300.0
        )
        assert result == (100.0, 200.0, 300.0)

    def test_0_values_all_none(self, extractor):
        result = extractor._match_totals_to_columns(
            [], 100.0, 200.0, 300.0
        )
        assert result == (None, None, None)

    def test_2_values_before_and_paid(self, extractor):
        """Document AI perde last_year → match before e paid."""
        result = extractor._match_totals_to_columns(
            [2579166.74, 2109050.28],  # before e paid
            2372596.08,   # sum_before (mais próximo de 2579166.74)
            22391052.36,  # sum_last (muito longe dos 2 valores)
            2109050.28,   # sum_paid (match exato com 2109050.28)
        )
        assert result[0] == 2579166.74   # before
        assert result[1] is None         # last_year perdido pelo OCR
        assert result[2] == 2109050.28   # paid

    def test_2_values_last_and_paid(self, extractor):
        """Se before é 0 e os 2 valores são last e paid."""
        result = extractor._match_totals_to_columns(
            [500.0, 300.0],
            0.0,    # sum_before
            500.0,  # sum_last
            300.0,  # sum_paid
        )
        assert result == (None, 500.0, 300.0)

    def test_2_values_before_and_last(self, extractor):
        """Se paid é 0 e os 2 valores são before e last."""
        result = extractor._match_totals_to_columns(
            [100.0, 200.0],
            100.0,  # sum_before
            200.0,  # sum_last
            0.0,    # sum_paid
        )
        assert result == (100.0, 200.0, None)

    def test_1_value_matches_closest(self, extractor):
        result = extractor._match_totals_to_columns(
            [500.0],
            500.0,       # exact match
            10000.0,
            2000.0,
        )
        assert result == (500.0, None, None)


class TestDocumentAIRealOCRIntegration:
    """Teste de integração com texto OCR REAL do Document AI.

    Usa o texto EXATO produzido pelo Document AI ao processar o PDF
    '0215_IRPF_LOVIS - IRPF 2025 DECLARACAO.pdf' (pages 16-17).

    O Document AI produz texto com diferenças significativas do Tesseract:
    - Marcas d'água (SIGN, SIGILO, POR, PROTEGIDA, FISCAL) em linhas separadas
    - Espaços extras em '16,66 %', 'C / VCTO', 'P / CTA'
    - Item 3: perde year_before (2.298,16) → extrai só 2 valores
    - Item 4: perde year_before (204.272,50) → extrai só 2 valores
    - TOTAL com apenas 2 dos 3 valores (perde last_year 22.391.052,36)
    """

    PAGE_16_TEXT = (
        "NOME : CLOVIS FELIX DE PAULA\n"
        "CPF : 604.382.581-34 1MPOSTO SOBRE A RENDA - PESSOA FÍSICA\n"
        "DECLARAÇÃO DE AJUSTE ANUAL EXERCÍCIO 2025 ANO - CALENDÁRIO 2024\n"
        "16 VEICULO CAMIONETE TOYOTA HILUZ CD 4X4 RENAVAM 0,00 80.000,00\n"
        "00341795623 ANO 2011/11\n"
        "16 MOTOCICLETA YAMAHA / CROSSER Z ABS RENAVAM 01347164496 0,00 10.000,00\n"
        "2023/23\n"
        "16 VEICULO CAMINHONETE VW SAVEIRO CE RENAVAM 0,00 50.000,00\n"
        "00995046581 ANO 2013/14\n"
        "16 CAMINHAO M.BENS / ACTROS 2651S6X4 RENAVAM 01151933292 0,00 200.000,00\n"
        "ANO 2018/18\n"
        "11 GALPAO EQUIPAPADO COM SILO E MAQUINAS PARA USO NA 0,00 7.308.433,93\n"
        "AGROPECUARIA FISCAL\n"
        "TOTAL 0,00 7.728.433,93\n"
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL ( Valores em Reais )\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "1 CEDULA RURAL 19000368 CONTRAIDA JUNTO 37.905,24 0,00 39.654,62\n"
        "AO BANCO SANTANDER\n"
        "SIGN\n"
        "2 CONTRATOS BCO SANTANDER NRS 21001317 160.380,29 671.977,30 59.223,92\n"
        "LIBERACOES 02 , 03 E 04/2021 TOTAL\n"
        "LIBERADO R $ 2.700.000,00 CUSTEIO RURAL\n"
        "2021 TENDO ASSUMIDO SALDO DO MESMO\n"
        "P / FINAL PARCERIA\n"
        "3 16,66 % CONTRATO C 106213047 COOP DE POR 0,00 2.298,16\n"
        "CREDITO SICREDI CONTRAIDO 04/2021 VALOR\n"
        "TOTAL $ 830.317,36 LIQUIDADO EM 2024\n"
        "4 CPR SANTANDER 23002357 03/23 C / VCTO 1.245.672,40 32.337,69\n"
        "FINAL 2025 TENDO ASSUMIDO SALDO P / CTA\n"
        "FINAL PARCERIA\n"
        "5 1/6 CREDITO RURAL SICREDI BNDS C10010219 101.808,84 509.200,56 26.723,13\n"
        "CO 6 BB CUSTEIO AGROP 7538 731.605,92 457.822,22 273.783,70\n"
        "7 CPR BCO BRASIL 520575 804.451,73 0,00 946.172,80\n"
        "PROTEGIDA\n"
        "8 CPR BCO DO BRASIL 614744 536.444,06 0,00 628.080,85\n"
        "9 CONTRAIU CPR 24006218 BCO SANTANDE 0,00 454.624,10 0,00\n"
        "EM 06/24\n"
        "10 CONTRAIU CPR 24011767 BCO SANTANDER 0,00 358.550,20 0,00\n"
        "11/24\n"
        "11 CONTRAIU CUSTEIO PECUARIO SICREDI C 0,00 978.780,56 0,00\n"
        "4000078476 03/24\n"
        "12 CONTRAIU CPR BB 715634 0,00 668.263,11 0,00\n"
        "13 FINANCIAMENTO CEF P / CTA CONSTRUÇÃO 0,00 1.415.651,98 0,00\n"
        "BARRACAO , SILO E MAQUINÁRIOS CONTRATO\n"
        "1841873\n"
        "14 FINANCIAMENTO CEF P / CTA CONSTRUÇÃO 0,00 391.368,63 0,00\n"
        "BARRACAO , SILO E MAQUINÁRIOS CONTRATO\n"
        "1907544\n"
        "15 FINANCIAMENTO CEF P / CTA CONSTRUÇÃO 0,00 828.947,39 0,00\n"
        "BARRACAO , SILO E MAQUINÁRIOS CONTRATO\n"
        "1907545\n"
        "Página 16 de 21\n"
    )

    PAGE_17_TEXT = (
        "NOME : CLOVIS FELIX DE PAULA\n"
        "CPF : 604.382.581-34 1MPOSTO SOBRE A RENDA - PESSOA FÍSICA\n"
        "DECLARAÇÃO DE AJUSTE ANUAL EXERCÍCIO 2025 ANO - CALENDÁRIO 2024\n"
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL ( Valores em Reais )\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "1 FINANCIAMENTO CEF P / CTA CONSTRUÇÃO 0,00 827.493,51 100.775,41\n"
        "BARRACAO , SILO E MAQUINÁRIOS CONTRATO\n"
        "2080556\n"
        "2 FINANCIAMENTO CEF P / CTA CONSTRUÇÃO 0,00 13.582.700,40 0,00\n"
        "BARRACAO , SILO E MAQUINÁRIOS CONTRATO\n"
        "2188715 FISCAL\n"
        "TOTAL 2.579.166,74 2.109.050,28\n"
        "SIGILO\n"
        "POR\n"
        "PROTEGIDA\n"
        "Página 17 de 21\n"
    )

    @pytest.fixture
    def extractor(self):
        return RuralDebtsExtractor()

    @pytest.fixture
    def context(self):
        pages_text = {16: self.PAGE_16_TEXT, 17: self.PAGE_17_TEXT}
        full_text = self.PAGE_16_TEXT + "\n" + self.PAGE_17_TEXT
        return ExtractionContext(
            full_text=full_text, pages_text=pages_text, total_pages=21
        )

    def test_extracts_all_17_items(self, extractor, context):
        result = extractor.extract(context)
        assert result is not None
        assert len(result["items"]) == 17

    def test_item3_2val_parse(self, extractor, context):
        """Item 3: Document AI perde year_before, extrai 2 valores."""
        result = extractor.extract(context)
        item3 = result["items"][2]
        assert item3["item"] == 3
        # year_before perdido pelo OCR → 0.0 (fallback 2val)
        assert item3["year_before_last_value"] == 0.0
        assert abs(item3["paid_value_in_last_year"] - 2298.16) < 0.01

    def test_item4_2val_parse(self, extractor, context):
        """Item 4: Document AI perde year_before (204.272,50)."""
        result = extractor.extract(context)
        item4 = result["items"][3]
        assert item4["item"] == 4
        assert item4["year_before_last_value"] == 0.0
        assert abs(item4["last_year_value"] - 1245672.40) < 0.01
        assert abs(item4["paid_value_in_last_year"] - 32337.69) < 0.01

    def test_total_2val_detected(self, extractor):
        """TOTAL com 2 valores deve ser detectado."""
        totals = extractor._extract_section_total(self.PAGE_17_TEXT)
        assert len(totals) == 2
        assert abs(totals[0] - 2579166.74) < 0.01
        assert abs(totals[1] - 2109050.28) < 0.01

    def test_paid_total_validated(self, extractor, context):
        """paid deve ser validado corretamente (match exato com pdf_total)."""
        result = extractor.extract(context)
        paid = result["total_values"]["paid_value_in_last_year"]
        assert abs(paid["amount"] - 2109050.28) < 0.01
        assert abs(paid["pdf_total"] - 2109050.28) < 0.01
        assert paid["valid"] is True

    def test_year_before_total_assigned(self, extractor, context):
        """year_before pdf_total deve ser 2.579.166,74."""
        result = extractor.extract(context)
        yb = result["total_values"]["year_before_last_value"]
        assert abs(yb["pdf_total"] - 2579166.74) < 0.01
        # valid=False porque items 3 e 4 perderam year_before
        assert yb["valid"] is False

    def test_last_year_total_none(self, extractor, context):
        """last_year pdf_total deve ser None (OCR perdeu este valor)."""
        result = extractor.extract(context)
        ly = result["total_values"]["last_year_value"]
        assert ly["pdf_total"] is None
        assert ly["valid"] is None

    def test_watermarks_in_description_cleaned(self, extractor, context):
        """Watermarks (SIGN, PROTEGIDA, FISCAL) não devem aparecer na descrição."""
        result = extractor.extract(context)
        for item in result["items"]:
            desc = item["description"].upper()
            assert "SIGN" not in desc.split(), f"Item {item['item']}: SIGN in desc"
            assert "PROTEGIDA" not in desc.split(), f"Item {item['item']}: PROTEGIDA in desc"

    def test_co_prefix_cleaned(self, extractor, context):
        """Prefixo 'CO' antes do item 6 deve ser limpo."""
        result = extractor.extract(context)
        item6 = result["items"][5]
        assert item6["item"] == 6
        assert abs(item6["year_before_last_value"] - 731605.92) < 0.01


class TestBug17033MultilineItem:
    """Regressão #17033: item cuja descrição quebra antes dos valores (OCR wrap)
    não era extraído, fazendo sumir itens 4+ quando vários itens em sequência
    têm descrição longa."""

    PAGE_TEXT = (
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)\n"
        "ITEM DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM VALOR PAGO EM 2024\n"
        "31/12/2023 31/12/2024\n"
        "1 CEDULA RURAL 19000368 CONTRAIDA JUNTO AO BANCO SANTANDER 100.000,00 120.000,00 20.000,00\n"
        "2 CONTRATOS BCO SANTANDER 50.000,00 30.000,00 10.000,00\n"
        "3 16,66% CONTRATO C 106213047 COOP DE CREDITO SICREDI 40.000,00 20.000,00 5.000,00\n"
        "4 CPR SANTANDER 23002357 03/23 C/VCTO FINAL 2025 TENDO\n"
        "ASSUMIDO SALDO P/ FUTURA AQUISICAO 200.000,00 180.000,00 30.000,00\n"
        "5 CREDITO RURAL SICREDI BNDS C10010219\n"
        "60.000,00 45.000,00 8.000,00\n"
        "6 BB CUSTEIO AGROP 7538 80.000,00 70.000,00 10.000,00\n"
        "TOTAL 530.000,00 465.000,00 83.000,00\n"
    )

    def test_finds_all_6_items(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 1)
        nums = [i["item"] for i in items]
        assert nums == [1, 2, 3, 4, 5, 6]

    def test_item4_desc_joined_across_lines(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 1)
        item4 = next(i for i in items if i["item"] == 4)
        assert "CPR SANTANDER" in item4["description"]
        assert "ASSUMIDO SALDO" in item4["description"]
        assert item4["year_before_last_value"] == 200000.0
        assert item4["last_year_value"] == 180000.0
        assert item4["paid_value_in_last_year"] == 30000.0

    def test_item5_values_on_next_line(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 1)
        item5 = next(i for i in items if i["item"] == 5)
        assert "CREDITO RURAL SICREDI" in item5["description"]
        assert item5["year_before_last_value"] == 60000.0
        assert item5["last_year_value"] == 45000.0
        assert item5["paid_value_in_last_year"] == 8000.0

    def test_item6_still_parses_after_multiline(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 1)
        item6 = next(i for i in items if i["item"] == 6)
        assert item6["year_before_last_value"] == 80000.0
        assert item6["paid_value_in_last_year"] == 10000.0

