"""Extrator de dívidas da atividade rural - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id, sum_currency_values
from ...validation_utils import create_validated_total


class RuralDebtsAbroadExtractor(ISectionExtractor):
    """Extrai dívidas vinculadas à atividade rural - Exterior (BUG #81784)."""
    
    SECTION_MARKERS = [
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR",
        "DIVIDAS VINCULADAS A ATIVIDADE RURAL - EXTERIOR",
        "DÍVIDAS VINCULADAS - EXTERIOR",
        "DIVIDAS VINCULADAS - EXTERIOR",
    ]
    
    SECTION_END_MARKERS = [
        "DEMONSTRATIVO",
        "RESUMO TRIBUTAÇÃO",
        "RESUMO TRIBUTACAO",
        "BENS DA ATIVIDADE RURAL",
        "PÁGINA",
        "PAGINA",
    ]
    
    @property
    def section_name(self) -> str:
        return "rural_activity_debts_abroad"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_totals = []
        
        for page_num, page_text in context.pages_text.items():
            upper_page = page_text.upper()
            
            if not any(marker in upper_page for marker in self.SECTION_MARKERS):
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
            
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
        
        pdf_before = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_last = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_paid = pdf_totals[2] if len(pdf_totals) > 2 else None
        
        totals = {
            "year_before_last_value": create_validated_total(sum_before, pdf_before),
            "last_year_value": create_validated_total(sum_last, pdf_last),
            "paid_value_in_last_year": create_validated_total(sum_paid, pdf_paid)
        }
        
        return {
            "section_name": "Dívidas Vinculadas à Atividade Rural - Exterior",
            "items": items,
            "total_values": totals
        }
    
    def _extract_section_total(self, page_text: str) -> list[float]:
        """Extrai o TOTAL específico da seção."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})'
        
        for line in lines:
            upper_line = line.upper()
            
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            for end in self.SECTION_END_MARKERS:
                if upper_line.strip().startswith(end):
                    return []
            
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
        
        in_section = False
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            # Detectar início
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                i += 1
                continue
            
            if not in_section:
                i += 1
                continue
            
            # Detectar fim
            for marker in self.SECTION_END_MARKERS:
                if upper_line.startswith(marker):
                    return items
            
            if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                i += 1
                continue
            
            # Padrão: ITEM DESC VAL1 VAL2 VAL3
            # Ex: "1 2024 EMPRESTIMO RURAL MES ABRIL BANCO 0,00 6.191.700,00 256.108,64"
            pattern = re.match(
                r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if pattern and "ITEM" not in upper_line and "TOTAL" not in upper_line:
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
        
        # Capturar descrição multi-linha
        desc_parts = [desc_start]
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            # Parar se encontrar outro item, total ou fim de seção
            if re.match(r"^\d+\s+", next_line) or "TOTAL" in upper_next:
                break
            
            for marker in self.SECTION_END_MARKERS:
                if upper_next.startswith(marker):
                    break
            else:
                # Adicionar continuação da descrição
                if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+", next_line):
                    desc_parts.append(next_line)
                j += 1
                continue
            break
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        item_id = generate_item_id(f"debt_abroad_{item_num}_{full_desc[:30]}")
        
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
