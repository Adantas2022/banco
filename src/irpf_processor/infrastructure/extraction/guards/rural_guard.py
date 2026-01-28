from typing import Any

from ..extractors.base import ExtractionContext
from ..validation_utils import extract_section_total, validate_total
from .base import GuardResult, GuardStatus, ISectionGuard


class RuralGuard(ISectionGuard):
    
    TOLERANCE = 0.02
    
    RURAL_SECTIONS = [
        "rural_income_and_expenditure_in_brazil",
        "rural_activity_assets_in_brazil",
        "rural_activity_debts_in_brazil",
        "livestock_movement_in_brazil",
    ]
    
    @property
    def section_name(self) -> str:
        return "rural_activity"
    
    @property
    def sum_fields(self) -> list[str]:
        return ["value", "gross_revenue", "funding_expenses"]
    
    def validate(
        self, 
        extracted_data: dict[str, Any], 
        context: ExtractionContext
    ) -> GuardResult:
        all_warnings: list[str] = []
        all_errors: list[str] = []
        
        section_results: dict[str, bool | None] = {}
        
        for section in self.RURAL_SECTIONS:
            section_data = extracted_data.get(section, {})
            
            if section_data:
                result = self._validate_rural_section(section, section_data, context)
                section_results[section] = result.valid_total
                all_warnings.extend(result.warnings)
                all_errors.extend(result.errors)
        
        valid_count = sum(1 for v in section_results.values() if v is True)
        invalid_count = sum(1 for v in section_results.values() if v is False)
        total_count = len([v for v in section_results.values() if v is not None])
        
        overall_valid: bool | None = None
        if total_count > 0:
            overall_valid = invalid_count == 0
        
        coverage = valid_count / max(total_count, 1)
        
        result = self._create_result(
            valid_total=overall_valid,
            extracted_sum=0.0,
            pdf_total=None,
            warnings=all_warnings,
            errors=all_errors,
        )
        result.coverage = coverage
        
        return result
    
    def _validate_rural_section(
        self, 
        section_name: str, 
        section_data: dict[str, Any],
        context: ExtractionContext
    ) -> GuardResult:
        items = section_data.get("items", [])
        
        if not items:
            return GuardResult(
                status=GuardStatus.SKIPPED,
                section_name=section_name,
                valid_total=None,
                warnings=["no_items"],
            )
        
        field_name = self._get_sum_field_for_section(section_name)
        extracted_sum = self._sum_items(items, field_name)
        
        pdf_total = self._extract_section_total(section_name, context)
        
        valid = None
        if pdf_total is not None:
            valid = validate_total(extracted_sum, pdf_total, self.TOLERANCE)
        
        warnings = []
        if valid is False:
            warnings.append(f"{section_name}:total_mismatch")
        
        return GuardResult(
            status=GuardStatus.PASSED if valid else GuardStatus.WARNING,
            section_name=section_name,
            valid_total=valid,
            extracted_sum=extracted_sum,
            pdf_total=pdf_total,
            warnings=warnings,
        )
    
    def _get_sum_field_for_section(self, section_name: str) -> str:
        field_map = {
            "rural_income_and_expenditure_in_brazil": "gross_revenue",
            "rural_activity_assets_in_brazil": "last_year_value",
            "rural_activity_debts_in_brazil": "paid_value_in_last_year",
            "livestock_movement_in_brazil": "final_quantity",
        }
        return field_map.get(section_name, "value")
    
    def _extract_section_total(
        self, 
        section_name: str, 
        context: ExtractionContext
    ) -> float | None:
        markers = {
            "rural_income_and_expenditure_in_brazil": "RECEITAS E DESPESAS",
            "rural_activity_assets_in_brazil": "BENS DA ATIVIDADE RURAL",
            "rural_activity_debts_in_brazil": "DÍVIDAS VINCULADAS",
            "livestock_movement_in_brazil": "MOVIMENTAÇÃO DO REBANHO",
        }
        
        marker = markers.get(section_name, "")
        
        for page_num, page_text in context.pages_text.items():
            if marker in page_text.upper():
                values = extract_section_total(page_text, "TOTAL")
                if values:
                    return values[0]
        
        return None
