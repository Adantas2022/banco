"""Enum PdfType - tipos de PDF detectados."""

from enum import Enum


class PdfType(str, Enum):
    """Tipos de PDF que podem ser processados."""

    DIGITAL = "DIGITAL"
    IMAGE = "IMAGE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"

    def requires_ocr(self) -> bool:
        """Verifica se requer OCR para extração."""
        return self in (PdfType.IMAGE, PdfType.MIXED)

    def is_extractable(self) -> bool:
        """Verifica se pode ser extraído."""
        return self != PdfType.UNKNOWN
