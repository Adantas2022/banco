"""Extrator de tabelas de PDFs usando pdfplumber."""

from dataclasses import dataclass
from typing import Optional, Union
from pathlib import Path

# Re-exporta funções de currency_utils para manter compatibilidade retroativa
from .currency_utils import (
    CurrencyFormat,
    detect_currency_format,
    parse_currency,
    sum_currency_values,
)

# Exporta explicitamente para facilitar imports
__all__ = [
    'ExtractedTable',
    'TableExtractor',
    'CurrencyFormat',
    'detect_currency_format',
    'parse_currency',
    'sum_currency_values',
    'generate_item_id',
]


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
    """Extrai tabelas estruturadas de PDFs.

    Em produção, usa ``safe_pdf_extractor`` (subprocesso) para proteção
    contra travamentos.  Se ``_pdfplumber`` for injetado (testes), usa
    o pdfplumber diretamente.
    """

    def __init__(self):
        self._pdfplumber = None

    def _ensure_pdfplumber(self):
        if self._pdfplumber is None:
            import pdfplumber
            self._pdfplumber = pdfplumber

    def extract_tables(
        self,
        pdf_source: Union[str, Path, bytes],
        page_numbers: Optional[list[int]] = None,
    ) -> list[ExtractedTable]:
        """Extrai todas as tabelas do PDF."""
        if self._pdfplumber is not None:
            return self._extract_tables_direct(pdf_source, page_numbers)
        return self._extract_tables_safe(pdf_source, page_numbers)

    def extract_text_by_page(
        self,
        pdf_source: Union[str, Path, bytes],
    ) -> dict[int, str]:
        """Extrai texto por página."""
        if self._pdfplumber is not None:
            return self._extract_text_by_page_direct(pdf_source)
        return self._extract_text_by_page_safe(pdf_source)

    # ─── Safe (subprocess) paths ──────────────────────────────────

    def _extract_tables_safe(
        self,
        pdf_source: Union[str, Path, bytes],
        page_numbers: Optional[list[int]] = None,
    ) -> list[ExtractedTable]:
        from .safe_pdf_extractor import extract_tables as safe_extract

        raw_tables, _ = safe_extract(pdf_source, page_numbers=page_numbers)
        tables: list[ExtractedTable] = []
        for raw in raw_tables:
            data = raw["data"]
            if not data or len(data) < 2:
                continue
            headers = [str(h).strip() if h else "" for h in data[0]]
            rows = []
            for row in data[1:]:
                cleaned = [str(cell).strip() if cell else "" for cell in row]
                if any(cleaned):
                    rows.append(cleaned)
            if headers and rows:
                tables.append(ExtractedTable(
                    headers=headers, rows=rows, page_number=raw["page_number"],
                ))
        return tables

    def _extract_text_by_page_safe(
        self, pdf_source: Union[str, Path, bytes],
    ) -> dict[int, str]:
        from .safe_pdf_extractor import extract_all_text

        pages_text, _, _ = extract_all_text(pdf_source)
        return pages_text

    # ─── Direct (injected pdfplumber) paths — kept for tests ─────

    def _extract_tables_direct(
        self,
        pdf_source: Union[str, Path, bytes],
        page_numbers: Optional[list[int]] = None,
    ) -> list[ExtractedTable]:
        pdf_file = self._to_file(pdf_source)
        tables: list[ExtractedTable] = []
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
                        cleaned = [str(cell).strip() if cell else "" for cell in row]
                        if any(cleaned):
                            rows.append(cleaned)
                    if headers and rows:
                        tables.append(ExtractedTable(
                            headers=headers, rows=rows, page_number=page_num,
                        ))
        return tables

    def _extract_text_by_page_direct(
        self, pdf_source: Union[str, Path, bytes],
    ) -> dict[int, str]:
        pdf_file = self._to_file(pdf_source)
        pages: dict[int, str] = {}
        with self._pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                pages[page_num] = page.extract_text() or ""
        return pages

    @staticmethod
    def _to_file(pdf_source: Union[str, Path, bytes]):
        if isinstance(pdf_source, bytes):
            import io
            return io.BytesIO(pdf_source)
        return pdf_source


def generate_item_id(content: str) -> str:
    """Gera ID único baseado no conteúdo."""
    import hashlib
    return hashlib.md5(content.encode()).hexdigest()
