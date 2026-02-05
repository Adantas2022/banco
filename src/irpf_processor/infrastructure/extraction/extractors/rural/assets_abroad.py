"""Extrator de bens da atividade rural - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id, sum_currency_values
from ...validation_utils import extract_section_total, create_validated_total


class RuralAssetsAbroadExtractor(ISectionExtractor):
    """Extrai bens da atividade rural - Exterior (BUG #81783).
    
    Baseado em RuralAssetsExtractor (Brasil), adaptado para Exterior.
    """
    
    SECTION_MARKERS = [
        "BENS DA ATIVIDADE RURAL - EXTERIOR",
        "BENS DA ATIVIDADE RURAL – EXTERIOR",
        "BENS DA ATIVIDADE RURAL EXTERIOR",
    ]
    
    SECTION_END_MARKERS = [
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR",
        "DIVIDAS VINCULADAS A ATIVIDADE RURAL - EXTERIOR",
        "DEMONSTRATIVO DE ATIVIDADE RURAL",
        "DEMONSTRATIVO DE RECEITAS E DESPESAS",
        "RESULTADO DA ATIVIDADE RURAL",
    ]
    
    @property
    def section_name(self) -> str:
        return "rural_activity_assets_abroad"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_totals = []
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            # Entrar na seção
            if any(marker in upper_text for marker in self.SECTION_MARKERS):
                in_section = True
            
            if not in_section:
                continue
            
            # Verificar "Sem Informações"
            if "SEM INFORMAÇÕES" in upper_text or "SEM INFORMACOES" in upper_text:
                lines = page_text.split("\n")
                for i, line in enumerate(lines):
                    if any(marker in line.upper() for marker in self.SECTION_MARKERS):
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].upper()
                            if "SEM INFORMAÇÕES" in next_line or "SEM INFORMACOES" in next_line:
                                return None
            
            # Encontrar onde começa a seção nesta página
            section_start_line = self._find_section_start_line(page_text)
            
            # Se a seção NÃO começa nesta página, considerar que já estamos dentro
            already_in_section = section_start_line is None and in_section
            
            start_after = section_start_line if section_start_line is not None else 0
            
            # Encontrar limite de extração (só end markers DEPOIS do início)
            end_line_index = self._find_end_marker_line(page_text, start_after)
            
            # Extrair itens
            page_items = self._extract_from_page(
                page_text, page_num, end_line_index, already_in_section
            )
            items.extend(page_items)
            
            # Extrair total
            if not pdf_totals:
                page_totals = self._extract_section_total(page_text, end_line_index)
                if page_totals:
                    pdf_totals = page_totals
            
            # Parar após marcador de fim
            if end_line_index is not None:
                break
        
        if not items:
            return None
        
        # Somar valores extraídos
        sum_before = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        
        pdf_before = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_last = pdf_totals[1] if len(pdf_totals) > 1 else None
        
        totals = {
            "year_before_last_value": create_validated_total(sum_before, pdf_before),
            "last_year_value": create_validated_total(sum_last, pdf_last)
        }
        
        return {
            "section_name": "Bens da Atividade Rural - Exterior",
            "items": items,
            "total_values": totals
        }
    
    def _find_section_start_line(self, page_text: str) -> Optional[int]:
        """Encontra o índice da linha onde começa a seção."""
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            upper_line = line.upper()
            for marker in self.SECTION_MARKERS:
                if marker in upper_line:
                    return i
        return None
    
    def _find_end_marker_line(self, page_text: str, start_after: int = 0) -> Optional[int]:
        """Encontra o índice da linha onde aparece um marcador de fim de seção.
        
        Args:
            page_text: Texto da página
            start_after: Só considerar end markers que aparecem DEPOIS desta linha
        """
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            # Só considerar linhas depois do início da seção
            if i <= start_after:
                continue
            upper_line = line.upper()
            for marker in self.SECTION_END_MARKERS:
                if marker in upper_line:
                    return i
        return None
    
    def _extract_from_page(
        self, 
        page_text: str, 
        page_num: int, 
        end_line_index: Optional[int] = None,
        already_in_section: bool = False
    ) -> list[dict]:
        """Extrai itens de uma página.
        
        Args:
            page_text: Texto da página
            page_num: Número da página
            end_line_index: Índice da linha onde termina a seção (opcional)
            already_in_section: Se True, considera que já estamos dentro da seção
                               (útil quando o header está na página anterior)
        """
        items = []
        lines = page_text.split("\n")
        
        max_line = end_line_index if end_line_index is not None else len(lines)
        
        in_section = already_in_section
        i = 0
        while i < max_line:
            line = lines[i].strip()
            upper_line = line.upper()
            
            # Detectar início da seção
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                i += 1
                continue
            
            if not in_section:
                i += 1
                continue
            
            # Padrão 1: CÓDIGO DESCRIÇÃO VALOR_ANT VALOR_ATUAL
            # Ex: "16 TRATORES NO EXTERIOR 149 CANADÁ 200.000,00 190.000,00"
            pattern = re.match(
                r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if pattern and "CÓDIGO" not in upper_line and "TOTAL" not in upper_line:
                item = self._parse_asset(pattern, lines, i, page_num, max_line)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            # Padrão 2: CÓDIGO DESCRIÇÃO em linhas separadas dos valores
            # BUG FIX: Alguns PDFs têm valores em linhas separadas
            pattern_alt = re.match(r"^(\d{1,3})\s+(.+)$", line)
            if pattern_alt and "CÓDIGO" not in upper_line and "TOTAL" not in upper_line:
                code = pattern_alt.group(1)
                desc = pattern_alt.group(2).strip()
                
                # Verificar se a próxima linha tem os valores
                if i + 1 < max_line:
                    next_line = lines[i + 1].strip()
                    values_match = re.match(r"^([\d.,]+)\s+([\d.,]+)\s*$", next_line)
                    if values_match:
                        before_val = parse_currency(values_match.group(1))
                        current_val = parse_currency(values_match.group(2))
                        
                        item_id = generate_item_id(f"abroad_{code}{desc[:30]}")
                        item = {
                            "code": code,
                            "description": desc,
                            "year_before_last_value": before_val,
                            "last_year_value": current_val,
                            "id": item_id,
                            "page": page_num,
                        }
                        items.append(item)
                        i += 2
                        continue
            
            i += 1
        
        return items
    
    def _parse_asset(
        self, 
        match: re.Match, 
        lines: list[str], 
        idx: int,
        page_num: int,
        max_line: Optional[int] = None
    ) -> dict:
        """Parse um item de bem da atividade rural - Exterior."""
        code = match.group(1)
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        
        desc_parts = [desc_start]
        j = idx + 1
        
        line_limit = max_line if max_line is not None else len(lines)
        
        while j < line_limit:
            next_line = lines[j].strip()
            
            if "TOTAL" in next_line.upper():
                break
            
            # Verificar se é novo item
            is_new_item = re.match(r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$", next_line)
            if is_new_item and "CÓDIGO" not in next_line.upper():
                break
            
            # Adicionar continuação de descrição
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+$", next_line):
                desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = self._clean_description(full_desc)
        
        normalized_desc = self._normalize_description(full_desc)
        item_id = generate_item_id(f"abroad_{code}{normalized_desc[:30]}")
        
        return {
            "code": code,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _clean_description(self, desc: str) -> str:
        """Limpa a descrição de padrões indesejados."""
        desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"^\d{2}/\d{2}/\d{4}\s+\d{2}/\d{2}/\d{4}\s*", "", desc)
        desc = re.sub(r"^\d{2}/\d{2}/\d{4}\s*", "", desc)
        desc = re.sub(r"^\d{4}/\d{4}\s+", "", desc)
        desc = re.sub(r"\s+", " ", desc).strip()
        return desc
    
    def _normalize_description(self, desc: str) -> str:
        normalized = re.sub(r"\s+", " ", desc)
        return normalized.strip()
    
    def _extract_section_total(self, page_text: str, end_line_index: Optional[int] = None) -> list[float]:
        """Extrai o TOTAL específico da seção."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})'
        
        max_line = end_line_index if end_line_index is not None else len(lines)
        
        for i, line in enumerate(lines):
            if i >= max_line:
                break
            
            upper_line = line.upper()
            
            # Entrar na seção
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Encontrar TOTAL dentro da seção
            if upper_line.strip().startswith("TOTAL"):
                matches = re.findall(num_pattern, line)
                if matches:
                    return [self._parse_currency(m) for m in matches]
        
        return []
    
    def _parse_currency(self, value_str: str) -> float:
        """Converte string de valor brasileiro para float."""
        if not value_str:
            return 0.0
        cleaned = value_str.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
