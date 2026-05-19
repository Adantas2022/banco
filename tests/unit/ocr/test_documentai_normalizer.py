import pytest

from irpf_processor.infrastructure.extraction.ocr.documentai_normalizer import (
    DocumentAINormalizer,
)


class TestDocumentAINormalizerPreserveColumnGaps:

    @pytest.fixture
    def normalizer(self):
        return DocumentAINormalizer()

    def test_preserves_multi_space_gaps_when_flag_set(self, normalizer):
        text = "Titular  303.363.419-20  50.926.955/0001-42  VULCABRAS  1.867,37"
        result = normalizer.normalize(text, preserve_column_gaps=True)

        assert "  " in result

    def test_collapses_spaces_when_flag_not_set(self, normalizer):
        text = "Titular  303.363.419-20  50.926.955/0001-42  VULCABRAS  1.867,37"
        result = normalizer.normalize(text, preserve_column_gaps=False)

        assert "  " not in result

    def test_fixes_period_as_decimal_when_preserving(self, normalizer):
        text = "Titular  303.363.419-20  1.867.37"
        result = normalizer.normalize(text, preserve_column_gaps=True)

        assert "1.867,37" in result

    def test_removes_blank_lines_when_preserving(self, normalizer):
        text = "Line 1\n\nLine 2"
        result = normalizer.normalize(text, preserve_column_gaps=True)

        lines = result.splitlines()
        assert all(line.strip() for line in lines)

    def test_empty_text_returns_empty(self, normalizer):
        assert normalizer.normalize("", preserve_column_gaps=True) == ""
        assert normalizer.normalize("", preserve_column_gaps=False) == ""


class TestDocumentAINormalizerCurrencyOrphans:

    @pytest.fixture
    def normalizer(self):
        return DocumentAINormalizer()

    def test_merges_orphan_currency_to_previous_line(self, normalizer):
        text = "Titular 303.363.419-20 VULCABRAS\n1.867,37"
        result = normalizer.normalize(text, preserve_column_gaps=False)

        assert "1.867,37" in result
        lines = result.splitlines()
        assert len(lines) == 1

    def test_does_not_merge_non_currency_orphan(self, normalizer):
        text = "VULCABRAS S.A.\nTitular"
        result = normalizer.normalize(text, preserve_column_gaps=False)

        lines = result.splitlines()
        assert len(lines) == 2


class TestDocumentAINormalizerFixPeriodAsDecimal:

    @pytest.fixture
    def normalizer(self):
        return DocumentAINormalizer()

    def test_fixes_simple_decimal(self, normalizer):
        result = normalizer._fix_period_as_decimal("0.00")

        assert result == "0,00"

    def test_fixes_with_thousands_separator(self, normalizer):
        result = normalizer._fix_period_as_decimal("358.550.20")

        assert result == "358.550,20"

    def test_fixes_with_millions_separator(self, normalizer):
        result = normalizer._fix_period_as_decimal("22.391.052.36")

        assert result == "22.391.052,36"

    def test_preserves_non_decimal_periods(self, normalizer):
        result = normalizer._fix_period_as_decimal("NOME DA EMPRESA S.A.")

        assert result == "NOME DA EMPRESA S.A."
