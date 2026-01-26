"""Extrator de rendimentos tributaveis de PJ recebidos acumuladamente pelo titular."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class AccumulatedIncomePJExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de PJ recebidos acumuladamente pelo titular."""
    
    SECTION_MARKER = "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE"
    ALT_MARKER = "RRA"
    HOLDER_MARKER = "PELO TITULAR"
    
    @property
    def section_name(self) -> str:
        return "accumulated_income_from_legal_person_to_holder"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return (
            self.SECTION_MARKER in upper_text and
            self.HOLDER_MARKER in upper_text
        )
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        for page_num, page_text in context.pages_text.items():
            upper_page = page_text.upper()
            
            if self.SECTION_MARKER not in upper_page:
                continue
            
            if self.HOLDER_MARKER not in upper_page:
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
        
        if not items:
            return None
        
        totals = self._calculate_totals(items)
        
        return {
            "section_name": "Rendimentos Tributáveis de Pessoa Jurídica Recebidos Acumuladamente pelo Titular",
            "items": items,
            "total_values": totals
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        is_holder = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            if self.SECTION_MARKER in upper_line:
                if self.HOLDER_MARKER in upper_line:
                    in_section = True
                    is_holder = True
                elif "PELOS DEPENDENTES" in upper_line:
                    in_section = False
                    is_holder = False
                continue
            
            if in_section and is_holder:
                if "RENDIMENTOS" in upper_line and "ACUMULADAMENTE" not in upper_line:
                    break
                if "SEM INFORMAÇÕES" in upper_line:
                    continue
            
            if not in_section or not is_holder:
                continue
            
            item = self._try_parse_income_line(line, lines, i, page_num)
            if item:
                items.append(item)
        
        return items
    
    def _try_parse_income_line(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        pattern = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s*$",
            line.strip()
        )
        
        if not pattern:
            pattern_alt = re.match(
                r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
                r"([\d]+[.,][\d]+[.,]?\d*)\s+"
                r"([\d]+[.,][\d]+[.,]?\d*)\s+"
                r"([\d]+[.,][\d]+[.,]?\d*)\s*$",
                line.strip()
            )
            if pattern_alt:
                return self._parse_alt_format(pattern_alt, lines, idx, page_num)
            return None
        
        payer_name_start = pattern.group(1).strip()
        
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = ""
        months_count = ""
        
        for j in range(idx + 1, min(idx + 8, len(lines))):
            next_line = lines[j].strip()
            
            cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", next_line)
            if cnpj_match:
                cnpj = cnpj_match.group(1)
            
            months_match = re.search(r"Meses[:\s]*(\d+)", next_line, re.IGNORECASE)
            if months_match:
                months_count = months_match.group(1)
            
            if cnpj:
                break
            
            if self._is_name_continuation(next_line):
                name_parts.append(next_line)
        
        if not cnpj:
            return None
        
        full_name = " ".join(name_parts)
        item_id = generate_item_id(f"{cnpj}{full_name}")
        
        result = {
            "payer_name": full_name,
            "accumulated_income": parse_currency(pattern.group(2)),
            "social_security_contribution": parse_currency(pattern.group(3)),
            "tax_withheld_at_source": parse_currency(pattern.group(4)),
            "judicial_expenses": parse_currency(pattern.group(5)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
        
        if months_count:
            result["months_count"] = int(months_count)
        
        return result
    
    def _parse_alt_format(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        payer_name_start = match.group(1).strip()
        
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = ""
        
        for j in range(idx + 1, min(idx + 5, len(lines))):
            next_line = lines[j].strip()
            
            cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", next_line)
            if cnpj_match:
                cnpj = cnpj_match.group(1)
                break
            
            if self._is_name_continuation(next_line):
                name_parts.append(next_line)
        
        if not cnpj:
            return None
        
        full_name = " ".join(name_parts)
        item_id = generate_item_id(f"{cnpj}{full_name}")
        
        return {
            "payer_name": full_name,
            "accumulated_income": parse_currency(match.group(2)),
            "tax_withheld_at_source": parse_currency(match.group(3)),
            "judicial_expenses": parse_currency(match.group(4)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "REND.", "MESES"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        
        if "TOTAL" in line.upper():
            return False
        
        if "Meses" in line or "CNPJ" in line:
            return False
        
        if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+$", line):
            return True
        
        return False
    
    def _calculate_totals(self, items: list[dict]) -> dict:
        totals = {
            "accumulated_income": {
                "amount": round(sum(i.get("accumulated_income", 0) for i in items), 2),
                "valid": True
            },
            "tax_withheld_at_source": {
                "amount": round(sum(i.get("tax_withheld_at_source", 0) for i in items), 2),
                "valid": True
            }
        }
        
        if any("social_security_contribution" in i for i in items):
            totals["social_security_contribution"] = {
                "amount": round(sum(i.get("social_security_contribution", 0) for i in items), 2),
                "valid": True
            }
        
        if any("judicial_expenses" in i for i in items):
            totals["judicial_expenses"] = {
                "amount": round(sum(i.get("judicial_expenses", 0) for i in items), 2),
                "valid": True
            }
        
        return totals
