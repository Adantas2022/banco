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
from .equity_evolution import EquityEvolutionExtractor
from .receipt import ReceiptExtractor, is_receipt_document
from .payments import PaymentsExtractor
from .donations import DonationsExtractor
from .income_suspended import IncomeSuspendedHolderExtractor
# Extractors de Dependentes (BUGs #81767, #81773, #81775)
from .income_pf_dependents import IncomePFDependentsExtractor
from .accumulated_income_pj_dependents import AccumulatedIncomePJDependentsExtractor
from .income_suspended_dependents import IncomeSuspendedDependentsExtractor
from .rural import (
    # Brasil
    RuralPropertiesExtractor,
    RuralIncomeExpenditureExtractor,
    RuralResultsExtractor,
    RuralAssetsExtractor,
    RuralDebtsExtractor,
    LivestockMovementExtractor,
    # Exterior (BUGs #81768, #81770, #81781, #81783, #81784, #81788)
    RuralPropertiesAbroadExtractor,
    RuralIncomeExpenditureAbroadExtractor,
    RuralResultsAbroadExtractor,
    RuralDebtsAbroadExtractor,
    LivestockMovementAbroadExtractor,
    RuralAssetsAbroadExtractor,
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
    "EquityEvolutionExtractor",
    "ReceiptExtractor",
    "is_receipt_document",
    "PaymentsExtractor",
    "DonationsExtractor",
    "IncomeSuspendedHolderExtractor",
    # Dependentes (BUGs #81767, #81773, #81775)
    "IncomePFDependentsExtractor",
    "AccumulatedIncomePJDependentsExtractor",
    "IncomeSuspendedDependentsExtractor",
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
    "RuralAssetsAbroadExtractor",
]
