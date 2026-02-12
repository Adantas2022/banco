"""Testes unitários para ExclusiveIncomeExtractor - subseção 12 (financial_abroad).

BUG #84113: A subseção "financial_investments_and_profits_and_dividends_abroad"
não aparecia no JSON, fazendo o total_value ficar incorreto.
"""

import pytest

from irpf_processor.infrastructure.extraction.extractors.base import ExtractionContext
from irpf_processor.infrastructure.extraction.extractors.exclusive_income import (
    ExclusiveIncomeExtractor,
)


@pytest.fixture
def extractor():
    return ExclusiveIncomeExtractor()


class TestFinancialAbroadInline:
    """Testes para subseção 12 com valor na mesma linha do título."""

    def test_formato_brasileiro_inline(self, extractor):
        """Formato BR: 3.580,00 (OCR)."""
        page = (
            "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA/DEFINITIVA\n"
            "12. Aplicacoes Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3.580,00\n"
            "13. Outros 0,00\n"
            "TOTAL 3.580,00\n"
        )
        context = ExtractionContext(full_text=page, pages_text={1: page}, total_pages=1)

        result = extractor.extract(context)

        assert result is not None
        abroad = result["subsections"].get(
            "financial_investments_and_profits_and_dividends_abroad"
        )
        assert abroad is not None
        assert abroad["total_value"] == 3580.0
        assert abroad["code"] == "12"

    def test_formato_americano_inline(self, extractor):
        """Formato US: 3,580.00 (pdfplumber em PDFs digitais)."""
        page = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00\n"
            "13. Outros 11,000.00\n"
            "TOTAL 146,780.00\n"
        )
        context = ExtractionContext(full_text=page, pages_text={1: page}, total_pages=1)

        result = extractor.extract(context)

        assert result is not None
        abroad = result["subsections"].get(
            "financial_investments_and_profits_and_dividends_abroad"
        )
        assert abroad is not None
        assert abroad["total_value"] == 3580.0

    def test_nao_captura_numero_da_lei(self, extractor):
        """Deve capturar 3,580.00 e não 14.754 (número da Lei)."""
        page = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00\n"
            "TOTAL 3,580.00\n"
        )
        context = ExtractionContext(full_text=page, pages_text={1: page}, total_pages=1)

        result = extractor.extract(context)

        assert result is not None
        abroad = result["subsections"].get(
            "financial_investments_and_profits_and_dividends_abroad"
        )
        assert abroad is not None
        # Deve ser 3580.0, NÃO 14754.0 ou 14.754 ou 3.58
        assert abroad["total_value"] == 3580.0


class TestFinancialAbroadMultiline:
    """Testes para subseção 12 com valor na linha seguinte."""

    def test_valor_na_linha_seguinte_formato_br(self, extractor):
        """Valor em linha separada, formato BR."""
        page = (
            "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA/DEFINITIVA\n"
            "12. Aplicacoes Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)\n"
            "3.580,00\n"
            "13. Outros 0,00\n"
            "TOTAL 3.580,00\n"
        )
        context = ExtractionContext(full_text=page, pages_text={1: page}, total_pages=1)

        result = extractor.extract(context)

        assert result is not None
        abroad = result["subsections"].get(
            "financial_investments_and_profits_and_dividends_abroad"
        )
        assert abroad is not None
        assert abroad["total_value"] == 3580.0

    def test_valor_na_linha_seguinte_formato_us(self, extractor):
        """Valor em linha separada, formato US."""
        page = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)\n"
            "3,580.00\n"
            "13. Outros 11,000.00\n"
            "TOTAL 146,780.00\n"
        )
        context = ExtractionContext(full_text=page, pages_text={1: page}, total_pages=1)

        result = extractor.extract(context)

        assert result is not None
        abroad = result["subsections"].get(
            "financial_investments_and_profits_and_dividends_abroad"
        )
        assert abroad is not None
        assert abroad["total_value"] == 3580.0


