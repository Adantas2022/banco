"""Extrator de rendimentos tributaveis de pessoa fisica e do exterior pelo titular."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class IncomePFExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de pessoa fisica e do exterior pelo titular."""
    
    SECTION_MARKER = "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA"
    ALT_MARKER = "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA E DO EXTERIOR"
    HOLDER_MARKER = "PELO TITULAR"
    
    MONTHS = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
    
    @property
    def section_name(self) -> str:
        return "income_from_individual_to_holder"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return (
            (self.SECTION_MARKER in upper_text or self.ALT_MARKER in upper_text) and
            self.HOLDER_MARKER in upper_text
        )
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        if not self.can_extract(context):
            return None
        
        for page_num, page_text in context.pages_text.items():
            upper_page = page_text.upper()
            
            if (self.SECTION_MARKER not in upper_page and self.ALT_MARKER not in upper_page):
                continue
            
            if self.HOLDER_MARKER not in upper_page:
                continue
            
            if "PELOS DEPENDENTES" in upper_page and "PELO TITULAR" not in upper_page:
                continue
            
            result = self._extract_monthly_format(page_text, page_num)
            if result:
                return result
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Física e do Exterior pelo Titular",
            "nit_pis_pasep": None,
            "monthly_income": [],
            "monthly_deductions": [],
            "income_totals": {
                "trabalho_nao_assalariado": 0.0,
                "por_temporada": 0.0,
                "alugueis_inclusive": 0.0,
                "outros": 0.0,
                "exterior": 0.0
            },
            "deduction_totals": {
                "previdencia_oficial": 0.0,
                "quantidade_dependentes": 0,
                "pensao_alimenticia": 0.0,
                "livro_caixa": 0.0,
                "darf_pago": 0.0
            }
        }
    
    def _extract_monthly_format(self, page_text: str, page_num: int) -> Optional[dict]:
        lines = page_text.split("\n")
        
        nit_pis_pasep = None
        monthly_income = []
        monthly_deductions = []
        income_totals = {}
        deduction_totals = {}
        
        in_income_section = False
        in_deduction_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper().strip()
            
            if "NIT/PIS/PASEP" in upper_line:
                nit_match = re.search(r"NIT/PIS/PASEP[:\s]*(\d[\d.\-/]*)?", line, re.IGNORECASE)
                if nit_match and nit_match.group(1):
                    nit_pis_pasep = nit_match.group(1).strip()
                continue
            
            if "RENDIMENTOS" in upper_line and "TRABALHO NÃO" not in upper_line and "ASSALARIADO" not in upper_line:
                if "DEDUÇÕES" not in upper_line:
                    in_income_section = True
                    in_deduction_section = False
                continue
            
            if "DEDUÇÕES CARNÊ-LEÃO" in upper_line or "DEDUCOES CARNE-LEAO" in upper_line:
                in_income_section = False
                in_deduction_section = True
                continue
            
            month_match = re.match(r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+", upper_line)
            if month_match:
                month = month_match.group(1)
                values_str = line[month_match.end():].strip()
                values = self._extract_values_from_line(values_str)
                
                if in_income_section or (not in_deduction_section and len(values) >= 4):
                    if len(values) >= 4:
                        monthly_income.append({
                            "month": month,
                            "trabalho_nao_assalariado": values[0],
                            "por_temporada": values[1],
                            "alugueis_inclusive": values[2],
                            "outros": values[3],
                            "exterior": values[4] if len(values) > 4 else 0.0
                        })
                elif in_deduction_section:
                    if len(values) >= 5:
                        monthly_deductions.append({
                            "month": month,
                            "previdencia_oficial": values[0],
                            "quantidade_dependentes": int(values[1]) if values[1] == int(values[1]) else 0,
                            "pensao_alimenticia": values[2],
                            "livro_caixa": values[3],
                            "darf_pago": values[4]
                        })
                continue
            
            if "TOTAL" in upper_line and not "TOTALIZAÇÃO" in upper_line:
                values_str = re.sub(r"^TOTAL\s*", "", line, flags=re.IGNORECASE).strip()
                values = self._extract_values_from_line(values_str)
                
                if in_income_section and len(values) >= 4:
                    income_totals = {
                        "trabalho_nao_assalariado": values[0],
                        "por_temporada": values[1],
                        "alugueis_inclusive": values[2],
                        "outros": values[3],
                        "exterior": values[4] if len(values) > 4 else 0.0
                    }
                    in_income_section = False
                elif in_deduction_section and len(values) >= 4:
                    deduction_totals = {
                        "previdencia_oficial": values[0],
                        "quantidade_dependentes": 0,
                        "pensao_alimenticia": values[1] if len(values) > 1 else 0.0,
                        "livro_caixa": values[2] if len(values) > 2 else 0.0,
                        "darf_pago": values[3] if len(values) > 3 else 0.0
                    }
                    in_deduction_section = False
        
        if not income_totals and monthly_income:
            income_totals = {
                "trabalho_nao_assalariado": sum(m.get("trabalho_nao_assalariado", 0) for m in monthly_income),
                "por_temporada": sum(m.get("por_temporada", 0) for m in monthly_income),
                "alugueis_inclusive": sum(m.get("alugueis_inclusive", 0) for m in monthly_income),
                "outros": sum(m.get("outros", 0) for m in monthly_income),
                "exterior": sum(m.get("exterior", 0) for m in monthly_income)
            }
        
        if not deduction_totals and monthly_deductions:
            deduction_totals = {
                "previdencia_oficial": sum(m.get("previdencia_oficial", 0) for m in monthly_deductions),
                "quantidade_dependentes": sum(m.get("quantidade_dependentes", 0) for m in monthly_deductions),
                "pensao_alimenticia": sum(m.get("pensao_alimenticia", 0) for m in monthly_deductions),
                "livro_caixa": sum(m.get("livro_caixa", 0) for m in monthly_deductions),
                "darf_pago": sum(m.get("darf_pago", 0) for m in monthly_deductions)
            }
        
        if not monthly_income and not income_totals:
            return None
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Física e do Exterior pelo Titular",
            "nit_pis_pasep": nit_pis_pasep,
            "monthly_income": monthly_income,
            "monthly_deductions": monthly_deductions,
            "income_totals": income_totals or {
                "trabalho_nao_assalariado": 0.0,
                "por_temporada": 0.0,
                "alugueis_inclusive": 0.0,
                "outros": 0.0,
                "exterior": 0.0
            },
            "deduction_totals": deduction_totals or {
                "previdencia_oficial": 0.0,
                "quantidade_dependentes": 0,
                "pensao_alimenticia": 0.0,
                "livro_caixa": 0.0,
                "darf_pago": 0.0
            },
            "page": page_num
        }
    
    def _extract_values_from_line(self, text: str) -> list[float]:
        values = []
        
        parts = re.findall(r"[\d.,]+", text)
        
        for part in parts:
            try:
                clean = part.replace(".", "").replace(",", ".")
                values.append(float(clean))
            except ValueError:
                continue
        
        return values
