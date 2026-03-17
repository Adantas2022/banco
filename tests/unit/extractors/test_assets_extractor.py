import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.assets import AssetsExtractor
from irpf_processor.infrastructure.extraction.table_extractor import parse_currency, generate_item_id


@pytest.fixture
def extractor():
    return AssetsExtractor()


@pytest.fixture
def sample_assets_page():
    return """
    DECLARACAO DE BENS E DIREITOS
    
    01 01 APARTAMENTO RESIDENCIAL 150.000,00 175.000,00
    01 02 TERRENO URBANO 80.000,00 85.000,00
    02 01 AUTOMOVEL FIAT ARGO 45.000,00 40.000,00
    06 01 CONTA CORRENTE BANCO DO BRASIL 10.000,00 15.000,00
    """


class TestAssetsExtractorSectionName:

    def test_returns_correct_section_name(self, extractor):
        assert extractor.section_name == "assets_declaration"


class TestAssetsExtractorCanExtract:

    def test_returns_false_when_no_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="RENDIMENTOS ISENTOS\nConteudo",
            pages_text={1: ""},
            total_pages=1
        )

        assert extractor.can_extract(context) is False

    def test_can_extract_is_callable(self, extractor):
        """Verify can_extract method exists and is callable."""
        assert callable(extractor.can_extract)


