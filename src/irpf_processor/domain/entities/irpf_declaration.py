"""Entidade IRPFDeclaration - Declaração de Imposto de Renda extraída."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from irpf_processor.domain.value_objects import Confidence, DocumentId, TenantId


@dataclass
class TaxpayerIdentification:
    """Identificação do contribuinte."""

    cpf: str
    normalized_cpf: str
    name: str
    exercise_year: str
    calendar_year: str
    occupation_nature: Optional[str] = None
    main_occupation: Optional[str] = None
    type_ir: Optional[str] = None
    contact_and_address: Optional[dict[str, Any]] = None


@dataclass
class AssetItem:
    """Item de bem ou direito declarado."""

    id: str
    asset_group_code: str
    asset_code: str
    asset_description: str
    before_year_asset_value: float
    current_year_asset_value: float
    country_code: str
    country_name: str
    country_valid: bool
    page: int


@dataclass
class AssetsDeclaration:
    """Declaração de bens e direitos."""

    section_name: str
    items: list[AssetItem]
    last_year_total_value: float
    current_year_total_value: float
    pages_with_problems: list[int] = field(default_factory=list)


@dataclass
class IncomeItem:
    """Item de rendimento."""

    id: str
    beneficiary: str
    cpf: str
    payer_cnpj: str
    payer_name: str
    value: float
    page: int


@dataclass
class IncomeSubsection:
    """Subseção de rendimentos."""

    name: str
    code: str
    total_value: float
    valid_total: bool
    items: list[IncomeItem]


@dataclass
class ExemptIncome:
    """Rendimentos isentos e não tributáveis."""

    section_name: str
    total_value: float
    valid_total: bool
    subsections: dict[str, IncomeSubsection]


@dataclass
class LegalPersonIncomeItem:
    """Rendimento de pessoa jurídica."""

    id: str
    payer_name: str
    cpf_cnpj: str
    income_from_legal_person: float
    official_social_security_contribution: float
    tax_withheld_at_source: float
    thirteenth_salary: float
    irrf_on_thirteenth_salary: float
    page: int


@dataclass
class LegalPersonIncome:
    """Rendimentos tributáveis de pessoa jurídica."""

    section_name: str
    items: list[LegalPersonIncomeItem]
    total_values: dict[str, dict[str, Any]]


@dataclass
class RuralProperty:
    """Propriedade rural explorada."""

    id: str
    code: int
    participation: float
    exploration_condition: int
    name_and_location: str
    area: float
    cib: str
    participants: dict[str, list[dict[str, Any]]]
    page: int


@dataclass
class RuralIncomeItem:
    """Item de receita/despesa rural."""

    id: str
    month: str
    gross_revenue: float
    funding_expenses: float
    page: int


@dataclass
class IRPFDeclaration:
    """Declaração de IRPF completa."""

    document_id: DocumentId
    tenant_id: TenantId
    confidence: Confidence
    
    # Identificação
    taxpayer_identification: TaxpayerIdentification
    
    # Valores totais
    total_value: int
    valid_total: bool
    equity_evolution: int
    total_pages: int
    
    # Seções principais
    assets_declaration: Optional[AssetsDeclaration] = None
    debts_and_encumbrances: Optional[dict[str, Any]] = None
    exempt_income: Optional[ExemptIncome] = None
    exclusive_taxation_income: Optional[dict[str, Any]] = None
    income_from_legal_person_to_holder: Optional[LegalPersonIncome] = None
    income_from_legal_person_to_dependents: Optional[LegalPersonIncome] = None
    
    # Atividade rural
    exploited_rural_properties_in_brazil: Optional[dict[str, Any]] = None
    rural_income_and_expenditure_in_brazil: Optional[dict[str, Any]] = None
    calculation_of_rural_results_in_brazil: Optional[dict[str, Any]] = None
    rural_activity_assets_in_brazil: Optional[dict[str, Any]] = None
    rural_activity_debts_in_brazil: Optional[dict[str, Any]] = None
    
    # Exterior
    exploited_rural_properties_abroad: Optional[dict[str, Any]] = None
    rural_income_and_expenditure_abroad: Optional[dict[str, Any]] = None
    
    # Metadados
    created_at: datetime = field(default_factory=datetime.utcnow)
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: int = 0

    def is_high_confidence(self, threshold: float = 0.95) -> bool:
        """Verifica se a extração tem alta confiança."""
        return self.confidence.overall >= threshold

    def get_cpf(self) -> str:
        """Retorna CPF normalizado do contribuinte."""
        return self.taxpayer_identification.normalized_cpf

    def get_exercise_year(self) -> str:
        """Retorna ano-exercício da declaração."""
        return self.taxpayer_identification.exercise_year

    def get_assets_total(self) -> float:
        """Retorna total de bens do ano atual."""
        if self.assets_declaration:
            return self.assets_declaration.current_year_total_value
        return 0.0

    def has_rural_activity(self) -> bool:
        """Verifica se tem atividade rural."""
        return self.exploited_rural_properties_in_brazil is not None
