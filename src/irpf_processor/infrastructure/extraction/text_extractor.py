"""Extrator de texto de PDFs."""

from pathlib import Path
from typing import Union

from irpf_processor.domain.enums import PdfType


class PdfTextExtractor:
    """Extrai texto de PDFs usando pdfplumber.

    Em produção, usa ``safe_pdf_extractor`` (subprocesso com signal.SIGALRM)
    para proteção contra travamentos.  Se ``_pdfplumber`` for injetado
    externamente (testes), usa o pdfplumber diretamente.
    """

    def __init__(self):
        self._pdfplumber = None
        self._last_confidence: float = 1.0

    def _ensure_pdfplumber(self):
        if self._pdfplumber is None:
            import pdfplumber
            self._pdfplumber = pdfplumber

    def extract_text(self, pdf_source: Union[str, Path, bytes]) -> str:
        """Extrai texto completo do PDF."""
        if self._pdfplumber is not None:
            return self._extract_text_direct(pdf_source)
        return self._extract_text_safe(pdf_source)

    def extract_text_by_page(self, pdf_source: Union[str, Path, bytes]) -> list[str]:
        """Extrai texto página por página."""
        if self._pdfplumber is not None:
            return self._extract_text_by_page_direct(pdf_source)
        return self._extract_text_by_page_safe(pdf_source)

    def detect_pdf_type(self, pdf_source: Union[str, Path, bytes]) -> PdfType:
        """Detecta se o PDF é digital ou imagem."""
        if self._pdfplumber is not None:
            return self._detect_pdf_type_direct(pdf_source)
        return self._detect_pdf_type_safe(pdf_source)

    def get_confidence(self) -> float:
        """Retorna confiança da última operação."""
        return self._last_confidence

    # ─── Safe (subprocess) paths ──────────────────────────────────

    def _extract_text_safe(self, pdf_source: Union[str, Path, bytes]) -> str:
        from .safe_pdf_extractor import extract_all_text

        pages_text, _, _, _ = extract_all_text(pdf_source)
        return "\n".join(
            pages_text[k] for k in sorted(pages_text.keys()) if pages_text[k]
        )

    def _extract_text_by_page_safe(self, pdf_source: Union[str, Path, bytes]) -> list[str]:
        from .safe_pdf_extractor import extract_all_text

        pages_text, _, _, _ = extract_all_text(pdf_source)
        return [pages_text[k] for k in sorted(pages_text.keys())]

    def _detect_pdf_type_safe(self, pdf_source: Union[str, Path, bytes]) -> PdfType:
        from .safe_pdf_extractor import extract_all_text

        pages_text, total_pages, _, _ = extract_all_text(pdf_source)
        if total_pages == 0:
            return PdfType.UNKNOWN

        pages_with_text = sum(
            1 for t in pages_text.values() if t and len(t.strip()) > 100
        )
        return self._classify_type(pages_with_text, total_pages)

    # ─── Direct (injected pdfplumber) paths — kept for tests ─────

    def _extract_text_direct(self, pdf_source: Union[str, Path, bytes]) -> str:
        pdf_file = self._to_file(pdf_source)
        text_parts = []
        with self._pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    def _extract_text_by_page_direct(self, pdf_source: Union[str, Path, bytes]) -> list[str]:
        pdf_file = self._to_file(pdf_source)
        pages = []
        with self._pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return pages

    def _detect_pdf_type_direct(self, pdf_source: Union[str, Path, bytes]) -> PdfType:
        pdf_file = self._to_file(pdf_source)
        with self._pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            pages_with_text = 0
            for page in pdf.pages:
                text = page.extract_text()
                if text and len(text.strip()) > 100:
                    pages_with_text += 1

        if total_pages == 0:
            return PdfType.UNKNOWN
        return self._classify_type(pages_with_text, total_pages)

    # ─── Shared helpers ───────────────────────────────────────────

    def _classify_type(self, pages_with_text: int, total_pages: int) -> PdfType:
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

    @staticmethod
    def _to_file(pdf_source: Union[str, Path, bytes]):
        if isinstance(pdf_source, bytes):
            import io
            return io.BytesIO(pdf_source)
        return pdf_source
