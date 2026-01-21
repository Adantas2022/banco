"""Extrator de apuração de resultado rural."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralResultsExtractor(ISectionExtractor):
    """Extrai apuração do resultado da atividade rural."""
    
    SECTION_MARKER = "APURAÇÃO DO RESULTADO"
    
    SUBSECTION_MARKERS = {
        "previous_exercise_info": "INFORMAÇÃO DO EXERCÍCIO ANTERIOR",
        "calculation_of_taxable_result": "APURAÇÃO DO RESULTADO TRIBUTÁVEL",
        "next_exercise_info": "INFORMAÇÕES PARA O EXERCÍCIO SEGUINTE",
        "calculation_of_exempt_result": "APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL"
    }
    
    @property
    def section_name(self) -> str:
        return "calculation_of_rural_results_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        subsections = {}
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            page_subsections = self._extract_from_page(page_text, page_num)
            subsections.update(page_subsections)
        
        if not subsections:
            return None
        
        return {
            "section_name": "Apuração do Resultado - Brasil",
            "subsections": subsections
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> dict:
        subsections = {}
        lines = page_text.split("\n")
        
        section_items = {key: [] for key in self.SUBSECTION_MARKERS}
        current_section = None
        
        for line in lines:
            upper = line.upper()
            
            for key, marker in self.SUBSECTION_MARKERS.items():
                if marker in upper:
                    current_section = key
                    break
            else:
                if current_section and not line.strip().startswith("Página"):
                    item = self._parse_result_line(line)
                    if item:
                        section_items[current_section].append(item)
        
        for key, items in section_items.items():
            if items:
                subsections[key] = {
                    "subsection_name": self.SUBSECTION_MARKERS[key],
                    "items": items,
                    "page": page_num
                }
        
        return subsections
    
    def _parse_result_line(self, line: str) -> Optional[dict]:
        pattern = re.match(r"^(.+?)\s+(-?[\d.,-]+|Pelo resultado)\s*$", line.strip())
        
        if not pattern:
            return None
        
        description = pattern.group(1).strip()
        value_str = pattern.group(2).strip()
        
        if not description or len(description) < 5:
            return None
        
        if value_str == "Pelo resultado":
            value = value_str
        else:
            value = parse_currency(value_str)
            if description == "Resultado":
                value = abs(value)
        
        return {
            "description": description,
            "value": value,
            "id": generate_item_id(description)
        }
