"""Extrator de imoveis rurais explorados."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import generate_item_id


class RuralPropertiesExtractor(ISectionExtractor):
    """Extrai dados de imoveis rurais explorados."""
    
    SECTION_MARKER = "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO"
    SECTION_END_MARKERS = [
        "RECEITAS DA ATIVIDADE RURAL",
        "DESPESAS DA ATIVIDADE RURAL",
        "RESULTADO DA ATIVIDADE RURAL",
        "DÍVIDAS E ÔNUS REAIS",
    ]
    
    @property
    def section_name(self) -> str:
        return "exploited_rural_properties_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        if not self.can_extract(context):
            return None
        
        items = []
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
        
        if not items:
            return {
                "section_name": "Dados e Identificacao do Imovel Explorado - Brasil",
                "items": [],
                "total_properties": 0,
                "total_area": 0.0
            }
        
        total_area = sum(item.get("area", 0) for item in items)
        
        return {
            "section_name": "Dados e Identificacao do Imovel Explorado - Brasil",
            "items": items,
            "total_properties": len(items),
            "total_area": round(total_area, 2)
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            if "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO" in upper_line:
                in_section = True
                i += 1
                continue
            
            if not in_section:
                i += 1
                continue
            
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                break
            
            if any(h in upper_line for h in ["CÓDIGO", "ATIVIDADE", "PARTICIPAÇÃO", "CONDIÇÃO", "ÁREA", "CIB", "NOME E", "(HA)", "EXPLORAÇÃO"]):
                i += 1
                continue
            
            if "PARTICIPANTE(S)" in upper_line or "PARTICIPANTES" in upper_line:
                i += 1
                continue
            
            item = self._try_parse_inline_property(line, lines, i, page_num)
            if item:
                items.append(item)
                skip_lines = self._count_property_lines(lines, i)
                i += max(1, skip_lines)
                continue
            
            if re.match(r"^\d{1,2}$", line):
                item = self._try_parse_multiline_property(lines, i, page_num)
                if item:
                    items.append(item)
                    skip_lines = self._count_multiline_property_lines(lines, i)
                    i += max(1, skip_lines)
                    continue
            
            i += 1
        
        return items
    
    def _try_parse_inline_property(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        pattern = re.match(
            r"^(\d{1,2})\s+"
            r"([\d.,]+)\s+"
            r"(\d)\s+"
            r"(.+?)\s+"
            r"([\d.]+,\d)\s+"
            r"([\d.-]+)$",
            line.strip()
        )
        
        if pattern:
            return self._parse_from_match(pattern, lines, idx, page_num)
        
        partial_pattern = re.match(
            r"^(\d{1,2})\s+"
            r"([\d.,]+)\s+"
            r"(\d)\s+"
            r"(.+)$",
            line.strip()
        )
        
        if partial_pattern:
            code = int(partial_pattern.group(1))
            participation_str = partial_pattern.group(2).replace(".", "").replace(",", ".")
            participation = float(participation_str)
            exploration = int(partial_pattern.group(3))
            remaining = partial_pattern.group(4).strip()
            
            area_cib_match = re.search(r"([\d.]+,\d)\s+([\d.-]+)$", remaining)
            
            if area_cib_match:
                name_location = remaining[:area_cib_match.start()].strip()
                area_str = area_cib_match.group(1).replace(".", "").replace(",", ".")
                area = float(area_str)
                cib = area_cib_match.group(2)
            else:
                name_parts = [remaining]
                area = 0.0
                cib = ""
                
                for j in range(idx + 1, min(idx + 5, len(lines))):
                    next_line = lines[j].strip()
                    
                    if "PARTICIPANTE" in next_line.upper():
                        break
                    
                    if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", next_line):
                        break
                    
                    area_cib_end = re.search(r"([\d.]+,\d)\s+([\d.-]+)$", next_line)
                    if area_cib_end:
                        name_part = next_line[:area_cib_end.start()].strip()
                        if name_part:
                            name_parts.append(name_part)
                        area_str = area_cib_end.group(1).replace(".", "").replace(",", ".")
                        area = float(area_str)
                        cib = area_cib_end.group(2)
                        break
                    
                    if next_line and not re.match(r"^[\d.-]+$", next_line):
                        name_parts.append(next_line)
                
                name_location = " ".join(name_parts)
            
            if not cib:
                return None
            
            name_location = self._normalize_name(name_location)
            participants = self._extract_participants(lines, idx)
            item_id = generate_item_id(f"{code}{name_location}{cib}")
            
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
        
        return None
    
    def _parse_from_match(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> dict:
        code = int(match.group(1))
        participation_str = match.group(2).replace(".", "").replace(",", ".")
        participation = float(participation_str)
        exploration = int(match.group(3))
        name_location = match.group(4).strip()
        area_str = match.group(5).replace(".", "").replace(",", ".")
        area = float(area_str)
        cib = match.group(6)
        
        name_location = self._normalize_name(name_location)
        participants = self._extract_participants(lines, idx)
        item_id = generate_item_id(f"{code}{name_location}{cib}")
        
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
    
    def _try_parse_multiline_property(
        self,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        line = lines[idx].strip()
        
        if not re.match(r"^\d{1,2}$", line):
            return None
        
        code = int(line)
        j = idx + 1
        
        if j >= len(lines):
            return None
        
        participation_str = lines[j].strip().replace(".", "").replace(",", ".")
        try:
            participation = float(participation_str)
        except ValueError:
            return None
        j += 1
        
        if j >= len(lines):
            return None
        
        exploration_str = lines[j].strip()
        if not re.match(r"^\d$", exploration_str):
            return None
        exploration = int(exploration_str)
        j += 1
        
        name_parts = []
        area = 0.0
        cib = ""
        
        while j < len(lines):
            next_line = lines[j].strip()
            
            if "PARTICIPANTE" in next_line.upper():
                break
            
            if re.match(r"^[\d.]+,\d$", next_line):
                area_str = next_line.replace(".", "").replace(",", ".")
                area = float(area_str)
                j += 1
                if j < len(lines) and re.match(r"^[\d.-]+$", lines[j].strip()):
                    cib = lines[j].strip()
                    j += 1
                break
            
            if next_line and not re.match(r"^(CÓDIGO|ATIVIDADE)", next_line.upper()):
                name_parts.append(next_line)
            j += 1
        
        if not cib:
            return None
        
        name_location = self._normalize_name(" ".join(name_parts))
        participants = self._extract_participants(lines, j - 1)
        item_id = generate_item_id(f"{code}{name_location}{cib}")
        
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
    
    def _normalize_name(self, name: str) -> str:
        name = re.sub(r"\s+", " ", name)
        return name.strip()
    
    def _count_property_lines(self, lines: list[str], start_idx: int) -> int:
        count = 1
        for j in range(start_idx + 1, min(start_idx + 10, len(lines))):
            line = lines[j].strip().upper()
            if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", lines[j].strip()):
                break
            if "PARTICIPANTE" in line:
                count += 1
                continue
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ].+\(\d{3}\.\d{3}\.\d{3}-\d{2}\)", lines[j].strip()):
                count += 1
                continue
            if any(marker in line for marker in self.SECTION_END_MARKERS):
                break
            count += 1
        return count
    
    def _count_multiline_property_lines(self, lines: list[str], start_idx: int) -> int:
        count = 1
        for j in range(start_idx + 1, min(start_idx + 15, len(lines))):
            line = lines[j].strip()
            if re.match(r"^\d{1,2}$", line):
                break
            if any(marker in line.upper() for marker in self.SECTION_END_MARKERS):
                break
            count += 1
        return count
    
    def _extract_participants(self, lines: list[str], start_idx: int) -> list[dict]:
        participants = []
        
        for j in range(start_idx + 1, min(start_idx + 10, len(lines))):
            next_line = lines[j].strip()
            
            if "PARTICIPANTE" in next_line.upper():
                continue
            
            if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", next_line):
                break
            
            if re.match(r"^\d{1,2}$", next_line):
                break
            
            if any(marker in next_line.upper() for marker in self.SECTION_END_MARKERS):
                break
            
            part_match = re.match(
                r"^(.+?)\s*\((\d{3}\.\d{3}\.\d{3}-\d{2})\)",
                next_line
            )
            
            if part_match:
                participants.append({
                    "participant_name": f"{part_match.group(1).strip()} ({part_match.group(2)})",
                    "foreigner": "Estrangeiro: Sim" in next_line,
                    "cpf": part_match.group(2),
                    "id": generate_item_id(part_match.group(2))
                })
        
        return participants
