"""Extrator de dívidas da atividade rural."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id, sum_currency_values
from ...validation_utils import extract_section_total, create_validated_total


class RuralDebtsExtractor(ISectionExtractor):
    """Extrai dívidas vinculadas à atividade rural."""
    
    SECTION_MARKER = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL"
    
    @property
    def section_name(self) -> str:
        return "rural_activity_debts_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_totals = []  # Totais extraídos do PDF
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
            
            # Extrair total do PDF APENAS após o marcador da seção
            if not pdf_totals:
                page_totals = self._extract_section_total(page_text)
                if page_totals:
                    pdf_totals = page_totals
        
        if not items:
            return None
        
        # Somar valores extraídos
        sum_before = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        sum_paid = sum_currency_values([i["paid_value_in_last_year"] for i in items], as_int=False)
        
        # Totais do PDF (se disponíveis)
        pdf_before = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_last = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_paid = pdf_totals[2] if len(pdf_totals) > 2 else None
        
        totals = {
            "year_before_last_value": create_validated_total(sum_before, pdf_before),
            "last_year_value": create_validated_total(sum_last, pdf_last),
            "paid_value_in_last_year": create_validated_total(sum_paid, pdf_paid)
        }
        
        return {
            "section_name": "Dívidas Vinculadas à Atividade Rural - Brasil",
            "items": items,
            "total_values": totals
        }
    
    def _extract_section_total(self, page_text: str) -> list[float]:
        """Extrai o TOTAL específico da seção de Dívidas Rurais.
        
        Busca a linha TOTAL apenas APÓS encontrar o marcador da seção,
        evitando pegar totais de seções anteriores na mesma página.
        """
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})'
        
        for line in lines:
            upper_line = line.upper()
            
            # Entrar na seção
            if self.SECTION_MARKER in upper_line:
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Encontrar linha de TOTAL dentro da seção
            if upper_line.strip().startswith("TOTAL"):
                matches = re.findall(num_pattern, line)
                if matches:
                    return [self._parse_currency(m) for m in matches]
        
        return []
    
    def _parse_currency(self, value_str: str) -> float:
        """Converte string de valor brasileiro para float."""
        if not value_str:
            return 0.0
        cleaned = value_str.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            pattern = re.match(
                r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if pattern and "ITEM" not in line.upper() and "TOTAL" not in line.upper():
                item = self._parse_debt(pattern, lines, i, page_num)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items
    
    def _parse_debt(
        self, 
        match: re.Match, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> dict:
        item_num = int(match.group(1))
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        paid_val = parse_currency(match.group(5))
        
        prefix_parts = self._get_prefix_lines(lines, idx)
        desc_parts = prefix_parts + [desc_start]
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            
            if re.match(r"^\d+\s+", next_line) or "TOTAL" in next_line.upper():
                break
            
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+", next_line):
                desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        item_id = generate_item_id(f"{item_num}{full_desc[:30]}")
        
        return {
            "item": item_num,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "paid_value_in_last_year": paid_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _get_prefix_lines(self, lines: list[str], idx: int) -> list[str]:
        prefix_parts = []
        k = idx - 1
        while k >= 0:
            prev_line = lines[k].strip()
            
            if not prev_line:
                break
            
            if re.match(r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", prev_line):
                break
            
            if re.match(r"^[\d.,]+\s+[\d.,]+\s*$", prev_line):
                break
            
            if "TOTAL" in prev_line.upper() or "ITEM" in prev_line.upper():
                break
            
            if re.match(r"^Página\s+\d+\s+de", prev_line, re.IGNORECASE):
                break
            
            if "DÍVIDAS VINCULADAS" in prev_line.upper():
                break
            
            if self._is_description_fragment(prev_line):
                prefix_parts.insert(0, prev_line)
                k -= 1
            else:
                break
        
        return prefix_parts
    
    def _is_description_fragment(self, line: str) -> bool:
        if re.match(r"^\d+$", line):
            return False
        
        if re.match(r"^[\d.,]+$", line):
            return False
        
        if len(line) < 3:
            return False
        
        return True
