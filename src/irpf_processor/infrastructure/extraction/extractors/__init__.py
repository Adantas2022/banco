"""Módulo de extratores de seções IRPF."""

from .base import ISectionExtractor, ExtractionContext
from .taxpayer import TaxpayerExtractor
from .assets import AssetsExtractor
from .debts import DebtsExtractor
from .income_pj import IncomePJExtractor
from .income_pj_dependents import IncomePJDependentsExtractor
from .income_pf import IncomePFExtractor
from .accumulated_income_pj import AccumulatedIncomePJExtractor
from .exempt_income import ExemptIncomeExtractor
from .exclusive_income import ExclusiveIncomeExtractor
from .receipt import ReceiptExtractor, is_receipt_document
from .payments import PaymentsExtractor
from .donations import DonationsExtractor
from .income_suspended import IncomeSuspendedHolderExtractor
from .rural import (
    # Brasil
    RuralPropertiesExtractor,
    RuralIncomeExpenditureExtractor,
    RuralResultsExtractor,
    RuralAssetsExtractor,
    RuralDebtsExtractor,
    LivestockMovementExtractor,
    # Exterior (BUGs #81768, #81770, #81781, #81784, #81788)
    RuralPropertiesAbroadExtractor,
    RuralIncomeExpenditureAbroadExtractor,
    RuralResultsAbroadExtractor,
    RuralDebtsAbroadExtractor,
    LivestockMovementAbroadExtractor,
)

__all__ = [
    "ISectionExtractor",
    "ExtractionContext",
    "TaxpayerExtractor",
    "AssetsExtractor",
    "DebtsExtractor",
    "IncomePJExtractor",
    "IncomePJDependentsExtractor",
    "IncomePFExtractor",
    "AccumulatedIncomePJExtractor",
    "ExemptIncomeExtractor",
    "ExclusiveIncomeExtractor",
    "ReceiptExtractor",
    "is_receipt_document",
    "PaymentsExtractor",
    "DonationsExtractor",
    "IncomeSuspendedHolderExtractor",
    # Rural Brasil
    "RuralPropertiesExtractor",
    "RuralIncomeExpenditureExtractor",
    "RuralResultsExtractor",
    "RuralAssetsExtractor",
    "RuralDebtsExtractor",
    "LivestockMovementExtractor",
    # Rural Exterior
    "RuralPropertiesAbroadExtractor",
    "RuralIncomeExpenditureAbroadExtractor",
    "RuralResultsAbroadExtractor",
    "RuralDebtsAbroadExtractor",
    "LivestockMovementAbroadExtractor",
]
