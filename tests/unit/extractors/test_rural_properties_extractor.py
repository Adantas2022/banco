"""Testes unitários para RuralPropertiesExtractor.

Bug #84111 - Área/CIB concatenados em name_and_location quando formato US.
"""

import pytest
from irpf_processor.infrastructure.extraction.extractors.rural.properties import (
    RuralPropertiesExtractor,
)
from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext


@pytest.fixture
def extractor():
    return RuralPropertiesExtractor()


class TestBug84111USAreaFormat:
    """Bug #84111: Área em formato US (800.0) não era parseada.

    Área/CIB eram concatenados no name_and_location. Fix: regex de área
    aceita tanto BR (800,0) quanto US (800.0).
    """

    PAGE_TEXT = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB (Nirf)\n"
        "ATIVIDADE (%) EXPLORAÇÃO (na)\n"
        "10 100.00 1 MÁQUINAS DE CULTURA DE SOLO, MATO 800.0 2.345.566-7\n"
        "GROSSO\n"
        "13 100.00 4 EXPLORAÇÃO DE AVES, SANTA CATARINA 400.0 3.456.435-7\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )

    def test_finds_2_items(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        assert len(items) == 2

    def test_item1_area_not_zero(self, extractor):
        """Bug #84111: area deve ser 800.0, não 0.0."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        assert items[0]["area"] == 800.0

    def test_item1_cib(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        assert items[0]["cib"] == "2.345.566-7"

    def test_item1_name_clean(self, extractor):
        """name_and_location NÃO deve conter área/CIB."""
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        name = items[0]["name_and_location"]
        assert "800.0" not in name
        assert "2.345.566-7" not in name
        assert "MATO GROSSO" in name

    def test_item2_area(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        assert items[1]["area"] == 400.0

    def test_item2_cib(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        assert items[1]["cib"] == "3.456.435-7"

    def test_item2_name_clean(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 14, set())
        name = items[1]["name_and_location"]
        assert "400.0" not in name
        assert "3.456.435-7" not in name
        assert "SANTA CATARINA" in name

    def test_total_area(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={14: self.PAGE_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert result["total_area"] == 1200.0


class TestBRAreaFormat:
    """Regressão: formato BR (800,0) deve continuar funcionando."""

    PAGE_TEXT = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "10 15,00 3 FAZENDA LAMBARI, CAMPOS DE JULIO/MT 1.200,0 4.695.449-0\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )

    def test_finds_item(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert len(items) == 1

    def test_area_br_format(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert items[0]["area"] == 1200.0

    def test_cib_br_format(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert items[0]["cib"] == "4.695.449-0"

    def test_name_clean(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert "FAZENDA LAMBARI" in items[0]["name_and_location"]
        assert "1.200" not in items[0]["name_and_location"]
