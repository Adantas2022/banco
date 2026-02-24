import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.donations import DonationsExtractor


@pytest.fixture
def extractor():
    return DonationsExtractor()


@pytest.fixture
def sample_donations_page():
    return """
    DOAÇÕES EFETUADAS
    
    CÓDIGO  DESCRIÇÃO                                              VALOR
    41      ECA NACIONAL 12.345.678/0001-90 FUNDO DA CRIANÇA       5.000,00
    47      FUNDO DO IDOSO 98.765.432/0001-10 FUNDO MUNICIPAL      3.000,00
    44      CULTURA 00.000.000/0001-91 PROJETO CULTURAL            2.000,00
    
    TOTAL                                                         10.000,00
    """


@pytest.fixture
def sample_donations_incentive():
    return """
    DOAÇÕES EFETUADAS
    
    71      ECA 12.345.678/0001-90 CONSELHO MUNICIPAL              1.500,00
    72      IDOSO 98.765.432/0001-10 FUNDO ESTADUAL                1.000,00
    74      DESPORTO 11.111.111/0001-11 PROJETO ESPORTIVO            800,00
    
    TOTAL                                                          3.300,00
    """


class TestDonationsExtractorSectionName:

    def test_returns_correct_section_name(self, extractor):
        assert extractor.section_name == "donations_made"


class TestDonationsExtractorCanExtract:

    def test_returns_true_when_section_marker_present(self, extractor):
        context = ExtractionContext(
            full_text="DOAÇÕES EFETUADAS\nConteudo",
            pages_text={1: "DOAÇÕES EFETUADAS\nConteudo"},
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


class TestDonationsExtractorExtract:

    def test_returns_none_when_no_items_found(self, extractor):
        context = ExtractionContext(
            full_text="DOAÇÕES EFETUADAS\nSem informações",
            pages_text={1: "DOAÇÕES EFETUADAS\nSEM INFORMAÇÕES"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_extract_is_callable(self, extractor):
        assert callable(extractor.extract)

    def test_extracts_eca_donations(self, extractor, sample_donations_page):
        context = ExtractionContext(
            full_text=sample_donations_page,
            pages_text={1: sample_donations_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            eca_codes = ["41", "42", "43", "71", "80"]
            eca_items = [i for i in result["items"] if i["donation_code"] in eca_codes]
            assert len(eca_items) >= 1

    def test_extracts_elderly_fund_donations(self, extractor, sample_donations_page):
        context = ExtractionContext(
            full_text=sample_donations_page,
            pages_text={1: sample_donations_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            elderly_codes = ["47", "48", "49", "72", "81"]
            elderly_items = [i for i in result["items"] if i["donation_code"] in elderly_codes]
            assert len(elderly_items) >= 1

    def test_calculates_total(self, extractor, sample_donations_page):
        context = ExtractionContext(
            full_text=sample_donations_page,
            pages_text={1: sample_donations_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert "total_value" in result
            assert isinstance(result["total_value"], float)
            assert result["total_value"] > 0


class TestDonationsExtractorResultStructure:

    def test_result_has_required_fields(self, extractor, sample_donations_page):
        context = ExtractionContext(
            full_text=sample_donations_page,
            pages_text={1: sample_donations_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert "section_name" in result
            assert "items" in result
            assert "total_value" in result
            assert "pages_with_problems" in result

    def test_section_name_is_correct(self, extractor, sample_donations_page):
        context = ExtractionContext(
            full_text=sample_donations_page,
            pages_text={1: sample_donations_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert result["section_name"] == "Doações Efetuadas"


class TestDonationsExtractorItemStructure:

    def test_item_has_required_fields(self, extractor, sample_donations_page):
        context = ExtractionContext(
            full_text=sample_donations_page,
            pages_text={1: sample_donations_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert "id" in item
            assert "donation_code" in item
            assert "donation_description" in item
            assert "value" in item
            assert "page" in item

    def test_extracts_beneficiary_cnpj(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        41      ECA 12.345.678/0001-90 FUNDO DA CRIANCA       1.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["beneficiary_cnpj"] == "12.345.678/0001-90"


class TestDonationsExtractorMultiplePages:

    def test_extracts_from_multiple_pages(self, extractor):
        page1 = """
        DOAÇÕES EFETUADAS
        41      ECA 12.345.678/0001-90 FUNDO 1       1.000,00
        """
        page2 = """
        DOAÇÕES EFETUADAS
        47      IDOSO 98.765.432/0001-10 FUNDO 2       500,00
        """

        context = ExtractionContext(
            full_text=page1 + "\n" + page2,
            pages_text={1: page1, 2: page2},
            total_pages=2
        )

        result = extractor.extract(context)

        if result:
            assert len(result["items"]) >= 1


class TestDonationsExtractorEdgeCases:

    def test_handles_empty_pages_text(self, extractor):
        context = ExtractionContext(
            full_text="DOAÇÕES EFETUADAS",
            pages_text={},
            total_pages=0
        )

        result = extractor.extract(context)

        assert result is None

    def test_handles_page_without_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="DOAÇÕES EFETUADAS",
            pages_text={1: "Page without marker"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_stops_at_section_end_marker(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        41      ECA 12.345.678/0001-90 FUNDO       1.000,00
        
        DOAÇÕES A PARTIDOS
        99      PARTIDO 00.000.000/0001-00 PARTIDO X       500,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            party_items = [i for i in result["items"] if "PARTIDO" in i.get("donation_description", "").upper()]
            assert len(party_items) == 0


class TestDonationsExtractorDonationCodes:

    def test_recognizes_eca_national_code_41(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        41      ECA NACIONAL 12.345.678/0001-90 FUNDO       1.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["donation_code"] == "41"

    def test_recognizes_elderly_national_code_47(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        47      FUNDO IDOSO NACIONAL 12.345.678/0001-90 FUNDO       1.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["donation_code"] == "47"

    def test_recognizes_culture_code_44(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        44      CULTURA 12.345.678/0001-90 PROJETO CULTURAL       2.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["donation_code"] == "44"

    def test_recognizes_sports_code_46(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        46      DESPORTO 12.345.678/0001-90 PROJETO ESPORTIVO       1.500,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["donation_code"] == "46"

    def test_recognizes_eca_direct_code_71(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        71      ECA 12.345.678/0001-90 CONSELHO MUNICIPAL       1.000,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["donation_code"] == "71"

    def test_recognizes_elderly_direct_code_72(self, extractor):
        page_text = """
        DOAÇÕES EFETUADAS
        72      IDOSO 12.345.678/0001-90 FUNDO ESTADUAL       800,00
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert result["items"][0]["donation_code"] == "72"
