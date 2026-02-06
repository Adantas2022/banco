"""Extrator de rendimentos tributaveis de PJ recebidos acumuladamente pelo titular."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import extract_section_total, create_validated_total


class AccumulatedIncomePJExtractor(ISectionExtractor):
    """Extrai rendimentos tributaveis de PJ recebidos acumuladamente pelo titular."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE PELO TITULAR",
        "RENDIMENTOS TRIBUTÁVEIS DE PJ RECEBIDOS ACUMULADAMENTE PELO TITULAR",
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE",
        # Markers parciais para títulos quebrados em múltiplas linhas
        "RECEBIDOS ACUMULADAMENTE PELO TITULAR",
        "ACUMULADAMENTE PELO TITULAR",
    ]
    HOLDER_MARKER = "PELO TITULAR"
    # Markers que indicam seção de dependentes (não do titular)
    DEPENDENTS_MARKERS = ["PELOS DEPENDENTES", "DEPENDENTES"]
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS"
    ]
    
    @property
    def section_name(self) -> str:
        return "accumulated_income_from_legal_person_to_holder"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        # Verificar se há marker do titular
        has_marker = any(marker in upper_text for marker in self.SECTION_MARKERS)
        if not has_marker:
            return False
        # Verificar se PELO TITULAR existe (para distinguir de DEPENDENTES)
        return self.HOLDER_MARKER in upper_text
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []  # Totais extraídos do PDF
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Entrar na seção - verificar se é seção do TITULAR
            if not in_section:
                # Verificar markers completos primeiro
                for marker in self.SECTION_MARKERS:
                    if marker in upper_page:
                        # Verificar se este marker é do titular e não dos dependentes
                        # Encontrar posição do marker e verificar contexto próximo
                        marker_pos = upper_page.find(marker)
                        context_around = upper_page[max(0, marker_pos-50):marker_pos+len(marker)+50]
                        
                        # Se "PELO TITULAR" está no marker ou próximo, é a seção correta
                        if self.HOLDER_MARKER in marker or self.HOLDER_MARKER in context_around:
                            # Verificar se NÃO está imediatamente seguido de "DEPENDENTES"
                            if "PELOS DEPENDENTES" not in context_around:
                                in_section = True
                                break
                        # Se é marker parcial sem "DEPENDENTES"
                        elif "DEPENDENTES" not in marker and "DEPENDENTES" not in context_around:
                            in_section = True
                            break
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # BUG FIX: Verificar se esta página é da seção de DEPENDENTES
            # O título pode estar quebrado em múltiplas linhas
            if self._is_dependents_section(upper_page):
                section_ended = True
                break
            
            # Extrair itens e total da seção
            page_items, section_totals = self._extract_from_page_with_totals(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Usar total da seção (não o primeiro TOTAL da página)
            if not pdf_totals and section_totals:
                pdf_totals = section_totals
            
            # Verificar fim após extração
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
        if not items:
            return None
        
        totals = self._calculate_totals(items, pdf_totals)
        
        return {
            "section_name": "Rendimentos Tributáveis de Pessoa Jurídica Recebidos Acumuladamente pelo Titular",
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
    
    def _is_dependents_section(self, upper_text: str) -> bool:
        """Verifica se o texto contém a seção de DEPENDENTES.
        
        BUG FIX: O título pode estar quebrado em múltiplas linhas:
        - "RECEBIDOS ACUMULADAMENTE PELOS (Valores em Reais)"
        - "DEPENDENTES"
        
        Detecta tanto o marker completo quanto o padrão quebrado.
        """
        # Marker completo
        if "RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES" in upper_text:
            return True
        
        # Padrão quebrado: "ACUMULADAMENTE PELOS" seguido de "DEPENDENTES" em linhas próximas
        lines = upper_text.split("\n")
        for i, line in enumerate(lines):
            if "ACUMULADAMENTE PELOS" in line and "PELO TITULAR" not in line:
                # Verificar se "DEPENDENTES" aparece nas próximas 3 linhas
                for j in range(1, 4):
                    if i + j < len(lines):
                        next_line = lines[i + j].strip()
                        if next_line.startswith("DEPENDENTES"):
                            return True
        
        return False
    
    def _extract_from_page_with_totals(self, page_text: str, page_num: int, seen_ids: set) -> tuple[list[dict], list[float]]:
        """Extrai itens e totais de uma página.
        
        Returns:
            Tuple com (lista de itens, lista de totais da seção)
        """
        items = []
        section_totals = []
        lines = page_text.split("\n")
        
        in_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início da seção
            if not in_section:
                for marker in self.SECTION_MARKERS:
                    if marker in upper_line:
                        # Verificar se é do TITULAR e não DEPENDENTES
                        if self.HOLDER_MARKER in upper_line or self.HOLDER_MARKER in marker:
                            if "PELOS DEPENDENTES" not in upper_line:
                                in_section = True
                                break
                        elif "DEPENDENTES" not in upper_line:
                            in_section = True
                            break
                if not in_section:
                    continue
            
            # Detectar fim da seção
            if in_section:
                # Se encontrar seção de DEPENDENTES, parar
                if "RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES" in upper_line:
                    break
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line:
                    continue
            
            # Capturar TOTAL da seção (apenas quando estamos dentro da seção)
            if in_section and upper_line.strip().startswith("TOTAL"):
                totals = self._parse_total_line(line)
                if totals:
                    section_totals = totals
                continue
            
            # Tentar parsear item
            item = self._try_parse_income_line(line, lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
        
        return items, section_totals
    
    def _parse_total_line(self, line: str) -> list[float]:
        """Extrai valores numéricos de uma linha TOTAL.
        
        Formato esperado: TOTAL 46.000,00 3.000,00 0,00 4.000,00
        """
        # Encontrar todos os valores numéricos no formato brasileiro
        pattern = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
        matches = re.findall(pattern, line)
        
        if matches:
            return [parse_currency(m) for m in matches]
        
        return []
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set, already_in_section: bool = False) -> list[dict]:
        """Extrai itens de uma página (sem totais).
        
        Args:
            page_text: Texto da página
            page_num: Número da página
            seen_ids: Set de IDs já vistos
            already_in_section: Se True, considera que já estamos na seção
        """
        items, _ = self._extract_from_page_with_totals(page_text, page_num, seen_ids)
        return items
    
    def _try_parse_income_line(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        # Formato 1: NOME CNPJ VALORES (CNPJ inline) - MAIS COMUM
        # Ex: "CAIXA ECONOMICA FEDERAL 00.360.305/0001-04 674.716,23 0,00 0,00 20.241"
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
        
        # Formato 2: NOME CNPJ 3 VALORES (sem despesas judiciais)
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
        
        # Formato 4 (legado): 3 valores
        pattern_alt = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s+"
            r"([\d]+[.,][\d]+[.,]?\d*)\s*$",
            line.strip()
        )
        
        if pattern_alt:
            return self._parse_3_values(pattern_alt, lines, idx, page_num)
        
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
        """
        payer_name = match.group(1).strip()
        cnpj = match.group(2)
        
        if self._should_skip_line(payer_name):
            return None
        
        # Verificar se o nome continua na próxima linha (ex: "GOVERNO DO ESTATO DE MINAS" + "GERAIS")
        payer_name = self._get_full_payer_name(payer_name, lines, idx)
        
        item_id = generate_item_id(f"{cnpj}{payer_name}")
        
        # Extrair metadados adicionais das linhas seguintes
        number_of_months = None
        tax_option = None
        tax_due_rra = None
        month_of_receipt = None
        amount_received_related_to_interest = None
        
        for j in range(idx + 1, min(idx + 6, len(lines))):
            next_line = lines[j].strip()
            
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
            
            # Parar se encontrar início de outro item ou seção
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+\s+\d{2}\.\d{3}\.\d{3}", next_line):
                break
            if next_line.upper().startswith("TOTAL"):
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
        
        # Adicionar campos opcionais (incluindo valores 0.0)
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
        
        return result
    
    def _get_full_payer_name(self, initial_name: str, lines: list[str], idx: int) -> str:
        """Concatena nome do pagador que pode estar em múltiplas linhas.
        
        Ex: Linha 38: "GOVERNO DO ESTATO DE MINAS 58.538.174/0001-92 ..."
            Linha 39: "GERAIS"
        Resultado: "GOVERNO DO ESTATO DE MINAS GERAIS"
        """
        full_name = initial_name
        
        # Verificar próxima linha
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
                not re.search(r"(OPÇÃO|MÊS|RECEBIMENTO|IMPOSTO|TOTAL)", next_line.upper()) and
                re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]*$", next_line) and
                len(next_line) <= 30
            ):
                full_name = f"{initial_name} {next_line}"
        
        return full_name
    
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
        
        # Verificar se o nome continua na próxima linha
        payer_name = self._get_full_payer_name(payer_name, lines, idx)
        
        item_id = generate_item_id(f"{cnpj}{payer_name}")
        
        return {
            "payer_name": payer_name,
            "cpf_cnpj": cnpj,
            "taxable_income_total": parse_currency(match.group(3)),
            "official_social_security_contribution": parse_currency(match.group(4)),
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
        payer_name_start = match.group(1).strip()
        
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = ""
        number_of_months = None
        
        for j in range(idx + 1, min(idx + 8, len(lines))):
            next_line = lines[j].strip()
            
            cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", next_line)
            if cnpj_match:
                cnpj = cnpj_match.group(1)
            
            months_match = re.search(r"Meses[:\s]*([\d.,]+)", next_line, re.IGNORECASE)
            if months_match:
                number_of_months = parse_currency(months_match.group(1))
            
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
            "taxable_income_total": parse_currency(match.group(2)),
            "official_social_security_contribution": parse_currency(match.group(3)),
            "tax_withheld_at_source": parse_currency(match.group(4)),
            "judicial_expenses": parse_currency(match.group(5)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
        
        if number_of_months is not None:
            result["number_of_months"] = number_of_months
        
        return result
    
    def _parse_3_values(
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
        item_id = generate_item_id(f"{cnpj}{full_name}")
        
        return {
            "payer_name": full_name,
            "taxable_income_total": parse_currency(match.group(2)),
            "tax_withheld_at_source": parse_currency(match.group(3)),
            "judicial_expenses": parse_currency(match.group(4)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
    
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
        """Calcula totais e valida contra os totais do PDF.
        
        Args:
            items: Lista de itens extraídos
            pdf_totals: Lista de totais do PDF [rend_acum, contrib_prev, pensao, irrf]
            
        Ordem dos totais no PDF (linha TOTAL):
        TOTAL RENDIMENTOS | CONTR. PREV. OFICIAL | PENSÃO ALIMENTÍCIA | IMPOSTO RETIDO NA FONTE
        """
        pdf_totals = pdf_totals or []
        
        # Somar valores extraídos
        sum_income = round(sum(i.get("taxable_income_total", 0) for i in items), 2)
        sum_contrib = round(sum(i.get("official_social_security_contribution", 0) for i in items), 2)
        sum_alimony = round(sum(i.get("alimony", 0) for i in items), 2)
        sum_irrf = round(sum(i.get("tax_withheld_at_source", 0) for i in items), 2)
        sum_judicial = round(sum(i.get("judicial_expenses", 0) for i in items), 2)
        
        # Totais do PDF (se disponíveis) - ordem: REND, CONTRIB, PENSAO, IRRF
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_contrib = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_alimony = pdf_totals[2] if len(pdf_totals) > 2 else None
        pdf_irrf = pdf_totals[3] if len(pdf_totals) > 3 else None
        
        totals = {
            "taxable_income_total": create_validated_total(sum_income, pdf_income),
            "official_social_security_contribution": create_validated_total(sum_contrib, pdf_contrib),
            "alimony": create_validated_total(sum_alimony, pdf_alimony),
            "tax_withheld_at_source": create_validated_total(sum_irrf, pdf_irrf)
        }
        
        if any("judicial_expenses" in i for i in items):
            totals["judicial_expenses"] = create_validated_total(sum_judicial, None)
        
        return totals
