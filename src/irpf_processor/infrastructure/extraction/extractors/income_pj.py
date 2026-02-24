"""Extrator de rendimentos tributáveis de pessoa jurídica."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import extract_section_total, create_validated_total


class IncomePJExtractor(ISectionExtractor):
    """Extrai rendimentos tributáveis de pessoa jurídica pelo titular."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELO TITULAR"
    ]
    HOLDER_MARKER = "PELO TITULAR"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELOS DEPENDENTES",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS"
    ]
    
    @property
    def section_name(self) -> str:
        return "income_from_legal_person_to_holder"
    
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
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # Extrair itens
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Extrair total do PDF (se existir nesta página)
            if not pdf_totals:
                page_totals = extract_section_total(
                    page_text, 
                    "TOTAL",
                    skip_keywords=["TOTAL DE DEDUÇÃO", "TOTAL DO"]
                )
                if page_totals:
                    pdf_totals = page_totals
            
            # Verificar fim após extração
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
        if not items:
            return None
        
        totals = self._calculate_totals(items, pdf_totals)
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Jurídica pelo Titular",
            "items": items,
            "total_values": totals
        }
    
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
            
            # Detectar início da seção
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            # Detectar fim da seção
            if in_section:
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line:
                    continue
            
            # Se não encontrou início explícito mas pode ter itens, continuar
            if "CNPJ" in upper_line or "CÓDIGO" in upper_line:
                in_section = True
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
        # Formato: NOME RENDIMENTO CONTRIB_PREV IRRF 13_SALARIO IRRF_13
        # Padrão unificado que aceita AMBOS os formatos:
        # - Brasileiro: 250.000,00 (ponto=milhar, vírgula=decimal)
        # - Americano: 250,000.00 (vírgula=milhar, ponto=decimal)
        num_pattern = r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})"
        pattern = re.match(
            rf"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,\-/]+?)\s+"
            rf"{num_pattern}\s+"
            rf"{num_pattern}\s+"
            rf"{num_pattern}\s+"
            rf"{num_pattern}\s+"
            rf"{num_pattern}\s*$",
            line.strip()
        )
        
        if not pattern:
            return None
        
        payer_name_start = pattern.group(1).strip()
        
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = ""
        
        # Procurar CNPJ nas linhas seguintes
        for j in range(idx + 1, min(idx + 6, len(lines))):
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
        # Incluir valores no ID para diferenciar entradas do mesmo pagador com valores diferentes
        income_val = pattern.group(2)
        contrib_val = pattern.group(3)
        item_id = generate_item_id(f"{cnpj}{full_name}{income_val}{contrib_val}")
        
        return {
            "payer_name": full_name,
            "income_from_legal_person": parse_currency(pattern.group(2)),
            "official_social_security_contribution": parse_currency(pattern.group(3)),
            "tax_withheld_at_source": parse_currency(pattern.group(4)),
            "thirteenth_salary": parse_currency(pattern.group(5)),
            "irrf_on_thirteenth_salary": parse_currency(pattern.group(6)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "REND.", "CÓDIGO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        
        if "TOTAL" in line.upper() or "CNPJ" in line.upper():
            return False
        
        if re.match(r"^\d{2}\.\d{3}\.\d{3}", line):
            return False
        
        if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+$", line):
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
