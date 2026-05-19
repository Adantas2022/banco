"""Utilitários para parsing de valores monetários.

Este módulo fornece funções para:
1. Detectar formato de moeda (brasileiro vs americano)
2. Converter strings monetárias para float
3. Somar valores monetários com precisão

Suporta tanto formato brasileiro (250.000,00) quanto americano (250,000.00).
"""

import logging
import re
from typing import Literal, Union

logger = logging.getLogger(__name__)

# Tipo para formato de moeda
CurrencyFormat = Literal['BR', 'US', 'AMBIGUOUS']


def detect_currency_format(value: str) -> CurrencyFormat:
    """
    Detecta o formato do valor monetário.
    
    Formatos suportados:
    - BR (Brasileiro): ponto como milhar, vírgula como decimal (250.000,00)
    - US (Americano): vírgula como milhar, ponto como decimal (250,000.00)
    
    Args:
        value: String com valor monetário
        
    Returns:
        'BR' para formato brasileiro
        'US' para formato americano
        'AMBIGUOUS' se não conseguir determinar
        
    Examples:
        >>> detect_currency_format("250.000,00")
        'BR'
        >>> detect_currency_format("250,000.00")
        'US'
        >>> detect_currency_format("1234")
        'AMBIGUOUS'
    """
    if not value:
        return 'AMBIGUOUS'
    
    # Limpar espaços e símbolos de moeda para análise
    cleaned = re.sub(r"[^\d,.]", "", value.strip())
    
    if not cleaned:
        return 'AMBIGUOUS'
    
    # Padrão 1: Termina com ,XX (2 dígitos após vírgula) → Brasileiro
    if re.search(r',\d{2}$', cleaned):
        return 'BR'
    
    # Padrão 2: Termina com .XX (2 dígitos após ponto) → Americano
    if re.search(r'\.\d{2}$', cleaned):
        return 'US'
    
    # Padrão 3: Múltiplos pontos como milhar (X.XXX.XXX) → Brasileiro
    if re.search(r'\d+\.\d{3}\.\d{3}', cleaned):
        return 'BR'
    
    # Padrão 4: Múltiplas vírgulas como milhar (X,XXX,XXX) → Americano
    if re.search(r'\d+,\d{3},\d{3}', cleaned):
        return 'US'
    
    # Padrão 5: Ponto seguido de exatamente 3 dígitos e depois vírgula ou fim → milhar BR
    if re.search(r'\.\d{3}(?:,|$)', cleaned):
        return 'BR'
    
    # Padrão 6: Vírgula seguida de exatamente 3 dígitos e depois ponto ou fim → milhar US
    if re.search(r',\d{3}(?:\.|$)', cleaned):
        return 'US'
    
    # Padrão 7: Termina com ,X (1 dígito após vírgula) → Brasileiro (ex: 100,5)
    if re.search(r',\d$', cleaned):
        return 'BR'
    
    # Padrão 8: Termina com .X (1 dígito após ponto) → Americano (ex: 100.5)
    if re.search(r'\.\d$', cleaned):
        return 'US'
    
    return 'AMBIGUOUS'


def parse_currency(value: str, format_hint: CurrencyFormat = None) -> float:
    """
    Converte string monetária para float com detecção automática de formato.
    
    Suporta tanto formato brasileiro (250.000,00) quanto americano (250,000.00).
    Quando o formato é ambíguo, assume formato brasileiro (padrão BR).
    
    Args:
        value: String com valor monetário
        format_hint: Dica de formato ('BR', 'US') ou None para auto-detectar
        
    Returns:
        Valor como float
        
    Examples:
        >>> parse_currency("250.000,00")  # BR
        250000.0
        >>> parse_currency("250,000.00")  # US
        250000.0
        >>> parse_currency("R$ 1.234,56")
        1234.56
        >>> parse_currency("$ 1,234.56")
        1234.56
    """
    if not value:
        return 0.0
    
    # Limpar caracteres não numéricos (exceto separadores)
    cleaned = re.sub(r"[^\d,.-]", "", value)
    
    if not cleaned:
        return 0.0
    
    # Detectar formato se não fornecido
    fmt = format_hint or detect_currency_format(cleaned)
    
    # Log quando formato americano é detectado (útil para monitoramento)
    if fmt == 'US':
        logger.debug(f"Formato americano detectado para valor: {value}")
    
    if fmt == 'US':
        # Formato americano: vírgula=milhar, ponto=decimal
        cleaned = cleaned.replace(",", "")  # Remove milhares
        # Ponto já é decimal, não precisa trocar
    else:
        # Formato brasileiro (padrão): ponto=milhar, vírgula=decimal
        cleaned = cleaned.replace(".", "")   # Remove milhares
        cleaned = cleaned.replace(",", ".")  # Converte decimal
    
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def sum_currency_values(values: list[float], as_int: bool = False) -> Union[float, int]:
    """
    Soma valores monetários com precisão usando a classe Money.
    
    Args:
        values: Lista de valores float
        as_int: Se True, retorna como int (centavos)
        
    Returns:
        Soma total como float ou int
        
    Examples:
        >>> sum_currency_values([100.50, 200.75, 50.25])
        351.5
        >>> sum_currency_values([100.50, 200.75], as_int=True)
        30125
    """
    from irpf_processor.domain.value_objects.money import Money
    
    total = Money.zero()
    for val in values:
        total = total + Money.from_number(val)
    
    if as_int:
        return total.to_int()
    return round(total.to_float(), 2)
