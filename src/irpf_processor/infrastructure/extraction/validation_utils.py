"""Utilitários para validação de totais extraídos vs totais do PDF.

Este módulo fornece funções para:
1. Extrair valores da linha TOTAL do PDF
2. Comparar soma dos itens extraídos com total do PDF
3. Gerar estrutura de validação com diagnóstico
"""

import re
from typing import Optional

from .table_extractor import parse_currency


def parse_currency_value(value_str: str) -> float:
    return parse_currency(value_str)


def extract_total_values_from_lines(
    lines: list[str], 
    keyword: str = "TOTAL",
    skip_keywords: list[str] = None
) -> list[float]:
    """Extrai valores numéricos da linha TOTAL do PDF.
    
    Args:
        lines: Lista de linhas do texto da página
        keyword: Palavra-chave para identificar a linha de total
        skip_keywords: Palavras que indicam que a linha deve ser ignorada
        
    Returns:
        Lista de valores float encontrados na linha TOTAL
    """
    skip_keywords = skip_keywords or []
    
    num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
    
    for line in lines:
        stripped = line.strip()
        upper_line = stripped.upper()
        
        # Verificar se é linha de total
        if not upper_line.startswith(keyword):
            continue
        
        # Verificar se deve pular (ex: "TOTAL DE DEDUÇÃO" vs "TOTAL")
        should_skip = False
        for skip in skip_keywords:
            if skip.upper() in upper_line:
                should_skip = True
                break
        
        if should_skip:
            continue
        
        # Extrair todos os valores numéricos
        matches = re.findall(num_pattern, stripped)
        if matches:
            return [parse_currency_value(m) for m in matches]
    
    return []


def validate_total(
    extracted_sum: float, 
    pdf_total: float, 
    tolerance: float = 0.02
) -> bool:
    """Compara soma extraída com total do PDF.
    
    Args:
        extracted_sum: Soma dos valores extraídos dos itens
        pdf_total: Total encontrado no PDF
        tolerance: Tolerância para diferenças de arredondamento (padrão: 0.02)
        
    Returns:
        True se os valores são considerados iguais (dentro da tolerância)
    """
    if pdf_total == 0:
        return extracted_sum == 0
    
    return abs(extracted_sum - pdf_total) <= tolerance


def create_validated_total(
    extracted_sum: float,
    pdf_total: Optional[float] = None,
    tolerance: float = 0.02
) -> dict:
    """Cria estrutura de total validado com diagnóstico.
    
    Args:
        extracted_sum: Soma dos valores extraídos
        pdf_total: Total do PDF (None se não foi possível extrair)
        tolerance: Tolerância para validação
        
    Returns:
        Dict com amount, pdf_total, valid, e difference
    """
    result = {
        "amount": round(extracted_sum, 2),
        "pdf_total": round(pdf_total, 2) if pdf_total is not None else None,
    }
    
    if pdf_total is not None:
        result["valid"] = validate_total(extracted_sum, pdf_total, tolerance)
        result["difference"] = round(extracted_sum - pdf_total, 2)
    else:
        # Se não conseguiu extrair o total do PDF, não pode validar
        result["valid"] = None
        result["difference"] = None
    
    return result


def extract_section_total(
    page_text: str,
    total_keyword: str = "TOTAL",
    skip_keywords: list[str] = None
) -> list[float]:
    """Wrapper conveniente para extrair totais de uma página.
    
    Args:
        page_text: Texto completo da página
        total_keyword: Palavra-chave para linha de total
        skip_keywords: Palavras que indicam linha a ignorar
        
    Returns:
        Lista de valores do total
    """
    lines = page_text.split("\n")
    return extract_total_values_from_lines(lines, total_keyword, skip_keywords)
