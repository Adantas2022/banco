"""Parser IRPF refatorado com Clean Code e Design Patterns.

Este módulo implementa:
- Strategy Pattern: cada seção tem seu próprio extrator
- Facade Pattern: IRPFParser orquestra todos os extratores
- Single Responsibility Principle: cada classe tem uma única responsabilidade
- Dynamic Selection: detecta seções presentes e usa apenas extratores relevantes
- Multi-Version Support: templates YAML para diferentes anos
"""

from __future__ import annotations

import asyncio
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from irpf_processor.shared.logging import get_logger
from irpf_processor.domain.enums import DocumentCategory
from irpf_processor.domain.services import ConfidenceCalculatorFactory, ConfidenceResult

from .extractors import (
    ExtractionContext,
    ISectionExtractor,
    TaxpayerExtractor,
    AssetsExtractor,
    DebtsExtractor,
    IncomePJExtractor,
    IncomePJDependentsExtractor,
    IncomePFExtractor,
    AccumulatedIncomePJExtractor,
    ExemptIncomeExtractor,
    ExclusiveIncomeExtractor,
    RuralPropertiesExtractor,
    RuralIncomeExpenditureExtractor,
    RuralResultsExtractor,
    RuralAssetsExtractor,
    RuralDebtsExtractor,
    LivestockMovementExtractor,
    PaymentsExtractor,
    DonationsExtractor,
    ReceiptExtractor,
    # Extractors holder suspended
    IncomeSuspendedHolderExtractor,
    # Extractors dependentes (BUGs #81767, #81773, #81775)
    IncomePFDependentsExtractor,
    AccumulatedIncomePJDependentsExtractor,
    IncomeSuspendedDependentsExtractor,
    # Extractors rural exterior (BUGs #81768, #81770, #81781, #81783, #81784, #81788)
    RuralPropertiesAbroadExtractor,
    RuralIncomeExpenditureAbroadExtractor,
    RuralResultsAbroadExtractor,
    RuralDebtsAbroadExtractor,
    LivestockMovementAbroadExtractor,
    RuralAssetsAbroadExtractor,
)
from .version_detector import VersionDetector, DocumentProfile
from .validation_executor import ValidationExecutor
from irpf_processor.templates import IRPFTemplate
from irpf_processor.templates.registry import YamlTemplateRegistry, ITemplateRegistry

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

NON_MONETARY_KEYS = {"page", "total_pages", "total_properties", "code", "country_code", "exploration_condition"}


def _normalize_floats(obj):
    if isinstance(obj, dict):
        return {k: _normalize_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_floats(v) for v in obj]
    if isinstance(obj, float):
        return round(obj, 2)
    return obj


@dataclass
class IRPFDeclarationResult:
    """Resultado da extração de uma declaração IRPF."""
    
    taxpayer_identification: dict = field(default_factory=dict)
    total_value: int = 0
    valid_total: bool = True
    equity_evolution: int = 0
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
    payments_made: Optional[dict] = None
    donations_made: Optional[dict] = None
    total_pages: int = 0
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0
    
    def to_dict(self) -> dict:
        raw = {
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
            "payments_made": self.payments_made,
            "donations_made": self.donations_made,
            "total_pages": self.total_pages,
        }
        return _normalize_floats(raw)


