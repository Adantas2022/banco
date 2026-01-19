"""Enumerações do domínio."""

from .auth_scope import AuthScope
from .document_category import DocumentCategory
from .document_status import DocumentStatus
from .pdf_type import PdfType

__all__ = [
    "AuthScope",
    "DocumentCategory",
    "DocumentStatus",
    "PdfType",
]
