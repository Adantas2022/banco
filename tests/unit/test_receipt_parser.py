import pytest

from irpf_processor.infrastructure.extraction.receipt_parser import (
    ReceiptParser,
    IRPFReceiptResult,
)


@pytest.fixture
def parser():
    return ReceiptParser()


@pytest.fixture
def sample_receipt_text():
    return """
    RECIBO DE ENTREGA
    DECLARACAO DE AJUSTE ANUAL
    EXERCICIO 2025
    ANO-CALENDARIO 2024
    
    CPF: 886.978.040-60
    Nome: GENESIS LOPES
    
    Numero do Recibo: 12345678901234
    Data/Hora de Transmissao: 15/04/2025 14:30:00
    
    IMPOSTO A RESTITUIR: R$ 1.500,00
    """


class TestIRPFReceiptResult:

    def test_default_values(self):
        result = IRPFReceiptResult()

        assert result.normalized_cpf == ""
        assert result.taxpayer_name == ""
        assert result.exercise_year == ""
        assert result.calendar_year == ""
        assert result.receipt_number == ""
        assert result.transmission_datetime == ""
        assert result.tax_due == 0.0
        assert result.tax_refund == 0.0
        assert result.confidence == 0.0

    def test_to_dict_contains_all_fields(self):
        result = IRPFReceiptResult(
            normalized_cpf="88697804060",
            cpf="886.978.040-60",
            taxpayer_name="GENESIS LOPES",
            exercise_year="2025",
            calendar_year="2024",
            receipt_number="12345678901234",
            transmission_datetime="15/04/2025 14:30:00",
            tax_refund=1500.0,
            confidence=0.95
        )

        data = result.to_dict()

        assert data["normalized_cpf"] == "88697804060"
        assert data["taxpayer_name"] == "GENESIS LOPES"
        assert data["exercise_year"] == "2025"
        assert data["calendar_year"] == "2024"
        assert data["receipt_number"] == "12345678901234"
        assert data["tax_refund"] == 1500.0


class TestReceiptParser:

    def test_parse_from_text_returns_result(self, parser, sample_receipt_text):
        result = parser.parse_from_text(sample_receipt_text)

        assert isinstance(result, IRPFReceiptResult)

    def test_extracts_cpf(self, parser, sample_receipt_text):
        result = parser.parse_from_text(sample_receipt_text)

        assert result.normalized_cpf == "88697804060"

    def test_extracts_name(self, parser, sample_receipt_text):
        result = parser.parse_from_text(sample_receipt_text)

        assert result.taxpayer_name == "GENESIS LOPES"

    def test_extracts_exercise_year(self, parser, sample_receipt_text):
        result = parser.parse_from_text(sample_receipt_text)

        assert result.exercise_year == "2025"

    def test_extracts_calendar_year(self, parser, sample_receipt_text):
        result = parser.parse_from_text(sample_receipt_text)

        assert result.calendar_year == "2024"


class TestReceiptParserCPFExtraction:

    def test_extracts_cpf_with_formatting(self, parser):
        text = "CPF: 886.978.040-60"

        result = parser.parse_from_text(text)

        assert result.normalized_cpf == "88697804060"

    def test_extracts_cpf_without_formatting(self, parser):
        text = "CPF: 88697804060"

        result = parser.parse_from_text(text)

        assert result.normalized_cpf == "88697804060"

    def test_handles_missing_cpf(self, parser):
        text = "RECIBO DE ENTREGA sem CPF"

        result = parser.parse_from_text(text)

        assert result.normalized_cpf == ""


class TestReceiptParserYearExtraction:

    def test_extracts_both_years(self, parser):
        text = "EXERCICIO 2025\nANO-CALENDARIO 2024"

        result = parser.parse_from_text(text)

        assert result.exercise_year == "2025"
        assert result.calendar_year == "2024"

    def test_handles_missing_years(self, parser):
        text = "CPF: 123.456.789-00"

        result = parser.parse_from_text(text)

        assert result.exercise_year == ""
        assert result.calendar_year == ""


class TestReceiptParserTaxExtraction:

    def test_extracts_tax_refund(self, parser):
        text = "IMPOSTO A RESTITUIR: R$ 2.500,00"

        result = parser.parse_from_text(text)

        assert result.tax_refund == 2500.0

    def test_extracts_tax_due(self, parser):
        text = "IMPOSTO A PAGAR: R$ 1.000,00"

        result = parser.parse_from_text(text)

        assert result.tax_due == 1000.0

    def test_handles_no_tax(self, parser):
        text = "CPF: 123.456.789-00"

        result = parser.parse_from_text(text)

        assert result.tax_due == 0.0
        assert result.tax_refund == 0.0


class TestReceiptParserEdgeCases:

    def test_handles_empty_text(self, parser):
        result = parser.parse_from_text("")

        assert isinstance(result, IRPFReceiptResult)

    def test_handles_whitespace_only(self, parser):
        result = parser.parse_from_text("   \n\t  ")

        assert isinstance(result, IRPFReceiptResult)

    def test_handles_special_characters(self, parser):
        text = "CPF: 886.978.040-60\nNome: JOSÉ MARIA DA SILVA JÚNIOR"

        result = parser.parse_from_text(text)

        assert result.normalized_cpf == "88697804060"
