"""Extrator de rendimentos tributaveis de PJ recebidos acumuladamente pelos dependentes."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import extract_section_total, create_validated_total


class AccumulatedIncomePJDependentsExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de PJ recebidos acumuladamente pelos dependentes (BUG #81773).
    
    Baseado em AccumulatedIncomePJExtractor (titular), adaptado para dependentes.
    """
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTÁVEIS DE PJ RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTAVEIS DE PESSOA JURIDICA RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
    ]
    DEPENDENTS_MARKER = "PELOS DEPENDENTES"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA",
    ]
    
    @property
    def section_name(self) -> str:
        return "accumulated_income_from_legal_person_to_dependents"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Entrar na seção - apenas DEPENDENTES
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                if self.DEPENDENTS_MARKER in upper_page:
                    in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # Verificar "Sem Informações"
            if "SEM INFORMAÇÕES" in upper_page or "SEM INFORMACOES" in upper_page:
                lines = page_text.split("\n")
                for i, line in enumerate(lines):
                    if any(marker in line.upper() for marker in self.SECTION_MARKERS):
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].upper()
                            if "SEM INFORMAÇÕES" in next_line or "SEM INFORMACOES" in next_line:
                                return None
            
            # Extrair itens
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Extrair total do PDF
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
            "section_name": "Rendimentos Tributáveis de Pessoa Jurídica Recebidos Acumuladamente pelos Dependentes",
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
                if self.DEPENDENTS_MARKER in upper_line:
                    in_section = True
                continue
            
            # Detectar fim da seção
            if in_section:
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line:
                    continue
            
            if not in_section:
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
        """Tenta parsear uma linha de rendimento acumulado."""
        
        # Formato 1: NOME CNPJ VALORES (CNPJ inline)
        pattern_cnpj_inline = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)",
            line.strip()
        )
        
        if pattern_cnpj_inline:
            return self._parse_cnpj_inline(pattern_cnpj_inline, lines, idx, page_num)
        
        # Formato 2: NOME CNPJ 3 VALORES
        pattern_cnpj_inline_3v = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)",
            line.strip()
        )
        
        if pattern_cnpj_inline_3v:
            return self._parse_cnpj_inline_3v(pattern_cnpj_inline_3v, lines, idx, page_num)
        
        # Formato 3 (legado): NOME VALORES (CNPJ em linhas seguintes)
        pattern = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s*$",
            line.strip()
        )
        
        if pattern:
            return self._parse_4_values(pattern, lines, idx, page_num)
        
        return None
    
    def _parse_cnpj_inline(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parse formato: NOME CNPJ REND CONTRIB IRRF DESP"""
        payer_name = match.group(1).strip()
        cnpj = match.group(2)
        
        if self._should_skip_line(payer_name):
            return None
        
        item_id = generate_item_id(f"dep_{cnpj}{payer_name}")
        
        return {
            "payer_name": payer_name,
            "cpf_cnpj": cnpj,
            "accumulated_income": parse_currency(match.group(3)),
            "social_security_contribution": parse_currency(match.group(4)),
            "alimony": parse_currency(match.group(5)),
            "tax_withheld_at_source": parse_currency(match.group(6)),
            "id": item_id,
            "page": page_num
        }
    
    def _parse_cnpj_inline_3v(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parse formato: NOME CNPJ REND CONTRIB IRRF (3 valores)"""
        payer_name = match.group(1).strip()
        cnpj = match.group(2)
        
        if self._should_skip_line(payer_name):
            return None
        
        item_id = generate_item_id(f"dep_{cnpj}{payer_name}")
        
        return {
            "payer_name": payer_name,
            "cpf_cnpj": cnpj,
            "accumulated_income": parse_currency(match.group(3)),
            "social_security_contribution": parse_currency(match.group(4)),
            "tax_withheld_at_source": parse_currency(match.group(5)),
            "id": item_id,
            "page": page_num
        }
    
    def _parse_4_values(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parse formato legado com CNPJ em linhas seguintes."""
        payer_name_start = match.group(1).strip()
        
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
        item_id = generate_item_id(f"dep_{cnpj}{full_name}")
        
        result = {
            "payer_name": full_name,
            "accumulated_income": parse_currency(match.group(2)),
            "social_security_contribution": parse_currency(match.group(3)),
            "tax_withheld_at_source": parse_currency(match.group(4)),
            "judicial_expenses": parse_currency(match.group(5)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
        
        if months_count:
            result["months_count"] = int(months_count)
        
        return result
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "REND.", "MESES", "CÓDIGO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        
        if "TOTAL" in line.upper() or "CNPJ" in line.upper():
            return False
        
        if "Meses" in line:
            return False
        
        if re.match(r"^\d{2}\.\d{3}\.\d{3}", line):
            return False
        
        if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+$", line):
            return True
        
        return False
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        """Calcula totais e valida contra os totais do PDF."""
        pdf_totals = pdf_totals or []
        
        sum_income = round(sum(i.get("accumulated_income", 0) for i in items), 2)
        sum_irrf = round(sum(i.get("tax_withheld_at_source", 0) for i in items), 2)
        sum_contrib = round(sum(i.get("social_security_contribution", 0) for i in items), 2)
        sum_judicial = round(sum(i.get("judicial_expenses", 0) for i in items), 2)
        
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_contrib = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_irrf = pdf_totals[2] if len(pdf_totals) > 2 else None
        pdf_judicial = pdf_totals[3] if len(pdf_totals) > 3 else None
        
        totals = {
            "accumulated_income": create_validated_total(sum_income, pdf_income),
            "tax_withheld_at_source": create_validated_total(sum_irrf, pdf_irrf)
        }
        
        if any("social_security_contribution" in i for i in items):
            totals["social_security_contribution"] = create_validated_total(sum_contrib, pdf_contrib)
        
        if any("judicial_expenses" in i for i in items):
            totals["judicial_expenses"] = create_validated_total(sum_judicial, pdf_judicial)
        
        return totals
