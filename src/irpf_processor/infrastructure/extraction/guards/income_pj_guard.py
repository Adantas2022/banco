from typing import Any

from ..extractors.base import ExtractionContext
from ..validation_utils import extract_section_total, validate_total
from .base import GuardResult, ISectionGuard


class IncomePJGuard(ISectionGuard):
    
    TOTAL_KEYWORD = "TOTAL"
    TOLERANCE = 0.02
    
    @property
    def section_name(self) -> str:
        return "income_from_legal_person_to_holder"
    
    @property
    def sum_fields(self) -> list[str]:
        return [
            "income_from_legal_person",
            "official_social_security_contribution",
            "tax_withheld_at_source",
            "thirteenth_salary",
            "irrf_on_thirteenth_salary",
        ]
    
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
        
        income_sum = self._sum_items(items, "income_from_legal_person")
        
        pdf_totals = self._extract_pdf_totals(context)
        pdf_income = pdf_totals.get("income")
        
        valid = None
        if pdf_income is not None:
            valid = validate_total(income_sum, pdf_income, self.TOLERANCE)
        
        warnings = []
        errors = []
        
        if valid is False:
            warnings.append(f"total_mismatch:expected={pdf_income},got={income_sum}")
        
        cnpj_errors = self._validate_cnpjs(items)
        if cnpj_errors:
            errors.extend(cnpj_errors)
        
        return self._create_result(
            valid_total=valid,
            extracted_sum=income_sum,
            pdf_total=pdf_income,
            warnings=warnings,
            errors=errors,
        )
    
    def _extract_pdf_totals(self, context: ExtractionContext) -> dict[str, float]:
        totals: dict[str, float] = {}
        
        for page_num, page_text in context.pages_text.items():
            upper_text = page_text.upper()
            if "PESSOA JURÍDICA" in upper_text and "TITULAR" in upper_text:
                values = extract_section_total(page_text, self.TOTAL_KEYWORD)
                
                if len(values) >= 5:
                    totals["income"] = values[0]
                    totals["contribution"] = values[1]
                    totals["irrf"] = values[2]
                    totals["thirteenth"] = values[3]
                    totals["irrf_thirteenth"] = values[4]
                    break
        
        return totals
    
    def _validate_cnpjs(self, items: list[dict[str, Any]]) -> list[str]:
        errors = []
        
        for i, item in enumerate(items):
            cnpj = item.get("cpf_cnpj", "")
            if cnpj and len(cnpj.replace(".", "").replace("/", "").replace("-", "")) != 14:
                errors.append(f"invalid_cnpj:item_{i}")
        
        return errors
