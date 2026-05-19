from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.rural.assets import (
    RuralAssetsExtractor,
)

MODULE_PATH = "irpf_processor.infrastructure.extraction.extractors.rural.assets"


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


def _make_llm_context(
    pages: dict[int, str] | None = None,
    document_id: str = "test-doc",
) -> ExtractionContext:
    pages = pages or {1: "BENS DA ATIVIDADE RURAL - BRASIL (Valores em Reais)"}
    full_text = "\n".join(pages.values())
    return ExtractionContext(
        full_text=full_text,
        pages_text=pages,
        total_pages=len(pages),
        document_id=document_id,
    )


def _make_chunk(
    items: list[dict] | None = None,
    year_before_last_total_value: float | None = None,
    last_year_total_value: float | None = None,
) -> dict[str, Any]:
    chunk: dict[str, Any] = {"items": items if items is not None else []}
    if year_before_last_total_value is not None:
        chunk["year_before_last_total_value"] = year_before_last_total_value
    if last_year_total_value is not None:
        chunk["last_year_total_value"] = last_year_total_value
    return chunk


def _make_item(
    code: str = "1",
    description: str = "TRATOR JOHN DEERE",
    year_before_last_value: float = 0.0,
    last_year_value: float = 0.0,
    page: int = 1,
) -> dict[str, Any]:
    return {
        "code": code,
        "description": description,
        "year_before_last_value": year_before_last_value,
        "last_year_value": last_year_value,
        "page": page,
    }


