import re
from typing import Any

from ..extractors.base import ExtractionContext
from ..validation_utils import parse_currency_value, validate_total
from .base import GuardResult, ISectionGuard


class PaymentsGuard(ISectionGuard):
    
    TOLERANCE = 0.02
    SECTION_MARKERS = [
        "PAGAMENTOS EFETUADOS",
    ]
    
    @property
    def section_name(self) -> str:
        return "payments_made"
    
    @property
    def sum_fields(self) -> list[str]:
        return ["value"]
    
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
        
        total_sum = self._sum_items(items, "value")
        
        pdf_total = self._extract_pdf_total(context)
        
        valid = None
        if pdf_total is not None:
            valid = validate_total(total_sum, pdf_total, self.TOLERANCE)
        
        warnings = []
        if valid is False:
            warnings.append(f"total_mismatch:expected={pdf_total},got={total_sum}")
        
        return self._create_result(
            valid_total=valid,
            extracted_sum=total_sum,
            pdf_total=pdf_total,
            warnings=warnings,
        )
    
    def _extract_pdf_total(self, context: ExtractionContext) -> float | None:
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        
        for page_num, page_text in context.pages_text.items():
            upper_text = page_text.upper()
            
            if not any(marker in upper_text for marker in self.SECTION_MARKERS):
                continue
            
            lines = page_text.split("\n")
            in_section = False
            
            for line in lines:
                upper_line = line.upper().strip()
                
                if any(marker in upper_line for marker in self.SECTION_MARKERS):
                    in_section = True
                    continue
                
                if in_section:
                    if "DOAÇÕES EFETUADAS" in upper_line or "DOAÇÕES A PARTIDOS" in upper_line:
                        break
                    
                    if upper_line.startswith("TOTAL") and "DEDUÇÃO" not in upper_line:
                        matches = re.findall(num_pattern, line)
                        if matches:
                            return parse_currency_value(matches[-1])
        
        return None
