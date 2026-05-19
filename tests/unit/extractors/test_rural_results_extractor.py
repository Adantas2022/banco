# tests/extractors/test_rural_results_parse_result_line.py
#  Bug #88457 - seção "calculation_of_taxable_result" não é exibida no nosso json
import pytest

from irpf_processor.infrastructure.extraction.extractors.rural.results import (
    RuralResultsExtractor,
)

from irpf_processor.infrastructure.extraction.extractors import ExtractionContext

from irpf_processor.infrastructure.extraction.irpf_parser import (
    IRPFDeclarationResult,
    IRPFParser,
)

@pytest.fixture
def extractor():
    return RuralResultsExtractor()


class TestParseResultLine:

    def test_result_when_string_and_currency_in_value(self, extractor):
        
        text = (
            """
            NOME: DARLON PEGORARO
            CPF: 001.991.141-61 IMPOSTO SOBRE A RENDA - PESSOA FÍSICA
            DECLARAÇÃO DE AJUSTE ANUAL EXERCÍCIO 2025 ANO-CALENDÁRIO 2024
            DEMONSTRATIVO DE ATIVIDADE RURAL - BRASIL
            DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL
            CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA CIB (Nirf)
            ATIVIDADE (%) EXPLORAÇÃO (ha)
            10 100,00 4 FAZ. CAFUNDO DAS PEDRAS, COXIM-MS 100,0 2.271.077-9
            RECEITAS E DESPESAS - BRASIL (Valores em Reais)
            MÊS RECEITA BRUTA DESPESAS DE CUSTEIO/INVESTIMENTO
            Janeiro 0,00 0,00
            Fevereiro 0,00 0,00
            Março 0,00 0,00
            Abril 0,00 0,00
            Maio 0,00 0,00
            Junho 0,00 0,00
            Julho 0,00 0,00
            Agosto 0,00 0,00
            Setembro 0,00 0,00
            Outubro 0,00 0,00
            Novembro 0,00 0,00
            Dezembro 328.000,00 0,00
            TOTAL 328.000,00 0,00
            APURAÇÃO DO RESULTADO - BRASIL (Valores em Reais)
            INFORMAÇÃO DO EXERCÍCIO ANTERIOR
            Saldo de prejuízo(s) a compensar de exercício(s) anterior(es) 0,00
            APURAÇÃO DO RESULTADO TRIBUTÁVEL
            Receita bruta total 328.000,00
            Despesa de custeio e investimento total 0,00
            Resultado 328.000,00
            Limite de 20% sobre a receita bruta total 65.600,00
            Opção pela forma de apuração do resultado tributável Pelo limite de 20% sobre a receita bruta total
            Compensação de prejuízo(s) de exercício(s) anterior(es) 0,00
            RESULTADO TRIBUTÁVEL 65.600,00
            INFORMAÇÕES PARA O EXERCÍCIO SEGUINTE
            Saldo de prejuízo(s) a compensar 0,00
            APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL
            Adiantamento(s) recebido(s) em 2024 por conta de venda para entrega futura 0,00
            Adiantamento(s) recebido(s) até 2023 a ser(em) informado(s) como receita(s) de produto(s) entregue(s) em 2024 0,00
            RESULTADO NÃO TRIBUTÁVEL 262.400,00
            MOVIMENTAÇÃO DO REBANHO - BRASIL
            Sem Informações
            BENS DA ATIVIDADE RURAL - BRASIL
            Sem Informações
            DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL
            Sem Informações
            Página 7 de11
            """
        )
        context = ExtractionContext(
            full_text=text, pages_text={1: text}, total_pages=1
        )
        result = extractor.extract(context)

        assert result is not None
        assert "Opção pela forma de apuração do resultado tributável" in [ n['description'] for n in result['subsections']['calculation_of_taxable_result']['items']]
        assert "Pelo limite de 20% sobre a receita bruta total" in [ n['value'] for n in result['subsections']['calculation_of_taxable_result']['items']]

    def test_parse_result_line_when_string_in_value(self, extractor):
        
        line = "Opção pela forma de apuração do resultado tributável Pelo limite de 20% sobre a receita bruta total"
        item = extractor._parse_result_line(line)

        assert item is not None
        assert "Opção pela forma de apuração do resultado tributável" in item['description']
        assert "Pelo limite de 20% sobre a receita bruta total" in item['value']

    def test_parse_result_line_when_currency_in_value(self, extractor):
        
        line = "Receita bruta total 328.000,00"
        item = extractor._parse_result_line(line)

        assert item is not None
        assert "Receita bruta total" in item['description']
        assert 328000.0 == item['value']

    def test_parse_result_line_when_two_uppercase_words_in_description(self, extractor):
        
        line = "Saldo de Prejuízos 0,00"
        item = extractor._parse_result_line(line)

        assert item is not None
        assert "Saldo de Prejuízos" in item['description']
        assert 0.0 == item['value']

    def test_parse_result_line_preserves_negative_resultado(self, extractor):
        line = "Resultado -15.432,10"
        item = extractor._parse_result_line(line)

        assert item is not None
        assert item["description"] == "Resultado"
        assert item["value"] == -15432.10

    def test_parse_result_line_preserves_negative_resultado_tributavel(self, extractor):
        line = "RESULTADO TRIBUTÁVEL -3.000,00"
        item = extractor._parse_result_line(line)

        assert item is not None
        assert item["description"] == "RESULTADO TRIBUTÁVEL"
        assert item["value"] == -3000.0