def _apply_llm_mocks(
    stack: ExitStack,
    extractor: RuralAssetsExtractor,
    chunks: Any,
    section_pages: dict[int, str] | None = None,
) -> None:
    if section_pages is None:
        section_pages = {1: "BENS DA ATIVIDADE RURAL - BRASIL"}
    stack.enter_context(
        patch.object(
            extractor,
            "get_llm_extraction_data",
            new_callable=AsyncMock,
            return_value=chunks,
        )
    )
    stack.enter_context(
        patch.object(extractor, "extract_section_pages", return_value=section_pages)
    )
    stack.enter_context(patch(f"{MODULE_PATH}.os.makedirs"))
    stack.enter_context(patch("builtins.open", mock_open()))


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

    def test_last_item_description_line_starting_with_total_keyword(self, extractor):
        """Regressão #17034: último item com descrição de 3 linhas em que a
        segunda linha começa com 'TOTAL DE' — antes da fix, o break em
        startswith('TOTAL') truncava a descrição para 2 linhas."""
        page_text = _make_section_text(
            "16 FAZENDA SANTA RITA COM 500 HECTARES 100.000,00 200.000,00",
            "ADQUIRIDA DE SANTA LTDA EM 15/03/2020",
            "TOTAL DE BENFEITORIAS INCLUIDAS NO VALOR DE R$ 50.000,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        items = result["items"]
        assert len(items) == 1
        desc = items[0]["description"]
        assert "FAZENDA SANTA RITA" in desc
        assert "ADQUIRIDA DE SANTA LTDA" in desc
        assert "TOTAL DE BENFEITORIAS" in desc


class TestBug16736PhantomItems:
    """Regressão #16736: linhas de continuação começando com preposição/mês +
    valor no fim (ex: "12 DE ABRIL DE 2022 R$ 50.000,00") eram classificadas
    como novo item, gerando phantom com código 12 e descrição "DE ABRIL DE…"."""

    def test_date_fragment_not_treated_as_new_item(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR JOHN DEERE 6125J 213.000,00 0,00",
            "12 DE ABRIL DE 2022 R$ 50.000,00",
            "16 COLHEITADEIRA MF 9120 500.000,00 100.000,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)
        assert result is not None
        items = result["items"]
        codes = [i["code"] for i in items]
        assert "12" not in codes
        assert codes == ["16", "16"]

    def test_preposition_fragment_not_item(self, extractor):
        page_text = _make_section_text(
            "16 GADO DE CORTE EM FAZENDA SANTA RITA 100.000,00 120.000,00",
            "21 E 22 DE DEZEMBRO R$ 35.000",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == "16"

    def test_valor_fragment_not_item(self, extractor):
        page_text = _make_section_text(
            "16 UMA COLHEITADEIRA CASE AXIAL 500.000,00 300.000,00",
            "15 VALOR TOTAL PAGO CONFORME NF 8.900,50",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == "16"

    def test_adq_fragment_not_item(self, extractor):
        page_text = _make_section_text(
            "17 TRATOR AGRICOLA NEW HOLLAND T7 200.000,00 150.000,00",
            "10 ADQ EM 15/03/2020 JOAO SILVA 75.000",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == "17"

    def test_real_items_still_parsed(self, extractor):
        """Não introduzir falso negativo: descrições reais iniciadas por
        substantivo/adjetivo continuam sendo capturadas."""
        page_text = _make_section_text(
            "16 CASA SEDE 100.000,00 110.000,00",
            "17 TRATOR JOHN DEERE 200.000,00 180.000,00",
            "11 CONSTRUCAO GALPAO NA FAZ. 50.000,00 55.000,00",
            "99 BENFEITORIAS EM AREA 20.000,00 25.000,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 4
        assert [i["code"] for i in result["items"]] == ["16", "17", "11", "99"]


class TestZeroColumnValueRecovery:
    def test_maybe_recover_from_line_with_trailing_zero_columns(self, extractor):
        nb, nl, nd = extractor._maybe_recover_zero_columns(
            "16 PRANCHA MARITIMA HYDRA 250.000,00 0,00 0,00",
            "PRANCHA MARITIMA HYDRA 250.000,00",
            0.0,
            0.0,
        )
        assert nb == pytest.approx(250000.0)
        assert nl == pytest.approx(250000.0)
        assert "250.000,00" not in nd
        assert "PRANCHA MARITIMA HYDRA" in nd

    def test_maybe_recover_skips_when_columns_already_filled(self, extractor):
        nb, nl, nd = extractor._maybe_recover_zero_columns(
            "16 FAZENDA 100.000,00 200.000,00",
            "FAZENDA",
            100000.0,
            200000.0,
        )
        assert nb == pytest.approx(100000.0)
        assert nl == pytest.approx(200000.0)
        assert nd == "FAZENDA"

    def test_extract_last_item_recovers_value_stuck_in_description(self, extractor):
        page_text = _make_section_text(
            "16 PLANTADEIRA SEMEATO 90.000,00 90.000,00",
            "16 CAMIONETE FORD 45.000,00 45.000,00",
            "16 PRANCHA MARITIMA HYDRA 250.000,00 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 3
        last = result["items"][-1]
        assert last["code"] == "16"
        assert last["year_before_last_value"] == pytest.approx(250000.0)
        assert last["last_year_value"] == pytest.approx(250000.0)
        assert "250.000,00" not in last["description"]
        assert "PRANCHA MARITIMA HYDRA" in last["description"]

    def test_extract_item_with_valid_columns_unchanged(self, extractor):
        page_text = _make_section_text(
            "16 FAZENDA SANTA RITA 100.000,00 200.000,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        item = result["items"][0]
        assert item["year_before_last_value"] == pytest.approx(100000.0)
        assert item["last_year_value"] == pytest.approx(200000.0)


class TestEndMarkerCaseSensitivity:
    def test_end_marker_uppercase(self, extractor):
        page_text = (
            SECTION_HEADER
            + "\n"
            + ITEM_HEADER
            + "\n"
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
            SECTION_HEADER
            + "\n"
            + ITEM_HEADER
            + "\n"
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
            SECTION_HEADER
            + "\n"
            + ITEM_HEADER
            + "\n"
            + "16 TRATOR ANO 86. 0,00 0,00\n"
            + "TOTAL 0,00 0,00\n"
            + "DIVIDAS VINCULADAS A ATIVIDADE RURAL\n"
            + "99 SHOULD NOT BE EXTRACTED 100,00 200,00\n"
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 1


class TestRegexRegressionWithInit:
    def test_init_sets_section_tracking_attributes(self, extractor):
        assert extractor._section_started is False
        assert extractor._section_start_page == -1

    def test_regex_extract_produces_identical_output_after_init(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR VALMET 138X4 EQUIP. ADQ. 12/86. 0,00 0,00",
            "17 GRADE TATU ANO 88. 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) == 2
        assert result["items"][0]["code"] == "16"
        assert result["items"][1]["code"] == "17"
        assert result["section_name"] == "Bens da Atividade Rural - Brasil"
        assert "extraction_method" not in result
        assert "total_values" in result


class TestConfigToggleBehavior:
    def test_llm_extraction_disabled_by_default(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                llm_extraction_rural_activity_assets_in_brazil=False
            )
            assert extractor.llm_extraction_enabled is False

    def test_llm_extraction_enabled_when_toggle_true(self, extractor):
        with patch(
            "irpf_processor.infrastructure.extraction.extractors.base.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                llm_extraction_rural_activity_assets_in_brazil=True
            )
            assert extractor.llm_extraction_enabled is True


class TestSingleChunkExtraction:
    async def test_single_chunk_returns_correct_structure(self, extractor):
        ctx = _make_llm_context()
        items = [
            _make_item(
                code="1",
                description="TRATOR",
                year_before_last_value=100.0,
                last_year_value=200.0,
            ),
            _make_item(
                code="2",
                description="GRADE",
                year_before_last_value=50.0,
                last_year_value=75.0,
            ),
        ]
        chunks = [
            _make_chunk(
                items=items,
                year_before_last_total_value=150.0,
                last_year_total_value=275.0,
            )
        ]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert result["section_name"] == "Bens da Atividade Rural - Brasil"
        assert result["extraction_method"] == "llm"
        assert len(result["items"]) == 2
        assert result["items"][0]["code"] == "1"
        assert result["items"][1]["code"] == "2"
        assert "total_values" in result


class TestMultiChunkMergeWithOverlap:
    async def test_overlap_page_items_replaced_by_later_chunk(self, extractor):
        ctx = _make_llm_context(pages={1: "p1", 2: "p2", 3: "p3"})
        chunk1_items = [
            _make_item(
                code="1",
                description="TRATOR",
                year_before_last_value=100.0,
                last_year_value=200.0,
                page=1,
            ),
            _make_item(
                code="2",
                description="GRADE OLD",
                year_before_last_value=50.0,
                last_year_value=75.0,
                page=2,
            ),
        ]
        chunk2_items = [
            _make_item(
                code="2",
                description="GRADE NEW",
                year_before_last_value=60.0,
                last_year_value=80.0,
                page=2,
            ),
            _make_item(
                code="3",
                description="ARADO",
                year_before_last_value=30.0,
                last_year_value=40.0,
                page=3,
            ),
        ]
        chunks = [
            _make_chunk(items=chunk1_items),
            _make_chunk(
                items=chunk2_items,
                year_before_last_total_value=190.0,
                last_year_total_value=320.0,
            ),
        ]
        section_pages = {1: "p1", 2: "p2", 3: "p3"}

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks, section_pages)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert len(result["items"]) == 3
        page2_items = [i for i in result["items"] if i["page"] == 2]
        assert len(page2_items) == 1
        assert page2_items[0]["description"] == "GRADE NEW"
        assert page2_items[0]["year_before_last_value"] == 60.0


class TestExceptionFallback:
    async def test_exception_in_llm_data_returns_none(self, extractor):
        ctx = _make_llm_context()
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    extractor,
                    "get_llm_extraction_data",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("LLM service unavailable"),
                )
            )
            stack.enter_context(patch(f"{MODULE_PATH}.os.makedirs"))
            stack.enter_context(patch("builtins.open", mock_open()))
            result = await extractor.extract_with_llm(ctx)

        assert result is None

    async def test_exception_in_section_pages_returns_none(self, extractor):
        ctx = _make_llm_context()
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    extractor,
                    "get_llm_extraction_data",
                    new_callable=AsyncMock,
                    return_value=[{"items": []}],
                )
            )
            stack.enter_context(
                patch.object(
                    extractor,
                    "extract_section_pages",
                    side_effect=ValueError("bad pages"),
                )
            )
            stack.enter_context(patch(f"{MODULE_PATH}.os.makedirs"))
            stack.enter_context(patch("builtins.open", mock_open()))
            result = await extractor.extract_with_llm(ctx)

        assert result is None


class TestEmptyItemsFallback:
    async def test_none_from_llm_returns_none(self, extractor):
        ctx = _make_llm_context()
        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, None)
            result = await extractor.extract_with_llm(ctx)

        assert result is None

    async def test_non_list_from_llm_returns_none(self, extractor):
        ctx = _make_llm_context()
        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, "not a list")
            result = await extractor.extract_with_llm(ctx)

        assert result is None

    async def test_empty_list_from_llm_returns_none(self, extractor):
        ctx = _make_llm_context()
        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, [])
            result = await extractor.extract_with_llm(ctx)

        assert result is None


class TestItemNormalization:
    def test_float_currency_passes_through(self, extractor):
        item = _make_item(year_before_last_value=1234.56, last_year_value=7890.12)
        result = extractor._normalize_llm_item(item, [1])
        assert result["year_before_last_value"] == 1234.56
        assert result["last_year_value"] == 7890.12

    def test_string_code_preserved(self, extractor):
        item = _make_item(code="16")
        result = extractor._normalize_llm_item(item, [1])
        assert result["code"] == "16"

    def test_whitespace_in_description_collapsed(self, extractor):
        item = _make_item(description="  TRATOR   JOHN    DEERE  ")
        result = extractor._normalize_llm_item(item, [1])
        assert result["description"] == "TRATOR JOHN DEERE"

    def test_currency_above_1b_set_to_zero(self, extractor):
        item = _make_item(year_before_last_value=2_000_000_000.0, last_year_value=500.0)
        result = extractor._normalize_llm_item(item, [1])
        assert result["year_before_last_value"] == 0.0
        assert result["last_year_value"] == 500.0

    def test_item_has_id_field(self, extractor):
        item = _make_item(code="1", description="TRATOR JOHN DEERE")
        result = extractor._normalize_llm_item(item, [1])
        assert "id" in result
        assert isinstance(result["id"], str)
        assert len(result["id"]) > 0


class TestIntraChunkDedup:
    async def test_duplicate_ids_keep_last_occurrence(self, extractor):
        ctx = _make_llm_context()
        items = [
            _make_item(
                code="1",
                description="TRATOR JOHN DEERE",
                year_before_last_value=100.0,
                last_year_value=200.0,
            ),
            _make_item(
                code="1",
                description="TRATOR JOHN DEERE",
                year_before_last_value=150.0,
                last_year_value=250.0,
            ),
        ]
        chunks = [
            _make_chunk(
                items=items,
                year_before_last_total_value=150.0,
                last_year_total_value=250.0,
            )
        ]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["year_before_last_value"] == 150.0
        assert result["items"][0]["last_year_value"] == 250.0


class TestPageValidation:
    def test_zero_page_clamped_to_first(self, extractor):
        item = _make_item(page=0)
        result = extractor._normalize_llm_item(item, [3, 4, 5])
        assert result["page"] == 3

    def test_negative_page_clamped_to_first(self, extractor):
        item = _make_item(page=-1)
        result = extractor._normalize_llm_item(item, [3, 4, 5])
        assert result["page"] == 3

    def test_page_below_range_clamped(self, extractor):
        item = _make_item(page=1)
        result = extractor._normalize_llm_item(item, [3, 4, 5])
        assert result["page"] == 3

    def test_page_above_range_clamped(self, extractor):
        item = _make_item(page=10)
        result = extractor._normalize_llm_item(item, [3, 4, 5])
        assert result["page"] == 5

    def test_page_within_range_unchanged(self, extractor):
        item = _make_item(page=4)
        result = extractor._normalize_llm_item(item, [3, 4, 5])
        assert result["page"] == 4

    def test_string_page_converted(self, extractor):
        item = _make_item()
        item["page"] = "3"
        result = extractor._normalize_llm_item(item, [1, 2, 3])
        assert result["page"] == 3

    def test_empty_page_range_no_clamping(self, extractor):
        item = _make_item(page=99)
        result = extractor._normalize_llm_item(item, [])
        assert result["page"] == 99


class TestCodeValidation:
    def test_empty_code_still_included(self, extractor):
        item = _make_item(code="")
        result = extractor._normalize_llm_item(item, [1])
        assert result["code"] == ""

    def test_non_numeric_code_still_included(self, extractor):
        item = _make_item(code="abc")
        result = extractor._normalize_llm_item(item, [1])
        assert result["code"] == "abc"

    def test_code_above_99_still_included(self, extractor):
        item = _make_item(code="100")
        result = extractor._normalize_llm_item(item, [1])
        assert result["code"] == "100"

    def test_valid_code_preserved(self, extractor):
        item = _make_item(code="16")
        result = extractor._normalize_llm_item(item, [1])
        assert result["code"] == "16"


class TestNonDictEntrySkip:
    async def test_none_entry_skipped(self, extractor):
        ctx = _make_llm_context()
        chunk = {
            "items": [
                None,
                _make_item(
                    code="1",
                    description="TRATOR",
                    year_before_last_value=100.0,
                    last_year_value=200.0,
                ),
            ],
            "year_before_last_total_value": 100.0,
            "last_year_total_value": 200.0,
        }

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, [chunk])
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == "1"

    async def test_string_entry_skipped(self, extractor):
        ctx = _make_llm_context()
        chunk = {
            "items": [
                "invalid entry",
                _make_item(
                    code="2",
                    description="GRADE",
                    year_before_last_value=50.0,
                    last_year_value=75.0,
                ),
            ],
            "year_before_last_total_value": 50.0,
            "last_year_total_value": 75.0,
        }

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, [chunk])
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert len(result["items"]) == 1
        assert result["items"][0]["code"] == "2"


