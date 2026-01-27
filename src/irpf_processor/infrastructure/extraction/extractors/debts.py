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
        "PAGAMENTOS EFETUADOS",
        "DOAÇÕES EFETUADAS",
        "ESPÓLIO"
    ]
    # Códigos válidos expandidos
    VALID_DEBT_CODES = {"10", "11", "12", "13", "14", "15", "16", "17", "18", "19"}
    
    @property
    def section_name(self) -> str:
        return "debts_and_encumbrances"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            # Verificar se é seção de atividade rural (ignorar)
            is_rural_debt_section = (
                "DÍVIDAS E ÔNUS REAIS - ATIVIDADE RURAL" in upper_text or 
                "DIVIDAS E ONUS REAIS - ATIVIDADE RURAL" in upper_text
            )
            
            # Entrar na seção de dívidas (não rural)
            if self.SECTION_MARKER in upper_text and not is_rural_debt_section:
                if "ATIVIDADE RURAL" not in upper_text:
                    in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # Extrair itens da página
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Verificar se a seção terminou APÓS extrair
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
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
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        """Verifica se esta página marca o fim definitivo da seção."""
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue
            
            # Verificar marcadores de fim de seção
            for marker in self.SECTION_END_MARKERS:
                if stripped == marker or stripped.startswith(marker + " "):
                    # Confirmar que é uma nova seção (tem código ou cabeçalho)
                    next_lines = " ".join(lines[i+1:i+5]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
                        return True
                    if re.search(r"^\d{2}\s+", next_lines):
                        return True
            
            # Se encontrar outra seção principal
            if stripped.startswith("PROPRIEDADES RURAIS EXPLORADAS"):
                return True
            if stripped == "BENS DA ATIVIDADE RURAL - BRASIL":
                return True
        
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            # Detectar início da seção
            if "DÍVIDAS E ÔNUS REAIS" in upper_line:
                if "ATIVIDADE RURAL" not in upper_line:
                    in_section = True
                    i += 1
                    continue
            
            # Detectar fim da seção nesta página
            if in_section and self._is_section_end_line(upper_line):
                break
            
            # Skip linhas de cabeçalho
            if "CÓDIGO" in upper_line or "DISCRIMINAÇÃO" in upper_line:
                in_section = True
                i += 1
                continue
            
            if "TOTAL" in upper_line and not re.match(r"^\d{2}\s+", line):
                i += 1
                continue
            
            # Tentar detectar item mesmo sem estar "in_section" se parecer item válido
            debt_match = re.match(
                r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if debt_match:
                code = debt_match.group(1)
                if self._is_valid_debt_code(code):
                    in_section = True
                    item = self._parse_debt(debt_match, lines, i, page_num)
                    if item and item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        items.append(item)
                        i = item.pop("_next_index", i + 1)
                        continue
            
            i += 1
        
        return items
    
    def _is_section_end_line(self, upper_line: str) -> bool:
        """Verifica se a linha indica fim da seção."""
        for marker in self.SECTION_END_MARKERS:
            if upper_line == marker or upper_line.startswith(marker + " "):
                return True
        
        # Outras seções que indicam fim
        if upper_line.startswith("PROPRIEDADES RURAIS"):
            return True
        if upper_line == "BENS DA ATIVIDADE RURAL - BRASIL":
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
            
            # Parar em TOTAL
            if "TOTAL" in upper_next and not re.match(r"^\d{2}\s+", next_line):
                break
            
            # Parar em marcadores de fim
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            # Parar se encontrar novo item
            is_new_item = re.match(r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", next_line)
            if is_new_item:
                break
            
            # Adicionar como continuação da descrição
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+\s+[\d.,]+$", next_line):
                if not next_line.upper().startswith("CÓDIGO"):
                    if not next_line.upper().startswith("DISCRIMINAÇÃO"):
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
