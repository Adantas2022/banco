"""Extrator de receitas e despesas rurais."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id
from ...validation_utils import extract_section_total, create_validated_total


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
        pdf_totals = []  # Totais extraídos do PDF
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
            
            # Extrair total do PDF (se existir nesta página)
            if not pdf_totals:
                page_totals = extract_section_total(page_text, "TOTAL")
                if page_totals:
                    pdf_totals = page_totals
        
        if not items:
            return None
        
        # Somar valores extraídos
        sum_revenue = round(sum(i["gross_revenue"] for i in items), 2)
        sum_expenses = round(sum(i["funding_expenses"] for i in items), 2)
        
        # Totais do PDF (se disponíveis)
        pdf_revenue = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_expenses = pdf_totals[1] if len(pdf_totals) > 1 else None
        
        totals = {
            "gross_revenue": create_validated_total(sum_revenue, pdf_revenue),
            "funding_expenses": create_validated_total(sum_expenses, pdf_expenses)
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
