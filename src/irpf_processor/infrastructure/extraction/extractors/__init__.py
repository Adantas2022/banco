"""Módulo de extratores de seções IRPF."""

from .base import ISectionExtractor, ExtractionContext
from .taxpayer import TaxpayerExtractor
from .assets import AssetsExtractor
from .income_pj import IncomePJExtractor
from .exempt_income import ExemptIncomeExtractor
from .exclusive_income import ExclusiveIncomeExtractor
from .receipt import ReceiptExtractor, is_receipt_document
from .rural import (
    RuralPropertiesExtractor,
    RuralIncomeExpenditureExtractor,
    RuralResultsExtractor,
    RuralAssetsExtractor,
    RuralDebtsExtractor,
)

__all__ = [
    "ISectionExtractor",
    "ExtractionContext",
    "TaxpayerExtractor",
    "AssetsExtractor",
    "IncomePJExtractor",
    "ExemptIncomeExtractor",
    "ExclusiveIncomeExtractor",
    "ReceiptExtractor",
    "is_receipt_document",
    "RuralPropertiesExtractor",
    "RuralIncomeExpenditureExtractor",
    "RuralResultsExtractor",
    "RuralAssetsExtractor",
    "RuralDebtsExtractor",
]
