"""Extrator de rendimentos com exigibilidade suspensa - Titular."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import create_validated_total


class IncomeSuspendedHolderExtractor(ISectionExtractor):
    """Extrai rendimentos tributáveis de PJ com imposto de exigibilidade suspensa - Titular (BUG #81776)."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA JURIDICA PELO TITULAR (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        "RENDIMENTOS TRIBUTÁVEIS DE PJ PELO TITULAR (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        "IMPOSTO COM EXIGIBILIDADE SUSPENSA",
        # Markers parciais para títulos quebrados em múltiplas linhas
        "PELO TITULAR (IMPOSTO COM",  # Início do título quebrado
        "EXIGIBILIDADE SUSPENSA)",  # Continuação do título
    ]
    
    HOLDER_MARKER = "PELO TITULAR"
    
    # Padrões que indicam início de seção quando encontrados juntos
    PARTIAL_MARKERS = [
        ("PELO TITULAR", "IMPOSTO COM"),
        ("IMPOSTO COM", "EXIGIBILIDADE SUSPENSA"),
    ]
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA JURIDICA PELOS DEPENDENTES",
        "PELOS DEPENDENTES (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE",
        "RENDIMENTOS TRIBUTAVEIS DE PESSOA JURIDICA RECEBIDOS ACUMULADAMENTE",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS",
    ]
    
    @property
    def section_name(self) -> str:
        return "income_from_legal_person_to_holder_with_suspended_requirements"
    
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
            
            # Entrar na seção - apenas TITULAR, não DEPENDENTES
            if not in_section:
                # Verificar markers completos
                if any(marker in upper_page for marker in self.SECTION_MARKERS):
                    if self.HOLDER_MARKER in upper_page and "PELOS DEPENDENTES" not in upper_page:
                        in_section = True
                
                # Verificar título quebrado em múltiplas linhas
                # Padrão: "PELO TITULAR (IMPOSTO COM" seguido de "EXIGIBILIDADE SUSPENSA)"
                if not in_section and self._has_holder_section_marker(upper_page):
                    in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # Verificar "Sem Informações"
            if "SEM INFORMAÇÕES" in upper_page or "SEM INFORMACOES" in upper_page:
                # Verificar se é específico para esta seção
                lines = page_text.split("\n")
                for i, line in enumerate(lines):
                    upper_line = line.upper()
                    if any(marker in upper_line for marker in self.SECTION_MARKERS):
                        if self.HOLDER_MARKER in upper_line:
                            # Verificar próxima linha
                            if i + 1 < len(lines):
                                next_line = lines[i + 1].upper()
                                if "SEM INFORMAÇÕES" in next_line or "SEM INFORMACOES" in next_line:
                                    return None
            
            # Extrair itens
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Extrair total
            if not pdf_totals:
                page_totals = self._extract_section_total(page_text)
                if page_totals:
                    pdf_totals = page_totals
            
            # Verificar fim
            if self._is_section_end(page_text):
                section_ended = True
        
        if not items:
            return None
        
        totals = self._calculate_totals(items, pdf_totals)
        
        return {
            "section_name": "Rendimentos Tributáveis de PJ pelo Titular (Imposto com Exigibilidade Suspensa)",
            "items": items,
            "total_values": totals
        }
    
    def _is_section_end(self, page_text: str) -> bool:
        """Verifica se a página marca o fim da seção."""
        upper_text = page_text.upper()
        for marker in self.SECTION_END_MARKERS:
            if marker in upper_text:
                return True
        return False
    
    def _has_holder_section_marker(self, upper_text: str) -> bool:
        """Detecta se o texto contém a seção de exigibilidade suspensa do TITULAR.
        
        BUG FIX: O título pode estar quebrado em múltiplas linhas:
        - "PELO TITULAR (IMPOSTO COM"
        - "EXIGIBILIDADE SUSPENSA)"
        
        Também verifica que NÃO é seção de dependentes.
        """
        # Se contém "PELOS DEPENDENTES", não é a seção do titular
        if "PELOS DEPENDENTES" in upper_text:
            # Verificar se há seção do titular ANTES da seção de dependentes
            holder_pos = upper_text.find("PELO TITULAR")
            dependents_pos = upper_text.find("PELOS DEPENDENTES")
            
            if holder_pos == -1 or holder_pos > dependents_pos:
                return False
        
        lines = upper_text.split("\n")
        for i, line in enumerate(lines):
            # Padrão 1: Título quebrado - "PELO TITULAR (IMPOSTO COM" em uma linha
            if "PELO TITULAR" in line and "(IMPOSTO COM" in line:
                # Verificar se é a seção correta (não dependentes)
                if "PELOS DEPENDENTES" not in line:
                    # Verificar se próxima linha tem "EXIGIBILIDADE SUSPENSA"
                    if i + 1 < len(lines):
                        next_line = lines[i + 1]
                        if "EXIGIBILIDADE SUSPENSA" in next_line:
                            return True
            
            # Padrão 2: Título completo em uma linha
            if "PELO TITULAR" in line and "EXIGIBILIDADE SUSPENSA" in line:
                if "PELOS DEPENDENTES" not in line:
                    return True
        
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início - apenas TITULAR (com suporte a título quebrado)
            if not in_section:
                # Padrão 1: Marker completo
                if any(marker in upper_line for marker in self.SECTION_MARKERS):
                    if self.HOLDER_MARKER in upper_line and "PELOS DEPENDENTES" not in upper_line:
                        in_section = True
                        continue
                
                # Padrão 2: Título quebrado - "PELO TITULAR (IMPOSTO COM" seguido de "EXIGIBILIDADE SUSPENSA"
                if "PELO TITULAR" in upper_line and "(IMPOSTO COM" in upper_line:
                    if "PELOS DEPENDENTES" not in upper_line:
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].upper()
                            if "EXIGIBILIDADE SUSPENSA" in next_line:
                                in_section = True
                                continue
            
            # Detectar fim
            if in_section:
                # Se encontrar seção de DEPENDENTES, parar
                if "PELOS DEPENDENTES" in upper_line and "EXIGIBILIDADE SUSPENSA" in upper_line:
                    break
                if "PELOS DEPENDENTES" in upper_line and "(IMPOSTO COM" in upper_line:
                    break
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
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
        """Tenta parsear uma linha de rendimento com exigibilidade suspensa.
        
        Formato esperado:
        NOME DA FONTE PAGADORA | CNPJ/CPF | RENDIMENTOS TRIBUTÁVEIS | IMPOSTO COM EXIGIBILIDADE SUSPENSA
        """
        # Padrão: NOME CNPJ RENDIMENTOS IMPOSTO
        # Ex: "EMPRESA ABC LTDA 12.345.678/0001-90 50.000,00 10.000,00"
        # BUG FIX: Incluir hífen no padrão do nome para capturar nomes como
        # "EMPREENDIMENTOS IMOBILIARIOS - EXIGIBILIDADE SUSPENSA"
        pattern = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,\-]+?)\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern:
            payer_name = pattern.group(1).strip()
            cnpj_cpf = pattern.group(2)
            taxable_income = parse_currency(pattern.group(3))
            suspended_tax = parse_currency(pattern.group(4))
            
            if self._should_skip_line(payer_name):
                return None
            
            item_id = generate_item_id(f"suspended_{cnpj_cpf}_{payer_name}")
            
            return {
                "id": item_id,
                "payer_name": payer_name,
                "cpf_cnpj": cnpj_cpf,
                "taxable_income": taxable_income,
                "tax_with_suspended_requirement": suspended_tax,
                "page": page_num
            }
        
        # Padrão alternativo: NOME + valores (CNPJ na próxima linha)
        pattern_alt = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,\-]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern_alt:
            payer_name = pattern_alt.group(1).strip()
            
            if self._should_skip_line(payer_name):
                return None
            
            taxable_income = parse_currency(pattern_alt.group(2))
            suspended_tax = parse_currency(pattern_alt.group(3))
            
            # Buscar CNPJ nas linhas seguintes
            cnpj_cpf = ""
            for j in range(idx + 1, min(idx + 5, len(lines))):
                next_line = lines[j].strip()
                cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})", next_line)
                if cnpj_match:
                    cnpj_cpf = cnpj_match.group(1)
                    break
            
            if not cnpj_cpf:
                return None
            
            item_id = generate_item_id(f"suspended_{cnpj_cpf}_{payer_name}")
            
            return {
                "id": item_id,
                "payer_name": payer_name,
                "cpf_cnpj": cnpj_cpf,
                "taxable_income": taxable_income,
                "tax_with_suspended_requirement": suspended_tax,
                "page": page_num
            }
        
        return None
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "RENDIMENTOS", "IMPOSTO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _extract_section_total(self, page_text: str) -> list[float]:
        """Extrai o TOTAL específico da seção."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})'
        
        for line in lines:
            upper_line = line.upper()
            
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                if self.HOLDER_MARKER in upper_line:
                    in_section = True
                continue
            
            if not in_section:
                continue
            
            if any(end in upper_line for end in self.SECTION_END_MARKERS):
                break
            
            if upper_line.strip().startswith("TOTAL"):
                matches = re.findall(num_pattern, line)
                if matches:
                    return [parse_currency(m) for m in matches]
        
        return []
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        """Calcula totais e valida contra os totais do PDF."""
        pdf_totals = pdf_totals or []
        
        sum_income = round(sum(i.get("taxable_income", 0) for i in items), 2)
        sum_tax = round(sum(i.get("tax_with_suspended_requirement", 0) for i in items), 2)
        
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_tax = pdf_totals[1] if len(pdf_totals) > 1 else None
        
        return {
            "taxable_income": create_validated_total(sum_income, pdf_income),
            "tax_with_suspended_requirement": create_validated_total(sum_tax, pdf_tax)
        }
