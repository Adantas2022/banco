import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.taxpayer import (
    TaxpayerExtractor,
    TaxpayerData,
)


@pytest.fixture
def extractor():
    return TaxpayerExtractor()


@pytest.fixture
def sample_irpf_text():
    return """
    DECLARACAO DE AJUSTE ANUAL
    EXERCICIO 2025
    ANO-CALENDARIO 2024
    
    IDENTIFICACAO DO CONTRIBUINTE
    CPF: 886.978.040-60
    Nome: GENESIS LOPES
    
    Natureza da Ocupacao: 12 - EMPRESARIO
    Ocupacao Principal: 610 - DIRETOR DE EMPRESA
    Tipo de declaracao: Declaracao de Ajuste Anual - Original
    
    Endereco: RUA DAS FLORES
    Numero: 123
    Complemento: APTO 101
    Bairro: CENTRO
    Municipio: SAO PAULO
    UF: SP
    CEP: 01234-567
    
    Telefone: (11) 98765-4321
    E-mail: genesis@example.com
    Celular: (11) 91234-5678
    """


class TestTaxpayerExtractorSectionName:

    def test_returns_correct_section_name(self, extractor):
        assert extractor.section_name == "taxpayer_identification"


class TestTaxpayerExtractorCanExtract:

    def test_returns_true_when_cpf_found(self, extractor):
        context = ExtractionContext(
            full_text="CPF: 886.978.040-60",
            pages_text={1: ""},
            total_pages=1
        )

        assert extractor.can_extract(context) is True

    def test_returns_true_for_cpf_without_formatting(self, extractor):
        context = ExtractionContext(
            full_text="CPF 88697804060",
            pages_text={1: ""},
            total_pages=1
        )

        assert extractor.can_extract(context) is True

    def test_returns_false_when_no_cpf(self, extractor):
        context = ExtractionContext(
            full_text="Document without CPF",
            pages_text={1: ""},
            total_pages=1
        )

        assert extractor.can_extract(context) is False


class TestTaxpayerExtractorExtractCPF:

    def test_extracts_cpf_with_formatting(self, extractor):
        context = ExtractionContext(
            full_text="CPF: 886.978.040-60",
            pages_text={1: ""},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["cpf"] == "886.978.040-60"
        assert result["normalized_cpf"] == "88697804060"


class TestTaxpayerExtractorExtractName:

    def test_extracts_name(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["name"] == "GENESIS LOPES"

    def test_handles_missing_name(self, extractor):
        context = ExtractionContext(
            full_text="CPF: 886.978.040-60",
            pages_text={1: ""},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["name"] == ""


class TestTaxpayerExtractorExtractYears:

    def test_extracts_exercise_year(self, extractor):
        context = ExtractionContext(
            full_text="EXERCICIO 2025\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["exercise_year"] == "2025"

    def test_extracts_calendar_year(self, extractor):
        context = ExtractionContext(
            full_text="ANO-CALENDARIO 2024\nCPF: 123.456.789-00",
            pages_text={1: ""},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["calendar_year"] == "2024"

    def test_extracts_both_years(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["exercise_year"] == "2025"
        assert result["calendar_year"] == "2024"


class TestTaxpayerExtractorExtractOccupation:

    def test_extracts_occupation_nature(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["occupation_nature"] == "12 - EMPRESARIO"

    def test_extracts_main_occupation(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["main_occupation"] == "610 - DIRETOR DE EMPRESA"


class TestTaxpayerExtractorExtractDeclarationType:

    def test_extracts_declaration_type(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["type_ir"] == "DECLARACAO DE AJUSTE ANUAL - ORIGINAL"


class TestTaxpayerExtractorExtractAddress:

    def test_extracts_full_address(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)
        address = result["contact_and_address"]

        assert address["uf"] == "SP"
        assert "01234" in address["zip_code"]

    def test_extracts_contact_info(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)
        address = result["contact_and_address"]

        assert "GENESIS@EXAMPLE.COM" in address["email"]


class TestTaxpayerExtractorFullExtraction:

    def test_full_extraction(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result["cpf"] == "886.978.040-60"
        assert result["normalized_cpf"] == "88697804060"
        assert result["name"] == "GENESIS LOPES"
        assert result["exercise_year"] == "2025"
        assert result["calendar_year"] == "2024"

    def test_returns_dict_with_all_keys(self, extractor, sample_irpf_text):
        context = ExtractionContext(
            full_text=sample_irpf_text,
            pages_text={1: sample_irpf_text},
            total_pages=1
        )

        result = extractor.extract(context)

        expected_keys = [
            "cpf", "normalized_cpf", "name", "exercise_year",
            "calendar_year", "occupation_nature", "main_occupation",
            "contact_and_address", "type_ir"
        ]

        for key in expected_keys:
            assert key in result


class TestTaxpayerData:

    def test_default_values(self):
        data = TaxpayerData()

        assert data.cpf == ""
        assert data.normalized_cpf == ""
        assert data.name == ""
        assert data.exercise_year == ""
        assert data.calendar_year == ""

    def test_to_dict_returns_dict(self):
        data = TaxpayerData(
            cpf="123.456.789-00",
            name="TEST USER",
            exercise_year="2025"
        )

        result = data.to_dict()

        assert isinstance(result, dict)
        assert result["cpf"] == "123.456.789-00"
        assert result["name"] == "TEST USER"


class TestExtractionContext:

    def test_add_warning(self):
        context = ExtractionContext(
            full_text="",
            pages_text={},
            total_pages=0
        )

        context.add_warning("Test warning")

        assert "Test warning" in context.warnings

    def test_get_page_text(self):
        context = ExtractionContext(
            full_text="Full text",
            pages_text={1: "Page 1", 2: "Page 2"},
            total_pages=2
        )

        assert context.get_page_text(1) == "Page 1"
        assert context.get_page_text(2) == "Page 2"
        assert context.get_page_text(3) == ""

    def test_find_pages_containing(self):
        context = ExtractionContext(
            full_text="Full text",
            pages_text={1: "Page with CPF", 2: "Page without", 3: "Another CPF page"},
            total_pages=3
        )

        result = context.find_pages_containing("CPF")

        assert 1 in result
        assert 3 in result
        assert 2 not in result
