"""Extrator de apuração do resultado - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralResultsAbroadExtractor(ISectionExtractor):
    """Extrai apuração do resultado da atividade rural - Exterior (BUG #81770)."""
    
    SECTION_MARKERS = [
        "APURAÇÃO DO RESULTADO - EXTERIOR",
        "APURACAO DO RESULTADO - EXTERIOR",
        "APURAÇÃO DO RESULTADO DA ATIVIDADE RURAL - EXTERIOR",
        "APURACAO DO RESULTADO DA ATIVIDADE RURAL - EXTERIOR",
        "APURAÇÃO DO RESULTADO NO EXTERIOR",
        "APURACAO DO RESULTADO NO EXTERIOR",
    ]
    
    SECTION_END_MARKERS = [
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "BENS DA ATIVIDADE RURAL",
        "DÍVIDAS VINCULADAS",
        "DIVIDAS VINCULADAS",
        "DEMONSTRATIVO",
        "RESUMO TRIBUTAÇÃO",
        "RESUMO TRIBUTACAO",
    ]
    
    @property
    def section_name(self) -> str:
        return "calculation_of_rural_results_abroad"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        result = {}
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Verificar se a página tem a seção
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                page_result = self._extract_from_page(page_text, page_num)
                if page_result:
                    result.update(page_result)
                break
        
        if not result:
            return None
        
        return {
            "section_name": "Apuração do Resultado - Exterior",
            **result
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> Optional[dict]:
        """Extrai dados da página de apuração do resultado exterior."""
        result = {"page": page_num}
        lines = page_text.split("\n")
        
        in_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Detectar fim
            for marker in self.SECTION_END_MARKERS:
                if marker in upper_line:
                    return result if len(result) > 1 else None
            
            if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                continue
            
            # Extrair valores
            
            # Saldo de prejuízo(s) a compensar de exercício(s) anterior(es)
            if "SALDO DE PREJUÍZO" in upper_line and "ANTERIOR" in upper_line:
                match = re.search(r"R\$\s*([\d.,]+)", line)
                if match:
                    result["loss_from_previous_years"] = self._parse_currency(match.group(1))
            
            # Resultado total - US$
            if "RESULTADO TOTAL" in upper_line and "US$" in upper_line:
                match = re.search(r"US\$\s*([\d.,]+)", line)
                if match:
                    result["total_result_usd"] = self._parse_currency(match.group(1))
            
            # Resultado total - (R$)
            # Formato: "Resultado total - (R$) (Resultado total - US$ multiplicado por 6,1917) 10.601.841,97"
            # Precisamos pegar o ÚLTIMO valor numérico da linha
            if "RESULTADO TOTAL" in upper_line and "(R$)" in upper_line:
                # Buscar todos os valores na linha e pegar o último
                all_values = re.findall(r"([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})", line)
                if all_values:
                    result["total_result_brl"] = self._parse_currency(all_values[-1])
            
            # Opção pela forma de apuração
            if "OPÇÃO PELA FORMA" in upper_line or "OPCAO PELA FORMA" in upper_line:
                # Capturar o texto da opção
                if "20%" in line:
                    result["taxable_result_option"] = "Pelo limite de 20% sobre a receita bruta total"
                elif "ESCRITURAÇÃO" in upper_line:
                    result["taxable_result_option"] = "Pela escrituração do Livro Caixa"
                else:
                    result["taxable_result_option"] = line.strip()
            
            # Limite de 20% sobre a receita bruta total
            if "LIMITE DE 20%" in upper_line:
                match = re.search(r"R\$\s*([\d.,]+)", line)
                if match:
                    result["limit_20_percent"] = self._parse_currency(match.group(1))
            
            # Compensação de prejuízo(s) de exercício(s) anterior(es)
            if "COMPENSAÇÃO DE PREJUÍZO" in upper_line or "COMPENSACAO DE PREJUIZO" in upper_line:
                match = re.search(r"R\$\s*([\d.,]+)", line)
                if match:
                    result["compensation_previous_losses"] = self._parse_currency(match.group(1))
            
            # RESULTADO TRIBUTÁVEL
            if "RESULTADO TRIBUTÁVEL" in upper_line or "RESULTADO TRIBUTAVEL" in upper_line:
                if "NÃO" not in upper_line and "NAO" not in upper_line:
                    match = re.search(r"R\$\s*([\d.,]+)", line)
                    if match:
                        result["taxable_result"] = self._parse_currency(match.group(1))
            
            # Saldo de prejuízo(s) a compensar (para exercício seguinte)
            if "SALDO DE PREJUÍZO" in upper_line and "COMPENSAR" in upper_line:
                if "SEGUINTE" in upper_line or i > 0 and "SEGUINTE" in lines[i-1].upper():
                    match = re.search(r"R\$\s*([\d.,]+)", line)
                    if match:
                        result["loss_for_next_years"] = self._parse_currency(match.group(1))
            
            # Adiantamento(s) recebido(s)
            if "ADIANTAMENTO" in upper_line:
                match = re.search(r"R\$\s*([\d.,]+)", line)
                if match:
                    if "2024" in line or "CORRENTE" in upper_line:
                        result["advances_received_current_year"] = self._parse_currency(match.group(1))
                    elif "2023" in line or "ANTERIOR" in upper_line:
                        result["advances_from_previous_years"] = self._parse_currency(match.group(1))
            
            # RESULTADO NÃO TRIBUTÁVEL
            if "RESULTADO NÃO TRIBUTÁVEL" in upper_line or "RESULTADO NAO TRIBUTAVEL" in upper_line:
                match = re.search(r"R\$\s*([\d.,]+)", line)
                if match:
                    result["non_taxable_result"] = self._parse_currency(match.group(1))
        
        return result if len(result) > 1 else None
    
    def _parse_currency(self, value_str: str) -> float:
        """Converte string de valor brasileiro para float."""
        if not value_str:
            return 0.0
        cleaned = value_str.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
