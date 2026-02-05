"""Extrator de imóveis rurais explorados - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralPropertiesAbroadExtractor(ISectionExtractor):
    """Extrai dados de imóveis rurais explorados - Exterior (BUG #81768)."""
    
    SECTION_MARKERS = [
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - EXTERIOR",
        "DADOS E IDENTIFICACAO DO IMOVEL EXPLORADO - EXTERIOR",
        "IMÓVEL EXPLORADO - EXTERIOR",
        "IMOVEL EXPLORADO - EXTERIOR",
    ]
    
    SECTION_END_MARKERS = [
        "RECEITAS E DESPESAS",
        "APURAÇÃO DO RESULTADO",
        "APURACAO DO RESULTADO",
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "BENS DA ATIVIDADE",
        "DÍVIDAS VINCULADAS",
        "DIVIDAS VINCULADAS",
    ]
    
    @property
    def section_name(self) -> str:
        return "exploited_rural_properties_abroad"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        
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
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)
            
            # Verificar fim
            for marker in self.SECTION_END_MARKERS:
                if marker in upper_page:
                    section_ended = True
                    break
        
        if not items:
            return None
        
        return {
            "section_name": "Dados e Identificação do Imóvel Explorado - Exterior",
            "items": items
        }
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        i = 0
        
        while i < len(lines):
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
            
            # Detectar fim
            for marker in self.SECTION_END_MARKERS:
                if marker in upper_line:
                    return items
            
            if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                i += 1
                continue
            
            # Pular cabeçalho
            if "CÓDIGO" in upper_line or "CODIGO" in upper_line or "ATIVIDADE" in upper_line:
                i += 1
                continue
            
            # Tentar parsear propriedade
            item = self._try_parse_property(lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
                i = item.pop("_next_index", i + 1)
                continue
            
            i += 1
        
        return items
    
    def _try_parse_property(
        self, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Tenta parsear uma propriedade rural no exterior.
        
        Formato esperado:
        CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME E LOCALIZAÇÃO ÁREA
        11     100,00       5        FINCA N. 858...    4.066,0
        """
        line = lines[idx].strip()
        
        # Padrão: CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME ÁREA
        # Ex: "11 100,00 5 FINCA N. 858 CORRALITO, CAPITAN BADO, 4.066,0"
        pattern = re.match(
            r"^(\d{2})\s+([\d.,]+)\s+(\d+)\s+(.+?)\s+([\d.,]+)\s*$",
            line
        )
        
        if pattern:
            activity_code = pattern.group(1)
            participation = self._parse_number(pattern.group(2))
            exploitation_condition = pattern.group(3)
            name_location = pattern.group(4).strip()
            area = self._parse_number(pattern.group(5))
            
            # Capturar nome multi-linha
            j = idx + 1
            while j < len(lines):
                next_line = lines[j].strip()
                upper_next = next_line.upper()
                
                # Parar se encontrar outro item ou fim
                if re.match(r"^\d{2}\s+[\d.,]+\s+\d+\s+", next_line):
                    break
                
                for marker in self.SECTION_END_MARKERS:
                    if marker in upper_next:
                        break
                else:
                    # Se não for valor ou cabeçalho, adicionar ao nome
                    if next_line and not re.match(r"^[\d.,]+$", next_line):
                        if not any(kw in upper_next for kw in ["CÓDIGO", "ATIVIDADE", "PÁGINA"]):
                            name_location = f"{name_location} {next_line}"
                    j += 1
                    continue
                break
            
            item_id = generate_item_id(f"prop_abroad_{activity_code}_{name_location[:30]}")
            
            return {
                "id": item_id,
                "activity_code": activity_code,
                "participation_percentage": participation,
                "exploitation_condition": exploitation_condition,
                "name_and_location": name_location,
                "area_hectares": area,
                "page": page_num,
                "_next_index": j
            }
        
        # Padrão alternativo sem área no final (área em linha separada)
        pattern_alt = re.match(
            r"^(\d{2})\s+([\d.,]+)\s+(\d+)\s+(.+)$",
            line
        )
        
        if pattern_alt:
            activity_code = pattern_alt.group(1)
            participation = self._parse_number(pattern_alt.group(2))
            exploitation_condition = pattern_alt.group(3)
            name_start = pattern_alt.group(4).strip()
            
            # Buscar área e nome nas linhas seguintes
            name_parts = [name_start]
            area = 0.0
            j = idx + 1
            
            while j < len(lines):
                next_line = lines[j].strip()
                upper_next = next_line.upper()
                
                # Parar se encontrar outro item
                if re.match(r"^\d{2}\s+[\d.,]+\s+\d+\s+", next_line):
                    break
                
                for marker in self.SECTION_END_MARKERS:
                    if marker in upper_next:
                        break
                else:
                    # Verificar se é apenas área
                    area_match = re.match(r"^([\d.,]+)\s*$", next_line)
                    if area_match:
                        area = self._parse_number(area_match.group(1))
                        j += 1
                        break
                    
                    # Adicionar ao nome
                    if next_line and not any(kw in upper_next for kw in ["CÓDIGO", "ATIVIDADE", "PÁGINA"]):
                        name_parts.append(next_line)
                    j += 1
                    continue
                break
            
            full_name = " ".join(name_parts)
            
            # Se último elemento do nome parece ser área, extrair
            words = full_name.split()
            if words and re.match(r"^[\d.,]+$", words[-1]):
                area = self._parse_number(words[-1])
                full_name = " ".join(words[:-1])
            
            if area == 0.0:
                return None
            
            item_id = generate_item_id(f"prop_abroad_{activity_code}_{full_name[:30]}")
            
            return {
                "id": item_id,
                "activity_code": activity_code,
                "participation_percentage": participation,
                "exploitation_condition": exploitation_condition,
                "name_and_location": full_name,
                "area_hectares": area,
                "page": page_num,
                "_next_index": j
            }
        
        return None
    
    def _parse_number(self, value: str) -> float:
        """Parseia número com formato brasileiro."""
        try:
            clean_value = value.replace(".", "").replace(",", ".")
            return float(clean_value)
        except (ValueError, AttributeError):
            return 0.0
