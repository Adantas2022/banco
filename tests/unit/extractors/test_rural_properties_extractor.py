"""Testes unitários para RuralPropertiesExtractor.

Bug #84111 - Área/CIB concatenados em name_and_location quando formato US.
Bug #89072 - Participants always null, area OCR comma→period, duplicate code.
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


class TestParticipantOCRSpaces:
    """Bug #89072: OCR adds spaces inside parentheses around CPF/CNPJ."""

    PAGE_TEXT = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "10 15,00 3 FAZENDA LAMBARI, CAMPOS DE JULIO/MT 1.200,0 4.695.449-0\n"
        "PARTICIPANTE ( S )\n"
        "JOAO DA SILVA ( 175.474.448-65 )\n"
        "Estrangeiro: Nao\n"
        "MARIA SOUZA ( 234.567.890-12 )\n"
        "Estrangeiro: Nao\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )

    def test_finds_2_participants(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert len(items) == 1
        assert items[0]["participants"] is not None
        assert len(items[0]["participants"]["items"]) == 2

    def test_participant_cpf_extracted(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        p = items[0]["participants"]["items"]
        assert p[0]["cpf"] == "175.474.448-65"
        assert p[1]["cpf"] == "234.567.890-12"

    def test_participant_name_formatted(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        p = items[0]["participants"]["items"]
        assert p[0]["participant_name"] == "JOAO DA SILVA (175.474.448-65)"

    def test_no_spaces_participants(self, extractor):
        """Regression: standard format without spaces still works."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 15,00 3 FAZENDA BOA VISTA 800,0 1.234.567-8\n"
            "PARTICIPANTE(S)\n"
            "PEDRO ALVES (111.222.333-44)\n"
            "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
        )
        items = extractor._extract_from_page(page, 10, set())
        assert items[0]["participants"] is not None
        assert items[0]["participants"]["items"][0]["cpf"] == "111.222.333-44"


class TestAreaOCRCommaAsPeriod:
    """Bug #89072: OCR renders comma as period in area values."""

    def test_normalize_area_value(self, extractor):
        assert extractor._normalize_area_value("1.200.0") == "1.200,0"
        assert extractor._normalize_area_value("3.595.1") == "3.595,1"

    def test_no_change_normal_br(self, extractor):
        assert extractor._normalize_area_value("1.200,0") == "1.200,0"

    def test_no_change_us_format(self, extractor):
        assert extractor._normalize_area_value("800.0") == "800.0"

    def test_no_change_simple_number(self, extractor):
        assert extractor._normalize_area_value("100") == "100"

    def test_area_parsed_correctly(self, extractor):
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 15,00 3 FAZENDA LAMBARI 1.200.0 4.695.449-0\n"
            "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
        )
        items = extractor._extract_from_page(page, 10, set())
        assert len(items) == 1
        assert items[0]["area"] == 1200.0


class TestDuplicateCodeOCR:
    """Bug #89072: OCR duplicates the property code digit."""

    PAGE_TEXT = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "10 10   15,00   3   FAZENDA VENTANIA 800,0 1.234.567-8\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )

    def test_parses_despite_duplicate_code(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert len(items) == 1

    def test_code_is_correct(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert items[0]["code"] == 10

    def test_name_correct(self, extractor):
        items = extractor._extract_from_page(self.PAGE_TEXT, 10, set())
        assert "FAZENDA VENTANIA" in items[0]["name_and_location"]


class TestPageBoundaryParticipants:
    """Bug #89072: Participants split across page boundary."""

    PAGE1_TEXT = (
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "10 15,00 3 FAZENDA LAMBARI 1.200,0 4.695.449-0\n"
        "PARTICIPANTE(S)\n"
        "JOAO DA SILVA (175.474.448-65)\n"
    )
    PAGE2_TEXT = (
        "MARIA SOUZA ( 234.567.890-12 )\n"
        "Estrangeiro: Nao\n"
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
        "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
        "11 50,00 1 FAZENDA BOA VISTA 500,0 2.345.678-9\n"
        "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
    )

    def test_page_boundary_participant_merged(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE1_TEXT + "\n" + self.PAGE2_TEXT,
            pages_text={10: self.PAGE1_TEXT, 11: self.PAGE2_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        assert result is not None
        prop10 = [i for i in result["items"] if i["code"] == 10][0]
        assert prop10["participants"] is not None
        assert len(prop10["participants"]["items"]) == 2

    def test_page2_property_also_extracted(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE1_TEXT + "\n" + self.PAGE2_TEXT,
            pages_text={10: self.PAGE1_TEXT, 11: self.PAGE2_TEXT},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        assert result["total_properties"] == 2


class TestPhantomCodeOCR:
    """Bug #90071: OCR insere phantom digits entre código e participação.

    Exemplo: '10 110  100,00  1  FAZENDA...' - o '110' é artefato OCR.
    """

    def test_normalize_removes_phantom(self, extractor):
        line = "10 110         100,00                1            FAZENDA SAO VICENTE"
        result = extractor._normalize_ocr_code_line(line)
        assert "110" not in result
        assert result.startswith("10 ")

    def test_normalize_keeps_dedup(self, extractor):
        """Regressão: dedup exato '10 10' ainda funciona."""
        line = "10 10   100,00   1   SEM DENOMINACAO"
        result = extractor._normalize_ocr_code_line(line)
        assert not result.startswith("10 10 ")
        assert result.startswith("10 ")

    def test_normalize_no_change_normal(self, extractor):
        line = "10 100,00 1 FAZENDA LAMBARI 800,0 1.234.567-8"
        result = extractor._normalize_ocr_code_line(line)
        assert result == line

    def test_extracts_item_with_phantom_code(self, extractor):
        """Item com phantom '110' deve ser extraído corretamente."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 110         100,00                1            FAZENDA SAO VICENTE , SANTOS REIS - SAO     36,7         4.149.803-8\n"
            "BORJA - RS\n"
            "RECEITAS E DESPESAS - BRASIL (Valores em Reais)\n"
        )
        items = extractor._extract_from_page(page, 22, set())
        assert len(items) == 1
        assert items[0]["code"] == 10
        assert items[0]["participation"] == 100.0
        assert items[0]["area"] == 36.7
        assert items[0]["cib"] == "4.149.803-8"
        assert "FAZENDA SAO VICENTE" in items[0]["name_and_location"]


class TestBug17029AreaNoCib:
    """Bug #17029: area absorvida no name_and_location quando não existe CIB.

    O OCR intercala o valor da area entre as partes do nome quando a coluna
    CIB está vazia. A regex _AREA_CIB_TAIL_RE falha e a area vira parte do nome.
    """

    def test_area_at_end_no_cib(self, extractor):
        """Area no final do remaining, sem CIB."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 100,00 1 SAO BORJA - MATRICULA 10151, SAO BORJA 277,2\n"
            "RECEITAS E DESPESAS - BRASIL\n"
        )
        items = extractor._extract_from_page(page, 28, set())
        assert len(items) == 1
        assert items[0]["area"] == 277.2
        assert "277" not in items[0]["name_and_location"]
        assert "SAO BORJA" in items[0]["name_and_location"]

    def test_area_mid_text_small(self, extractor):
        """Area intercalada no meio do nome pelo OCR (valor pequeno)."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 100,00 1 SAO BORJA - MATRICULA 2042, SAO BORJA - 1,9 RS\n"
            "RECEITAS E DESPESAS - BRASIL\n"
        )
        items = extractor._extract_from_page(page, 28, set())
        assert len(items) == 1
        assert items[0]["area"] == 1.9
        assert "1,9" not in items[0]["name_and_location"]
        assert "SAO BORJA" in items[0]["name_and_location"]
        assert "RS" in items[0]["name_and_location"]

    def test_area_mid_text_large(self, extractor):
        """Area intercalada no meio do nome pelo OCR (valor grande com milhar)."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 100,00 1 SAO NICOLAU - MATRICULA 978, SAO 4.696,0 NICOLAU -RS\n"
            "RECEITAS E DESPESAS - BRASIL\n"
        )
        items = extractor._extract_from_page(page, 28, set())
        assert len(items) == 1
        assert items[0]["area"] == 4696.0
        assert "4.696" not in items[0]["name_and_location"]
        assert "SAO NICOLAU" in items[0]["name_and_location"]
        assert "NICOLAU -RS" in items[0]["name_and_location"]

    def test_area_with_cib_still_works(self, extractor):
        """Regressão: items COM CIB continuam funcionando normalmente."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 100,00 1 FAZENDA SOSSEGO, RODOVIA BR 163 540,9 6.231.817-9\n"
            "RECEITAS E DESPESAS - BRASIL\n"
        )
        items = extractor._extract_from_page(page, 28, set())
        assert len(items) == 1
        assert items[0]["area"] == 540.9
        assert items[0]["cib"] == "6.231.817-9"
        assert "540" not in items[0]["name_and_location"]

    def test_area_mid_with_continuation_line(self, extractor):
        """Area no meio + continuação do nome na próxima linha."""
        page = (
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL\n"
            "CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB\n"
            "10 100,00 1 LINHA DO RIO - MATRICULA 489, GUARANI 3,9 DASMISSOES\n"
            "RECEITAS E DESPESAS - BRASIL\n"
        )
        items = extractor._extract_from_page(page, 28, set())
        assert len(items) == 1
        assert items[0]["area"] == 3.9
        assert "3,9" not in items[0]["name_and_location"]
        assert "GUARANI" in items[0]["name_and_location"]
        assert "DASMISSOES" in items[0]["name_and_location"]

