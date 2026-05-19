import pytest

from irpf_processor.infrastructure.extraction.ocr.post_processor import PostProcessor


class TestPostProcessor:

    @pytest.fixture
    def processor(self):
        return PostProcessor(lang="pt-BR")

    def test_fix_common_ocr_errors_cpf(self, processor):
        text = "CPF: 123.456.7B9-OO"
        result = processor.fix_ocr_errors(text)

        assert "123.456.789-00" in result

    def test_fix_common_ocr_errors_cnpj(self, processor):
        text = "CNPJ: 12345678000199"
        result = processor.format_cnpj(text)

        assert "12.345.678/0001-99" in result

    def test_fix_accents_declaracao(self, processor):
        text = "DECLARACAO DE AJUSTE ANUAL"
        result = processor.fix_accents(text)

        assert "DECLARAÇÃO" in result

    def test_fix_accents_contribuicao(self, processor):
        text = "CONTRIBUICAO PREVIDENCIARIA"
        result = processor.fix_accents(text)

        assert "CONTRIBUIÇÃO" in result

    def test_fix_accents_codigo(self, processor):
        text = "CODIGO DO BEM"
        result = processor.fix_accents(text)

        assert "CÓDIGO" in result

    def test_normalize_whitespace_multiple_spaces(self, processor):
        text = "VALOR:    R$   1.234,56"
        result = processor.normalize_whitespace(text)

        assert "VALOR: R$ 1.234,56" in result

    def test_normalize_whitespace_multiple_newlines(self, processor):
        text = "LINHA 1\n\n\n\nLINHA 2"
        result = processor.normalize_whitespace(text)

        assert "\n\n\n" not in result
        assert "LINHA 1" in result
        assert "LINHA 2" in result

    def test_fix_currency_american_format(self, processor):
        text = "Total: R$ 1,234.56"
        result = processor.fix_currency(text)

        assert "1.234,56" in result

    def test_format_cpf_unformatted(self, processor):
        text = "CPF: 12345678900"
        result = processor.format_cpf(text)

        assert "123.456.789-00" in result

    def test_format_cnpj_unformatted(self, processor):
        text = "CNPJ: 12345678000199"
        result = processor.format_cnpj(text)

        assert "12.345.678/0001-99" in result

    def test_remove_artifacts_pipes(self, processor):
        text = "CPF: 123.456.789-00 ||||| NOME:"
        result = processor.remove_artifacts(text)

        assert "|||||" not in result

    def test_remove_artifacts_dashes(self, processor):
        text = "SEÇÃO -------- VALORES"
        result = processor.remove_artifacts(text)

        assert "--------" not in result

    def test_fix_line_breaks_hyphenated_words(self, processor):
        text = "CONTRI-\nBUINTE"
        result = processor.fix_line_breaks(text)

        assert "CONTRIBUINTE" in result

    def test_fix_line_breaks_hyphen(self, processor):
        text = "CONTRI-\nBUINTE TESTE"
        result = processor.fix_line_breaks(text)

        assert "CONTRIBUINTE" in result

    def test_full_process_pipeline(self, processor):
        raw_text = """
        DECLARACAO DE AJUSTE ANUAL
        CPF: 12345678900
        NOME: JOAO DA SILVA
        VALOR:    R$   1,234.56 ||||
        """
        result = processor.process(raw_text)

        assert "DECLARAÇÃO" in result
        assert "123.456.789-00" in result
        assert "||||" not in result
        assert "    " not in result

    def test_preserves_valid_text(self, processor):
        text = "CPF: 123.456.789-00 NOME: JOÃO DA SILVA"
        result = processor.process(text)

        assert "123.456.789-00" in result
        assert "JOÃO DA SILVA" in result

    def test_empty_text_returns_empty(self, processor):
        result = processor.process("")

        assert result == ""

    def test_none_handling(self, processor):
        result = processor.process(None)

        assert result == ""

    def test_fix_digits_o_to_0(self, processor):
        result = processor._fix_digits("1O2O3")

        assert result == "10203"

    def test_fix_digits_l_to_1(self, processor):
        result = processor._fix_digits("l23l56")

        assert result == "123156"