class TestEmptyItemsWithTotals:
    async def test_empty_items_with_totals_returns_result(self, extractor):
        ctx = _make_llm_context()
        chunks = [
            _make_chunk(
                items=[],
                year_before_last_total_value=1000.0,
                last_year_total_value=2000.0,
            )
        ]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert result["items"] == []
        assert result["extraction_method"] == "llm"
        assert "total_values" in result

    async def test_empty_items_without_totals_returns_none(self, extractor):
        ctx = _make_llm_context()
        chunks = [_make_chunk(items=[])]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is None


class TestTotalValidation:
    async def test_create_validated_total_called_with_sums_and_pdf_totals(self, extractor):
        ctx = _make_llm_context()
        items = [
            _make_item(
                code="1",
                year_before_last_value=100.0,
                last_year_value=200.0,
            ),
            _make_item(
                code="2",
                description="GRADE",
                year_before_last_value=50.0,
                last_year_value=75.0,
            ),
        ]
        chunks = [
            _make_chunk(
                items=items,
                year_before_last_total_value=150.0,
                last_year_total_value=275.0,
            )
        ]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            mock_validate = stack.enter_context(
                patch(
                    f"{MODULE_PATH}.create_validated_total",
                    return_value={"value": 0.0},
                )
            )
            await extractor.extract_with_llm(ctx)

        assert mock_validate.call_count == 2
        first_call = mock_validate.call_args_list[0]
        second_call = mock_validate.call_args_list[1]
        assert first_call.args[0] == pytest.approx(150.0)
        assert first_call.args[1] == pytest.approx(150.0)
        assert second_call.args[0] == pytest.approx(275.0)
        assert second_call.args[1] == pytest.approx(275.0)


