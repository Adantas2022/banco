"""Extrator de imóveis rurais explorados - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralPropertiesAbroadExtractor(ISectionExtractor):
    """Extrai dados de imóveis rurais explorados - Exterior.
    
    Estrutura esperada (conforme gabarito):
    {
        "section_name": "Dados e Identificação do Imóvel Explorado - Exterior",
        "items": [
            {
                "code": 10,
                "participation": 80.0,
                "exploration_condition": 2,
                "name_and_location": "AGRICULTURA NO EXTERIOR, ESTADOS UNIDOS",
                "area": 400.0,
                "participants": {
                    "items": [
                        {
                            "participant_name": "PARTICIPANTE (31.371.955/0001-89)",
                            "foreigner": true,
                            "id": "..."
                        }
                    ]
                },
                "id": "...",
                "page": 18
            }
        ]
    }
    """
    
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
        10     80,00       2        AGRICULTURA NO EXTERIOR, ESTADOS 400,0
        UNIDOS
        PARTICIPANTE(S)
        PARTICIPANTE (31.371.955/0001-89) Estrangeiro: Sim
        """
        line = lines[idx].strip()
        
        # Padrão: CÓDIGO PARTICIPAÇÃO CONDIÇÃO NOME ÁREA
        # Ex: "10 80,00 2 AGRICULTURA NO EXTERIOR, ESTADOS 400,0"
        pattern = re.match(
            r"^(\d{1,2})\s+([\d.,]+)\s+(\d+)\s+(.+?)\s+([\d.,]+)\s*$",
            line
        )
        
        if pattern:
            code = int(pattern.group(1))
            participation = self._parse_number(pattern.group(2))
            exploration_condition = int(pattern.group(3))
            name_location = pattern.group(4).strip()
            area = self._parse_number(pattern.group(5))
            
            # Capturar continuação do nome (até PARTICIPANTE(S))
            j = idx + 1
            while j < len(lines):
                next_line = lines[j].strip()
                upper_next = next_line.upper()
                
                # Parar se encontrar PARTICIPANTE(S)
                if "PARTICIPANTE" in upper_next:
                    break
                
                # Parar se encontrar outro item
                if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d+\s+", next_line):
                    break
                
                # Parar se encontrar fim de seção
                if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                    break
                
                # Adicionar ao nome se for texto válido
                if next_line and not re.match(r"^[\d.,]+$", next_line):
                    if not any(kw in upper_next for kw in ["CÓDIGO", "ATIVIDADE", "PÁGINA", "(HA)", "(%)"]):
                        name_location = f"{name_location} {next_line}"
                
                j += 1
            
            # Extrair participantes
            participants = self._extract_participants(lines, j)
            next_index = participants.pop("_next_index", j)
            
            item_id = generate_item_id(f"prop_abroad_{code}_{name_location[:30]}")
            
            result = {
                "code": code,
                "participation": participation,
                "exploration_condition": exploration_condition,
                "name_and_location": name_location,
                "area": area,
                "id": item_id,
                "page": page_num,
                "_next_index": next_index
            }
            
            # Adicionar participantes se existirem
            if participants.get("items"):
                result["participants"] = participants
            
            return result
        
        # Padrão alternativo sem área no final (área em linha separada)
        pattern_alt = re.match(
            r"^(\d{1,2})\s+([\d.,]+)\s+(\d+)\s+(.+)$",
            line
        )
        
        if pattern_alt:
            code = int(pattern_alt.group(1))
            participation = self._parse_number(pattern_alt.group(2))
            exploration_condition = int(pattern_alt.group(3))
            name_start = pattern_alt.group(4).strip()
            
            # Buscar área e nome nas linhas seguintes
            name_parts = [name_start]
            area = 0.0
            j = idx + 1
            
            while j < len(lines):
                next_line = lines[j].strip()
                upper_next = next_line.upper()
                
                # Parar se encontrar PARTICIPANTE(S)
                if "PARTICIPANTE" in upper_next:
                    break
                
                # Parar se encontrar outro item
                if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d+\s+", next_line):
                    break
                
                # Parar se encontrar fim de seção
                if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                    break
                
                # Verificar se é apenas área
                area_match = re.match(r"^([\d.,]+)\s*$", next_line)
                if area_match:
                    area = self._parse_number(area_match.group(1))
                    j += 1
                    break
                
                # Adicionar ao nome
                if next_line and not any(kw in upper_next for kw in ["CÓDIGO", "ATIVIDADE", "PÁGINA", "(HA)", "(%)"]):
                    name_parts.append(next_line)
                j += 1
            
            full_name = " ".join(name_parts)
            
            # Se último elemento do nome parece ser área, extrair
            words = full_name.split()
            if words and re.match(r"^[\d.,]+$", words[-1]):
                area = self._parse_number(words[-1])
                full_name = " ".join(words[:-1])
            
            if area == 0.0:
                return None
            
            # Extrair participantes
            participants = self._extract_participants(lines, j)
            next_index = participants.pop("_next_index", j)
            
            item_id = generate_item_id(f"prop_abroad_{code}_{full_name[:30]}")
            
            result = {
                "code": code,
                "participation": participation,
                "exploration_condition": exploration_condition,
                "name_and_location": full_name,
                "area": area,
                "id": item_id,
                "page": page_num,
                "_next_index": next_index
            }
            
            # Adicionar participantes se existirem
            if participants.get("items"):
                result["participants"] = participants
            
            return result
        
        return None
    
    def _extract_participants(self, lines: list[str], start_idx: int) -> dict:
        """Extrai participantes da propriedade.
        
        Formato:
        PARTICIPANTE(S)
        PARTICIPANTE (31.371.955/0001-89) Estrangeiro: Sim
        """
        participants_items = []
        j = start_idx
        in_participants = False
        
        while j < len(lines):
            line = lines[j].strip()
            upper_line = line.upper()
            
            # Detectar início da seção de participantes
            if upper_line == "PARTICIPANTE(S)" or upper_line == "PARTICIPANTES":
                in_participants = True
                j += 1
                continue
            
            if not in_participants:
                # Se encontramos linha de participante sem cabeçalho
                if "PARTICIPANTE" in upper_line and "ESTRANGEIRO" in upper_line:
                    in_participants = True
                else:
                    break
            
            # Parar se encontrar fim de seção ou novo item
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                break
            
            if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d+\s+", line):
                break
            
            # Parsear participante
            # Formato: "PARTICIPANTE (31.371.955/0001-89) Estrangeiro: Sim"
            participant_match = re.match(
                r"^(.+?)\s+Estrangeiro:\s*(Sim|Não|S|N)\s*$",
                line,
                re.IGNORECASE
            )
            
            if participant_match:
                participant_name = participant_match.group(1).strip()
                foreigner_str = participant_match.group(2).upper()
                foreigner = foreigner_str in ["SIM", "S"]
                
                participant_id = generate_item_id(f"participant_{participant_name}")
                
                participants_items.append({
                    "participant_name": participant_name,
                    "foreigner": foreigner,
                    "id": participant_id
                })
            
            j += 1
        
        return {
            "items": participants_items,
            "_next_index": j
        }
    
    def _parse_number(self, value: str) -> float:
        return parse_currency(value)
