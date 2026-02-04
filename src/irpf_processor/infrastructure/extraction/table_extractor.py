"""Extrator de tabelas de PDFs usando pdfplumber."""

import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal, Optional, Union
from pathlib import Path

from .field_extractors import normalize_cpf, normalize_cnpj

logger = logging.getLogger(__name__)

# Tipo para formato de moeda
CurrencyFormat = Literal['BR', 'US', 'AMBIGUOUS']


@dataclass
class ExtractedTable:
    """Representa uma tabela extraída."""
    
    headers: list[str]
    rows: list[list[str]]
    page_number: int
    
    def to_dicts(self) -> list[dict[str, str]]:
        """Converte tabela para lista de dicionários."""
        return [dict(zip(self.headers, row)) for row in self.rows]


class TableExtractor:
    """Extrai tabelas estruturadas de PDFs."""
    
    def __init__(self):
        self._pdfplumber = None
    
    def _ensure_pdfplumber(self):
        if self._pdfplumber is None:
            import pdfplumber
            self._pdfplumber = pdfplumber
    
    def extract_tables(
        self, 
        pdf_source: Union[str, Path, bytes],
        page_numbers: Optional[list[int]] = None
    ) -> list[ExtractedTable]:
        """Extrai todas as tabelas do PDF."""
        self._ensure_pdfplumber()
        
        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source
        
        tables = []
        
        with self._pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                if page_numbers and page_num not in page_numbers:
                    continue
                
                page_tables = page.extract_tables()
                
                for table in page_tables:
                    if not table or len(table) < 2:
                        continue
                    
                    headers = [str(h).strip() if h else "" for h in table[0]]
                    rows = []
                    
                    for row in table[1:]:
                        cleaned_row = [str(cell).strip() if cell else "" for cell in row]
                        if any(cleaned_row):
                            rows.append(cleaned_row)
                    
                    if headers and rows:
                        tables.append(ExtractedTable(
                            headers=headers,
                            rows=rows,
                            page_number=page_num
                        ))
        
        return tables
    
    def extract_text_by_page(
        self, 
        pdf_source: Union[str, Path, bytes]
    ) -> dict[int, str]:
        """Extrai texto por página."""
        self._ensure_pdfplumber()
        
        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source
        
        pages = {}
        
        with self._pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                pages[page_num] = text
        
        return pages


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
    from irpf_processor.domain.value_objects.money import Money
    
    total = Money.zero()
    for val in values:
        total = total + Money.from_number(val)
    
    if as_int:
        return total.to_int()
    return round(total.to_float(), 2)


def generate_item_id(content: str) -> str:
    """Gera ID único baseado no conteúdo."""
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()
