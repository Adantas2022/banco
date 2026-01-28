"""Extrator de rendimentos tributaveis de pessoa fisica e do exterior pelo titular."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class IncomePFExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de pessoa fisica e do exterior pelo titular."""
    
    SECTION_MARKER = "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA"
    ALT_MARKER = "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA E DO EXTERIOR"
    HOLDER_MARKER = "PELO TITULAR"
    
    MONTHS_MAP = {
        "JAN": "jan", "FEV": "fev", "MAR": "mar", "ABR": "abr",
        "MAI": "mai", "JUN": "jun", "JUL": "jul", "AGO": "ago",
        "SET": "set", "OUT": "out", "NOV": "nov", "DEZ": "dez"
    }
    
    @property
    def section_name(self) -> str:
        return "income_from_individual_to_holder"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return (
            (self.SECTION_MARKER in upper_text or self.ALT_MARKER in upper_text) and
            self.HOLDER_MARKER in upper_text
        )
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        if not self.can_extract(context):
            return None
        
        for page_num, page_text in context.pages_text.items():
            upper_page = page_text.upper()
            
            if (self.SECTION_MARKER not in upper_page and self.ALT_MARKER not in upper_page):
                continue
            
            if self.HOLDER_MARKER not in upper_page:
                continue
            
            if "PELOS DEPENDENTES" in upper_page and "PELO TITULAR" not in upper_page:
                continue
            
            result = self._extract_dimensa_format(page_text, page_num)
            if result:
                return result
        
        return self._empty_result()
    
    def _empty_result(self) -> dict[str, Any]:
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Física e do Exterior pelo Titular",
            "items": []
        }
    
    def _extract_dimensa_format(self, page_text: str, page_num: int) -> Optional[dict]:
        lines = page_text.split("\n")
        
        nit_pis_pasep = ""
        income_data: dict[str, dict] = {}
        deductions_data: dict[str, dict] = {}
        
        in_income_section = False
        in_deduction_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper().strip()
            
            if "NIT/PIS/PASEP" in upper_line:
                nit_match = re.search(r"NIT/PIS/PASEP[:\s]*(\d[\d.\-/]*)?", line, re.IGNORECASE)
                if nit_match and nit_match.group(1):
                    nit_pis_pasep = nit_match.group(1).strip()
                continue
            
            if "RENDIMENTOS" in upper_line and "TRABALHO NÃO" not in upper_line and "ASSALARIADO" not in upper_line:
                if "DEDUÇÕES" not in upper_line:
                    in_income_section = True
                    in_deduction_section = False
                continue
            
            if "DEDUÇÕES CARNÊ-LEÃO" in upper_line or "DEDUCOES CARNE-LEAO" in upper_line:
                in_income_section = False
                in_deduction_section = True
                continue
            
            month_match = re.match(r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+", upper_line)
            if month_match:
                month_upper = month_match.group(1)
                month_lower = self.MONTHS_MAP.get(month_upper, month_upper.lower())
                values_str = line[month_match.end():].strip()
                values = self._extract_values_from_line(values_str)
                
                if in_income_section or (not in_deduction_section and len(values) >= 4):
                    if len(values) >= 4:
                        income_data[month_lower] = {
                            "unwaged_work": values[0],
                            "rental": values[1],
                            "others": values[2],
                            "income_from_abroad": values[3],
                        }
                elif in_deduction_section:
                    if len(values) >= 4:
                        deductions_data[month_lower] = {
                            "official_social_security": values[0],
                            "dependents_number": int(values[1]) if values[1] == int(values[1]) else 0,
                            "alimony": values[2],
                            "cashbook": values[3]
                        }
                continue
            
            if "TOTAL" in upper_line and "TOTALIZAÇÃO" not in upper_line:
                if in_income_section:
                    in_income_section = False
                elif in_deduction_section:
                    in_deduction_section = False
        
        if not income_data:
            return None
        
        item = {
            "nit_pis_pasep": nit_pis_pasep,
            "income": income_data,
        }
        
        if deductions_data:
            item["deductions"] = deductions_data
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Física e do Exterior pelo Titular",
            "items": [item],
            "page": page_num
        }
    
    def _extract_values_from_line(self, text: str) -> list[float]:
        values = []
        
        parts = re.findall(r"[\d.,]+", text)
        
        for part in parts:
            try:
                clean = part.replace(".", "").replace(",", ".")
                values.append(float(clean))
            except ValueError:
                continue
        
        return values
