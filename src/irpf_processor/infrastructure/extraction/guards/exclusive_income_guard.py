from typing import Any

from ..extractors.base import ExtractionContext
from ..validation_utils import validate_total
from .base import GuardResult, ISectionGuard


class ExclusiveIncomeGuard(ISectionGuard):
    
    TOLERANCE = 0.02
    
    @property
    def section_name(self) -> str:
        return "exclusive_taxation_income"
    
    @property
    def sum_fields(self) -> list[str]:
        return ["total_value", "value"]
    
    def validate(
        self, 
        extracted_data: dict[str, Any], 
        context: ExtractionContext
    ) -> GuardResult:
        warnings: list[str] = []
        
        total_value = self._calculate_total(extracted_data)
        
        pdf_total = extracted_data.get("total_value")
        if pdf_total is None or pdf_total == 0:
            pdf_total = self._calculate_expected_total(extracted_data)
        
        valid = None
        if pdf_total is not None and pdf_total > 0:
            valid = validate_total(total_value, pdf_total, self.TOLERANCE)
        
        if valid is False:
            warnings.append(f"total_mismatch:expected={pdf_total},got={total_value}")
        
        return self._create_result(
            valid_total=valid,
            extracted_sum=total_value,
            pdf_total=pdf_total if pdf_total and pdf_total > 0 else None,
            warnings=warnings,
        )
    
    def _calculate_total(self, data: dict[str, Any]) -> float:
        total = 0.0
        
        subsections = data.get("subsections", {})
        if subsections:
            for subsection_name, subsection_data in subsections.items():
                if isinstance(subsection_data, dict):
                    subsection_total = subsection_data.get("total_value", 0)
                    if isinstance(subsection_total, (int, float)):
                        total += float(subsection_total)
        
        if total == 0:
            for key, value in data.items():
                if key in ("section_name", "total_value", "valid_total", "subsections"):
                    continue
                if isinstance(value, dict):
                    subsection_total = value.get("total_value", 0)
                    if isinstance(subsection_total, (int, float)):
                        total += float(subsection_total)
                    items = value.get("items", [])
                    if items:
                        total += self._sum_items(items, "value")
        
        return round(total, 2)
    
    def _calculate_expected_total(self, data: dict[str, Any]) -> float:
        return self._calculate_total(data)
