from typing import Any, Optional

from irpf_processor.templates.models import IRPFTemplate, ValidationType

from .extractors.base import ExtractionContext
from .guards import (
    AssetsGuard,
    DebtsGuard,
    DonationsGuard,
    ExclusiveIncomeGuard,
    ExemptIncomeGuard,
    GuardResult,
    GuardStatus,
    IncomePJGuard,
    ISectionGuard,
    PaymentsGuard,
    RuralGuard,
)
from .validation_utils import create_validated_total, extract_section_total


class ValidationExecutor:
    
    GUARD_REGISTRY: dict[str, type[ISectionGuard]] = {
        "assets_declaration": AssetsGuard,
        "debts_and_encumbrances": DebtsGuard,
        "income_from_legal_person_to_holder": IncomePJGuard,
        "income_from_legal_person_to_dependents": IncomePJGuard,
        "exclusive_taxation_income": ExclusiveIncomeGuard,
        "exempt_income": ExemptIncomeGuard,
        "rural_activity": RuralGuard,
        "payments_made": PaymentsGuard,
        "donations_made": DonationsGuard,
    }
    
    def __init__(self, template: Optional[IRPFTemplate] = None) -> None:
        self._template = template
        self._guards: dict[str, ISectionGuard] = {}
        self._initialize_guards()
    
    def _initialize_guards(self) -> None:
        for section_name, guard_class in self.GUARD_REGISTRY.items():
            self._guards[section_name] = guard_class()
    
    def validate_section(
        self,
        section_name: str,
        extracted_data: dict[str, Any],
        context: ExtractionContext,
    ) -> dict[str, Any]:
        if not self._should_validate_section(section_name):
            return extracted_data
        
        guard = self._guards.get(section_name)
        
        if guard:
            result = guard.validate(extracted_data, context)
            extracted_data = self._apply_guard_result(extracted_data, result)
        else:
            extracted_data = self._apply_template_validation(
                section_name, extracted_data, context
            )
        
        return extracted_data
    
    def validate_all_sections(
        self,
        sections: dict[str, Any],
        context: ExtractionContext,
    ) -> dict[str, Any]:
        validated_sections: dict[str, Any] = {}
        
        for section_name, section_data in sections.items():
            if isinstance(section_data, dict):
                validated_sections[section_name] = self.validate_section(
                    section_name, section_data, context
                )
            else:
                validated_sections[section_name] = section_data
        
        return validated_sections
    
    def get_validation_summary(
        self, 
        sections: dict[str, Any]
    ) -> dict[str, Any]:
        summary = {
            "total_sections": 0,
            "validated_sections": 0,
            "valid_totals": 0,
            "invalid_totals": 0,
            "skipped": 0,
            "sections_detail": {},
        }
        
        for section_name, section_data in sections.items():
            if not isinstance(section_data, dict):
                continue
            
            summary["total_sections"] += 1
            
            valid_total = section_data.get("valid_total")
            
            if valid_total is True:
                summary["validated_sections"] += 1
                summary["valid_totals"] += 1
            elif valid_total is False:
                summary["validated_sections"] += 1
                summary["invalid_totals"] += 1
            else:
                summary["skipped"] += 1
            
            summary["sections_detail"][section_name] = {
                "valid_total": valid_total,
                "total_value": section_data.get("total_value"),
            }
        
        return summary
    
    def _should_validate_section(self, section_name: str) -> bool:
        if self._template:
            section_def = self._template.get_section(section_name)
            if section_def:
                return section_def.has_totals
        
        return section_name in self.GUARD_REGISTRY
    
    def _apply_guard_result(
        self, 
        data: dict[str, Any], 
        result: GuardResult
    ) -> dict[str, Any]:
        data["valid_total"] = result.valid_total
        
        if result.extracted_sum is not None:
            data["total_value"] = result.extracted_sum
        
        if result.pdf_total is not None or result.extracted_sum is not None:
            data["total_validation"] = {
                "extracted_sum": result.extracted_sum,
                "pdf_total": result.pdf_total,
                "difference": result.difference,
                "status": result.status.value,
            }
        
        if result.warnings:
            existing_warnings = data.get("warnings", [])
            data["warnings"] = existing_warnings + result.warnings
        
        return data
    
    def _apply_template_validation(
        self,
        section_name: str,
        data: dict[str, Any],
        context: ExtractionContext,
    ) -> dict[str, Any]:
        if not self._template:
            return data
        
        validations = self._template.get_validations_for_section(section_name)
        
        for validation in validations:
            if validation.type == ValidationType.SUM_CHECK:
                data = self._apply_sum_check(
                    data, 
                    validation.field or "", 
                    validation.total_field or "",
                    context,
                )
        
        return data
    
    def _apply_sum_check(
        self,
        data: dict[str, Any],
        field_name: str,
        total_field_name: str,
        context: ExtractionContext,
    ) -> dict[str, Any]:
        items = data.get("items", [])
        
        extracted_sum = 0.0
        for item in items:
            value = item.get(field_name)
            if isinstance(value, (int, float)):
                extracted_sum += float(value)
        
        extracted_sum = round(extracted_sum, 2)
        
        pdf_total = self._extract_pdf_total_generic(context)
        
        validated_total = create_validated_total(extracted_sum, pdf_total)
        
        if "total_values" not in data:
            data["total_values"] = {}
        
        data["total_values"][total_field_name] = validated_total
        data["valid_total"] = validated_total.get("valid")
        data["total_value"] = extracted_sum
        
        return data
    
    def _extract_pdf_total_generic(
        self, 
        context: ExtractionContext
    ) -> Optional[float]:
        for page_num, page_text in context.pages_text.items():
            values = extract_section_total(page_text, "TOTAL")
            if values:
                return values[0]
        
        return None
