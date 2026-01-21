"""Extrator de rendimentos sujeitos à tributação exclusiva/definitiva."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class ExclusiveIncomeExtractor(ISectionExtractor):
    """Extrai rendimentos de tributação exclusiva/definitiva."""
    
    SECTION_MARKER = "TRIBUTAÇÃO EXCLUSIVA"
    
    @property
    def section_name(self) -> str:
        return "exclusive_taxation_income"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        subsections = {}
        
        variable_income = self._extract_variable_income_gains(context)
        if variable_income:
            subsections["net_gains_from_variable_income_stocks_futures_and_reits"] = variable_income
        
        financial = self._extract_financial_income(context)
        if financial["items"]:
            subsections["income_from_financial_investments"] = financial
        
        if not subsections:
            return None
        
        total_value = sum(s["total_value"] for s in subsections.values())
        
        return {
            "section_name": "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva",
            "total_value": round(total_value, 2),
            "valid_total": True,
            "subsections": subsections
        }
    
    def _extract_variable_income_gains(self, context: ExtractionContext) -> Optional[dict]:
        for page_text in context.pages_text.values():
            if "05." in page_text and "Ganhos líquidos" in page_text:
                pattern = re.search(
                    r"05\.\s*Ganhos líquidos em renda variável[^\d]+([\d.,]+)",
                    page_text,
                    re.IGNORECASE
                )
                if pattern:
                    value = parse_currency(pattern.group(1))
                    return {
                        "name": "05. Ganhos líquidos em renda variável (bolsa de valores, de mercadorias, de futuros e assemelhados e fundos de investimento imobiliário)",
                        "code": "05",
                        "total_value": value,
                        "valid_total": True,
                        "items": None
                    }
        return None
    
    def _extract_financial_income(self, context: ExtractionContext) -> dict:
        items = []
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            lines = page_text.split("\n")
            in_section = False
            
            for i, line in enumerate(lines):
                if "06." in line and "aplicações financeiras" in line.lower():
                    in_section = True
                    continue
                
                if in_section:
                    if "TOTAL" in line.upper() or re.match(r"^\d{2}\.", line):
                        in_section = False
                        continue
                    
                    item = self._parse_item(line, lines, i, page_num)
                    if item:
                        items.append(item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": "06. Rendimentos de aplicações financeiras",
            "code": "06",
            "total_value": total,
            "valid_total": True,
            "items": items
        }
    
    def _parse_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        pattern = re.match(
            r"^(Titular|Dependente)\s+"
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"(.+?)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if not pattern:
            return None
        
        beneficiary = pattern.group(1)
        cpf = pattern.group(2)
        cnpj = pattern.group(3)
        payer_name = pattern.group(4).strip()
        value = parse_currency(pattern.group(5))
        
        item_id = generate_item_id(f"{cnpj}{cpf}{value}")
        
        return {
            "beneficiary": beneficiary,
            "cpf": cpf,
            "payer_cnpj": cnpj,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num
        }
