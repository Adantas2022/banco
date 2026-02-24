"""Extrator de texto de PDFs."""

from pathlib import Path
from typing import Optional, Union

from irpf_processor.domain.enums import PdfType


class PdfTextExtractor:
    """Extrai texto de PDFs usando pdfplumber."""
    
    def __init__(self):
        self._pdfplumber = None
        self._last_confidence: float = 1.0
    
    def _ensure_pdfplumber(self):
        if self._pdfplumber is None:
            import pdfplumber
            self._pdfplumber = pdfplumber
    
    def extract_text(self, pdf_source: Union[str, Path, bytes]) -> str:
        """Extrai texto completo do PDF."""
        self._ensure_pdfplumber()
        
        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source
        
        text_parts = []
        
        with self._pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        return "\n".join(text_parts)
    
    def extract_text_by_page(self, pdf_source: Union[str, Path, bytes]) -> list[str]:
        """Extrai texto página por página."""
        self._ensure_pdfplumber()
        
        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source
        
        pages = []
        
        with self._pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                pages.append(page_text)
        
        return pages
    
    def detect_pdf_type(self, pdf_source: Union[str, Path, bytes]) -> PdfType:
        """Detecta se o PDF é digital ou imagem."""
        self._ensure_pdfplumber()
        
        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source
        
        with self._pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            pages_with_text = 0
            
            for page in pdf.pages:
                text = page.extract_text()
                if text and len(text.strip()) > 100:
                    pages_with_text += 1
        
        if total_pages == 0:
            return PdfType.UNKNOWN
        
        text_ratio = pages_with_text / total_pages
        
        if text_ratio >= 0.8:
            self._last_confidence = 1.0
            return PdfType.DIGITAL
        elif text_ratio <= 0.2:
            self._last_confidence = 0.7
            return PdfType.IMAGE
        else:
            self._last_confidence = 0.8
            return PdfType.MIXED
    
    def get_confidence(self) -> float:
        """Retorna confiança da última operação."""
        return self._last_confidence
