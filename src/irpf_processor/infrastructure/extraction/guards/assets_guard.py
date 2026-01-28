from typing import Any

from ..extractors.base import ExtractionContext
from ..validation_utils import extract_section_total, validate_total
from .base import GuardResult, ISectionGuard


class AssetsGuard(ISectionGuard):
    
    TOTAL_KEYWORD = "TOTAL"
    TOLERANCE = 0.02
    
    @property
    def section_name(self) -> str:
        return "assets_declaration"
    
    @property
    def sum_fields(self) -> list[str]:
        return ["before_year_asset_value", "current_year_asset_value"]
    
    def validate(
        self, 
        extracted_data: dict[str, Any], 
        context: ExtractionContext
    ) -> GuardResult:
        items = extracted_data.get("items", [])
        
        if not items:
            return self._create_result(
                valid_total=None,
                extracted_sum=0.0,
                pdf_total=None,
                warnings=["no_items_extracted"],
            )
        
        current_year_sum = self._sum_items(items, "current_year_asset_value")
        
        pdf_totals = self._extract_pdf_totals(context)
        pdf_current_year = pdf_totals.get("current_year")
        
        valid = None
        if pdf_current_year is not None:
            valid = validate_total(current_year_sum, pdf_current_year, self.TOLERANCE)
        
        warnings = []
        if valid is False:
            warnings.append(f"total_mismatch:expected={pdf_current_year},got={current_year_sum}")
        
        return self._create_result(
            valid_total=valid,
            extracted_sum=current_year_sum,
            pdf_total=pdf_current_year,
            warnings=warnings,
        )
    
    def _extract_pdf_totals(self, context: ExtractionContext) -> dict[str, float]:
        totals: dict[str, float] = {}
        
        for page_num, page_text in context.pages_text.items():
            if "BENS E DIREITOS" in page_text.upper():
                values = extract_section_total(page_text, self.TOTAL_KEYWORD)
                
                if len(values) >= 2:
                    totals["before_year"] = values[0]
                    totals["current_year"] = values[1]
                    break
        
        return totals
