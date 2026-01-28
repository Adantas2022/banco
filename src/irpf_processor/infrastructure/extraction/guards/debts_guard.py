import re
from typing import Any

from ..extractors.base import ExtractionContext
from ..validation_utils import parse_currency_value, validate_total
from .base import GuardResult, ISectionGuard


class DebtsGuard(ISectionGuard):
    
    TOLERANCE = 0.02
    SECTION_MARKERS = [
        "DÍVIDAS E ÔNUS REAIS",
        "DIVIDAS E ONUS REAIS",
        "DÍVIDAS E ÔNUS",
    ]
    
    @property
    def section_name(self) -> str:
        return "debts_and_encumbrances"
    
    @property
    def sum_fields(self) -> list[str]:
        return ["year_before_last_value", "last_year_value", "current_year_value"]
    
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
        
        last_year_sum = self._sum_items(items, "last_year_value")
        
        pdf_totals = self._extract_pdf_totals(context)
        pdf_last_year = pdf_totals.get("last_year")
        
        valid = None
        if pdf_last_year is not None:
            valid = validate_total(last_year_sum, pdf_last_year, self.TOLERANCE)
        
        warnings = []
        if valid is False:
            warnings.append(f"total_mismatch:expected={pdf_last_year},got={last_year_sum}")
        
        return self._create_result(
            valid_total=valid,
            extracted_sum=last_year_sum,
            pdf_total=pdf_last_year,
            warnings=warnings,
        )
    
    def _extract_pdf_totals(self, context: ExtractionContext) -> dict[str, float]:
        totals: dict[str, float] = {}
        num_pattern = r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})'
        
        for page_num, page_text in context.pages_text.items():
            upper_text = page_text.upper()
            
            is_debts_page = any(marker in upper_text for marker in self.SECTION_MARKERS)
            
            if not is_debts_page:
                continue
            
            lines = page_text.split("\n")
            in_debts_section = False
            
            for i, line in enumerate(lines):
                upper_line = line.upper().strip()
                
                if any(marker in upper_line for marker in self.SECTION_MARKERS):
                    in_debts_section = True
                    continue
                
                if in_debts_section and upper_line.startswith("TOTAL"):
                    if "DEDUÇÃO" in upper_line or "DEDUCAO" in upper_line:
                        continue
                    
                    matches = re.findall(num_pattern, line)
                    if len(matches) >= 2:
                        totals["year_before_last"] = parse_currency_value(matches[0])
                        totals["last_year"] = parse_currency_value(matches[1])
                        if len(matches) >= 3:
                            totals["current_year"] = parse_currency_value(matches[2])
                        return totals
        
        return totals
