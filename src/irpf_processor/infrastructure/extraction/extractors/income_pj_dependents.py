"""Extrator de rendimentos tributaveis de pessoa juridica pelos dependentes."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import extract_section_total, create_validated_total


class IncomePJDependentsExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de pessoa juridica pelos dependentes."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELOS DEPENDENTES"
    ]
    DEPENDENTS_MARKER = "PELOS DEPENDENTES"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA",
        "PAGAMENTOS EFETUADOS"
    ]
    
    @property
    def section_name(self) -> str:
        return "income_from_legal_person_to_dependents"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []  # Totais extraídos do PDF
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Entrar na seção
            section_start_found = any(marker in upper_page for marker in self.SECTION_MARKERS)
            if section_start_found and self.DEPENDENTS_MARKER in upper_page:
                in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # Extrair itens
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Extrair total do PDF SOMENTE após o marcador de dependentes
            # Isso evita capturar o total da seção do titular que pode estar na mesma página
            if not pdf_totals:
                page_totals = self._extract_total_after_section_marker(page_text)
                if page_totals:
                    pdf_totals = page_totals
            
            # Verificar fim após extração
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
        if not items:
            return None
        
        totals = self._calculate_totals(items, pdf_totals)
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoas Jurídicas pelos Dependentes",
            "items": items,
            "total_values": totals
        }
    
    def _extract_total_after_section_marker(self, page_text: str) -> list[float]:
        """Extrai o total APENAS após o marcador da seção de dependentes.
        
        Isso evita capturar o total da seção do titular que pode estar na mesma página.
        """
        lines = page_text.split("\n")
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        
        found_dependents_marker = False
        
        for line in lines:
            upper_line = line.upper()
            
            # Encontrar marcador de dependentes
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                if self.DEPENDENTS_MARKER in upper_line and "PELO TITULAR" not in upper_line:
                    found_dependents_marker = True
                    continue
            
            # Só procurar TOTAL após o marcador de dependentes
            if not found_dependents_marker:
                continue
            
            stripped = line.strip()
            if stripped.upper().startswith("TOTAL") and "TOTAL DE DEDUÇÃO" not in stripped.upper():
                import re
                matches = re.findall(num_pattern, stripped)
                if matches:
                    from ..validation_utils import parse_currency_value
                    return [parse_currency_value(m) for m in matches]
        
        return []
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        """Verifica se a página marca o fim da seção."""
        upper_text = page_text.upper()
        for marker in self.SECTION_END_MARKERS:
            if marker in upper_text:
                return True
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início da seção (DEPENDENTES, não TITULAR)
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                # Verificar que não é a seção do titular
                if "PELO TITULAR" not in upper_line:
                    in_section = True
                    continue
            
            if not in_section:
                continue
            
            # Detectar fim da seção - apenas se for uma nova seção diferente
            if "RENDIMENTOS TRIBUTÁVEIS" in upper_line and "PESSOA FÍSICA" in upper_line:
                break
            if "RENDIMENTOS ISENTOS" in upper_line:
                break
            if "PAGAMENTOS EFETUADOS" in upper_line:
                break
            if "SEM INFORMAÇÕES" in upper_line:
                continue
            if "TOTAL" in upper_line and not any(marker in upper_line for marker in self.SECTION_MARKERS):
                # É o TOTAL da seção, processar e depois parar
                continue
            
            # Tentar parsear item
            item = self._try_parse_income_line(line, lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
        
        return items
    
    def _try_parse_income_line(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        from .income_pj import _LINE_5VAL_RE, _LINE_4VAL_RE, _find_cnpj
        
        stripped = line.strip()
        
        m5 = _LINE_5VAL_RE.match(stripped)
        m4 = _LINE_4VAL_RE.match(stripped) if not m5 else None
        match = m5 or m4
        
        if not match:
            return None
        
        payer_name_start = match.group(1).strip()
        
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = ""
        dependent_name = ""
        dependent_cpf = ""
        
        for j in range(idx + 1, min(idx + 8, len(lines))):
            next_line = lines[j].strip()
            
            if not cnpj:
                cnpj = _find_cnpj(next_line)
            
            cpf_dep_match = re.search(r"(?:CPF\s+DO\s+)?DEPENDENTE[:\s]*(\d{3}\.\d{3}\.\d{3}-\d{2})", next_line, re.IGNORECASE)
            if cpf_dep_match:
                dependent_cpf = cpf_dep_match.group(1)
            elif not dependent_cpf:
                cpf_match = re.search(r"CPF[:\s]+(\d{3}\.\d{3}\.\d{3}-\d{2})", next_line)
                if cpf_match:
                    dependent_cpf = cpf_match.group(1)
            
            dependent_match = re.search(r"Dependente[:\s]*(.+?)(?:\s+CPF|$)", next_line, re.IGNORECASE)
            if dependent_match:
                dependent_name = dependent_match.group(1).strip()
            
            if cnpj and (dependent_cpf or dependent_name):
                break
            
            if self._is_name_continuation(next_line):
                name_parts.append(next_line)
        
        if not cnpj:
            return None
        
        full_name = " ".join(name_parts)
        item_id = generate_item_id(f"{cnpj}{full_name}{dependent_cpf}")
        
        if m5:
            result = {
                "payer_name": full_name,
                "income_from_legal_person": parse_currency(match.group(2)),
                "official_social_security_contribution": parse_currency(match.group(3)),
                "tax_withheld_at_source": parse_currency(match.group(4)),
                "thirteenth_salary": parse_currency(match.group(5)),
                "irrf_on_thirteenth_salary": parse_currency(match.group(6)),
                "cpf_cnpj": cnpj,
                "id": item_id,
                "page": page_num,
                "beneficiary_type": "Dependente"
            }
        else:
            result = {
                "payer_name": full_name,
                "income_from_legal_person": parse_currency(match.group(2)),
                "official_social_security_contribution": 0.0,
                "tax_withheld_at_source": parse_currency(match.group(3)),
                "thirteenth_salary": parse_currency(match.group(4)),
                "irrf_on_thirteenth_salary": parse_currency(match.group(5)),
                "cpf_cnpj": cnpj,
                "id": item_id,
                "page": page_num,
                "beneficiary_type": "Dependente"
            }
        
        if dependent_name:
            result["dependent_name"] = dependent_name
        if dependent_cpf:
            result["dependent_cpf"] = dependent_cpf
        
        return result
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "REND.", "DEPENDENTE", "CÓDIGO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        if "TOTAL" in line.upper() or "CNPJ" in line.upper():
            return False
        if "Dependente" in line or "CPF" in line:
            return False
        if re.match(r"^\d{2}\.\d{3}\.\d{3}", line):
            return False
        if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d\s.,&]+$", line):
            return True
        return False
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        """Calcula totais e valida contra os totais do PDF.
        
        Args:
            items: Lista de itens extraídos
            pdf_totals: Lista de totais do PDF [rend, contrib, irrf, 13º, irrf_13]
        """
        pdf_totals = pdf_totals or []
        
        # Somar valores extraídos
        sum_income = round(sum(i["income_from_legal_person"] for i in items), 2)
        sum_contrib = round(sum(i["official_social_security_contribution"] for i in items), 2)
        sum_irrf = round(sum(i["tax_withheld_at_source"] for i in items), 2)
        sum_13 = round(sum(i["thirteenth_salary"] for i in items), 2)
        sum_irrf_13 = round(sum(i["irrf_on_thirteenth_salary"] for i in items), 2)
        
        # Totais do PDF (se disponíveis)
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_contrib = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_irrf = pdf_totals[2] if len(pdf_totals) > 2 else None
        pdf_13 = pdf_totals[3] if len(pdf_totals) > 3 else None
        pdf_irrf_13 = pdf_totals[4] if len(pdf_totals) > 4 else None
        
        return {
            "income_from_legal_person": create_validated_total(sum_income, pdf_income),
            "official_social_security_contribution": create_validated_total(sum_contrib, pdf_contrib),
            "tax_withheld_at_source": create_validated_total(sum_irrf, pdf_irrf),
            "thirteenth_salary": create_validated_total(sum_13, pdf_13),
            "irrf_on_thirteenth_salary": create_validated_total(sum_irrf_13, pdf_irrf_13)
        }
