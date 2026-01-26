"""Extrator de tabelas de PDFs usando pdfplumber."""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Union
from pathlib import Path

from .field_extractors import normalize_cpf, normalize_cnpj


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


def parse_currency(value: str) -> float:
    if not value:
        return 0.0
    
    cleaned = re.sub(r"[^\d,.-]", "", value)
    cleaned = cleaned.replace(".", "").replace(",", ".")
    
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
