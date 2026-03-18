import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.rural.assets import RuralAssetsExtractor


@pytest.fixture
def extractor():
    return RuralAssetsExtractor()


def _make_context(pages: dict[int, str]) -> ExtractionContext:
    full_text = "\n".join(pages.values())
    return ExtractionContext(full_text=full_text, pages_text=pages, total_pages=len(pages))


SECTION_HEADER = "BENS DA ATIVIDADE RURAL - BRASIL (Valores em Reais)"
ITEM_HEADER = "CÓDIGO DISCRIMINAÇÃO SITUAÇÃO EM SITUAÇÃO EM"


def _make_section_text(*item_lines: str) -> str:
    lines = [SECTION_HEADER, ITEM_HEADER, "31/12/2022 31/12/2023"]
    lines.extend(item_lines)
    lines.append("TOTAL 0,00 0,00")
    lines.append("DÍVIDAS VINCULADAS À ATIVIDADE RURAL")
    return "\n".join(lines)


class TestItemCodeRegex:

    def test_nf_number_not_treated_as_new_item(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR SLC JOHN DEERE 7500 ADQ. EM 22/08/2000 CFE NF 0,00 0,00",
            "12964 DA APOIO RURAL NO VALOR DE R$ 75000,00",
            "(FINANCIADO).",
            "17 GRADE TATU ANO 88. 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        codes = [item["code"] for item in result["items"]]
        assert "12964" not in codes
        assert codes.count("16") == 1
        assert codes.count("17") == 1
        assert len(result["items"]) == 2

    def test_year_not_treated_as_new_item(self, extractor):
        page_text = _make_section_text(
            "99 25% DO SALDO EM COTA CAPITAL JUNTO AO SICREDI 87.624,85 98.657,83",
            "DE LUCIO M.B. BASSO. SALDO: EM 2021 R$ 310.386,34; EM 2022",
            "R$ 350.499,40; EM 2023 R$ 394.631,33.",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        codes = [item["code"] for item in result["items"]]
        assert "2022" not in codes
        assert len(result["items"]) == 1

    def test_large_nf_number_not_treated_as_new_item(self, extractor):
        page_text = _make_section_text(
            "17 COLHEITADEIRA MF 38 GTH ADQ. DE AGCO DO BRASIL CFE NF 0,00 0,00",
            "9305 EM 03/2002 NO VALOR DE R$ 320.000,00.",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        codes = [item["code"] for item in result["items"]]
        assert "9305" not in codes
        assert len(result["items"]) == 1

    def test_valid_two_digit_code_is_new_item(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR VALMET 138X4 EQUIP. ADQ. 12/86. 0,00 0,00",
            "17 GRADE TATU ANO 88. 0,00 0,00",
            "11 CONSTRUCAO DE GALPAO NA FAZ. RECANTO. 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 3
        codes = [item["code"] for item in result["items"]]
        assert codes == ["16", "17", "11"]


class TestMultiLineDescription:

    def test_three_line_item_produces_single_item(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR SLC JOHN DEERE 7500 ADQ. EM 22/08/2000 CFE NF 0,00 0,00",
            "12964 DA APOIO RURAL NO VALOR DE R$ 75000,00",
            "(FINANCIADO).",
            "17 GRADE TATU ANO 88. 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        trator = [i for i in result["items"] if i["code"] == "16"][0]
        assert "12964 DA APOIO RURAL" in trator["description"]
        assert "(FINANCIADO)" in trator["description"]

    def test_cooperative_share_with_year_value_pairs(self, extractor):
        page_text = _make_section_text(
            "99 25% DO SALDO EM COTA CAPITAL JUNTO AO SICREDI EM NOME 87.624,85 98.657,83",
            "DE LUCIO M.B. BASSO. SALDO: EM 2021 R$ 310.386,34; EM 2022",
            "R$ 350.499,40; EM 2023 R$ 394.631,33.",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["code"] == "99"
        assert item["year_before_last_value"] == 87624.85
        assert item["last_year_value"] == 98657.83
        assert "LUCIO M.B. BASSO" in item["description"]
        assert "394.631,33" in item["description"]


class TestTotalInDescription:

    def test_item_with_total_in_description_is_not_skipped(self, extractor):
        page_text = _make_section_text(
            "17 TRONCO PARECE MOVEL, MODELO TOTAL FLEX, NR DE SERIE 0,00 0,00",
            "PM-0879 ANO DE FABRICACAO 2019, ADQ EM 14/05/2019 DE",
            "TERRA BOA MAQUINAS AGRICOLAS LTDA 17.897.655/0001-07, NF",
            "7048, PELO VALOR DE R$ 35.000,00.",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        items = result["items"]
        assert len(items) == 1
        assert items[0]["code"] == "17"
        assert "TRONCO PARECE MOVEL" in items[0]["description"]
        assert "TOTAL FLEX" in items[0]["description"]

    def test_actual_total_row_still_stops_parsing(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR ANO 86. 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1


class TestEndMarkerCaseSensitivity:

    def test_end_marker_uppercase(self, extractor):
        page_text = (
            SECTION_HEADER + "\n"
            + ITEM_HEADER + "\n"
            + "16 TRATOR ANO 86. 0,00 0,00\n"
            + "TOTAL 0,00 0,00\n"
            + "DÍVIDAS VINCULADAS À ATIVIDADE RURAL\n"
            + "99 SHOULD NOT BE EXTRACTED 100,00 200,00\n"
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == "16"

    def test_end_marker_mixed_case(self, extractor):
        page_text = (
            SECTION_HEADER + "\n"
            + ITEM_HEADER + "\n"
            + "16 TRATOR ANO 86. 0,00 0,00\n"
            + "TOTAL 0,00 0,00\n"
            + "Dívidas Vinculadas à Atividade Rural\n"
            + "99 SHOULD NOT BE EXTRACTED 100,00 200,00\n"
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1

    def test_end_marker_no_accents(self, extractor):
        page_text = (
            SECTION_HEADER + "\n"
            + ITEM_HEADER + "\n"
            + "16 TRATOR ANO 86. 0,00 0,00\n"
            + "TOTAL 0,00 0,00\n"
            + "DIVIDAS VINCULADAS A ATIVIDADE RURAL\n"
            + "99 SHOULD NOT BE EXTRACTED 100,00 200,00\n"
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1
