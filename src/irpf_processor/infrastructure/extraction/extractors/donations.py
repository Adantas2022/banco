"""Extrator de doacoes efetuadas."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class DonationsExtractor(ISectionExtractor):
    """Extrai doacoes efetuadas (ECA, idoso, cultura, desporto, etc)."""
    
    SECTION_MARKER = "DOAÇÕES EFETUADAS"
    SECTION_END_MARKERS = [
        "DOAÇÕES A PARTIDOS",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS TRIBUTÁVEIS",
        "BENS E DIREITOS",
        "DÍVIDAS E ÔNUS",
        "PAGAMENTOS EFETUADOS"
    ]
    
    DONATION_CODES = {
        "40": "Doações em espécie",
        "41": "Estatuto da Criança e do Adolescente - Nacional",
        "42": "Estatuto da Criança e do Adolescente - Estadual",
        "43": "Estatuto da Criança e do Adolescente - Municipal",
        "44": "Incentivo à cultura",
        "45": "Incentivo à atividade audiovisual",
        "46": "Incentivo ao desporto",
        "47": "Fundo do Idoso - Nacional",
        "48": "Fundo do Idoso - Estadual",
        "49": "Fundo do Idoso - Municipal",
        "50": "Fundo Nacional de Desenvolvimento Científico",
        "61": "PRONON - Programa Nacional de Apoio à Atenção Oncológica",
        "62": "PRONAS/PCD - Programa Nacional de Apoio à Atenção da Saúde da Pessoa com Deficiência",
        "71": "ECA - Estatuto da Criança e do Adolescente",
        "72": "Fundo do Idoso",
        "73": "Incentivo à Cultura e à Atividade Audiovisual",
        "74": "Incentivo ao Desporto",
        "75": "PRONON",
        "76": "PRONAS/PCD",
        "80": "Doações diretamente na declaração - ECA",
        "81": "Doações diretamente na declaração - Idoso",
        "99": "Outras doações"
    }
    
    @property
    def section_name(self) -> str:
        return "donations_made"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return self.SECTION_MARKER in upper_text and "DOAÇÕES A PARTIDOS" not in upper_text.split(self.SECTION_MARKER)[0]
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            if self.SECTION_MARKER in upper_text:
                in_section = True
            
            if in_section and not section_ended:
                page_items, found_end = self._extract_from_page_with_end_detection(page_text, page_num)
                items.extend(page_items)
                
                if found_end:
                    section_ended = True
        
        total_value = round(sum(i.get("value", 0) for i in items), 2)
        
        return {
            "section_name": "Doações Efetuadas",
            "items": items,
            "total_value": total_value,
            "pages_with_problems": []
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items, _ = self._extract_from_page_with_end_detection(page_text, page_num)
        return items
    
    def _extract_from_page_with_end_detection(self, page_text: str, page_num: int) -> tuple[list[dict], bool]:
        items = []
        lines = page_text.split("\n")
        found_end = False
        
        in_section = False
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            if "DOAÇÕES EFETUADAS" in upper_line and "PARTIDOS" not in upper_line:
                in_section = True
                i += 1
                continue
            
            if not in_section:
                i += 1
                continue
            
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                found_end = True
                break
            
            if "CÓDIGO" in upper_line or "TOTAL" in upper_line or "SEM INFORMAÇÕES" in upper_line:
                i += 1
                continue
            
            item = self._try_parse_donation(line, lines, i, page_num)
            if item:
                items.append(item)
                i = item.pop("_next_index", i + 1)
                continue
            
            i += 1
        
        return items, found_end
    
    def _try_parse_donation(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        pattern_with_value = re.match(
            r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s*$",
            line
        )
        
        if pattern_with_value:
            return self._parse_donation_line(pattern_with_value, lines, idx, page_num)
        
        pattern_code_only = re.match(r"^(\d{2})\s+(.+)$", line)
        if pattern_code_only:
            code = pattern_code_only.group(1)
            if code in self.DONATION_CODES or (code.isdigit() and int(code) >= 40):
                return self._parse_donation_multiline(pattern_code_only, lines, idx, page_num)
        
        return None
    
    def _parse_donation_line(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        code = match.group(1)
        desc_and_beneficiary = match.group(2).strip()
        value = parse_currency(match.group(3))
        
        beneficiary_cnpj = ""
        beneficiary_name = ""
        description = desc_and_beneficiary
        
        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", desc_and_beneficiary)
        
        if cnpj_match:
            beneficiary_cnpj = cnpj_match.group(1)
            parts = desc_and_beneficiary.split(beneficiary_cnpj)
            if len(parts) >= 2:
                description = parts[0].strip()
                beneficiary_name = parts[1].strip()
        
        desc_parts = [description]
        name_parts = [beneficiary_name] if beneficiary_name else []
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next:
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            is_new_item = re.match(r"^(\d{2})\s+", next_line)
            if is_new_item:
                break
            
            if re.match(r"^[\d.,]+\s*$", next_line):
                break
            
            if next_line and not next_line.upper().startswith("CÓDIGO"):
                if beneficiary_cnpj and not beneficiary_name:
                    name_parts.append(next_line)
                elif not re.match(r"^\d+$", next_line):
                    desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        if name_parts:
            beneficiary_name = " ".join(name_parts)
            beneficiary_name = re.sub(r"\s+", " ", beneficiary_name).strip()
        
        item_id = generate_item_id(f"{code}{beneficiary_cnpj}{full_desc}")
        
        return {
            "donation_code": code,
            "donation_description": full_desc,
            "beneficiary_cnpj": beneficiary_cnpj,
            "beneficiary_name": beneficiary_name,
            "value": value,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _parse_donation_multiline(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        code = match.group(1)
        first_part = match.group(2).strip()
        
        desc_parts = [first_part]
        beneficiary_cnpj = ""
        beneficiary_name = ""
        value = 0.0
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next:
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            is_new_item = re.match(r"^(\d{2})\s+", next_line)
            if is_new_item and j > idx + 1:
                break
            
            cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", next_line)
            
            if cnpj_match and not beneficiary_cnpj:
                beneficiary_cnpj = cnpj_match.group(1)
            
            value_match = re.search(r"([\d.,]+)\s*$", next_line)
            if value_match and not re.match(r"^\d{2}\.\d{3}\.\d{3}", next_line):
                potential_value = parse_currency(value_match.group(1))
                if potential_value > 0:
                    value = potential_value
            
            if not next_line.upper().startswith("CÓDIGO"):
                if not re.match(r"^[\d.,]+\s*$", next_line):
                    desc_parts.append(next_line)
            
            j += 1
        
        if value == 0:
            return None
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        full_desc = re.sub(r"\s*[\d.,]+\s*$", "", full_desc).strip()
        
        item_id = generate_item_id(f"{code}{beneficiary_cnpj}{full_desc}")
        
        return {
            "donation_code": code,
            "donation_description": full_desc,
            "beneficiary_cnpj": beneficiary_cnpj,
            "beneficiary_name": beneficiary_name,
            "value": value,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
