"""Extrator de rendimentos com exigibilidade suspensa - Dependentes."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import create_validated_total


class IncomeSuspendedDependentsExtractor(ISectionExtractor):
    """Extrai rendimentos tributáveis de PJ com imposto de exigibilidade suspensa - Dependentes (BUG #81775).
    
    Baseado em IncomeSuspendedHolderExtractor (titular), adaptado para dependentes.
    """
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA JURIDICA PELOS DEPENDENTES (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        "PELOS DEPENDENTES (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        # Markers parciais para headers quebrados em múltiplas linhas
        "PELOS DEPENDENTES (IMPOSTO COM",  # Quando "EXIGIBILIDADE SUSPENSA)" está na próxima linha
    ]
    
    # Marker para validar que é a seção de DEPENDENTES com EXIGIBILIDADE SUSPENSA
    DEPENDENTS_MARKER = "DEPENDENTES"
    SUSPENDED_MARKER = "EXIGIBILIDADE SUSPENSA"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE",
        "RENDIMENTOS TRIBUTAVEIS DE PESSOA JURIDICA RECEBIDOS ACUMULADAMENTE",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS",
    ]
    
    @property
    def section_name(self) -> str:
        return "income_from_legal_person_to_dependents_with_suspended_requirements"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        """Verifica se a seção está presente no documento.
        
        Lida com headers que podem estar quebrados em múltiplas linhas.
        """
        # Verificar markers completos primeiro
        upper_text = context.full_text.upper()
        for marker in self.SECTION_MARKERS:
            if marker in upper_text:
                # Se o marker inclui "EXIGIBILIDADE SUSPENSA" ou "DEPENDENTES", é válido
                if "EXIGIBILIDADE SUSPENSA" in marker or "(IMPOSTO COM" in marker:
                    return True
        
        # Verificar se existe a seção com header quebrado em múltiplas linhas
        for page_text in context.pages_text.values():
            lines = page_text.split("\n")
            for i, line in enumerate(lines):
                upper_line = line.upper()
                # Detectar "PELOS DEPENDENTES (IMPOSTO COM" seguido de "EXIGIBILIDADE SUSPENSA)"
                if "PELOS DEPENDENTES (IMPOSTO COM" in upper_line and "PELO TITULAR" not in upper_line:
                    # Verificar se EXIGIBILIDADE SUSPENSA está na mesma linha ou próxima
                    if "EXIGIBILIDADE SUSPENSA" in upper_line:
                        return True
                    if i + 1 < len(lines) and "EXIGIBILIDADE SUSPENSA" in lines[i + 1].upper():
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
            
            # Entrar na seção - detectar headers que podem estar quebrados
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
            
            # Verificar se a seção começa nesta página
            section_starts_here = self._is_section_start(page_text)
            already_in_section = in_section and not section_starts_here
            
            # Extrair itens
            page_items = self._extract_from_page(page_text, page_num, seen_ids, already_in_section)
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
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Jurídica pelos Dependentes (Imposto com Exigibilidade Suspensa)",
            "items": items,
            "total_values": totals
        }
    
    def _is_section_start(self, page_text: str) -> bool:
        """Verifica se esta página contém o início da seção de dependentes com exigibilidade suspensa.
        
        Lida com headers quebrados em múltiplas linhas.
        """
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Verificar markers completos
            for marker in self.SECTION_MARKERS:
                if marker in upper_line:
                    if "DEPENDENTES" in marker and "PELO TITULAR" not in upper_line:
                        return True
            
            # Detectar header quebrado em múltiplas linhas
            if "PELOS DEPENDENTES (IMPOSTO COM" in upper_line and "PELO TITULAR" not in upper_line:
                # Verificar se EXIGIBILIDADE SUSPENSA está na mesma linha
                if self.SUSPENDED_MARKER in upper_line:
                    return True
                # Verificar na próxima linha
                if i + 1 < len(lines) and self.SUSPENDED_MARKER in lines[i + 1].upper():
                    return True
        
        return False
    
    def _is_section_end(self, page_text: str) -> bool:
        """Verifica se a página marca o fim da seção."""
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
        """Extrai itens de rendimentos com exigibilidade suspensa de uma página.
        
        Args:
            page_text: Texto da página
            page_num: Número da página
            seen_ids: Set de IDs já vistos (para evitar duplicatas)
            already_in_section: Se True, considera que já estamos dentro da seção
        """
        items = []
        lines = page_text.split("\n")
        
        in_section = already_in_section
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início da seção (headers podem estar quebrados)
            if not in_section:
                # Verificar markers completos
                for marker in self.SECTION_MARKERS:
                    if marker in upper_line:
                        if "DEPENDENTES" in marker and "PELO TITULAR" not in upper_line:
                            in_section = True
                            continue
                
                # Detectar header quebrado
                if "PELOS DEPENDENTES (IMPOSTO COM" in upper_line and "PELO TITULAR" not in upper_line:
                    if self.SUSPENDED_MARKER in upper_line:
                        in_section = True
                    elif i + 1 < len(lines) and self.SUSPENDED_MARKER in lines[i + 1].upper():
                        in_section = True
                continue
            
            # Detectar fim
            if in_section:
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                    continue
            
            # Pular linhas de header e continuação
            if self.SUSPENDED_MARKER in upper_line and ")" in upper_line:
                continue
            if "(VALORES EM REAIS)" in upper_line:
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
        """Tenta parsear uma linha de rendimento com exigibilidade suspensa."""
        
        # Padrão: NOME CNPJ RENDIMENTOS IMPOSTO
        pattern = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
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
            
            # Extrair CPF do dependente das linhas seguintes
            dependent_cpf = self._extract_dependent_cpf(lines, idx)
            
            item_id = generate_item_id(f"susp_dep_{cnpj_cpf}_{payer_name}")
            
            result = {
                "payer_name": payer_name,
                "cpf_cnpj": cnpj_cpf,
                "taxable_income_with_suspended_requirements": taxable_income,
                "court_deposits_of_the_tax": suspended_tax,
                "id": item_id,
                "page": page_num
            }
            
            if dependent_cpf:
                result["dependent_cpf"] = dependent_cpf
            
            return result
        
        # Padrão alternativo: NOME + valores (CNPJ na próxima linha)
        pattern_alt = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s.,]+?)\s+"
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
            
            # Extrair CPF do dependente das linhas seguintes
            dependent_cpf = self._extract_dependent_cpf(lines, idx)
            
            item_id = generate_item_id(f"susp_dep_{cnpj_cpf}_{payer_name}")
            
            result = {
                "payer_name": payer_name,
                "cpf_cnpj": cnpj_cpf,
                "taxable_income_with_suspended_requirements": taxable_income,
                "court_deposits_of_the_tax": suspended_tax,
                "id": item_id,
                "page": page_num
            }
            
            if dependent_cpf:
                result["dependent_cpf"] = dependent_cpf
            
            return result
        
        return None
    
    def _extract_dependent_cpf(self, lines: list[str], idx: int) -> Optional[str]:
        """Extrai o CPF do dependente das linhas seguintes.
        
        Formato: "CPF DO DEPENDENTE: 303.216.120-78"
        """
        for j in range(idx + 1, min(idx + 5, len(lines))):
            next_line = lines[j].strip()
            
            # Parar se encontrar outro item ou seção
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+\s+\d{2}\.\d{3}\.\d{3}", next_line):
                break
            if next_line.upper().startswith("TOTAL"):
                break
            if any(marker in next_line.upper() for marker in self.SECTION_END_MARKERS):
                break
            
            # Extrair CPF do dependente
            cpf_match = re.search(r"CPF DO DEPENDENTE[:\s]*([\d.-]+)", next_line, re.IGNORECASE)
            if cpf_match:
                return cpf_match.group(1)
        
        return None
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "RENDIMENTOS", "IMPOSTO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _extract_section_total(self, page_text: str) -> list[float]:
        """Extrai o TOTAL específico da seção."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        
        for line in lines:
            upper_line = line.upper()
            
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                if self.DEPENDENTS_MARKER in upper_line:
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
        
        sum_income = round(sum(i.get("taxable_income_with_suspended_requirements", 0) for i in items), 2)
        sum_tax = round(sum(i.get("court_deposits_of_the_tax", 0) for i in items), 2)
        
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_tax = pdf_totals[1] if len(pdf_totals) > 1 else None
        
        return {
            "taxable_income_with_suspended_requirements": create_validated_total(sum_income, pdf_income),
            "court_deposits_of_the_tax": create_validated_total(sum_tax, pdf_tax)
        }
