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
