"""Extrator de rendimentos tributaveis de pessoa fisica e do exterior pelos dependentes."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class IncomePFDependentsExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de pessoa fisica e do exterior pelos dependentes (BUG #81767).
    
    Baseado em IncomePFExtractor (titular), adaptado para dependentes.
    """
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA E DO EXTERIOR PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA FISICA PELOS DEPENDENTES",
    ]
    
    DEPENDENTS_MARKER = "PELOS DEPENDENTES"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA",
        "PAGAMENTOS EFETUADOS",
    ]
    
    MONTHS_MAP = {
        "JAN": "jan", "FEV": "fev", "MAR": "mar", "ABR": "abr",
        "MAI": "mai", "JUN": "jun", "JUL": "jul", "AGO": "ago",
        "SET": "set", "OUT": "out", "NOV": "nov", "DEZ": "dez"
    }
    
    @property
    def section_name(self) -> str:
        return "income_from_individual_to_dependents"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        if not self.can_extract(context):
            return None
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            if not any(marker in upper_page for marker in self.SECTION_MARKERS):
                continue
            
            # Verificar se é seção de dependentes (não titular)
            if self.DEPENDENTS_MARKER not in upper_page:
                continue
            
            # Verificar "Sem Informações"
            if "SEM INFORMAÇÕES" in upper_page or "SEM INFORMACOES" in upper_page:
                lines = page_text.split("\n")
                for i, line in enumerate(lines):
                    if any(marker in line.upper() for marker in self.SECTION_MARKERS):
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].upper()
                            if "SEM INFORMAÇÕES" in next_line or "SEM INFORMACOES" in next_line:
                                return None
            
            result = self._extract_dimensa_format(page_text, page_num)
            if result:
                return result
        
        return None
    
    def _extract_dimensa_format(self, page_text: str, page_num: int) -> Optional[dict]:
        """Extrai dados no formato DIMENSA."""
        lines = page_text.split("\n")
        
        dependent_cpf = ""
        nit_pis_pasep = ""
        income_data: dict[str, dict] = {}
        deductions_data: dict[str, dict] = {}
        income_totals_pdf: dict[str, float] = {}
        deductions_totals_pdf: dict[str, float] = {}
        
        in_section = False
        in_income_section = False
        in_deduction_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper().strip()
            
            # Detectar início da seção
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Detectar fim da seção
            for end_marker in self.SECTION_END_MARKERS:
                if end_marker in upper_line:
                    in_section = False
                    break
            
            if not in_section:
                break
            
            # CPF do dependente (BUG FIX: capturar dependent_cpf)
            cpf_match = re.search(r"CPF[:\s]*(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})", line, re.IGNORECASE)
            if cpf_match and not dependent_cpf:
                dependent_cpf = cpf_match.group(1).strip()
                continue
            
            # NIT/PIS/PASEP
            if "NIT/PIS/PASEP" in upper_line:
                nit_match = re.search(r"NIT/PIS/PASEP[:\s]*(\d[\d.\-/]*)?", line, re.IGNORECASE)
                if nit_match and nit_match.group(1):
                    nit_pis_pasep = nit_match.group(1).strip()
                continue
            
            # Seção de rendimentos
            if "RENDIMENTOS" in upper_line and "TRABALHO NÃO" not in upper_line and "ASSALARIADO" not in upper_line:
                if "DEDUÇÕES" not in upper_line:
                    in_income_section = True
                    in_deduction_section = False
                continue
            
            # Seção de deduções
            if "DEDUÇÕES CARNÊ-LEÃO" in upper_line or "DEDUCOES CARNE-LEAO" in upper_line:
                in_income_section = False
                in_deduction_section = True
                continue
            
            # Parsear linhas de mês
            month_match = re.match(r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)\s+", upper_line)
            if month_match:
                month_upper = month_match.group(1)
                month_lower = self.MONTHS_MAP.get(month_upper, month_upper.lower())
                values_str = line[month_match.end():].strip()
                values = self._extract_values_from_line(values_str)
                
                if in_income_section or (not in_deduction_section and len(values) >= 4):
                    if len(values) >= 4:
                        income_data[month_lower] = {
                            "unwaged_work": values[0],
                            "rental": values[1],
                            "others": values[2],
                            "income_from_abroad": values[3],
                        }
                elif in_deduction_section:
                    if len(values) >= 4:
                        deductions_data[month_lower] = {
                            "official_social_security": values[0],
                            "dependents_number": int(values[1]) if values[1] == int(values[1]) else 0,
                            "alimony": values[2],
                            "cashbook": values[3]
                        }
                continue
            
            # Parsear linha de TOTAL
            if "TOTAL" in upper_line and "TOTALIZAÇÃO" not in upper_line:
                values_str = re.sub(r"^TOTAL\s*", "", line, flags=re.IGNORECASE).strip()
                values = self._extract_values_from_line(values_str)
                
                if in_income_section and len(values) >= 4:
                    income_totals_pdf = {
                        "unwaged_work": values[0],
                        "rental": values[1],
                        "others": values[2],
                        "income_from_abroad": values[3],
                    }
                    in_income_section = False
                elif in_deduction_section and len(values) >= 3:
                    deductions_totals_pdf = {
                        "official_social_security": values[0],
                        "alimony": values[1] if len(values) > 1 else 0.0,
                        "cashbook": values[2] if len(values) > 2 else 0.0,
                    }
                    in_deduction_section = False
        
        if not income_data:
            return None
        
        # Calcular totais
        income_data["total"] = self._calculate_income_totals(income_data, income_totals_pdf)
        
        item = {
            "nit_pis_pasep": nit_pis_pasep,
            "income": income_data,
        }
        
        # BUG FIX: Adicionar dependent_cpf se encontrado
        if dependent_cpf:
            item["dependent_cpf"] = dependent_cpf
        
        if deductions_data:
            deductions_data["total"] = self._calculate_deductions_totals(deductions_data, deductions_totals_pdf)
            item["deductions"] = deductions_data
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Física e do Exterior pelos Dependentes",
            "items": [item],
            "page": page_num
        }
    
    def _calculate_income_totals(self, income_data: dict, pdf_totals: dict) -> dict:
        """Calcula totais de income com estrutura {amount, valid}."""
        months = list(self.MONTHS_MAP.values())
        
        calculated = {
            "unwaged_work": round(sum(income_data.get(m, {}).get("unwaged_work", 0) for m in months), 2),
            "rental": round(sum(income_data.get(m, {}).get("rental", 0) for m in months), 2),
            "others": round(sum(income_data.get(m, {}).get("others", 0) for m in months), 2),
            "income_from_abroad": round(sum(income_data.get(m, {}).get("income_from_abroad", 0) for m in months), 2),
        }
        
        result = {}
        for field in ["unwaged_work", "rental", "others", "income_from_abroad"]:
            amount = pdf_totals.get(field, calculated[field])
            valid = abs(calculated[field] - amount) < 0.01 if pdf_totals else True
            result[field] = {"amount": amount, "valid": valid}
        
        return result
    
    def _calculate_deductions_totals(self, deductions_data: dict, pdf_totals: dict) -> dict:
        """Calcula totais de deductions com estrutura {amount, valid}."""
        months = list(self.MONTHS_MAP.values())
        
        calculated = {
            "official_social_security": round(sum(deductions_data.get(m, {}).get("official_social_security", 0) for m in months), 2),
            "alimony": round(sum(deductions_data.get(m, {}).get("alimony", 0) for m in months), 2),
            "cashbook": round(sum(deductions_data.get(m, {}).get("cashbook", 0) for m in months), 2),
        }
        
        result = {}
        for field in ["official_social_security", "alimony", "cashbook"]:
            amount = pdf_totals.get(field, calculated[field])
            valid = abs(calculated[field] - amount) < 0.01 if pdf_totals else True
            result[field] = {"amount": amount, "valid": valid}
        
        return result
    
    def _extract_values_from_line(self, text: str) -> list[float]:
        """Extrai valores numéricos de uma linha."""
        values = []
        parts = re.findall(r"[\d.,]+", text)
        
        for part in parts:
            try:
                clean = part.replace(".", "").replace(",", ".")
                values.append(float(clean))
            except ValueError:
                continue
        
        return values
