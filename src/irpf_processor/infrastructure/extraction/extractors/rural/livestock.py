"""Extrator de movimentacao do rebanho - Brasil."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class LivestockMovementExtractor(ISectionExtractor):
    """Extrai movimentacao do rebanho - Brasil."""
    
    SECTION_MARKER = "MOVIMENTAÇÃO DO REBANHO"
    BRAZIL_MARKER = "BRASIL"
    
    @property
    def section_name(self) -> str:
        return "livestock_movement_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return self.SECTION_MARKER in upper_text
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        for page_num, page_text in context.pages_text.items():
            upper_page = page_text.upper()
            
            if self.SECTION_MARKER not in upper_page:
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
        
        if not items:
            return None
        
        totals = self._calculate_totals(items)
        
        return {
            "section_name": "Movimentação do Rebanho - Brasil",
            "items": items,
            "total_values": totals
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            if self.SECTION_MARKER in upper_line:
                in_section = True
                continue
            
            if in_section:
                if "BENS DA ATIVIDADE" in upper_line:
                    break
                if "DÍVIDAS" in upper_line:
                    break
                if "RECEITAS E DESPESAS" in upper_line:
                    break
                if "SEM INFORMAÇÕES" in upper_line:
                    continue
            
            if not in_section:
                continue
            
            item = self._try_parse_livestock_line(line, lines, i, page_num)
            if item:
                items.append(item)
        
        return items
    
    def _try_parse_livestock_line(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        pattern = re.match(
            r"^(\d{2})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+?)\s+"
            r"(\d+)\s+"
            r"(\d+)\s+"
            r"(\d+)\s+"
            r"(\d+)\s+"
            r"(\d+)\s*$",
            line.strip()
        )
        
        if not pattern:
            pattern_alt = re.match(
                r"^(\d{2})\s+(.+?)\s+"
                r"([\d.,]+)\s+"
                r"([\d.,]+)\s+"
                r"([\d.,]+)\s+"
                r"([\d.,]+)\s+"
                r"([\d.,]+)\s*$",
                line.strip()
            )
            if pattern_alt:
                pattern = pattern_alt
        
        if not pattern:
            return None
        
        code = pattern.group(1)
        species = pattern.group(2).strip()
        
        if self._should_skip_line(species):
            return None
        
        item_id = generate_item_id(f"livestock_{code}_{species}")
        
        return {
            "id": item_id,
            "code": code,
            "species": species,
            "initial_quantity": self._parse_int(pattern.group(3)),
            "births": self._parse_int(pattern.group(4)),
            "purchases": self._parse_int(pattern.group(5)),
            "deaths": self._parse_int(pattern.group(6)),
            "sales": self._parse_int(pattern.group(7)),
            "final_quantity": self._calculate_final_quantity(pattern),
            "page": page_num
        }
    
    def _parse_int(self, value: str) -> int:
        try:
            clean_value = value.replace(".", "").replace(",", "")
            return int(clean_value)
        except (ValueError, AttributeError):
            return 0
    
    def _calculate_final_quantity(self, match: re.Match) -> int:
        initial = self._parse_int(match.group(3))
        births = self._parse_int(match.group(4))
        purchases = self._parse_int(match.group(5))
        deaths = self._parse_int(match.group(6))
        sales = self._parse_int(match.group(7))
        
        return initial + births + purchases - deaths - sales
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CÓDIGO", "ESPÉCIE", "QUANTIDADE", "NASCIMENTO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _calculate_totals(self, items: list[dict]) -> dict:
        return {
            "initial_quantity": {
                "amount": sum(i.get("initial_quantity", 0) for i in items),
                "valid": True
            },
            "births": {
                "amount": sum(i.get("births", 0) for i in items),
                "valid": True
            },
            "purchases": {
                "amount": sum(i.get("purchases", 0) for i in items),
                "valid": True
            },
            "deaths": {
                "amount": sum(i.get("deaths", 0) for i in items),
                "valid": True
            },
            "sales": {
                "amount": sum(i.get("sales", 0) for i in items),
                "valid": True
            },
            "final_quantity": {
                "amount": sum(i.get("final_quantity", 0) for i in items),
                "valid": True
            }
        }
