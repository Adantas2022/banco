"""Parser IRPF refatorado com Clean Code e Design Patterns.

Este módulo implementa:
- Strategy Pattern: cada seção tem seu próprio extrator
- Facade Pattern: IRPFParser orquestra todos os extratores
- Single Responsibility Principle: cada classe tem uma única responsabilidade
- Dynamic Selection: detecta seções presentes e usa apenas extratores relevantes
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from irpf_processor.shared.logging import get_logger

from .extractors import (
    ExtractionContext,
    ISectionExtractor,
    TaxpayerExtractor,
    AssetsExtractor,
    IncomePJExtractor,
    ExemptIncomeExtractor,
    ExclusiveIncomeExtractor,
    RuralPropertiesExtractor,
    RuralIncomeExpenditureExtractor,
    RuralResultsExtractor,
    RuralAssetsExtractor,
    RuralDebtsExtractor,
)
from .version_detector import VersionDetector, DocumentProfile

logger = get_logger(__name__)

OPTIONAL_SECTIONS = {
    "exploited_rural_properties_in_brazil",
    "rural_income_and_expenditure_in_brazil",
    "calculation_of_rural_results_in_brazil",
    "livestock_movement_in_brazil",
    "rural_activity_assets_in_brazil",
    "rural_activity_debts_in_brazil",
    "exploited_rural_properties_abroad",
    "rural_income_and_expenditure_abroad",
    "calculation_of_rural_results_abroad",
    "rural_activity_assets_abroad",
    "rural_activity_debts_abroad",
    "livestock_movement_abroad",
    "income_from_individual_to_holder",
    "income_from_individual_to_dependents",
    "income_from_legal_person_to_dependents",
    "accumulated_income_from_legal_person_to_holder",
    "accumulated_income_from_legal_person_to_dependents",
}


@dataclass
class IRPFDeclarationResult:
    """Resultado da extração de uma declaração IRPF."""
    
    taxpayer_identification: dict = field(default_factory=dict)
    total_value: float = 0.0
    valid_total: bool = True
    equity_evolution: float = 0.0
    assets_declaration: Optional[dict] = None
    debts_and_encumbrances: Optional[dict] = None
    exempt_income: Optional[dict] = None
    exclusive_taxation_income: Optional[dict] = None
    income_from_individual_to_holder: Optional[Any] = None
    income_from_individual_to_dependents: Optional[Any] = None
    income_from_legal_person_to_holder: Optional[dict] = None
    income_from_legal_person_to_dependents: Optional[Any] = None
    income_from_legal_person_to_holder_with_suspended_requirements: Optional[Any] = None
    income_from_legal_person_to_dependents_with_suspended_requirements: Optional[Any] = None
    accumulated_income_from_legal_person_to_holder: Optional[Any] = None
    accumulated_income_from_legal_person_to_dependents: Optional[Any] = None
    exploited_rural_properties_in_brazil: Optional[dict] = None
    rural_income_and_expenditure_in_brazil: Optional[dict] = None
    calculation_of_rural_results_in_brazil: Optional[dict] = None
    livestock_movement_in_brazil: Optional[Any] = None
    rural_activity_assets_in_brazil: Optional[dict] = None
    rural_activity_debts_in_brazil: Optional[dict] = None
    exploited_rural_properties_abroad: Optional[Any] = None
    rural_income_and_expenditure_abroad: Optional[Any] = None
    calculation_of_rural_results_abroad: Optional[Any] = None
    rural_activity_assets_abroad: Optional[Any] = None
    rural_activity_debts_abroad: Optional[Any] = None
    livestock_movement_abroad: Optional[Any] = None
    total_pages: int = 0
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "taxpayer_identification": self.taxpayer_identification,
            "total_value": self.total_value,
            "valid_total": self.valid_total,
            "equity_evolution": self.equity_evolution,
            "assets_declaration": self.assets_declaration,
            "debts_and_encumbrances": self.debts_and_encumbrances or {},
            "exempt_income": self.exempt_income,
            "exclusive_taxation_income": self.exclusive_taxation_income,
            "income_from_individual_to_holder": self.income_from_individual_to_holder,
            "income_from_individual_to_dependents": self.income_from_individual_to_dependents,
            "income_from_legal_person_to_holder": self.income_from_legal_person_to_holder,
            "income_from_legal_person_to_dependents": self.income_from_legal_person_to_dependents,
            "income_from_legal_person_to_holder_with_suspended_requirements": self.income_from_legal_person_to_holder_with_suspended_requirements,
            "income_from_legal_person_to_dependents_with_suspended_requirements": self.income_from_legal_person_to_dependents_with_suspended_requirements,
            "accumulated_income_from_legal_person_to_holder": self.accumulated_income_from_legal_person_to_holder,
            "accumulated_income_from_legal_person_to_dependents": self.accumulated_income_from_legal_person_to_dependents,
            "exploited_rural_properties_in_brazil": self.exploited_rural_properties_in_brazil,
            "rural_income_and_expenditure_in_brazil": self.rural_income_and_expenditure_in_brazil,
            "calculation_of_rural_results_in_brazil": self.calculation_of_rural_results_in_brazil,
            "livestock_movement_in_brazil": self.livestock_movement_in_brazil,
            "rural_activity_assets_in_brazil": self.rural_activity_assets_in_brazil,
            "rural_activity_debts_in_brazil": self.rural_activity_debts_in_brazil,
            "exploited_rural_properties_abroad": self.exploited_rural_properties_abroad,
            "rural_income_and_expenditure_abroad": self.rural_income_and_expenditure_abroad,
            "calculation_of_rural_results_abroad": self.calculation_of_rural_results_abroad,
            "rural_activity_assets_abroad": self.rural_activity_assets_abroad,
            "rural_activity_debts_abroad": self.rural_activity_debts_abroad,
            "livestock_movement_abroad": self.livestock_movement_abroad,
            "total_pages": self.total_pages,
        }


class IRPFParser:
    """Parser IRPF que orquestra extratores especializados (Facade Pattern).
    
    Características:
    - Detecção automática de versão e seções do documento
    - Seleção dinâmica de extratores baseada no conteúdo
    - Extensível: fácil adicionar novos extratores
    """
    
    EXTRACTOR_MAPPING: dict[str, type[ISectionExtractor]] = {
        "taxpayer_identification": TaxpayerExtractor,
        "assets_declaration": AssetsExtractor,
        "income_from_legal_person_to_holder": IncomePJExtractor,
        "exempt_income": ExemptIncomeExtractor,
        "exclusive_taxation_income": ExclusiveIncomeExtractor,
        "exploited_rural_properties_in_brazil": RuralPropertiesExtractor,
        "rural_income_and_expenditure_in_brazil": RuralIncomeExpenditureExtractor,
        "calculation_of_rural_results_in_brazil": RuralResultsExtractor,
        "rural_activity_assets_in_brazil": RuralAssetsExtractor,
        "rural_activity_debts_in_brazil": RuralDebtsExtractor,
    }
    
    def __init__(
        self, 
        extractors: Optional[list[ISectionExtractor]] = None,
        auto_detect: bool = True
    ):
        self._custom_extractors = extractors
        self._auto_detect = auto_detect
        self._version_detector = VersionDetector()
        self._pdfplumber = None
        self._last_profile: Optional[DocumentProfile] = None
    
    def _create_extractors_for_profile(
        self, 
        profile: DocumentProfile
    ) -> list[ISectionExtractor]:
        """Cria extratores dinamicamente baseado no perfil do documento."""
        extractors = []
        
        extractors.append(TaxpayerExtractor())
        
        for section_name in profile.detected_sections:
            if section_name == "taxpayer_identification":
                continue
            
            extractor_class = self.EXTRACTOR_MAPPING.get(section_name)
            if extractor_class:
                extractors.append(extractor_class())
        
        return extractors
    
    def _create_default_extractors(self) -> list[ISectionExtractor]:
        return [cls() for cls in self.EXTRACTOR_MAPPING.values()]
    
    def _ensure_pdfplumber(self):
        if self._pdfplumber is None:
            import pdfplumber
            self._pdfplumber = pdfplumber
    
    def parse(self, pdf_source: Union[str, Path, bytes]) -> IRPFDeclarationResult:
        """Parseia documento IRPF com detecção dinâmica de seções."""
        context = self._create_context(pdf_source)
        result = IRPFDeclarationResult(total_pages=context.total_pages)
        
        if self._auto_detect and not self._custom_extractors:
            profile = self._version_detector.detect(context)
            self._last_profile = profile
            extractors = self._create_extractors_for_profile(profile)
            
            context.add_warning(
                f"Documento detectado: IRPF {profile.exercise_year} "
                f"({len(profile.detected_sections)} seções encontradas)"
            )
        else:
            extractors = self._custom_extractors or self._create_default_extractors()
        
        for extractor in extractors:
            self._run_extractor(extractor, context, result)
        
        result.warnings = context.warnings
        result.confidence = self._calculate_confidence(result)
        result.total_value = self._calculate_total_value(result)
        
        return result
    
    def get_document_profile(self) -> Optional[DocumentProfile]:
        """Retorna o perfil do último documento processado."""
        return self._last_profile
    
    def _create_context(self, pdf_source: Union[str, Path, bytes]) -> ExtractionContext:
        self._ensure_pdfplumber()
        
        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source
        
        full_text = ""
        pages_text: dict[int, str] = {}
        total_pages = 0
        
        with self._pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                pages_text[page_num] = page_text
                full_text += page_text + "\n"
        
        return ExtractionContext(
            full_text=full_text,
            pages_text=pages_text,
            total_pages=total_pages
        )
    
    def _run_extractor(
        self,
        extractor: ISectionExtractor,
        context: ExtractionContext,
        result: IRPFDeclarationResult
    ) -> None:
        if not extractor.can_extract(context):
            return
        
        try:
            data = extractor.extract(context)
            if data:
                self._assign_to_result(extractor.section_name, data, result)
        except Exception as e:
            if extractor.section_name in OPTIONAL_SECTIONS:
                logger.debug(
                    "Secao opcional nao extraida",
                    section=extractor.section_name,
                    error=str(e)
                )
            else:
                context.add_warning(f"Erro ao extrair {extractor.section_name}: {str(e)}")
    
    def _assign_to_result(
        self, 
        section_name: str, 
        data: dict, 
        result: IRPFDeclarationResult
    ) -> None:
        if hasattr(result, section_name):
            setattr(result, section_name, data)
    
    def _calculate_confidence(self, result: IRPFDeclarationResult) -> float:
        scores = []
        
        if result.taxpayer_identification.get("normalized_cpf"):
            scores.append(1.0)
        
        if result.taxpayer_identification.get("name"):
            scores.append(1.0)
        
        if result.assets_declaration:
            scores.append(0.9)
        
        if result.income_from_legal_person_to_holder:
            scores.append(0.9)
        
        if not scores:
            return 0.0
        
        return sum(scores) / len(scores)
    
    def _calculate_total_value(self, result: IRPFDeclarationResult) -> float:
        if result.assets_declaration:
            return result.assets_declaration.get("current_year_total_value", 0.0)
        return 0.0


# Alias para compatibilidade
FullIRPFParser = IRPFParser
