"""Extrator de imóveis rurais explorados."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import generate_item_id


class RuralPropertiesExtractor(ISectionExtractor):
    """Extrai dados de imóveis rurais explorados."""
    
    SECTION_MARKER = "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO"
    
    @property
    def section_name(self) -> str:
        return "exploited_rural_properties_in_brazil"
    
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
        
        return {
            "section_name": "Dados e Identificação do Imóvel Explorado - Brasil",
            "items": items
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        for i, line in enumerate(lines):
            pattern = re.match(
                r"^(\d+)\s+"
                r"([\d.,]+)\s+"
                r"(\d+)\s+"
                r"(.+?)\s+"
                r"([\d.,]+)\s+"
                r"([\d.-]+)\s*$",
                line.strip()
            )
            
            if pattern:
                item = self._parse_property(pattern, lines, i, page_num)
                if item:
                    items.append(item)
        
        return items
    
    def _parse_property(
        self, 
        match: re.Match, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> dict:
        code = int(match.group(1))
        participation = float(match.group(2).replace(",", "."))
        exploration = int(match.group(3))
        name_location = match.group(4).strip()
        area = float(match.group(5).replace(",", "."))
        cib = match.group(6)
        
        participants = self._extract_participants(lines, idx)
        
        item_id = generate_item_id(f"{code}{name_location}")
        
        return {
            "code": code,
            "participation": participation,
            "exploration_condition": exploration,
            "name_and_location": name_location,
            "area": area,
            "cib": cib,
            "participants": {"items": participants},
            "id": item_id,
            "page": page_num
        }
    
    def _extract_participants(self, lines: list[str], start_idx: int) -> list[dict]:
        participants = []
        
        for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
            next_line = lines[j].strip()
            
            if "PARTICIPANTE" in next_line.upper():
                continue
            
            part_match = re.match(
                r"^(.+?)\s*\((\d{3}\.\d{3}\.\d{3}-\d{2})\)",
                next_line
            )
            
            if part_match:
                participants.append({
                    "participant_name": f"{part_match.group(1).strip()} ({part_match.group(2)})",
                    "foreigner": "Estrangeiro: Sim" in next_line,
                    "id": generate_item_id(part_match.group(2))
                })
            
            if re.match(r"^(RECEITAS|MÊS|\d+\s+[\d.,]+)", next_line):
                break
        
        return participants
