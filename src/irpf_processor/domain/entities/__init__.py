"""Entidades do domínio."""

from .api_key import ApiKey
from .document import Document
from .extraction_result import ExtractionResult
from .irpf_declaration import (
    IRPFDeclaration,
    TaxpayerIdentification,
    AssetsDeclaration,
    AssetItem,
    ExemptIncome,
    LegalPersonIncome,
)

__all__ = [
    "ApiKey",
    "Document",
    "ExtractionResult",
    "IRPFDeclaration",
    "TaxpayerIdentification",
    "AssetsDeclaration",
    "AssetItem",
    "ExemptIncome",
    "LegalPersonIncome",
]