class TestNormalizeOcrSlashes:

    @pytest.fixture
    def processor(self):
        return PostProcessor(lang="pt-BR")

    def test_collapses_spaces_around_slash_in_cnpj(self, processor):
        text = "50.926.955 / 0001-42"
        result = processor.normalize_ocr_slashes(text)

        assert result == "50.926.955/0001-42"

    def test_collapses_leading_space_only(self, processor):
        text = "50.926.955 /0001-42"
        result = processor.normalize_ocr_slashes(text)

        assert result == "50.926.955/0001-42"

    def test_collapses_trailing_space_only(self, processor):
        text = "50.926.955/ 0001-42"
        result = processor.normalize_ocr_slashes(text)

        assert result == "50.926.955/0001-42"

    def test_preserves_already_clean_cnpj(self, processor):
        text = "50.926.955/0001-42"
        result = processor.normalize_ocr_slashes(text)

        assert result == "50.926.955/0001-42"

    def test_does_not_affect_s_a_text(self, processor):
        text = "VULCABRAS S / A"
        result = processor.normalize_ocr_slashes(text)

        assert result == "VULCABRAS S / A"

    def test_does_not_affect_currency_values(self, processor):
        text = "R$ 1.234,56"
        result = processor.normalize_ocr_slashes(text)

        assert result == "R$ 1.234,56"

    def test_handles_cross_line_cnpj(self, processor):
        text = "75.813.691\n/ 0001-41"
        result = processor.normalize_ocr_slashes(text)

        assert result == "75.813.691/0001-41"

    def test_multiple_cnpjs_in_same_text(self, processor):
        text = "50.926.955 / 0001-42  VULCABRAS S / A  02.332.886 / 0001-04  XP INVESTIMENTOS"
        result = processor.normalize_ocr_slashes(text)

        assert "50.926.955/0001-42" in result
        assert "02.332.886/0001-04" in result
        assert "S / A" in result

    def test_records_correction_metrics(self, processor):
        processor.normalize_ocr_slashes("50.926.955 / 0001-42")

        corrections = processor.get_last_corrections()
        assert corrections.get("ocr_slash_normalize", 0) > 0

    def test_no_correction_when_text_unchanged(self, processor):
        processor.normalize_ocr_slashes("50.926.955/0001-42")

        corrections = processor.get_last_corrections()
        assert corrections.get("ocr_slash_normalize", 0) == 0


class TestNormalizeWhitespacePreserveColumnGaps:

    @pytest.fixture
    def processor(self):
        return PostProcessor(lang="pt-BR")

    def test_preserves_multi_space_column_gaps(self, processor):
        text = "Titular  303.363.419-20  50.926.955/0001-42  VULCABRAS  1.867,37"
        result = processor.normalize_whitespace(text, preserve_column_gaps=True)

        assert "  " in result

    def test_collapses_spaces_when_not_preserving(self, processor):
        text = "Titular  303.363.419-20  50.926.955/0001-42  VULCABRAS  1.867,37"
        result = processor.normalize_whitespace(text, preserve_column_gaps=False)

        assert "  " not in result

    def test_converts_tabs_to_spaces_when_preserving(self, processor):
        text = "Titular\t303.363.419-20"
        result = processor.normalize_whitespace(text, preserve_column_gaps=True)

        assert "\t" not in result
        assert "Titular" in result

    def test_strips_trailing_spaces_from_lines_when_preserving(self, processor):
        text = "Titular  303.363.419-20   \nNext line"
        result = processor.normalize_whitespace(text, preserve_column_gaps=True)

        assert " \n" not in result

    def test_collapses_triple_newlines_when_preserving(self, processor):
        text = "Line 1\n\n\nLine 2"
        result = processor.normalize_whitespace(text, preserve_column_gaps=True)

        assert "\n\n\n" not in result
        assert "Line 1" in result
        assert "Line 2" in result

    def test_process_with_preserve_column_gaps(self, processor):
        text = "Titular  303.363.419-20  50.926.955 / 0001-42  VULCABRAS  1.867,37"
        result = processor.process(text, preserve_column_gaps=True)

        assert "  " in result
        assert "50.926.955/0001-42" in result
