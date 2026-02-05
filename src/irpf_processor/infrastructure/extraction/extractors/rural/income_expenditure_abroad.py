"""Extrator de receitas e despesas - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id
from ...validation_utils import create_validated_total


class RuralIncomeExpenditureAbroadExtractor(ISectionExtractor):
    """Extrai receitas e despesas da atividade rural - Exterior (BUG #81788)."""
    
    SECTION_MARKERS = [
        "RECEITAS E DESPESAS - EXTERIOR",
        "RECEITAS E DESPESAS NO EXTERIOR",
    ]
    
    SECTION_END_MARKERS = [
        "APURAÇÃO DO RESULTADO",
        "APURACAO DO RESULTADO",
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "BENS DA ATIVIDADE",
        "DÍVIDAS VINCULADAS",
        "DIVIDAS VINCULADAS",
        "DEMONSTRATIVO",
    ]
    
    @property
    def section_name(self) -> str:
        return "rural_income_and_expenditure_abroad"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_total_usd = None
        
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
            page_items, total = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            if total and pdf_total_usd is None:
                pdf_total_usd = total
            
            # Verificar fim
            for marker in self.SECTION_END_MARKERS:
                if marker in upper_page:
                    section_ended = True
                    break
        
        if not items:
            return None
        
        # Calcular total
        sum_result_usd = sum(i.get("result_usd", 0) for i in items)
        
        return {
            "section_name": "Receitas e Despesas - Exterior",
            "items": items,
            "total_values": {
                "result_usd": create_validated_total(sum_result_usd, pdf_total_usd)
            }
        }
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> tuple[list[dict], Optional[float]]:
        items = []
        total_usd = None
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
                    return items, total_usd
            
            if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                continue
            
            # Pular cabeçalho
            if "CÓDIGO" in upper_line or "CODIGO" in upper_line or "NOME DO PAÍS" in upper_line:
                continue
            
            # Extrair TOTAL
            if upper_line.strip().startswith("TOTAL"):
                total_match = re.search(r"([\d.,]+)\s*$", line)
                if total_match:
                    total_usd = self._parse_number(total_match.group(1))
                continue
            
            # Tentar parsear item
            item = self._try_parse_item(line, lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
        
        return items, total_usd
    
    def _try_parse_item(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Tenta parsear uma linha de receita/despesa exterior.
        
        Formato esperado:
        CÓDIGO   NOME DO PAÍS   RECEITA BRUTA   DESPESAS   RESULTADO   RESULTADO
        DO PAÍS                 TOTAL           CUSTEIO    MOEDA ORIG  US$
        586      PARAGUAI       17.198...       3.788...   13.409...   1.712.266,74
        """
        # Padrão: CÓD PAÍS RECEITA DESPESA RESULTADO_LOCAL RESULTADO_USD
        # Ex: "586 PARAGUAI 17.198.179.956,00 3.788.973.872,00 13.409.206.084,00 1.712.266,74"
        pattern = re.match(
            r"^(\d{3})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern:
            country_code = pattern.group(1)
            country_name = pattern.group(2).strip()
            gross_revenue = self._parse_number(pattern.group(3))
            expenses = self._parse_number(pattern.group(4))
            result_local = self._parse_number(pattern.group(5))
            result_usd = self._parse_number(pattern.group(6))
            
            item_id = generate_item_id(f"income_abroad_{country_code}_{country_name}")
            
            return {
                "id": item_id,
                "country_code": country_code,
                "country_name": country_name,
                "gross_revenue_local_currency": gross_revenue,
                "expenses_local_currency": expenses,
                "result_local_currency": result_local,
                "result_usd": result_usd,
                "page": page_num
            }
        
        # Padrão alternativo: apenas código + país + resultado USD (simplificado)
        pattern_simple = re.match(
            r"^(\d{3})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+?)\s+([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern_simple:
            country_code = pattern_simple.group(1)
            country_name = pattern_simple.group(2).strip()
            result_usd = self._parse_number(pattern_simple.group(3))
            
            item_id = generate_item_id(f"income_abroad_{country_code}_{country_name}")
            
            return {
                "id": item_id,
                "country_code": country_code,
                "country_name": country_name,
                "result_usd": result_usd,
                "page": page_num
            }
        
        return None
    
    def _parse_number(self, value: str) -> float:
        """Parseia número com formato brasileiro."""
        try:
            clean_value = value.replace(".", "").replace(",", ".")
            return float(clean_value)
        except (ValueError, AttributeError):
            return 0.0
