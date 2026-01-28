"""Extrator de bens da atividade rural."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id, sum_currency_values
from ...validation_utils import extract_section_total, create_validated_total


class RuralAssetsExtractor(ISectionExtractor):
    """Extrai bens da atividade rural."""
    
    SECTION_MARKER = "BENS DA ATIVIDADE RURAL"
    
    @property
    def section_name(self) -> str:
        return "rural_activity_assets_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    SECTION_END_MARKERS = [
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL",
        "BENS DA ATIVIDADE RURAL - EXTERIOR",
        "DEMONSTRATIVO DE ATIVIDADE RURAL - EXTERIOR"
    ]
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_totals = []  # Totais extraídos do PDF
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            if self.SECTION_MARKER in upper_text and "BRASIL" in upper_text and "EXTERIOR" not in upper_text:
                in_section = True
            
            if in_section:
                # Encontrar posição do marcador de fim (se existir nesta página)
                end_line_index = self._find_end_marker_line(page_text)
                
                # Processar itens até o marcador de fim (ou toda a página se não houver)
                page_items = self._extract_from_page(page_text, page_num, end_line_index)
                items.extend(page_items)
                
                # Extrair total do PDF APENAS dentro da seção
                if not pdf_totals:
                    page_totals = self._extract_section_total(page_text, end_line_index)
                    if page_totals:
                        pdf_totals = page_totals
                
                # Se encontrou marcador de fim, parar após processar esta página
                if end_line_index is not None:
                    break
        
        if not items:
            return None
        
        # Somar valores extraídos
        sum_before = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        
        # Totais do PDF (se disponíveis)
        pdf_before = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_last = pdf_totals[1] if len(pdf_totals) > 1 else None
        
        totals = {
            "year_before_last_value": create_validated_total(sum_before, pdf_before),
            "last_year_value": create_validated_total(sum_last, pdf_last)
        }
        
        return {
            "section_name": "Bens da Atividade Rural - Brasil",
            "items": items,
            "total_values": totals
        }
    
    def _find_end_marker_line(self, page_text: str) -> Optional[int]:
        """Encontra o índice da linha onde aparece um marcador de fim de seção.
        
        Returns:
            Índice da linha do marcador, ou None se não houver marcador na página.
        """
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            for marker in self.SECTION_END_MARKERS:
                if marker in line:
                    return i
        return None
    
    def _extract_from_page(
        self, 
        page_text: str, 
        page_num: int, 
        end_line_index: Optional[int] = None
    ) -> list[dict]:
        """Extrai itens de uma página.
        
        Args:
            page_text: Texto da página.
            page_num: Número da página.
            end_line_index: Índice da linha onde parar a extração (opcional).
                           Se fornecido, extrai apenas até esta linha.
        """
        items = []
        lines = page_text.split("\n")
        
        # Limitar extração até o marcador de fim, se especificado
        max_line = end_line_index if end_line_index is not None else len(lines)
        
        i = 0
        while i < max_line:
            line = lines[i].strip()
            
            pattern = re.match(
                r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if pattern and "CÓDIGO" not in line.upper() and "TOTAL" not in line.upper():
                item = self._parse_asset(pattern, lines, i, page_num, max_line)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
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
        """Parse um item de bem da atividade rural.
        
        Args:
            match: Match do regex com os grupos capturados.
            lines: Lista de linhas da página.
            idx: Índice da linha atual.
            page_num: Número da página.
            max_line: Linha máxima para coletar descrição (boundary).
        """
        code = match.group(1)
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        
        # NOTA: Removido uso de _get_prefix_lines() pois linhas anteriores
        # pertencem ao item anterior, não ao atual. A descrição sempre
        # começa na linha principal do item e continua nas linhas seguintes.
        # O método foi mantido para possível uso futuro em casos especiais.
        desc_parts = [desc_start]
        j = idx + 1
        
        # Respeitar limite de linha se especificado
        line_limit = max_line if max_line is not None else len(lines)
        
        while j < line_limit:
            next_line = lines[j].strip()
            
            if "TOTAL" in next_line.upper():
                break
            
            is_new_item = re.match(r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$", next_line)
            if is_new_item and "CÓDIGO" not in next_line.upper():
                break
            
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+$", next_line):
                desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"^\d{2}/\d{2}/\d{4}\s+\d{2}/\d{2}/\d{4}\s*", "", full_desc)
        full_desc = re.sub(r"^\d{2}/\d{2}/\d{4}\s*", "", full_desc)
        full_desc = re.sub(r"^\d{4}/\d{4}\s+", "", full_desc)
        full_desc = re.sub(r"^CHASSI\s+[A-Z0-9]+\s*", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"^[A-Z0-9]{15,}\s+", "", full_desc)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        normalized_desc = self._normalize_description(full_desc)
        item_id = generate_item_id(f"{code}{normalized_desc[:30]}")
        
        return {
            "code": code,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _get_prefix_lines(self, lines: list[str], idx: int) -> list[str]:
        prefix_parts = []
        k = idx - 1
        while k >= 0:
            prev_line = lines[k].strip()
            
            if not prev_line:
                break
            
            if re.match(r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$", prev_line):
                break
            
            if re.match(r"^[\d.,]+\s+[\d.,]+\s*$", prev_line):
                break
            
            if "TOTAL" in prev_line.upper() or "CÓDIGO" in prev_line.upper():
                break
            
            if re.match(r"^Página\s+\d+\s+de", prev_line, re.IGNORECASE):
                break
            
            if re.match(r"^BENS DA ATIVIDADE RURAL", prev_line.upper()):
                break
            
            if self._is_description_fragment(prev_line):
                prefix_parts.insert(0, prev_line)
                k -= 1
            else:
                break
        
        return prefix_parts
    
    def _is_description_fragment(self, line: str) -> bool:
        if re.match(r"^\d+$", line):
            return False
        
        if re.match(r"^[\d.,]+$", line):
            return False
        
        if len(line) < 3:
            return False
        
        if re.match(r"^\d{2}/\d{2}/\d{4}", line):
            return False
        
        if re.match(r"^\d{4}/\d{4}\s", line):
            return False
        
        if re.match(r"^[A-Z0-9]{10,}\s", line):
            return False
        
        if re.match(r"^CHASSI\s+", line.upper()):
            return False
        
        if re.match(r"^ADQ\.\s+EM", line.upper()):
            return False
        
        header_patterns = [
            r"^NOME\s*:",
            r"^CPF\s*:",
            r"IMPOSTO\s+SOBRE",
            r"DECLARAÇÃO\s+DE",
            r"EXERCÍCIO\s+\d{4}",
            r"ANO-CALENDÁRIO",
        ]
        for pattern in header_patterns:
            if re.search(pattern, line.upper()):
                return False
        
        return True
    
    def _normalize_description(self, desc: str) -> str:
        normalized = re.sub(r"\s+", " ", desc)
        return normalized.strip()
    
    def _extract_section_total(self, page_text: str, end_line_index: Optional[int] = None) -> list[float]:
        """Extrai o TOTAL específico da seção de Bens Rurais.
        
        Busca a linha TOTAL apenas APÓS encontrar o marcador da seção
        e ANTES do marcador de fim (se existir).
        """
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:\.[\d]{3})*,[\d]{2})'
        
        # Limitar busca até o marcador de fim
        max_line = end_line_index if end_line_index is not None else len(lines)
        
        for i, line in enumerate(lines):
            if i >= max_line:
                break
                
            upper_line = line.upper()
            
            # Entrar na seção
            if self.SECTION_MARKER in upper_line and "BRASIL" in upper_line and "EXTERIOR" not in upper_line:
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Encontrar linha de TOTAL dentro da seção
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