class IRPFParser:
    """Parser IRPF que orquestra extratores especializados (Facade Pattern).
    
    Características:
    - Detecção automática de versão e seções do documento
    - Seleção dinâmica de extratores baseada no conteúdo
    - Suporte a múltiplas versões via templates YAML
    - Extensível: fácil adicionar novos extratores
    
    Exemplo:
        parser = IRPFParser()
        result = parser.parse("declaracao.pdf")
        
        print(f"Versão: {parser.detected_version}")
        print(f"Template: {parser.current_template.description}")
    """
    
    EXTRACTOR_MAPPING: dict[str, type[ISectionExtractor]] = {
        "taxpayer_identification": TaxpayerExtractor,
        "assets_declaration": AssetsExtractor,
        "debts_and_encumbrances": DebtsExtractor,
        "income_from_legal_person_to_holder": IncomePJExtractor,
        "income_from_legal_person_to_dependents": IncomePJDependentsExtractor,
        "income_from_individual_to_holder": IncomePFExtractor,
        "accumulated_income_from_legal_person_to_holder": AccumulatedIncomePJExtractor,
        "exempt_income": ExemptIncomeExtractor,
        "exclusive_taxation_income": ExclusiveIncomeExtractor,
        "exploited_rural_properties_in_brazil": RuralPropertiesExtractor,
        "rural_income_and_expenditure_in_brazil": RuralIncomeExpenditureExtractor,
        "calculation_of_rural_results_in_brazil": RuralResultsExtractor,
        "rural_activity_assets_in_brazil": RuralAssetsExtractor,
        "rural_activity_debts_in_brazil": RuralDebtsExtractor,
        "livestock_movement_in_brazil": LivestockMovementExtractor,
        "payments_made": PaymentsExtractor,
        "donations_made": DonationsExtractor,
        # Holder with suspended requirements (BUG #81776)
        "income_from_legal_person_to_holder_with_suspended_requirements": IncomeSuspendedHolderExtractor,
        # Dependentes (BUGs #81767, #81773, #81775)
        "income_from_individual_to_dependents": IncomePFDependentsExtractor,
        "accumulated_income_from_legal_person_to_dependents": AccumulatedIncomePJDependentsExtractor,
        "income_from_legal_person_to_dependents_with_suspended_requirements": IncomeSuspendedDependentsExtractor,
        # Rural Exterior (BUGs #81768, #81770, #81781, #81783, #81784, #81788)
        "exploited_rural_properties_abroad": RuralPropertiesAbroadExtractor,
        "rural_income_and_expenditure_abroad": RuralIncomeExpenditureAbroadExtractor,
        "calculation_of_rural_results_abroad": RuralResultsAbroadExtractor,
        "rural_activity_assets_abroad": RuralAssetsAbroadExtractor,
        "rural_activity_debts_abroad": RuralDebtsAbroadExtractor,
        "livestock_movement_abroad": LivestockMovementAbroadExtractor,
    }
    
    def __init__(
        self, 
        extractors: Optional[list[ISectionExtractor]] = None,
        auto_detect: bool = True,
        template_registry: Optional[ITemplateRegistry] = None,
        enable_validation: bool = True,
        max_llm_parallel: int = 5
    ):
        self._custom_extractors = extractors
        self._auto_detect = auto_detect
        self._version_detector = VersionDetector()
        self._template_registry = template_registry or YamlTemplateRegistry()
        self._pdfplumber = None
        self._last_profile: Optional[DocumentProfile] = None
        self._last_context: Optional[ExtractionContext] = None
        self._current_template: Optional[IRPFTemplate] = None
        self._detected_version: Optional[str] = None
        self._enable_validation = enable_validation
        self._validation_executor: Optional[ValidationExecutor] = None
        self._validation_summary: Optional[dict] = None
        self._llm_semaphore = asyncio.Semaphore(max_llm_parallel)
    
    @property
    def detected_version(self) -> Optional[str]:
        """Retorna a versão detectada do último documento processado."""
        return self._detected_version
    
    @property
    def current_template(self) -> Optional[IRPFTemplate]:
        """Retorna o template usado no último processamento."""
        return self._current_template
    
    @property
    def available_versions(self) -> list[str]:
        return self._template_registry.list_versions()
    
    @property
    def validation_summary(self) -> Optional[dict]:
        return self._validation_summary
    
    @property
    def last_extraction_context(self) -> Optional[ExtractionContext]:
        """Retorna o ExtractionContext do último documento processado.
        
        Permite acesso aos textos (full_text, pages_text) usados na
        aplicação de REGEX durante a extração.
        """
        return self._last_context
    
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
    
    def parse(
        self, 
        pdf_source: Union[str, Path, bytes],
        version: Optional[str] = None,
    ) -> IRPFDeclarationResult:
        """Parseia documento IRPF com detecção dinâmica de seções e versão.
        
        Args:
            pdf_source: Caminho do PDF, Path ou bytes
            version: Versão específica do template (opcional, detecta automaticamente)
            
        Returns:
            IRPFDeclarationResult com os dados extraídos
        """
        context = self._create_context(pdf_source)
        self._last_context = context
        result = IRPFDeclarationResult(total_pages=context.total_pages)
        
        self._detected_version = version or self._template_registry.detect_version(context.full_text)
        self._current_template = self._template_registry.get_template_or_latest(self._detected_version)
        
        if self._current_template:
            context.add_warning(
                f"Template: {self._current_template.description} (v{self._current_template.version})"
            )
        else:
            context.add_warning("Nenhum template encontrado, usando extração genérica")
        
        if self._enable_validation:
            self._validation_executor = ValidationExecutor(self._current_template)
        
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
        
        # for extractor in extractors:
        #     self._run_extractor(extractor, context, result)

        # Run extractors in parallel
        asyncio.run(self.run_all_extractors(extractors, context, result))

        # self._propagate_rural_exempt_to_exempt_income(result)

        if self._enable_validation and self._validation_executor:
            self._validation_summary = self._validation_executor.get_validation_summary(
                result.to_dict()
            )
            valid_totals = self._validation_summary.get("valid_totals", 0)
            invalid_totals = self._validation_summary.get("invalid_totals", 0)
            if invalid_totals > 0:
                context.add_warning(
                    f"Validacao de totais: {valid_totals} OK, {invalid_totals} com divergencia"
                )
        
        result.warnings = context.warnings
        result.confidence = self._calculate_confidence(result)
        result.total_value = self._calculate_total_value(result)
        result.equity_evolution = self._calculate_equity_evolution(result)
        
        return result

    
    async def run_all_extractors(self, extractors, context, result):
        tasks = [
            self._run_extractor_async(extractor, context, result)
            for extractor in extractors
        ]
        await asyncio.gather(*tasks)

    
    async def _run_extractor_async(self, extractor, context, result):
        if not extractor.can_extract(context):
            return

        try:
            use_llm = getattr(extractor, 'LLM_EXTRACTION_ENABLED', False)
            has_llm_method = hasattr(extractor, 'extract_with_llm')

            if use_llm and has_llm_method:
                async with self._llm_semaphore:
                    context.add_warning(f"[LLM] Starting async LLM for {extractor.section_name}")
                    try:
                        llm_prompt = getattr(extractor, 'LLM_PROMPT', None)
                        data = await extractor.extract_with_llm(context, llm_prompt)
                    except Exception as e:
                        context.add_warning(f"[LLM] Failed: {e}, fallback to sync extract()")
                        loop = asyncio.get_running_loop()
                        data = await loop.run_in_executor(None, extractor.extract, context)

            else:
                # Sync extractor → run in background thread
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(None, extractor.extract, context)

            if data:
                if self._enable_validation and self._validation_executor:
                    data = self._validation_executor.validate_section(
                        extractor.section_name, data, context
                    )
                self._assign_to_result(extractor.section_name, data, result)

        except Exception as e:
            context.add_warning(f"Erro ao extrair {extractor.section_name}: {e}")


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
                page_text = unicodedata.normalize("NFC", page.extract_text() or "")
                pages_text[page_num] = page_text
                full_text += page_text + "\n"
        
        pdf_path_str = str(pdf_source) if not isinstance(pdf_source, bytes) else None
        
        context = ExtractionContext(
            full_text=full_text,
            pages_text=pages_text,
            total_pages=total_pages,
            pdf_path=pdf_path_str
        )
        
        if self._is_scanned_pdf(full_text, total_pages):
            context.add_warning(
                "PDF_SCANNED: Este documento parece ser escaneado (imagem). "
                "Recomendado processar via OCR para melhor extracao."
            )
            logger.warning(
                "PDF escaneado detectado",
                total_pages=total_pages,
                text_chars=len(full_text.strip())
            )
        
        return context
    
    def _is_scanned_pdf(self, full_text: str, total_pages: int) -> bool:
        text_stripped = full_text.strip()
        chars_per_page = len(text_stripped) / max(total_pages, 1)
        return chars_per_page < 50
    
    def _run_extractor(
        self,
        extractor: ISectionExtractor,
        context: ExtractionContext,
        result: IRPFDeclarationResult
    ) -> None:
        if not extractor.can_extract(context):
            return
        
        try:
            # Check if extractor has LLM flag and extract_with_llm method
            use_llm = getattr(extractor, 'LLM_EXTRACTION_ENABLED', False)
            has_llm_method = hasattr(extractor, 'extract_with_llm')
            
            if use_llm and has_llm_method:
                # Use async extract_with_llm method
                context.add_warning(f"[LLM] Starting LLM extraction for {extractor.section_name}...")
                try:
                    # Pass extractor's own LLM_PROMPT as the custom prompt
                    llm_prompt = getattr(extractor, 'LLM_PROMPT', None)
                    data = asyncio.run(extractor.extract_with_llm(context, llm_prompt))

                    if data:
                        context.add_warning(f"[LLM] ✓ LLM extraction succeeded for {extractor.section_name}")
                    else:
                        # LLM method returned None (error was caught internally)
                        context.add_warning(
                            f"[LLM] ✗ LLM extraction failed (check warnings) - falling back to regex"
                        )
                        data = extractor.extract(context)
                        
                except ModuleNotFoundError as llm_error:
                    # Import errors during LLM - likely missing Azure OpenAI config
                    context.add_warning(
                        f"[LLM] ✗ ModuleNotFoundError: {str(llm_error)} - falling back to regex"
                    )
                    # Fall back to regular extract method
                    data = extractor.extract(context)
                except Exception as llm_error:
                    context.add_warning(
                        f"[LLM] ✗ {type(llm_error).__name__}: {str(llm_error)} - falling back to regex"
                    )
                    # Fall back to regular extract method
                    data = extractor.extract(context)
            else:
                # Use regular sync extract method
                data = extractor.extract(context)
            
            if data:
                if self._enable_validation and self._validation_executor:
                    data = self._validation_executor.validate_section(
                        extractor.section_name, data, context
                    )

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
        
    
    def _calculate_confidence(
        self, 
        result: IRPFDeclarationResult,
        extraction_method: str = "digital",
        ocr_confidence: float | None = None,
    ) -> float:
        detected_sections = set()
        if self._last_profile:
            detected_sections = self._last_profile.detected_sections
        
        calculator = ConfidenceCalculatorFactory.for_declaration(
            use_ocr=(extraction_method == "ocr")
        )
        
        confidence_result = calculator.calculate(
            extracted_data=result.to_dict(),
            extraction_method=extraction_method,
            ocr_confidence=ocr_confidence,
            detected_sections=detected_sections,
        )
        
        self._last_confidence_result = confidence_result
        return confidence_result.overall
    
    def get_confidence_details(self) -> ConfidenceResult | None:
        return getattr(self, "_last_confidence_result", None)
    
    def _calculate_total_value(self, result: IRPFDeclarationResult) -> int:
        if result.assets_declaration:
            value = result.assets_declaration.get("current_year_total_value", 0)
            return int(value)
        return 0
    
    def _calculate_equity_evolution(self, result: IRPFDeclarationResult) -> int:
        if not result.assets_declaration:
            return 0

        current_year = result.assets_declaration.get("current_year_total_value", 0.0)
        last_year = result.assets_declaration.get("last_year_total_value", 0.0)

        return int(current_year - last_year)

    def _propagate_rural_exempt_to_exempt_income(
        self, result: IRPFDeclarationResult
    ) -> None:
        if not result.exempt_income:
            return
        if not result.calculation_of_rural_results_in_brazil:
            return

        subsections = result.exempt_income.get("subsections", {})
        existing = subsections.get("exempt_portion_from_rural_activity")
        if existing and existing.get("total_value", 0) > 0:
            return

        rural_subs = result.calculation_of_rural_results_in_brazil.get("subsections", {})
        exempt_result = rural_subs.get("calculation_of_exempt_result")
        if not exempt_result:
            return

        items = exempt_result.get("items", [])
        if not items:
            return

        rural_value = 0.0
        for item in items:
            val = item.get("value", 0)
            if isinstance(val, (int, float)) and val > 0:
                rural_value = float(val)

        if rural_value <= 0:
            return

        subsections["exempt_portion_from_rural_activity"] = {
            "name": "15. Parcela não tributável correspondente à atividade rural",
            "code": "15",
            "total_value": round(rural_value, 2),
            "valid_total": True,
            "items": None,
        }

        new_total = sum(
            s.get("total_value", 0) for s in subsections.values()
        )
        result.exempt_income["total_value"] = round(new_total, 2)

    _ORPHAN_CURRENCY_RE = re.compile(r"^\d[\d.]*,\d{2}$")

    def _split_text_by_pages(self, text: str, total_pages: int) -> dict[int, str]:
        """Tenta dividir o texto por páginas usando o marcador 'Pagina X de Y'.
        
        O OCR concatena todo o texto mas preserva os marcadores de página.
        Este método tenta reconstruir a estrutura por páginas.
        """
        page_pattern = r"P[aá]gina\s*(\d+)\s*(?:de|DE)\s*(\d+)"
        
        matches = list(re.finditer(page_pattern, text, re.IGNORECASE))
        
        if not matches:
            return {1: text}
        
        pages_text: dict[int, str] = {}
        
        for i, match in enumerate(matches):
            page_num = int(match.group(1))
            
            if i == 0:
                prev_end = 0
            else:
                prev_end = matches[i - 1].end()
            
            page_content = text[prev_end:match.start()].strip()
            
            after_marker = text[match.end():]
            for line in after_marker.split("\n"):
                stripped = line.strip()
                if not stripped:
                    continue
                if self._ORPHAN_CURRENCY_RE.match(stripped):
                    page_content += "\n" + stripped
                else:
                    break
            
            if page_content:
                pages_text[page_num] = page_content
        
        if not pages_text:
            return {1: text}
        
        return pages_text

    def parse_from_text(
        self,
        text: str,
        total_pages: int = 1,
        version: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
        pdf_path: Optional[str] = None,
    ) -> IRPFDeclarationResult:
        pages_text = self._split_text_by_pages(text, total_pages)
        return self.parse_from_pages_text(
            pages_text=pages_text,
            full_text=text,
            total_pages=total_pages,
            version=version,
            ocr_confidence=ocr_confidence,
            warning_message="Texto extraido via OCR",
            pdf_path=pdf_path,
        )

    def parse_from_pages_text(
        self,
        pages_text: dict[int, str],
        full_text: Optional[str] = None,
        total_pages: Optional[int] = None,
        version: Optional[str] = None,
        ocr_confidence: Optional[float] = None,
        warning_message: str = "Texto extraido via OCR (estrutura por pagina preservada)",
        pdf_path: Optional[str] = None,
    ) -> IRPFDeclarationResult:
        ordered_pages = {
            page_num: pages_text[page_num]
            for page_num in sorted(pages_text.keys())
        }
        if not ordered_pages:
            fallback_text = full_text or ""
            ordered_pages = {1: fallback_text}

        if full_text is None:
            full_text = "\n".join(ordered_pages.values())

        context_total_pages = total_pages or len(ordered_pages)
        context = ExtractionContext(
            full_text=full_text,
            pages_text=ordered_pages,
            total_pages=context_total_pages,
            pdf_path=pdf_path,
        )
        return self._parse_ocr_context(
            context=context,
            version=version,
            ocr_confidence=ocr_confidence,
            warning_message=warning_message,
        )

    def _parse_ocr_context(
        self,
        context: ExtractionContext,
        version: Optional[str],
        ocr_confidence: Optional[float],
        warning_message: str,
    ) -> IRPFDeclarationResult:
        result = IRPFDeclarationResult(total_pages=context.total_pages)
        self._last_context = context

        self._detected_version = version or self._template_registry.detect_version(context.full_text)
        self._current_template = self._template_registry.get_template_or_latest(self._detected_version)

        if self._current_template:
            context.add_warning(
                f"Template: {self._current_template.description} (v{self._current_template.version})"
            )
        else:
            context.add_warning("Nenhum template encontrado, usando extracao generica")

        context.add_warning(warning_message)

        if self._auto_detect and not self._custom_extractors:
            profile = self._version_detector.detect(context)
            self._last_profile = profile
            extractors = self._create_extractors_for_profile(profile)

            context.add_warning(
                f"Documento detectado: IRPF {profile.exercise_year} "
                f"({len(profile.detected_sections)} secoes encontradas)"
            )
        else:
            extractors = self._custom_extractors or self._create_default_extractors()

        for extractor in extractors:
            self._run_extractor(extractor, context, result)

        result.warnings = context.warnings
        result.confidence = self._calculate_confidence(
            result,
            extraction_method="ocr",
            ocr_confidence=ocr_confidence,
        )
        result.total_value = self._calculate_total_value(result)
        result.equity_evolution = self._calculate_equity_evolution(result)

        return result
