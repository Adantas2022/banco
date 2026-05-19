"""Enum DocumentCategory - categorias de documentos IRPF."""

from enum import Enum


class DocumentCategory(str, Enum):
    """Categoria do documento IRPF."""

    DECLARACAO = "DECLARACAO"
    RECIBO = "RECIBO"
    UNKNOWN = "UNKNOWN"

    def is_declaration(self) -> bool:
        return self == DocumentCategory.DECLARACAO

    def is_receipt(self) -> bool:
        return self == DocumentCategory.RECIBO
