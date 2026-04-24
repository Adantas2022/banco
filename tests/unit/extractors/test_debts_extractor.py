"""Testes unitários para DebtsExtractor.

Bug #90076 - Items mit identical desc+values across pages blocked by seen_ids.
           - OCR duplicate code '14 14' absorbed by headeronly break check.
"""

import pytest
from irpf_processor.infrastructure.extraction.extractors.debts import DebtsExtractor
from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext


@pytest.fixture
def extractor():
    return DebtsExtractor()


class TestCrossPageDuplicateID:
    """Bug #90076: Itens com mesma descrição+valores em páginas diferentes
    não devem colidir no seen_ids.
    """

    PAGE8 = (
        "DÍVIDAS E ÔNUS REAIS\n"
        "CÓDIGO   DISCRIMINAÇÃO\n"
        "14        EMPRESTIMO ADQUIRIDO DE JOAO              200.000,00              200.000,00              0,00\n"
        "DA SILVA CPF : 111.222.333-44\n"
    )
    PAGE9 = (
        "14        EMPRESTIMO ADQUIRIDO DE JOAO              200.000,00              200.000,00              0,00\n"
        "DA SILVA CPF : 111.222.333-44\n"
        "TOTAL                                              400.000,00              400.000,00              0,00\n"
        "DOAÇÕES A PARTIDOS POLÍTICOS\n"
    )

    def test_extracts_both_identical_items(self, extractor):
        """Mesmo desc+valores em páginas distintas devem gerar IDs diferentes."""
        full = self.PAGE8 + "\n" + self.PAGE9
        ctx = ExtractionContext(
            full_text=full,
            pages_text={8: self.PAGE8, 9: self.PAGE9},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 2
        assert result["items"][0]["page"] == 8
        assert result["items"][1]["page"] == 9

    def test_totals_include_both(self, extractor):
        full = self.PAGE8 + "\n" + self.PAGE9
        ctx = ExtractionContext(
            full_text=full,
            pages_text={8: self.PAGE8, 9: self.PAGE9},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        assert result["year_before_last_total_value"] == 400000.0
        assert result["last_year_total_value"] == 400000.0


class TestDuplicateCodeOCR:
    """Bug #90076: OCR duplica o código: '14 14 EMPRESTIMO...'."""

    PAGE = (
        "DÍVIDAS E ÔNUS REAIS\n"
        "CÓDIGO   DISCRIMINAÇÃO\n"
        "14        EMPRESTIMO DE MARIA                       200.000,00              200.000,00              0,00\n"
        "SOUZA CPF : 999.888.777-66\n"
        "14 14        EMPRESTIMO DE MARIA                       180.000,00               180.000,00              0,00\n"
        "SOUZA CPF : 999.888.777-66\n"
        "TOTAL                                              380.000,00              380.000,00              0,00\n"
        "DOAÇÕES A PARTIDOS POLÍTICOS\n"
    )

    def test_extracts_both_items(self, extractor):
        """Item com '14 14' deve ser normalizado e extraído."""
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={9: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 2

    def test_values_correct(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={9: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        values = sorted([it["year_before_last_value"] for it in result["items"]])
        assert values == [180000.0, 200000.0]

    def test_dup_not_absorbed_as_description(self, extractor):
        """A linha '14 14 EMPRESTIMO...' NÃO deve ser absorvida como
        continuação da descrição do item anterior."""
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={9: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        for item in result["items"]:
            assert "180.000" not in item["debt_description"]
            assert "200.000" not in item["debt_description"]


class TestSamePageDuplicateItems:
    """Bug #16728: Items with identical code/description/values on the SAME page
    must all be extracted. The taxpayer has multiple separate loans (contratos de
    mútuo) to the same entity with the same amounts."""

    PAGE = (
        "DÍVIDAS E ÔNUS REAIS\n"
        "CÓDIGO   DISCRIMINAÇÃO                           SITUAÇÃO EM       SITUAÇÃO EM 31/12/2023   VALOR PAGO\n"
        "                                                 31/12/2022                                   EM 2023\n"
        "14        SALDO DEVEDOR REF A EMPRESTIMO JUNTO A              500.000,00              71.000,00              429.000,00\n"
        "DJALMA AQUINO AZEVEDO - CPF 005.703.519-95.\n"
        "13        SALDO DEVEDOR REF A EMPRESTIMO JUNTO A EMP.              91.450,00              91.450,00              0,00\n"
        "AZEPLAST IND. E COM. LTDA - CNPJ N. 83.062.174/0001-\n"
        "06, CFE CTTO DE MUTUO.\n"
        "13        SALDO DEVEDOR REF A EMPRESTIMO JUNTO A EMP.              91.450,00              91.450,00              0,00\n"
        "AZEPLAST IND. E COM. LTDA - CNPJ N. 83.062.174/0001-\n"
        "06, CFE CTTO DE MUTUO.\n"
        "13        SALDO DEVEDOR REF A EMPRESTIMO JUNTO A EMP.              92.940,00              92.940,00              0,00\n"
        "AZEPLAST IND. E COM. LTDA - CNPJ N. 83.062.174/0001-\n"
        "06, CFE CTTO DE MUTUO.\n"
        "13        SALDO DEVEDOR REF A EMPRESTIMO JUNTO A EMP.              92.940,00              92.940,00              0,00\n"
        "AZEPLAST IND. E COM. LTDA - CNPJ N. 83.062.174/0001-\n"
        "06, CFE CTTO DE MUTUO.\n"
        "TOTAL                                              868.780,00              438.780,00              429.000,00\n"
        "DOAÇÕES A PARTIDOS POLÍTICOS\n"
    )

    def test_all_five_items_extracted(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={12: self.PAGE},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 5

    def test_duplicate_items_have_distinct_ids(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={12: self.PAGE},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        ids = [item["id"] for item in result["items"]]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {ids}"

    def test_totals_include_all_duplicates(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={12: self.PAGE},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        # 500000 + 91450 + 91450 + 92940 + 92940 = 868780
        assert result["year_before_last_total_value"] == 868780.0
        # 71000 + 91450 + 91450 + 92940 + 92940 = 438780
        assert result["last_year_total_value"] == 438780.0

    def test_each_duplicate_has_correct_values(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={12: self.PAGE},
            total_pages=21,
        )
        result = extractor.extract(ctx)
        items_91450 = [i for i in result["items"] if i["year_before_last_value"] == 91450.0]
        items_92940 = [i for i in result["items"] if i["year_before_last_value"] == 92940.0]
        assert len(items_91450) == 2, f"Expected 2 items with 91450, got {len(items_91450)}"
        assert len(items_92940) == 2, f"Expected 2 items with 92940, got {len(items_92940)}"


class TestTripleDuplicateItems:
    """Edge case: three identical entries on the same page."""

    PAGE = (
        "DÍVIDAS E ÔNUS REAIS\n"
        "CÓDIGO   DISCRIMINAÇÃO\n"
        "13        EMPRESTIMO AZEPLAST              50.000,00              50.000,00              0,00\n"
        "13        EMPRESTIMO AZEPLAST              50.000,00              50.000,00              0,00\n"
        "13        EMPRESTIMO AZEPLAST              50.000,00              50.000,00              0,00\n"
        "TOTAL                                     150.000,00             150.000,00              0,00\n"
        "DOAÇÕES EFETUADAS\n"
    )

    def test_all_three_extracted(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={5: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 3

    def test_all_three_distinct_ids(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={5: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        ids = [item["id"] for item in result["items"]]
        assert len(ids) == len(set(ids))


class TestResolveDuplicateID:
    """Unit tests for _resolve_duplicate_id static method."""

    def test_first_occurrence_unchanged(self, extractor):
        seen = set()
        result = extractor._resolve_duplicate_id("abc123", seen)
        assert result == "abc123"

    def test_second_occurrence_different(self, extractor):
        seen = {"abc123"}
        result = extractor._resolve_duplicate_id("abc123", seen)
        assert result != "abc123"

    def test_third_occurrence_different_from_both(self, extractor):
        seen = set()
        id1 = extractor._resolve_duplicate_id("abc123", seen)
        seen.add(id1)
        id2 = extractor._resolve_duplicate_id("abc123", seen)
        seen.add(id2)
        id3 = extractor._resolve_duplicate_id("abc123", seen)
        assert len({id1, id2, id3}) == 3

    def test_deterministic(self, extractor):
        seen1 = {"abc123"}
        seen2 = {"abc123"}
        r1 = extractor._resolve_duplicate_id("abc123", seen1)
        r2 = extractor._resolve_duplicate_id("abc123", seen2)
        assert r1 == r2


class TestNonDuplicateRegression:
    """Regression: items with different values must still work exactly as before."""

    PAGE = (
        "DÍVIDAS E ÔNUS REAIS\n"
        "CÓDIGO   DISCRIMINAÇÃO\n"
        "14        EMPRESTIMO JOAO              200.000,00              200.000,00              0,00\n"
        "13        EMPRESTIMO MARIA              100.000,00              80.000,00              20.000,00\n"
        "TOTAL                                  300.000,00              280.000,00              20.000,00\n"
        "DOAÇÕES EFETUADAS\n"
    )

    def test_both_extracted(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={5: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        assert result is not None
        assert len(result["items"]) == 2

    def test_ids_different(self, extractor):
        ctx = ExtractionContext(
            full_text=self.PAGE,
            pages_text={5: self.PAGE},
            total_pages=10,
        )
        result = extractor.extract(ctx)
        assert result["items"][0]["id"] != result["items"][1]["id"]

