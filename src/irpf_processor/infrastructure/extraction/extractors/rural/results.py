"""Extrator de apuração de resultado rural."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralResultsExtractor(ISectionExtractor):
    """Extrai apuração do resultado da atividade rural - BRASIL.
    
    BUG #81762 fix: Usar marcadores específicos para Brasil e ignorar
    seções de Exterior para evitar fusão incorreta de dados.
    """
    
    # Marcadores específicos para BRASIL (ordem de precedência)
    SECTION_MARKERS_BRAZIL = [
        "APURAÇÃO DO RESULTADO DA ATIVIDADE RURAL NO BRASIL",
        "APURACAO DO RESULTADO DA ATIVIDADE RURAL NO BRASIL",  # OCR
        "APURAÇÃO DO RESULTADO - BRASIL",
        "APURACAO DO RESULTADO - BRASIL",
        "APURAÇÃO DO RESULTADO NO BRASIL",
        "APURACAO DO RESULTADO NO BRASIL",
    ]
    
    # Marcadores genéricos (usar apenas se não encontrar específico)
    SECTION_MARKER_GENERIC = "APURAÇÃO DO RESULTADO"
    
    # Marcadores de EXTERIOR - para EXCLUIR desta extração
    SECTION_MARKERS_ABROAD = [
        "APURAÇÃO DO RESULTADO DA ATIVIDADE RURAL NO EXTERIOR",
        "APURACAO DO RESULTADO DA ATIVIDADE RURAL NO EXTERIOR",
        "APURAÇÃO DO RESULTADO - EXTERIOR",
        "APURACAO DO RESULTADO - EXTERIOR",
        "APURAÇÃO DO RESULTADO NO EXTERIOR",
        "APURACAO DO RESULTADO NO EXTERIOR",
        "EXTERIOR",  # Marcador de seção no início da página
    ]
    
    SUBSECTION_MARKERS = {
        "previous_exercise_info": "INFORMAÇÃO DO EXERCÍCIO ANTERIOR",
        "calculation_of_taxable_result": "APURAÇÃO DO RESULTADO TRIBUTÁVEL",
        "next_exercise_info": "INFORMAÇÕES PARA O EXERCÍCIO SEGUINTE",
        "calculation_of_exempt_result": "APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL"
    }
    
    # BUG #81762 fix: Marcadores que indicam FIM da seção de Apuração do Resultado
    # Quando encontrar esses marcadores, parar de processar linhas
    SECTION_END_MARKERS = [
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "BENS DA ATIVIDADE RURAL",
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL",
        "DIVIDAS VINCULADAS A ATIVIDADE RURAL",
        "DÍVIDAS VINCULADAS A ATIVIDADE RURAL",
    ]
    
    @property
    def section_name(self) -> str:
        return "calculation_of_rural_results_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        # Verificar se há marcador Brasil específico ou genérico
        has_brazil = any(m in upper_text for m in self.SECTION_MARKERS_BRAZIL)
        has_generic = self.SECTION_MARKER_GENERIC in upper_text
        return has_brazil or has_generic
    
    def _is_abroad_section(self, page_text: str) -> bool:
        """Verifica se a página pertence à seção de EXTERIOR.
        
        BUG #81762 fix: Detectar páginas de Exterior para excluí-las.
        """
        upper_text = page_text.upper()
        
        # Verificar marcadores explícitos de exterior
        for marker in self.SECTION_MARKERS_ABROAD:
            if marker in upper_text:
                return True
        
        # Verificar se "EXTERIOR" aparece próximo de "APURAÇÃO DO RESULTADO"
        if "EXTERIOR" in upper_text and "APURAÇÃO DO RESULTADO" in upper_text:
            # Verificar contexto - se "EXTERIOR" está perto do marcador
            lines = page_text.split("\n")
            for i, line in enumerate(lines):
                upper_line = line.upper().strip()
                if "EXTERIOR" in upper_line:
                    # Verificar linhas próximas
                    context_lines = lines[max(0, i-3):min(len(lines), i+3)]
                    context_text = " ".join(l.upper() for l in context_lines)
                    if "APURAÇÃO" in context_text or "RESULTADO" in context_text:
                        return True
        
        return False
    
    def _is_brazil_section(self, page_text: str) -> bool:
        """Verifica se a página pertence à seção de BRASIL.
        
        BUG #81762 fix: Confirmar que é seção Brasil e não Exterior.
        """
        upper_text = page_text.upper()
        
        # Se tem marcador explícito de Brasil, é Brasil
        for marker in self.SECTION_MARKERS_BRAZIL:
            if marker in upper_text:
                return True
        
        # Se tem marcador genérico MAS NÃO tem marcador de Exterior
        if self.SECTION_MARKER_GENERIC in upper_text:
            return not self._is_abroad_section(page_text)
        
        return False
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        subsections = {}
        
        for page_num, page_text in sorted(context.pages_text.items()):
            upper_text = page_text.upper()
            
            # BUG #81762 fix: Ignorar páginas de seção EXTERIOR
            if self._is_abroad_section(page_text):
                continue
            
            # Verificar se é página de Brasil
            if not self._is_brazil_section(page_text):
                # Verificar se tem marcador genérico (fallback)
                if self.SECTION_MARKER_GENERIC not in upper_text:
                    continue
            
            page_subsections = self._extract_from_page(page_text, page_num)
            subsections.update(page_subsections)
        
        if not subsections:
            return None
        
        return {
            "section_name": "Apuração do Resultado - Brasil",
            "subsections": subsections
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> dict:
        subsections = {}
        lines = page_text.split("\n")
        
        section_items = {key: [] for key in self.SUBSECTION_MARKERS}
        current_section = None
        
        for line in lines:
            upper = line.strip().upper()
            
            # BUG #81762 fix: Verificar se chegamos ao fim da seção de Apuração
            # Se encontrar marcador de fim, parar de processar esta página
            if any(end_marker in upper for end_marker in self.SECTION_END_MARKERS):
                # Chegamos em outra seção (ex: MOVIMENTAÇÃO DO REBANHO)
                # Parar de processar linhas desta página para esta seção
                current_section = None
                break  # Parar completamente o processamento desta página
            
            # Check if line is a section marker (must start with the marker, not just contain it)
            is_marker = False
            for key, marker in self.SUBSECTION_MARKERS.items():
                if upper.startswith(marker) or upper == marker:
                    current_section = key
                    is_marker = True
                    break
            
            if not is_marker:
                if current_section and not line.strip().startswith("Página"):
                    item = self._parse_result_line(line)
                    if item:
                        section_items[current_section].append(item)
        
        for key, items in section_items.items():
            if items:
                subsections[key] = {
                    "subsection_name": self.SUBSECTION_MARKERS[key],
                    "items": items,
                    "page": page_num
                }
        
        return subsections
    
    def _parse_result_line(self, line: str) -> Optional[dict]:
        line_stripped = line.strip()
        
        # Fallback específico para "Pelo resultado" (case-insensitive)
        if re.search(r"pelo\s+resultado", line_stripped, re.IGNORECASE):
            description = re.sub(r"\s*pelo\s+resultado\s*$", "", line_stripped, flags=re.IGNORECASE).strip()
            if description and len(description) >= 5:
                return {
                    "description": description,
                    "value": "Pelo resultado",
                    "id": generate_item_id(description)
                }
        
        pattern = re.match(r"^(.+?)\s+(-?[\d.,-]+)\s*$", line_stripped)
        
        if not pattern:
            return None
        
        description = pattern.group(1).strip()
        value_str = pattern.group(2).strip()
        
        if not description or len(description) < 5:
            return None
        
        value = parse_currency(value_str)
        if description == "Resultado":
            value = abs(value)
        
        return {
            "description": description,
            "value": value,
            "id": generate_item_id(description)
        }