class TestFinancialAbroadCrossPage:
    """Testes para subseção 12 em página diferente do marcador da seção."""

    def test_subsecao_12_em_outra_pagina(self, extractor):
        """BUG #84113: Subseção 12 na página 6, marcador na página 5."""
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)\n"
            "01. 13º salário 30,000.00\n"
            "06. Rendimentos de aplicações financeiras 8,700.00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome da Fonte Pagadora Valor\n"
            "Titular 171.955.328-95 15.148.412/0001-40 BANCO XPTO 8,700.00\n"
            "11. Participação nos lucros ou resultados 50,000.00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome da Fonte Pagadora Valor\n"
            "Titular 171.955.328-95 36.373.714/0001-92 INDUSTRIA DE INSUMOS 50,000.00\n"
            "Página 5 de21\n"
        )
        page6 = (
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00\n"
            "13. Outros 11,000.00\n"
            "Titular 171.955.328-95 51.572.102/0001-12 FINACNEIRA XYZ OUTROS 11,000.00\n"
            "TOTAL 146,780.00\n"
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR\n"
            "Página 6 de21\n"
        )

        full_text = page5 + "\n" + page6
        pages_text = {5: page5, 6: page6}
        context = ExtractionContext(full_text=full_text, pages_text=pages_text, total_pages=21)

        result = extractor.extract(context)

        assert result is not None
        abroad = result["subsections"].get(
            "financial_investments_and_profits_and_dividends_abroad"
        )
        assert abroad is not None, "Subseção 12 deve estar presente mesmo em página diferente"
        assert abroad["total_value"] == 3580.0


class TestFinancialAbroadTotalValue:
    """Testes para verificar que o total_value da seção inclui a subseção 12."""

    def test_total_inclui_subsecao_12(self, extractor):
        """Total da seção deve somar TODAS as subseções incluindo a 12."""
        page = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA\n"
            "01. 13º salário 30,000.00\n"
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00\n"
            "TOTAL 33,580.00\n"
        )
        context = ExtractionContext(full_text=page, pages_text={1: page}, total_pages=1)

        result = extractor.extract(context)

        assert result is not None
        # total = 30000 + 3580 = 33580
        assert result["total_value"] == 33580.0

    def test_total_correto_cenario_completo_84113(self, extractor):
        """Cenário completo do bug #84113 com todas as subseções."""
        page5 = (
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA (Valores em Reais)\n"
            "01. 13º salário 30,000.00\n"
            "06. Rendimentos de aplicações financeiras 8,700.00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome da Fonte Pagadora Valor\n"
            "Titular 171.955.328-95 15.148.412/0001-40 BANCO XPTO 8,700.00\n"
            "07. Rendimentos recebidos acumuladamente 39,000.00\n"
            "08. 13º salário recebido pelos dependentes 2,500.00\n"
            "10. Juros sobre capital próprio 2,000.00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome da Fonte Pagadora Valor\n"
            "Titular 171.955.328-95 75.657.379/0001-06 CONSTRUTORA E INCORPORADORA 2,000.00\n"
            "11. Participação nos lucros ou resultados 50,000.00\n"
            "Beneficiário CPF CNPJ da Fonte Pagadora Nome da Fonte Pagadora Valor\n"
            "Titular 171.955.328-95 36.373.714/0001-92 INDÚSTRIA DE INSUMOS 50,000.00\n"
            "AGROPECUÁRIOS\n"
            "Página 5 de21\n"
        )
        page6 = (
            "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023) 3,580.00\n"
            "13. Outros 11,000.00\n"
            "Beneficiário CPF CPF/CNPJ da Fonte Nome da Fonte Descrição Valor\n"
            "Pagadora Pagadora\n"
            "Titular 171.955.328-95 51.572.102/0001-12 FINACNEIRA XYZ OUTROS 11,000.00\n"
            "TOTAL 146,780.00\n"
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR\n"
            "Página 6 de21\n"
        )

        full_text = page5 + "\n" + page6
        pages_text = {5: page5, 6: page6}
        context = ExtractionContext(full_text=full_text, pages_text=pages_text, total_pages=21)

        result = extractor.extract(context)

        assert result is not None
        # Verificar que TODAS as subseções estão presentes
        subs = result["subsections"]
        assert "thirteenth_salary" in subs
        assert "income_from_financial_investments" in subs
        assert "accumulated_income_received" in subs
        assert "thirteen_salary_received_by_dependents" in subs
        assert "interest_on_own_capital" in subs
        assert "profit_or_results_sharing" in subs
        assert "financial_investments_and_profits_and_dividends_abroad" in subs
        assert "others_13" in subs

        # Verificar total = soma de todas as subseções
        expected_total = 146780.0
        assert abs(result["total_value"] - expected_total) < 0.01, (
            f"Total deveria ser {expected_total}, mas foi {result['total_value']}"
        )
