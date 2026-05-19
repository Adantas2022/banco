"""Testes unitários para extratores de campos."""

from decimal import Decimal

import pytest

from irpf_processor.infrastructure.extraction.field_extractors import (
    extract_cpf,
    extract_cnpj,
    extract_currency,
    extract_date,
    normalize_cpf,
    normalize_cnpj,
    validate_cpf,
    validate_cnpj,
)


class TestExtractCpf:
    """Testes para extração de CPF."""
    
    def test_extract_cpf_formatted(self):
        text = "CPF do contribuinte: 886.978.040-60"
        result = extract_cpf(text)
        assert result == "886.978.040-60"
    
    def test_extract_cpf_unformatted(self):
        text = "CPF: 88697804060"
        result = extract_cpf(text)
        assert result == "88697804060"
    
    def test_extract_cpf_not_found(self):
        text = "Nenhum documento aqui"
        result = extract_cpf(text)
        assert result is None
    
    def test_extract_cpf_partial_format(self):
        text = "CPF 886978040-60"
        result = extract_cpf(text)
        assert result is not None


class TestExtractCnpj:
    """Testes para extração de CNPJ."""
    
    def test_extract_cnpj_formatted(self):
        text = "CNPJ: 33.520.594/0001-10"
        result = extract_cnpj(text)
        assert result == "33.520.594/0001-10"
    
    def test_extract_cnpj_unformatted(self):
        text = "CNPJ 33520594000110"
        result = extract_cnpj(text)
        assert result == "33520594000110"
    
    def test_extract_cnpj_not_found(self):
        text = "Sem CNPJ aqui"
        result = extract_cnpj(text)
        assert result is None


class TestExtractCurrency:
    """Testes para extração de valores monetários."""
    
    def test_extract_currency_with_symbol(self):
        text = "Valor: R$ 1.234,56"
        result = extract_currency(text)
        assert result == Decimal("1234.56")
    
    def test_extract_currency_without_symbol(self):
        text = "Total: 9.876,54"
        result = extract_currency(text)
        assert result == Decimal("9876.54")
    
    def test_extract_currency_integer(self):
        text = "Valor 1000"
        result = extract_currency(text)
        assert result == Decimal("1000")
    
    def test_extract_currency_large_value(self):
        text = "Patrimônio: R$ 25.040.026,18"
        result = extract_currency(text)
        assert result == Decimal("25040026.18")
    
    def test_extract_currency_not_found(self):
        text = "Sem valores aqui"
        result = extract_currency(text)
        assert result is None


class TestExtractDate:
    """Testes para extração de datas."""
    
    def test_extract_date_valid(self):
        text = "Data de emissão: 15/01/2025"
        result = extract_date(text)
        assert result == "15/01/2025"
    
    def test_extract_date_not_found(self):
        text = "Sem data aqui"
        result = extract_date(text)
        assert result is None


class TestNormalizeCpf:
    """Testes para normalização de CPF."""
    
    def test_normalize_cpf_formatted(self):
        result = normalize_cpf("886.978.040-60")
        assert result == "88697804060"
    
    def test_normalize_cpf_already_clean(self):
        result = normalize_cpf("88697804060")
        assert result == "88697804060"


class TestNormalizeCnpj:
    """Testes para normalização de CNPJ."""
    
    def test_normalize_cnpj_formatted(self):
        result = normalize_cnpj("33.520.594/0001-10")
        assert result == "33520594000110"
    
    def test_normalize_cnpj_already_clean(self):
        result = normalize_cnpj("33520594000110")
        assert result == "33520594000110"


class TestValidateCpf:
    """Testes para validação de CPF."""
    
    def test_validate_cpf_valid(self):
        assert validate_cpf("88697804060") is True
    
    def test_validate_cpf_valid_formatted(self):
        assert validate_cpf("886.978.040-60") is True
    
    def test_validate_cpf_invalid_checksum(self):
        assert validate_cpf("88697804061") is False
    
    def test_validate_cpf_all_same_digits(self):
        assert validate_cpf("11111111111") is False
    
    def test_validate_cpf_wrong_length(self):
        assert validate_cpf("1234567890") is False


class TestValidateCnpj:
    """Testes para validação de CNPJ."""
    
    def test_validate_cnpj_valid(self):
        assert validate_cnpj("11222333000181") is True
    
    def test_validate_cnpj_invalid_checksum(self):
        assert validate_cnpj("11222333000182") is False
    
    def test_validate_cnpj_all_same_digits(self):
        assert validate_cnpj("11111111111111") is False
    
    def test_validate_cnpj_wrong_length(self):
        assert validate_cnpj("1122233300018") is False
