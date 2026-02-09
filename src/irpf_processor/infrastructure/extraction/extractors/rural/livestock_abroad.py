"""Extrator de movimentacao do rebanho - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id
from ...validation_utils import create_validated_total


class LivestockMovementAbroadExtractor(ISectionExtractor):
    """Extrai movimentacao do rebanho - Exterior (BUG #81781)."""
    
    SECTION_MARKERS = [
        "MOVIMENTAÇÃO DO REBANHO - EXTERIOR",
        "MOVIMENTACAO DO REBANHO - EXTERIOR",
        "MOVIMENTAGAO DO REBANHO - EXTERIOR",  # OCR: Ç -> G
    ]
    
    SECTION_END_MARKERS = [
        "BENS DA ATIVIDADE RURAL",
        "DÍVIDAS VINCULADAS",
        "DIVIDAS VINCULADAS",
        "DEMONSTRATIVO",
        "RESUMO TRIBUTAÇÃO",
        "RESUMO TRIBUTACAO",
        "PÁGINA",
        "PAGINA",
    ]
    
    @property
    def section_name(self) -> str:
        return "livestock_movement_abroad"
    
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
            
            # Extrair total do PDF
            if not pdf_totals:
                page_totals = self._extract_section_total(page_text)
                if page_totals:
                    pdf_totals = page_totals
            
            # Verificar fim após extração
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
        if not items:
            return None
        
        totals = self._calculate_totals(items, pdf_totals)
        
        return {
            "section_name": "Movimentação do Rebanho - Exterior",
            "items": items,
            "total_values": totals
        }
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        """Verifica se a página marca o fim definitivo da seção."""
        lines = page_text.split("\n")
        in_section = False
        
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            
            # Entrar na seção primeiro
            if any(marker in stripped for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Verificar fim
            for marker in self.SECTION_END_MARKERS:
                if stripped.startswith(marker):
                    return True
        
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if in_section:
                # Detectar fim
                for marker in self.SECTION_END_MARKERS:
                    if upper_line.strip().startswith(marker):
                        return items
                
                if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
                    continue
                
                # Pular cabeçalho
                if "ESPÉCIE" in upper_line or "ESPECIE" in upper_line:
                    continue
            
            if not in_section:
                continue
            
            # Tentar parsear linha
            item = self._try_parse_livestock_line(line, lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
        
        return items
    
    def _try_parse_livestock_line(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Tenta parsear uma linha de movimentação do rebanho."""
        
        # Normalizar linha
        line = re.sub(r'(\d)\s+,', r'\1,', line.strip())
        
        # Padrão: Espécie VALOR1 VALOR2 VALOR3 VALOR4 VALOR5 VALOR6
        # Ex: "Bovinos e bufalinos 14.819,00 0,00 3.341,00 180,00 3.469,00 14.511,00"
        pattern = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line
        )
        
        if pattern:
            species = pattern.group(1).strip()
            
            if self._should_skip_line(species):
                return None
            
            # Verificar se próxima linha é continuação do nome da espécie
            # Ex: "Asininos, equinos" + "e muares"
            if idx + 1 < len(lines):
                next_line = lines[idx + 1].strip()
                if next_line and not re.match(r'^[\d.,]+', next_line) and not self._should_skip_line(next_line):
                    # Se a próxima linha não começa com número e não é cabeçalho/total,
                    # é continuação do nome da espécie
                    if re.match(r'^[a-záàâãéêíóôõúç]', next_line, re.IGNORECASE) and len(next_line) < 30:
                        species = f"{species} {next_line}"
            
            code = self._get_species_code(species)
            item_id = generate_item_id(f"livestock_abroad_{species}")
            
            return {
                "id": item_id,
                "code": code,
                "species": species,
                "initial_stock": self._parse_number(pattern.group(2)),
                "acquisitions": self._parse_number(pattern.group(3)),
                "births": self._parse_number(pattern.group(4)),
                "consumption_and_losses": self._parse_number(pattern.group(5)),
                "sales": self._parse_number(pattern.group(6)),
                "final_stock": self._parse_number(pattern.group(7)),
                "page": page_num
            }
        
        # Padrão multi-linha: espécie em linha anterior (ex: "e muares" continuação)
        # Capturar linhas com 6 valores apenas
        pattern_values = re.match(
            r"^([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line
        )
        
        if pattern_values and idx > 0:
            # Buscar espécie na linha anterior
            prev_line = lines[idx - 1].strip()
            if prev_line and not re.match(r"^[\d.,]+", prev_line):
                species = prev_line
                if self._should_skip_line(species):
                    return None
                
                code = self._get_species_code(species)
                item_id = generate_item_id(f"livestock_abroad_{species}")
                
                return {
                    "id": item_id,
                    "code": code,
                    "species": species,
                    "initial_stock": self._parse_number(pattern_values.group(1)),
                    "acquisitions": self._parse_number(pattern_values.group(2)),
                    "births": self._parse_number(pattern_values.group(3)),
                    "consumption_and_losses": self._parse_number(pattern_values.group(4)),
                    "sales": self._parse_number(pattern_values.group(5)),
                    "final_stock": self._parse_number(pattern_values.group(6)),
                    "page": page_num
                }
        
        return None
    
    def _get_species_code(self, species: str) -> str:
        """Retorna código padrão baseado no nome da espécie."""
        species_upper = species.upper()
        codes = {
            "BOVINOS": "01",
            "BUFALINOS": "01",
            "SUINOS": "02",
            "SUÍNOS": "02",
            "CAPRINOS": "03",
            "OVINOS": "03",
            "ASININOS": "04",
            "EQUINOS": "04",
            "MUARES": "04",
            "AVES": "05",
            "OUTROS": "99",
        }
        
        for key, code in codes.items():
            if key in species_upper:
                return code
        return "99"
    
    def _parse_number(self, value: str) -> float:
        return parse_currency(value)
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CÓDIGO", "ESPÉCIE", "QUANTIDADE", "NASCIMENTO", "ESTOQUE", "PÁGINA"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        """Calcula totais e valida contra os totais do PDF."""
        pdf_totals = pdf_totals or []
        
        sum_initial = sum(i.get("initial_stock", 0) for i in items)
        sum_acquisitions = sum(i.get("acquisitions", 0) for i in items)
        sum_births = sum(i.get("births", 0) for i in items)
        sum_losses = sum(i.get("consumption_and_losses", 0) for i in items)
        sum_sales = sum(i.get("sales", 0) for i in items)
        sum_final = sum(i.get("final_stock", 0) for i in items)
        
        pdf_initial = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_acquisitions = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_births = pdf_totals[2] if len(pdf_totals) > 2 else None
        pdf_losses = pdf_totals[3] if len(pdf_totals) > 3 else None
        pdf_sales = pdf_totals[4] if len(pdf_totals) > 4 else None
        pdf_final = pdf_totals[5] if len(pdf_totals) > 5 else None
        
        return {
            "initial_stock": create_validated_total(sum_initial, pdf_initial),
            "acquisitions": create_validated_total(sum_acquisitions, pdf_acquisitions),
            "births": create_validated_total(sum_births, pdf_births),
            "consumption_and_losses": create_validated_total(sum_losses, pdf_losses),
            "sales": create_validated_total(sum_sales, pdf_sales),
            "final_stock": create_validated_total(sum_final, pdf_final)
        }
    
    def _extract_section_total(self, page_text: str) -> list[float]:
        """Extrai o TOTAL específico da seção."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        
        for line in lines:
            upper_line = line.upper()
            
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            for end in self.SECTION_END_MARKERS:
                if upper_line.strip().startswith(end):
                    return []
            
            if upper_line.strip().startswith("TOTAL"):
                matches = re.findall(num_pattern, line)
                if matches:
                    return [self._parse_number(m) for m in matches]
        
        return []
