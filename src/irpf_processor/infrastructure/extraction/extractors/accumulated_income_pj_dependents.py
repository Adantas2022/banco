"""Extrator de rendimentos tributaveis de PJ recebidos acumuladamente pelos dependentes."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import extract_section_total, create_validated_total


class AccumulatedIncomePJDependentsExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de PJ recebidos acumuladamente pelos dependentes.
    
    Estrutura esperada (conforme gabarito):
    {
        "section_name": "Rendimentos Tributáveis de Pessoa Jurídica Recebidos Acumuladamente pelos Dependentes",
        "items": [
            {
                "payer_name": "GOVERNO DO ESTADO DO AMAZONAS",
                "cpf_cnpj": "04.572.100/0001-43",
                "taxable_income_total": 40000.0,
                "official_social_security_contribution": 8000.0,
                "alimony": 0.0,
                "tax_withheld_at_source": 1000.0,
                "tax_option": "Exclusiva",
                "month_of_receipt": "Mar.",
                "amount_received_related_to_interest": 0.0,
                "number_of_months": 120.0,
                "tax_due_rra": 0.0,
                "exempt_portion_65_years": null,
                "dependent_cpf": "303.216.120-78",
                "feeding": null,
                "id": "...",
                "page": 8
            }
        ],
        "total_values": {
            "taxable_income_total": {...},
            "official_social_security_contribution": {...},
            "alimony": {...},
            "tax_withheld_at_source": {...}
        }
    }
    """
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTÁVEIS DE PJ RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTAVEIS DE PESSOA JURIDICA RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
        "RECEBIDOS ACUMULADAMENTE PELOS",
        "ACUMULADAMENTE PELOS DEPENDENTES",
    ]
    
    DEPENDENTS_MARKER = "DEPENDENTES"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA",
        "IMPOSTO PAGO / RETIDO",
    ]
    
    @property
    def section_name(self) -> str:
        return "accumulated_income_from_legal_person_to_dependents"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        for marker in self.SECTION_MARKERS:
            if marker in upper_text:
                if "PESSOA JURÍDICA" in marker or "PESSOA JURIDICA" in marker:
                    return True
        
        for page_text in context.pages_text.values():
            lines = page_text.split("\n")
            for i, line in enumerate(lines):
                upper_line = line.upper()
                if ("PESSOA JURÍDICA" in upper_line or "PESSOA JURIDICA" in upper_line or 
                    "TRIBUTÁVEIS" in upper_line or "TRIBUTAVEIS" in upper_line):
                    if "RECEBIDOS ACUMULADAMENTE PELOS" in upper_line and "PELO TITULAR" not in upper_line:
                        if "DEPENDENTES" in upper_line:
                            return True
                        if i + 1 < len(lines) and "DEPENDENTES" in lines[i + 1].upper():
                            return True
        
        return False
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            if not in_section:
                in_section = self._is_section_start(page_text)
            
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
            
            section_starts_here = self._is_section_start(page_text)
            already_in_section = in_section and not section_starts_here
            
            page_items = self._extract_from_page(page_text, page_num, seen_ids, already_in_section)
            items.extend(page_items)
            
            if not pdf_totals:
                page_totals = extract_section_total(
                    page_text, 
                    "TOTAL",
                    skip_keywords=["TOTAL DE DEDUÇÃO", "TOTAL DO"]
                )
                if page_totals:
                    pdf_totals = page_totals
            
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
    
    def _is_section_start(self, page_text: str) -> bool:
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            for marker in self.SECTION_MARKERS:
                if marker in upper_line:
                    if "PESSOA JURÍDICA" in marker or "PESSOA JURIDICA" in marker:
                        return True
            
            if ("PESSOA JURÍDICA" in upper_line or "PESSOA JURIDICA" in upper_line or 
                "TRIBUTÁVEIS" in upper_line or "TRIBUTAVEIS" in upper_line):
                if "RECEBIDOS ACUMULADAMENTE PELOS" in upper_line and "PELO TITULAR" not in upper_line:
                    if "DEPENDENTES" in upper_line:
                        return True
                    if i + 1 < len(lines) and "DEPENDENTES" in lines[i + 1].upper():
                        return True
        
        return False
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        upper_text = page_text.upper()
        for marker in self.SECTION_END_MARKERS:
            if marker in upper_text:
                return True
        return False
    
    def _extract_from_page(
        self, 
        page_text: str, 
        page_num: int, 
        seen_ids: set,
        already_in_section: bool = False
    ) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = already_in_section
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            if not in_section:
                for marker in self.SECTION_MARKERS:
                    if marker in upper_line:
                        if "PESSOA JURÍDICA" in marker or "PESSOA JURIDICA" in marker:
                            in_section = True
                            continue
                
                if ("PESSOA JURÍDICA" in upper_line or "PESSOA JURIDICA" in upper_line or 
                    "TRIBUTÁVEIS" in upper_line or "TRIBUTAVEIS" in upper_line):
                    if "RECEBIDOS ACUMULADAMENTE PELOS" in upper_line and "PELO TITULAR" not in upper_line:
                        if "DEPENDENTES" in upper_line:
                            in_section = True
                        elif i + 1 < len(lines) and "DEPENDENTES" in lines[i + 1].upper():
                            in_section = True
                continue
            
            if in_section:
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                    continue
            
            if "DEPENDENTES" == upper_line.strip() or "(VALORES EM REAIS)" in upper_line:
                continue
            
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
        
        # Formato: NOME CNPJ VALORES (4 valores: REND, CONTRIB, PENSAO, IRRF)
        pattern_cnpj_inline = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d\s.,&()\-]+?)\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)",
            line.strip()
        )
        
        if pattern_cnpj_inline:
            return self._parse_cnpj_inline(pattern_cnpj_inline, lines, idx, page_num)
        
        # Formato com 3 valores
        pattern_cnpj_inline_3v = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d\s.,&()\-]+?)\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)",
            line.strip()
        )
        
        if pattern_cnpj_inline_3v:
            return self._parse_cnpj_inline_3v(pattern_cnpj_inline_3v, lines, idx, page_num)
        
        return None
    
    def _parse_cnpj_inline(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parse formato: NOME CNPJ REND CONTRIB PENSAO IRRF
        
        Campos extraídos conforme schema:
        - payer_name: Nome da fonte pagadora (pode estar em múltiplas linhas)
        - cpf_cnpj: CNPJ da fonte
        - taxable_income_total: Total de rendimentos tributáveis
        - official_social_security_contribution: Contribuição previdenciária oficial
        - alimony: Pensão alimentícia
        - tax_withheld_at_source: Imposto retido na fonte
        - tax_option: Opção de tributação (Exclusiva/Ajuste)
        - month_of_receipt: Mês de recebimento
        - amount_received_related_to_interest: Valor recebido referente a juros
        - number_of_months: Número de meses
        - tax_due_rra: Imposto devido RRA
        - dependent_cpf: CPF do dependente
        """
        payer_name = match.group(1).strip()
        cnpj = match.group(2)
        
        if self._should_skip_line(payer_name):
            return None
        
        # Verificar se o nome continua na próxima linha
        payer_name = self._get_full_payer_name(payer_name, lines, idx)
        
        item_id = generate_item_id(f"dep_{cnpj}{payer_name}")
        
        # Extrair metadados adicionais das linhas seguintes
        number_of_months = None
        tax_option = None
        tax_due_rra = None
        month_of_receipt = None
        amount_received_related_to_interest = None
        dependent_cpf = None
        exempt_portion_65_years = None
        feeding = None
        
        for j in range(idx + 1, min(idx + 8, len(lines))):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            # Extrair opção de tributação
            option_match = re.search(r"OPÇÃO DE TRIBUTAÇÃO:\s*(\w+)", next_line, re.IGNORECASE)
            if option_match:
                tax_option = option_match.group(1)
            
            # Extrair mês de recebimento
            month_match = re.search(r"MÊS\s+(\w+\.?)", next_line, re.IGNORECASE)
            if month_match:
                month_of_receipt = month_match.group(1)
            
            # Extrair valor recebido referente a juros
            interest_match = re.search(r"Valor Recebido[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if interest_match:
                amount_received_related_to_interest = parse_currency(interest_match.group(1))
            
            # Extrair número de meses
            months_match = re.search(r"(?:NÚM\.?\s*MESES|MESES)[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if months_match:
                number_of_months = parse_currency(months_match.group(1))
            
            # Imposto devido RRA
            rra_match = re.search(r"IMPOSTO DEVIDO RRA[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if rra_match:
                tax_due_rra = parse_currency(rra_match.group(1))
            
            # CPF do dependente
            cpf_dep_match = re.search(r"CPF DO DEPENDENTE[:\s]*([\d.-]+)", next_line, re.IGNORECASE)
            if cpf_dep_match:
                dependent_cpf = cpf_dep_match.group(1)
            
            # Parar se encontrar início de outro item ou seção
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+\s+\d{2}\.\d{3}\.\d{3}", next_line):
                break
            if upper_next.startswith("TOTAL"):
                break
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
        
        result = {
            "payer_name": payer_name,
            "cpf_cnpj": cnpj,
            "taxable_income_total": parse_currency(match.group(3)),
            "official_social_security_contribution": parse_currency(match.group(4)),
            "alimony": parse_currency(match.group(5)),
            "tax_withheld_at_source": parse_currency(match.group(6)),
            "id": item_id,
            "page": page_num
        }
        
        # Adicionar campos opcionais
        if tax_option is not None:
            result["tax_option"] = tax_option
        if month_of_receipt is not None:
            result["month_of_receipt"] = month_of_receipt
        if amount_received_related_to_interest is not None:
            result["amount_received_related_to_interest"] = amount_received_related_to_interest
        if number_of_months is not None:
            result["number_of_months"] = number_of_months
        if tax_due_rra is not None:
            result["tax_due_rra"] = tax_due_rra
        if dependent_cpf is not None:
            result["dependent_cpf"] = dependent_cpf
        
        # Campos que podem ser null no gabarito
        result["exempt_portion_65_years"] = exempt_portion_65_years
        result["feeding"] = feeding
        
        return result
    
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
        
        payer_name = self._get_full_payer_name(payer_name, lines, idx)
        
        item_id = generate_item_id(f"dep_{cnpj}{payer_name}")
        
        # Extrair metadados
        number_of_months = None
        tax_option = None
        tax_due_rra = None
        month_of_receipt = None
        amount_received_related_to_interest = None
        dependent_cpf = None
        
        for j in range(idx + 1, min(idx + 8, len(lines))):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            option_match = re.search(r"OPÇÃO DE TRIBUTAÇÃO:\s*(\w+)", next_line, re.IGNORECASE)
            if option_match:
                tax_option = option_match.group(1)
            
            month_match = re.search(r"MÊS\s+(\w+\.?)", next_line, re.IGNORECASE)
            if month_match:
                month_of_receipt = month_match.group(1)
            
            interest_match = re.search(r"Valor Recebido[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if interest_match:
                amount_received_related_to_interest = parse_currency(interest_match.group(1))
            
            months_match = re.search(r"(?:NÚM\.?\s*MESES|MESES)[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if months_match:
                number_of_months = parse_currency(months_match.group(1))
            
            rra_match = re.search(r"IMPOSTO DEVIDO RRA[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if rra_match:
                tax_due_rra = parse_currency(rra_match.group(1))
            
            cpf_dep_match = re.search(r"CPF DO DEPENDENTE[:\s]*([\d.-]+)", next_line, re.IGNORECASE)
            if cpf_dep_match:
                dependent_cpf = cpf_dep_match.group(1)
            
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+\s+\d{2}\.\d{3}\.\d{3}", next_line):
                break
            if upper_next.startswith("TOTAL"):
                break
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
        
        result = {
            "payer_name": payer_name,
            "cpf_cnpj": cnpj,
            "taxable_income_total": parse_currency(match.group(3)),
            "official_social_security_contribution": parse_currency(match.group(4)),
            "tax_withheld_at_source": parse_currency(match.group(5)),
            "id": item_id,
            "page": page_num
        }
        
        if tax_option is not None:
            result["tax_option"] = tax_option
        if month_of_receipt is not None:
            result["month_of_receipt"] = month_of_receipt
        if amount_received_related_to_interest is not None:
            result["amount_received_related_to_interest"] = amount_received_related_to_interest
        if number_of_months is not None:
            result["number_of_months"] = number_of_months
        if tax_due_rra is not None:
            result["tax_due_rra"] = tax_due_rra
        if dependent_cpf is not None:
            result["dependent_cpf"] = dependent_cpf
        
        result["exempt_portion_65_years"] = None
        result["feeding"] = None
        
        return result
    
    def _get_full_payer_name(self, initial_name: str, lines: list[str], idx: int) -> str:
        """Concatena nome do pagador que pode estar em múltiplas linhas.
        
        Ex: Linha 7: "GOVERNO DO ESTADO DO 04.572.100/0001-43 ..."
            Linha 8: "AMAZONAS"
        Resultado: "GOVERNO DO ESTADO DO AMAZONAS"
        """
        full_name = initial_name
        
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            
            # É continuação se:
            # - Não contém CNPJ
            # - Não contém valores numéricos típicos (XX.XXX,XX)
            # - Não é uma linha de metadados (OPÇÃO, MÊS, etc)
            # - É texto em maiúsculas curto (nome do estado, etc)
            if (
                not re.search(r"\d{2}\.\d{3}\.\d{3}", next_line) and
                not re.search(r"\d+[.,]\d{3}[.,]\d{2}", next_line) and
                not re.search(r"(OPÇÃO|MÊS|RECEBIMENTO|IMPOSTO|TOTAL|CPF DO)", next_line.upper()) and
                re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]*$", next_line) and
                len(next_line) <= 30
            ):
                full_name = f"{initial_name} {next_line}"
        
        return full_name
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "REND.", "MESES", "CÓDIGO", "FONTE PAGADORA"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        """Calcula totais e valida contra os totais do PDF."""
        pdf_totals = pdf_totals or []
        
        sum_income = round(sum(i.get("taxable_income_total", 0) for i in items), 2)
        sum_contrib = round(sum(i.get("official_social_security_contribution", 0) for i in items), 2)
        sum_alimony = round(sum(i.get("alimony", 0) for i in items), 2)
        sum_irrf = round(sum(i.get("tax_withheld_at_source", 0) for i in items), 2)
        
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_contrib = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_alimony = pdf_totals[2] if len(pdf_totals) > 2 else None
        pdf_irrf = pdf_totals[3] if len(pdf_totals) > 3 else None
        
        return {
            "taxable_income_total": create_validated_total(sum_income, pdf_income),
            "official_social_security_contribution": create_validated_total(sum_contrib, pdf_contrib),
            "alimony": create_validated_total(sum_alimony, pdf_alimony),
            "tax_withheld_at_source": create_validated_total(sum_irrf, pdf_irrf)
        }