class TestStructuralEqualitySC004:
    REGEX_TOP_KEYS = {"section_name", "items", "total_values"}
    LLM_TOP_KEYS = {"section_name", "items", "total_values", "extraction_method"}
    ITEM_KEYS = {
        "code",
        "description",
        "year_before_last_value",
        "last_year_value",
        "id",
        "page",
    }
    ITEM_TYPES = {
        "code": str,
        "description": str,
        "year_before_last_value": float,
        "last_year_value": float,
        "id": str,
        "page": int,
    }

    def test_regex_path_top_level_keys(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR VALMET 138X4 EQUIP. ADQ. 12/86. 0,00 0,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert set(result.keys()) == self.REGEX_TOP_KEYS

    async def test_llm_path_top_level_keys(self, extractor):
        ctx = _make_llm_context()
        items = [_make_item(code="1", description="TRATOR", last_year_value=100.0)]
        chunks = [_make_chunk(items=items, last_year_total_value=100.0)]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert set(result.keys()) == self.LLM_TOP_KEYS

    def test_regex_path_item_keys_and_types(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR VALMET 138X4 EQUIP. ADQ. 12/86. 1.234,56 7.890,12",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        assert len(result["items"]) >= 1
        item = result["items"][0]
        assert set(item.keys()) == self.ITEM_KEYS
        for key, expected_type in self.ITEM_TYPES.items():
            assert isinstance(item[key], expected_type), (
                f"regex item[{key!r}] is {type(item[key]).__name__}, expected {expected_type.__name__}"
            )

    async def test_llm_path_item_keys_and_types(self, extractor):
        ctx = _make_llm_context()
        items = [
            _make_item(
                code="16",
                description="TRATOR VALMET",
                year_before_last_value=1234.56,
                last_year_value=7890.12,
            )
        ]
        chunks = [
            _make_chunk(
                items=items,
                year_before_last_total_value=1234.56,
                last_year_total_value=7890.12,
            )
        ]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        assert len(result["items"]) >= 1
        item = result["items"][0]
        assert set(item.keys()) == self.ITEM_KEYS
        for key, expected_type in self.ITEM_TYPES.items():
            assert isinstance(item[key], expected_type), (
                f"llm item[{key!r}] is {type(item[key]).__name__}, expected {expected_type.__name__}"
            )

    def test_regex_total_values_structure(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR VALMET 0,00 100,00",
        )
        ctx = _make_context({1: page_text})
        result = extractor.extract(ctx)

        assert result is not None
        tv = result["total_values"]
        assert isinstance(tv, dict)
        assert "year_before_last_value" in tv
        assert "last_year_value" in tv

    async def test_llm_total_values_structure(self, extractor):
        ctx = _make_llm_context()
        items = [_make_item(code="16", last_year_value=100.0)]
        chunks = [_make_chunk(items=items, last_year_total_value=100.0)]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            result = await extractor.extract_with_llm(ctx)

        assert result is not None
        tv = result["total_values"]
        assert isinstance(tv, dict)
        assert "year_before_last_value" in tv
        assert "last_year_value" in tv

    async def test_both_paths_share_section_name(self, extractor):
        page_text = _make_section_text(
            "16 TRATOR 0,00 100,00",
        )
        regex_ctx = _make_context({1: page_text})
        regex_result = extractor.extract(regex_ctx)

        llm_ctx = _make_llm_context()
        items = [_make_item(code="16", last_year_value=100.0)]
        chunks = [_make_chunk(items=items, last_year_total_value=100.0)]

        with ExitStack() as stack:
            _apply_llm_mocks(stack, extractor, chunks)
            llm_result = await extractor.extract_with_llm(llm_ctx)

        assert regex_result is not None
        assert llm_result is not None
        assert regex_result["section_name"] == llm_result["section_name"]
