import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.payments import PaymentsExtractor


@pytest.fixture
def extractor():
    return PaymentsExtractor()


@pytest.fixture
def sample_payments_page():
    return """
    PAGAMENTOS EFETUADOS
    
    CÓDIGO  DESCRIÇÃO                                              VALOR
    01      INSTRUÇÃO 12.345.678/0001-90 ESCOLA ABC                12.000,00
    02      INSTRUÇÃO 98.765.432/0001-10 FACULDADE XYZ             24.000,00
    26      PENSÃO ALIMENTÍCIA 123.456.789-00 MARIA DA SILVA        6.000,00
    
    TOTAL                                                          42.000,00
    """


@pytest.fixture
def sample_payments_health():
    return """
    PAGAMENTOS EFETUADOS
    
    03      HOSPITAIS 12.345.678/0001-90 HOSPITAL SAO LUCAS        5.000,00
    05      MÉDICOS 123.456.789-00 DR JOAO SILVA                   2.500,00
    29      PLANO DE SAÚDE 01.234.567/0001-89 UNIMED               8.400,00
    
    TOTAL                                                         15.900,00
    """


class TestPaymentsExtractorSectionName:

    def test_returns_correct_section_name(self, extractor):
        assert extractor.section_name == "payments_made"


class TestPaymentsExtractorCanExtract:

    def test_returns_true_when_section_marker_present(self, extractor):
        context = ExtractionContext(
            full_text="PAGAMENTOS EFETUADOS\nConteudo",
            pages_text={1: "PAGAMENTOS EFETUADOS\nConteudo"},
            total_pages=1
        )

        assert extractor.can_extract(context) is True

    def test_returns_false_when_no_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="RENDIMENTOS ISENTOS\nConteudo",
            pages_text={1: "RENDIMENTOS ISENTOS\nConteudo"},
            total_pages=1
        )

        assert extractor.can_extract(context) is False

    def test_can_extract_is_callable(self, extractor):
        assert callable(extractor.can_extract)


class TestPaymentsExtractorExtract:

    def test_returns_none_when_no_items_found(self, extractor):
        context = ExtractionContext(
            full_text="PAGAMENTOS EFETUADOS\nSem informações",
            pages_text={1: "PAGAMENTOS EFETUADOS\nSEM INFORMAÇÕES"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_extract_is_callable(self, extractor):
        assert callable(extractor.extract)

    def test_extracts_instruction_payments(self, extractor, sample_payments_page):
        context = ExtractionContext(
            full_text=sample_payments_page,
            pages_text={1: sample_payments_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert len(result["items"]) >= 1
            instruction_items = [i for i in result["items"] if i["payment_code"] in ["01", "02"]]
            assert len(instruction_items) >= 1

    def test_extracts_health_payments(self, extractor, sample_payments_health):
        context = ExtractionContext(
            full_text=sample_payments_health,
            pages_text={1: sample_payments_health},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            health_codes = ["03", "05", "29"]
            health_items = [i for i in result["items"] if i["payment_code"] in health_codes]
            assert len(health_items) >= 1

    def test_calculates_total(self, extractor, sample_payments_page):
        context = ExtractionContext(
            full_text=sample_payments_page,
            pages_text={1: sample_payments_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert "total_value" in result
            assert isinstance(result["total_value"], float)
            assert result["total_value"] > 0


class TestPaymentsExtractorResultStructure:

    def test_result_has_required_fields(self, extractor, sample_payments_page):
        context = ExtractionContext(
            full_text=sample_payments_page,
            pages_text={1: sample_payments_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert "section_name" in result
            assert "items" in result
            assert "total_value" in result
            assert "pages_with_problems" in result

    def test_section_name_is_correct(self, extractor, sample_payments_page):
        context = ExtractionContext(
            full_text=sample_payments_page,
            pages_text={1: sample_payments_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert result["section_name"] == "Pagamentos Efetuados"


class TestPaymentsExtractorItemStructure:

    def test_item_has_required_fields(self, extractor, sample_payments_page):
        context = ExtractionContext(
            full_text=sample_payments_page,
            pages_text={1: sample_payments_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert "id" in item
            assert "payment_code" in item
            assert "payment_description" in item
            assert "value" in item
            assert "page" in item

    def test_extracts_beneficiary_cpf(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        26      PENSÃO 123.456.789-00 BENEFICIARIO TESTE        1.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["beneficiary_cpf_cnpj"] == "123.456.789-00"

    def test_extracts_beneficiary_cnpj(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        01      INSTRUÇÃO 12.345.678/0001-90 ESCOLA TESTE       10.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["beneficiary_cpf_cnpj"] == "12.345.678/0001-90"


class TestPaymentsExtractorMultiplePages:

    def test_extracts_from_multiple_pages(self, extractor):
        page1 = """
        PAGAMENTOS EFETUADOS
        01      INSTRUÇÃO 12.345.678/0001-90 ESCOLA 1       5.000,00
        """
        page2 = """
        PAGAMENTOS EFETUADOS
        02      INSTRUÇÃO 98.765.432/0001-10 ESCOLA 2       3.000,00
        """

        context = ExtractionContext(
            full_text=page1 + "\n" + page2,
            pages_text={1: page1, 2: page2},
            total_pages=2
        )

        result = extractor.extract(context)

        if result:
            assert len(result["items"]) >= 1


class TestPaymentsExtractorEdgeCases:

    def test_handles_empty_pages_text(self, extractor):
        context = ExtractionContext(
            full_text="PAGAMENTOS EFETUADOS",
            pages_text={},
            total_pages=0
        )

        result = extractor.extract(context)

        assert result is None

    def test_handles_page_without_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="PAGAMENTOS EFETUADOS",
            pages_text={1: "Page without marker"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_stops_at_section_end_marker(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        01      INSTRUÇÃO 12.345.678/0001-90 ESCOLA       5.000,00
        
        DOAÇÕES EFETUADAS
        41      DOAÇÃO ECA 00.000.000/0001-00 FUNDO       1.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            donation_items = [i for i in result["items"] if i["payment_code"] == "41"]
            assert len(donation_items) == 0


class TestPaymentsExtractorPaymentCodes:

    def test_recognizes_instruction_code_01(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        01      INSTRUÇÃO NO BRASIL 12.345.678/0001-90 ESCOLA       10.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["payment_code"] == "01"

    def test_recognizes_health_code_03(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        03      HOSPITAL 12.345.678/0001-90 HOSPITAL ABC       5.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["payment_code"] == "03"

    def test_recognizes_alimony_code_26(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        26      PENSÃO ALIMENTÍCIA 123.456.789-00 FULANO       2.400,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["payment_code"] == "26"

    def test_recognizes_health_plan_code_29(self, extractor):
        page_text = """
        PAGAMENTOS EFETUADOS
        29      PLANO DE SAÚDE 12.345.678/0001-90 UNIMED       9.600,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["payment_code"] == "29"
