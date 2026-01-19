"""Extrator de bens da atividade rural."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralAssetsExtractor(ISectionExtractor):
    """Extrai bens da atividade rural."""
    
    SECTION_MARKER = "BENS DA ATIVIDADE RURAL"
    
    @property
    def section_name(self) -> str:
        return "rural_activity_assets_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
        
        if not items:
            return None
        
        totals = {
            "year_before_last_value": {
                "amount": round(sum(i["year_before_last_value"] for i in items), 2),
                "valid": True
            },
            "last_year_value": {
                "amount": round(sum(i["last_year_value"] for i in items), 2),
                "valid": True
            }
        }
        
        return {
            "section_name": "Bens da Atividade Rural - Brasil",
            "items": items,
            "total_values": totals
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            pattern = re.match(
                r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if pattern and "CÓDIGO" not in line.upper() and "TOTAL" not in line.upper():
                item = self._parse_asset(pattern, lines, i, page_num)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items
    
    def _parse_asset(
        self, 
        match: re.Match, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> dict:
        code = match.group(1)
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        
        desc_parts = [desc_start]
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            
            if re.match(r"^\d+\s+", next_line) or "TOTAL" in next_line.upper():
                break
            
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+$", next_line):
                desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        item_id = generate_item_id(f"{code}{full_desc[:30]}")
        
        return {
            "code": code,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