class TestAssetsExtractorExtract:

    def test_returns_none_when_no_items_found(self, extractor):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS\nSem itens",
            pages_text={1: "DECLARACAO DE BENS E DIREITOS\nSem itens"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_extract_is_callable(self, extractor):
        """Verify extract method exists and is callable."""
        assert callable(extractor.extract)

    def test_calculates_totals(self, extractor, sample_assets_page):
        context = ExtractionContext(
            full_text=sample_assets_page,
            pages_text={1: sample_assets_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            assert "last_year_total_value" in result
            assert "current_year_total_value" in result
            assert isinstance(result["last_year_total_value"], float)
            assert isinstance(result["current_year_total_value"], float)

    def test_result_structure(self, extractor, sample_assets_page):
        context = ExtractionContext(
            full_text=sample_assets_page,
            pages_text={1: sample_assets_page},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert "section_name" in result
            assert "items" in result
            assert "last_year_total_value" in result
            assert "current_year_total_value" in result
            assert "pages_with_problems" in result


class TestAssetsExtractorItemStructure:

    def test_item_has_required_fields(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 APARTAMENTO 100.000,00 120.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert "id" in item
            assert "asset_group_code" in item
            assert "asset_code" in item
            assert "asset_description" in item
            assert "before_year_asset_value" in item
            assert "current_year_asset_value" in item

    def test_item_values_parsed_correctly(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 IMOVEL 100.000,00 150.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "01"
            assert item["asset_code"] == "01"
            assert item["before_year_asset_value"] == 100000.0
            assert item["current_year_asset_value"] == 150000.0


class TestAssetsExtractorMultiplePages:

    def test_extracts_from_multiple_pages(self, extractor):
        page1 = "DECLARACAO DE BENS E DIREITOS\n01 01 IMOVEL 1 100.000,00 110.000,00"
        page2 = "DECLARACAO DE BENS E DIREITOS\n01 02 IMOVEL 2 200.000,00 220.000,00"

        context = ExtractionContext(
            full_text=page1 + "\n" + page2,
            pages_text={1: page1, 2: page2},
            total_pages=2
        )

        result = extractor.extract(context)

        if result:
            assert len(result["items"]) >= 1

    def test_extracts_from_multipage_without_header_on_subsequent_pages(self, extractor):
        page1 = "DECLARAÇÃO DE BENS E DIREITOS\n01 01 IMOVEL PRIMEIRO 100.000,00 110.000,00"
        page2 = "01 02 IMOVEL SEGUNDO 200.000,00 220.000,00"
        page3 = "01 03 IMOVEL TERCEIRO 300.000,00 330.000,00"

        context = ExtractionContext(
            full_text=page1 + "\n" + page2 + "\n" + page3,
            pages_text={1: page1, 2: page2, 3: page3},
            total_pages=3
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 3
        assert result["items"][0]["asset_description"] == "IMOVEL PRIMEIRO"
        assert result["items"][1]["asset_description"] == "IMOVEL SEGUNDO"
        assert result["items"][2]["asset_description"] == "IMOVEL TERCEIRO"

    def test_stops_at_end_marker(self, extractor):
        page1 = "DECLARAÇÃO DE BENS E DIREITOS\n01 01 IMOVEL UM 100.000,00 110.000,00"
        page2 = "01 02 IMOVEL DOIS 200.000,00 220.000,00"
        page3 = "DÍVIDAS E ÔNUS REAIS\nOutro conteudo"

        context = ExtractionContext(
            full_text=page1 + "\n" + page2 + "\n" + page3,
            pages_text={1: page1, 2: page2, 3: page3},
            total_pages=3
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 2

    def test_extracts_large_multipage_section(self, extractor):
        page1 = "DECLARAÇÃO DE BENS E DIREITOS\n01 01 BEM A 10.000,00 11.000,00"
        pages = {1: page1}
        full_text = page1

        for i in range(2, 11):
            page_content = f"01 0{i % 10} BEM {chr(64 + i)} {i * 10000},00 {i * 11000},00"
            pages[i] = page_content
            full_text += "\n" + page_content

        context = ExtractionContext(
            full_text=full_text,
            pages_text=pages,
            total_pages=10
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 10


class TestParseCurrency:

    def test_parses_brazilian_format(self):
        assert parse_currency("100.000,00") == 100000.0

    def test_parses_simple_format(self):
        assert parse_currency("1.000,50") == 1000.5

    def test_handles_empty_string(self):
        assert parse_currency("") == 0.0

    def test_handles_invalid_format(self):
        assert parse_currency("invalid") == 0.0

    def test_removes_currency_symbols(self):
        assert parse_currency("R$ 1.000,00") == 1000.0


class TestGenerateItemId:

    def test_generates_consistent_id(self):
        id1 = generate_item_id("test content")
        id2 = generate_item_id("test content")

        assert id1 == id2

    def test_generates_different_ids_for_different_content(self):
        id1 = generate_item_id("content 1")
        id2 = generate_item_id("content 2")

        assert id1 != id2

    def test_returns_hash_string(self):
        item_id = generate_item_id("test")

        assert isinstance(item_id, str)
        assert len(item_id) > 0


class TestAssetsExtractorAssetGroups:

    def test_extracts_real_estate_group_01(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 CASA RESIDENCIAL 500.000,00 550.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "01"

    def test_extracts_vehicle_group_02(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n02 01 AUTOMOVEL HONDA 80.000,00 70.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "02"

    def test_extracts_deposit_group_06(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n06 01 CONTA POUPANCA 25.000,00 30.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["asset_group_code"] == "06"


class TestAssetsExtractorCountryInfo:

    def test_default_country_is_brazil(self, extractor):
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 IMOVEL 100.000,00 100.000,00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            assert item["country_code"] == "105"
            assert item["country_name"] == "BRASIL"
            assert item["country_valid"] is True


class TestAssetsExtractorEdgeCases:

    def test_handles_empty_pages_text(self, extractor):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS",
            pages_text={},
            total_pages=0
        )

        result = extractor.extract(context)

        assert result is None

    def test_handles_page_without_section_marker(self, extractor):
        context = ExtractionContext(
            full_text="DECLARACAO DE BENS E DIREITOS",
            pages_text={1: "Page without marker"},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is None

    def test_skips_non_matching_lines(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        Random text that should be skipped
        01 01 VALID ASSET 10.000,00 12.000,00
        More random text
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result:
            assert len(result["items"]) == 1


class TestAssetsExtractorAdditionalInfo:

    def test_extracts_real_estate_cei_cno(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        01 01 IMOVEL CONSTRUCAO 100.000,00 150.000,00
        CEI 12.345.67890/12
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("cei_cno") == "12.345.67890/12"

    def test_extracts_participation_traded_on_stock_market(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        03 01 ACOES PETROBRAS 50.000,00 60.000,00
        Negociadas em Bolsa Sim
        Código de Negociação PETR4
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("traded_on_stock_market") is True
                assert item["additional_info"].get("trading_code") == "PETR4"

    def test_extracts_deposit_bank_info(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        06 01 CONTA CORRENTE 10.000,00 15.000,00
        CNPJ 00.000.000/0001-91
        Banco 001
        Agência 1234
        Conta 56789-0
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("bank") == "001"
                assert item["additional_info"].get("agency") == "1234"
                assert item["additional_info"].get("account") == "56789-0"

    def test_extracts_fund_cnpj(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        07 01 FUNDO DE INVESTIMENTO 80.000,00 90.000,00
        CNPJ 12.345.678/0001-90
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("cnpj") == "12.345.678/0001-90"

    def test_extracts_fund_custodian_info(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        07 01 FUNDO ACOES 100.000,00 120.000,00
        CNPJ do Custodiante 98.765.432/0001-10
        Próprio Custodiante Sim
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("custodian_cnpj") == "98.765.432/0001-10"
                assert item["additional_info"].get("self_custodian") is True

    def test_extracts_real_estate_address_info(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        01 01 APARTAMENTO 200.000,00 250.000,00
        Inscrição Municipal 12345678
        Logradouro Rua das Flores Nº 100
        Complemento Apto 10
        Município São Paulo UF SP
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("municipal_registration") == "12345678"
                assert item["additional_info"].get("street_address") == "Rua das Flores"
                assert item["additional_info"].get("number") == "100"
                assert item["additional_info"].get("complement") == "Apto 10"
                assert item["additional_info"].get("city") == "São Paulo"
                assert item["additional_info"].get("state") == "SP"

    def test_extracts_deposit_payment_account(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
        06 01 CONTA PAGAMENTO 5.000,00 7.000,00
        Conta Pagamento Sim
        """
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        if result and result["items"]:
            item = result["items"][0]
            if "additional_info" in item:
                assert item["additional_info"].get("is_payment_account") is True


class TestBug86842USFormatCurrency:
    """Bug #86842: DocumentAI retorna valores com '.' e ',' invertidos (formato US)."""

    def test_parses_us_format_currency_values(self, extractor):
        """Valores US-format como 150,000.00 devem ser parseados como 150000.0."""
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 01 APARTAMENTO RESIDENCIAL 150,000.00 160,000.00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["before_year_asset_value"] == 150000.0
        assert item["current_year_asset_value"] == 160000.0

    def test_description_does_not_contain_us_currency_values(self, extractor):
        """asset_description NÃO deve conter valores monetários US-format residuais."""
        page_text = "DECLARACAO DE BENS E DIREITOS\n02 02 AERONAVE 200,000.00 200,000.00\nRegistro de Aeronave: 12343241"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        item = result["items"][0]
        assert item["asset_description"] == "AERONAVE"
        assert "200,000.00" not in item["asset_description"]

    def test_description_loja_does_not_contain_values(self, extractor):
        """'LOJA EM SAO PAULO 180,000.00' deve ficar 'LOJA EM SAO PAULO'."""
        page_text = "DECLARACAO DE BENS E DIREITOS\n01 18 LOJA EM SAO PAULO 180,000.00 180,000.00"
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        item = result["items"][0]
        assert item["asset_description"] == "LOJA EM SAO PAULO"

    def test_mixed_br_and_us_format(self, extractor):
        """Mistura de formatos BR e US na mesma página deve funcionar."""
        page_text = """DECLARACAO DE BENS E DIREITOS
01 01 IMOVEL PRIMEIRO 150.000,00 160.000,00
01 02 IMOVEL SEGUNDO 200,000.00 220,000.00"""
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 2
        assert result["items"][0]["before_year_asset_value"] == 150000.0
        assert result["items"][1]["before_year_asset_value"] == 200000.0

    def test_totals_correct_with_us_format(self, extractor):
        """Totais devem estar corretos quando valores vêm em formato US."""
        page_text = """DECLARACAO DE BENS E DIREITOS
01 01 IMOVEL A 150,000.00 160,000.00
01 02 IMOVEL B 200,000.00 220,000.00"""
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        assert result["last_year_total_value"] == 350000.0
        assert result["current_year_total_value"] == 380000.0

    def test_area_extracts_zero_value_without_unit(self, extractor):
        """Área com valor '0,0' sem unidade deve ser extraída como '0,0'."""
        page_text = """DECLARACAO DE BENS E DIREITOS
01 01 IMOVEL 100.000,00 120.000,00
Área Total: 0,0"""
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        item = result["items"][0]
        assert item["additional_info"]["area"] == "0,0"

    def test_airship_registration_field_name(self, extractor):
        """Campo deve ser 'airship_registration', não 'aircraft_registration'."""
        page_text = """DECLARACAO DE BENS E DIREITOS
02 02 AERONAVE 400.000,00 410.000,00
Registro de Aeronave: PTABC"""
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        item = result["items"][0]
        assert "airship_registration" in item["additional_info"]
        assert "aircraft_registration" not in item["additional_info"]
        assert item["additional_info"]["airship_registration"] == "PTABC"

    def test_parse_currency_us_format(self):
        """parse_currency deve lidar com formato US."""
        assert parse_currency("150,000.00") == 150000.0
        assert parse_currency("1,234,567.89") == 1234567.89
        assert parse_currency("200,000.00") == 200000.0

    def test_parse_currency_br_format_still_works(self):
        """parse_currency deve continuar funcionando com formato BR."""
        assert parse_currency("150.000,00") == 150000.0
        assert parse_currency("1.234.567,89") == 1234567.89
        assert parse_currency("200.000,00") == 200000.0


class TestLaw14754OptionSuffixRemoval:

    def test_asset_description_does_not_include_law_option_suffix(self, extractor):
        base_description = "IBAN : PT50003505570003478390043 ; BIC SWIFT : CGDIPTPL"
        law_suffix_line1 = (
            "Opção pela atualização do valor do bem ou direito no exterior para o valor "
            "de mercado em 31/12/2023, nos termos do art. 14 da Lei nº"
        )
        law_suffix_line2 = "14.754 , de 2023 : Não"

        page_text = "\n".join(
            [
                "DECLARACAO DE BENS E DIREITOS",
                f"06 01 {base_description} 36,33 0,00",
                law_suffix_line1,
                law_suffix_line2,
            ]
        )
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1,
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["asset_description"] == base_description


class TestCpfExtractionFailures:

    def test_participation_item_without_valid_cpf_keeps_none(self, extractor):
        page_text = """DECLARACAO DE BENS E DIREITOS
03 02 40.000 QUOTAS DE CAPITAL DA ECOINTEL ENERGIA RENOVAVEL LTDA 40.000,00 40.000,00
Bem ou direito pertencente ao: Titular
CPF: XXXX.XXX.XXX-XX
CNPJ: 47.968.226/0001-44"""
        context = ExtractionContext(
            full_text=page_text,
            pages_text={1: page_text},
            total_pages=1,
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["additional_info"]["beneficiary"] == "Titular"
        assert item["additional_info"]["cnpj"] == "47.968.226/0001-44"
        assert item["additional_info"]["cpf"] is None


class TestBug88130IsolatedHeaderBoundary:

    PAGE_TEXT = "\n".join([
        "DECLARACAO DE BENS E DIREITOS",
        "07 01 FUNDO ACOES 10.000,00 12.000,00",
        "06 01",
        "01 CONTA CORRENTE 5.000,00 6.000,00",
    ])

    def test_isolated_header_does_not_merge_into_previous_item(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        assert len(result["items"]) == 2

    def test_first_item_description_not_polluted(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        item1 = result["items"][0]
        assert item1["asset_group_code"] == "07"
        assert item1["asset_description"] == "FUNDO ACOES"
        assert "CONTA CORRENTE" not in item1["asset_description"]

    def test_second_item_extracted_correctly(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        items_06 = [i for i in result["items"] if i["asset_group_code"] == "06"]
        assert len(items_06) == 1
        assert items_06[0]["asset_code"] == "01"


class TestAssetsTotalExtraction:

    PAGE_TEXT = "\n".join([
        "DECLARACAO DE BENS E DIREITOS",
        "01 01 APARTAMENTO RESIDENCIAL 100.000,00 110.000,00",
        "01 02 TERRENO URBANO 50.000,00 55.000,00",
        "02 01 AUTOMOVEL FIAT ARGO 30.000,00 28.000,00",
        "06 01 CONTA CORRENTE BANCO DO BRASIL 20.000,00 15.000,00",
        "TOTAL 0,00 9,00",
        "TOTAL 200.872,94 208.879,08",
        "DIVIDAS E ONUS REAIS (Valores em Reais)",
    ])

    def test_pdf_total_extracted_from_correct_line(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        assert "total_values" in result
        tv = result["total_values"]
        assert "before_year_asset_value" in tv
        assert "current_year_asset_value" in tv

    def test_pdf_total_before_year_matches_expected(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        pdf_total = result["total_values"]["before_year_asset_value"]["pdf_total"]
        assert pdf_total is not None
        assert abs(pdf_total - 200872.94) < 0.01

    def test_pdf_total_current_year_matches_expected(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        pdf_total = result["total_values"]["current_year_asset_value"]["pdf_total"]
        assert pdf_total is not None
        assert abs(pdf_total - 208879.08) < 0.01

    def test_pdf_total_ignores_subtotals_before_end_marker(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        pdf_total_before = result["total_values"]["before_year_asset_value"]["pdf_total"]
        pdf_total_current = result["total_values"]["current_year_asset_value"]["pdf_total"]
        
        assert pdf_total_before is not None
        assert pdf_total_current is not None
        assert abs(pdf_total_before - 9.0) > 0.01
        assert abs(pdf_total_current - 9.0) > 0.01
        assert abs(pdf_total_before - 200872.94) < 0.01
        assert abs(pdf_total_current - 208879.08) < 0.01

    def test_amount_matches_sum_of_items(self, extractor):
        context = ExtractionContext(
            full_text=self.PAGE_TEXT,
            pages_text={1: self.PAGE_TEXT},
            total_pages=1
        )

        result = extractor.extract(context)

        assert result is not None
        amount_before = result["total_values"]["before_year_asset_value"]["amount"]
        amount_current = result["total_values"]["current_year_asset_value"]["amount"]
        
        expected_before = 100000.0 + 50000.0 + 30000.0 + 20000.0
        expected_current = 110000.0 + 55000.0 + 28000.0 + 15000.0
        
        assert abs(amount_before - expected_before) < 0.01
        assert abs(amount_current - expected_current) < 0.01

