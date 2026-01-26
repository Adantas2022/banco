"""Extrator de dívidas e ônus reais."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id, sum_currency_values


class DebtsExtractor(ISectionExtractor):
    """Extrai dívidas e ônus reais."""
    
    SECTION_MARKER = "DÍVIDAS E ÔNUS REAIS"
    SECTION_END_MARKERS = [
        "DOAÇÕES A PARTIDOS",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS TRIBUTÁVEIS",
        "PROPRIEDADES RURAIS EXPLORADAS",
        "PAGAMENTOS EFETUADOS",
        "DOAÇÕES EFETUADAS",
        "BENS DA ATIVIDADE RURAL"
    ]
    VALID_DEBT_CODES = {"10", "11", "12", "13", "14", "15"}
    
    @property
    def section_name(self) -> str:
        return "debts_and_encumbrances"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            is_rural_debt_section = "DÍVIDAS E ÔNUS REAIS - ATIVIDADE RURAL" in upper_text or "DIVIDAS E ONUS REAIS - ATIVIDADE RURAL" in upper_text
            
            if self._has_rural_section_heading(page_text) and not is_rural_debt_section:
                if in_section:
                    break
                continue
            
            if self.SECTION_MARKER in upper_text:
                is_other_rural = "ATIVIDADE RURAL" in upper_text and not is_rural_debt_section
                if not is_other_rural:
                    in_section = True
            
            if in_section:
                if self._has_section_end_heading(page_text):
                    page_items = self._extract_from_page(page_text, page_num)
                    items.extend(page_items)
                    break
                
                page_items = self._extract_from_page(page_text, page_num)
                items.extend(page_items)
        
        if not items:
            return None
        
        year_before_last_total = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        last_year_total = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        paid_total = sum_currency_values([i.get("current_year_value", 0) for i in items], as_int=False)
        
        return {
            "section_name": "Dívidas e Ônus Reais",
            "items": items,
            "amount_of_codes_equal_to_amount_of_values": True,
            "year_before_last_total_value": year_before_last_total,
            "last_year_total_value": last_year_total,
            "current_year_total_value": paid_total,
            "pages_with_problems": []
        }
    
    def _has_section_end_heading(self, page_text: str) -> bool:
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue
            for marker in self.SECTION_END_MARKERS:
                if stripped == marker or stripped.startswith(marker + " "):
                    next_lines = " ".join(lines[i+1:i+4]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
                        return True
                    if re.search(r"^\d{2}\s+", stripped[len(marker):].strip()):
                        return True
        return False
    
    def _has_rural_section_heading(self, page_text: str) -> bool:
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue
            if "ATIVIDADE RURAL" in stripped:
                if "DÍVIDAS E ÔNUS REAIS" in stripped or "DIVIDAS E ONUS REAIS" in stripped:
                    continue
                if stripped.startswith("PROPRIEDADES RURAIS"):
                    return True
                if stripped == "ATIVIDADE RURAL - BRASIL" or stripped == "ATIVIDADE RURAL BRASIL":
                    return True
                if stripped.startswith("ATIVIDADE RURAL") and len(stripped) < 40:
                    next_lines = " ".join(lines[i+1:i+4]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines or "PROPRIEDADE" in next_lines:
                        return True
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        found_header = False
        consecutive_invalid = 0
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            if "DÍVIDAS E ÔNUS REAIS" in upper_line:
                found_header = True
                in_section = True
                i += 1
                continue
            
            if found_header and self._is_section_end_line(upper_line):
                break
            
            if "CÓDIGO" in upper_line or "TOTAL" in upper_line:
                if not found_header:
                    in_section = True
                i += 1
                continue
            
            if not in_section:
                debt_match = re.match(
                    r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                    line
                )
                if debt_match and self._is_valid_debt_code(debt_match.group(1)):
                    in_section = True
            
            if not in_section:
                i += 1
                continue
            
            debt_match = re.match(
                r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if debt_match:
                code = debt_match.group(1)
                if not self._is_valid_debt_code(code):
                    consecutive_invalid += 1
                    if consecutive_invalid >= 3:
                        break
                    i += 1
                    continue
                
                consecutive_invalid = 0
                item = self._parse_debt(debt_match, lines, i, page_num)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items
    
    def _is_section_end_line(self, upper_line: str) -> bool:
        for marker in self.SECTION_END_MARKERS:
            if upper_line == marker or upper_line.startswith(marker + " "):
                return True
        return False
    
    def _is_valid_debt_code(self, code: str) -> bool:
        return code in self.VALID_DEBT_CODES
    
    def _parse_debt(
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
        paid_val = parse_currency(match.group(5))
        
        desc_parts = [desc_start]
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next:
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            is_new_item = re.match(r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", next_line)
            if is_new_item:
                break
            
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+\s+[\d.,]+$", next_line):
                if not next_line.upper().startswith("CÓDIGO"):
                    desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        normalized_desc = re.sub(r"(\S)\(", r"\1 (", full_desc)
        normalized_desc = re.sub(r"\(\s+", "(", normalized_desc)
        item_id = generate_item_id(normalized_desc)
        
        return {
            "debt_code": code,
            "debt_description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "current_year_value": paid_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
