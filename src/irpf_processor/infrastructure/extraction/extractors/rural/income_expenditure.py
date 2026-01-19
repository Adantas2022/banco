"""Extrator de receitas e despesas rurais."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralIncomeExpenditureExtractor(ISectionExtractor):
    """Extrai receitas e despesas da atividade rural."""
    
    SECTION_MARKER = "RECEITAS E DESPESAS"
    
    MONTHS = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    
    @property
    def section_name(self) -> str:
        return "rural_income_and_expenditure_in_brazil"
    
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
        
        totals = {
            "gross_revenue": {
                "amount": round(sum(i["gross_revenue"] for i in items), 2),
                "valid": True
            },
            "funding_expenses": {
                "amount": round(sum(i["funding_expenses"] for i in items), 2),
                "valid": True
            }
        }
        
        return {
            "section_name": "Receitas e Despesas - Brasil",
            "items": items,
            "total_values": totals
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        for line in lines:
            for month in self.MONTHS:
                if line.strip().startswith(month):
                    item = self._parse_month_line(line, month, page_num)
                    if item:
                        items.append(item)
        
        return items
    
    def _parse_month_line(
        self, 
        line: str, 
        month: str, 
        page_num: int
    ) -> Optional[dict]:
        pattern = re.match(
            rf"^{month}\s+([\d.,]+)\s+([\d.,]+)\s*$",
            line.strip()
        )
        
        if not pattern:
            return None
        
        revenue = parse_currency(pattern.group(1))
        expenses = parse_currency(pattern.group(2))
        
        item_id = generate_item_id(f"{month}{revenue}{expenses}")
        
        return {
            "month": month,
            "gross_revenue": revenue,
            "funding_expenses": expenses,
            "id": item_id,
            "page": page_num
        }
