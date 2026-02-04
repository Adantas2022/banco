"""Extratores de campos específicos."""

import re
from decimal import Decimal
from typing import Optional

from .table_extractor import parse_currency, detect_currency_format


CPF_PATTERN = re.compile(r"\d{3}\.?\d{3}\.?\d{3}-?\d{2}")
CNPJ_PATTERN = re.compile(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}")
CURRENCY_PATTERN = re.compile(r"R?\$?\s*([\d.,]+)")
DATE_PATTERN = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def extract_cpf(text: str) -> Optional[str]:
    """Extrai CPF do texto."""
    match = CPF_PATTERN.search(text)
    return match.group() if match else None


def extract_cnpj(text: str) -> Optional[str]:
    """Extrai CNPJ do texto."""
    match = CNPJ_PATTERN.search(text)
    return match.group() if match else None


def extract_currency(text: str) -> Optional[Decimal]:
    """Extrai valor monetário do texto.
    
    Suporta tanto formato brasileiro (1.234,56) quanto americano (1,234.56).
    """
    match = CURRENCY_PATTERN.search(text)
    if not match:
        return None
    
    value_str = match.group(1)
    # Usa parse_currency com detecção automática de formato (BR/US)
    value_float = parse_currency(value_str)
    
    try:
        return Decimal(str(value_float))
    except Exception:
        return None


def extract_date(text: str) -> Optional[str]:
    """Extrai data no formato DD/MM/YYYY."""
    match = DATE_PATTERN.search(text)
    if not match:
        return None
    return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"


def normalize_cpf(cpf: str) -> str:
    """Remove formatação do CPF."""
    return re.sub(r"[^\d]", "", cpf)


def normalize_cnpj(cnpj: str) -> str:
    """Remove formatação do CNPJ."""
    return re.sub(r"[^\d]", "", cnpj)


def validate_cpf(cpf: str) -> bool:
    """Valida CPF usando dígitos verificadores."""
    cpf = normalize_cpf(cpf)
    
    if len(cpf) != 11:
        return False
    
    if cpf == cpf[0] * 11:
        return False
    
    def calc_digit(cpf_partial: str, weights: list[int]) -> int:
        total = sum(int(d) * w for d, w in zip(cpf_partial, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder
    
    first_digit = calc_digit(cpf[:9], list(range(10, 1, -1)))
    second_digit = calc_digit(cpf[:10], list(range(11, 1, -1)))
    
    return cpf[-2:] == f"{first_digit}{second_digit}"


def validate_cnpj(cnpj: str) -> bool:
    """Valida CNPJ usando dígitos verificadores."""
    cnpj = normalize_cnpj(cnpj)
    
    if len(cnpj) != 14:
        return False
    
    if cnpj == cnpj[0] * 14:
        return False
    
    def calc_digit(cnpj_partial: str, weights: list[int]) -> int:
        total = sum(int(d) * w for d, w in zip(cnpj_partial, weights))
        remainder = total % 11
        return 0 if remainder < 2 else 11 - remainder
    
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    
    first_digit = calc_digit(cnpj[:12], weights1)
    second_digit = calc_digit(cnpj[:13], weights2)
    
    return cnpj[-2:] == f"{first_digit}{second_digit}"
