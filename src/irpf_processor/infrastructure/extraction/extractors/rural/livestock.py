"""Extrator de movimentacao do rebanho - Brasil."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id
from ...validation_utils import extract_section_total, create_validated_total


class LivestockMovementExtractor(ISectionExtractor):
    """Extrai movimentacao do rebanho - Brasil."""
    
    # Marcadores incluindo variações OCR comuns (ex: "Ç" pode virar "G" no OCR)
    SECTION_MARKERS = [
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "MOVIMENTAGAO DO REBANHO",  # OCR: Ç -> G
        "MOVIMENTO DO REBANHO"
    ]
    BRAZIL_MARKER = "BRASIL"
    
    SECTION_END_MARKERS = [
        "BENS DA ATIVIDADE",
        "DÍVIDAS E ÔNUS",
        "RECEITAS E DESPESAS",
        "RESULTADO DA ATIVIDADE",
        "CÁLCULO DO RESULTADO"
    ]
    
    @property
    def section_name(self) -> str:
        return "livestock_movement_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []  # Totais extraídos do PDF
        
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
            
            # Extrair total do PDF APENAS dentro da seção
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
            "section_name": "Movimentação do Rebanho - Brasil",
            "items": items,
            "total_values": totals
        }
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        """Verifica se a página marca o fim definitivo da seção."""
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue
            
            for marker in self.SECTION_END_MARKERS:
                if marker in stripped:
                    # Confirmar que é nova seção
                    next_lines = " ".join(lines[i+1:i+5]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
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
                if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line:
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
        
        # Normalizar linha para OCR (espaços antes da vírgula)
        line = re.sub(r'(\d)\s+,', r'\1,', line.strip())
        
        # Formato 1: Código Espécie Qtd_Inicial Aquisições Nascimentos Perdas Vendas Qtd_Final
        # ou: Código Espécie valores...
        
        # Padrão com código de 2 dígitos e 6 valores
        pattern = re.match(
            r"^(\d{2})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line
        )
        
        if pattern:
            code = pattern.group(1)
            species = pattern.group(2).strip()
            
            if self._should_skip_line(species):
                return None
            
            item_id = generate_item_id(f"livestock_{code}_{species}")
            
            return {
                "id": item_id,
                "code": code,
                "species": species,
                "initial_stock": self._parse_number(pattern.group(3)),
                "acquisitions": self._parse_number(pattern.group(4)),
                "births": self._parse_number(pattern.group(5)),
                "consumption_and_losses": self._parse_number(pattern.group(6)),
                "sales": self._parse_number(pattern.group(7)),
                "final_stock": self._parse_number(pattern.group(8)),
                "page": page_num
            }
        
        # NOVO: Padrão OCR SEM código - Espécie seguida de 6 valores
        # Ex: "Bovinos e bufalinos 6.621,00 23.415,00 239,00 152,00 22.986,00 7.137,00"
        pattern_no_code = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line
        )
        
        if pattern_no_code:
            species = pattern_no_code.group(1).strip()
            
            if self._should_skip_line(species):
                return None
            
            # Gerar código baseado no nome da espécie
            code = self._get_species_code(species)
            item_id = generate_item_id(f"livestock_{species}")
            
            return {
                "id": item_id,
                "code": code,
                "species": species,
                "initial_stock": self._parse_number(pattern_no_code.group(2)),
                "acquisitions": self._parse_number(pattern_no_code.group(3)),
                "births": self._parse_number(pattern_no_code.group(4)),
                "consumption_and_losses": self._parse_number(pattern_no_code.group(5)),
                "sales": self._parse_number(pattern_no_code.group(6)),
                "final_stock": self._parse_number(pattern_no_code.group(7)),
                "page": page_num
            }
        
        # Padrão com 5 números (sem final_stock, calculado)
        pattern_5 = re.match(
            r"^([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line
        )
        
        if pattern_5:
            species = pattern_5.group(1).strip()
            
            if self._should_skip_line(species):
                return None
            
            code = self._get_species_code(species)
            initial = self._parse_number(pattern_5.group(2))
            acquisitions = self._parse_number(pattern_5.group(3))
            births = self._parse_number(pattern_5.group(4))
            losses = self._parse_number(pattern_5.group(5))
            sales = self._parse_number(pattern_5.group(6))
            
            # Calcular estoque final
            final_stock = initial + acquisitions + births - losses - sales
            
            item_id = generate_item_id(f"livestock_{species}")
            
            return {
                "id": item_id,
                "code": code,
                "species": species,
                "initial_stock": initial,
                "acquisitions": acquisitions,
                "births": births,
                "consumption_and_losses": losses,
                "sales": sales,
                "final_stock": final_stock,
                "page": page_num
            }
        
        # Padrão com código e 6 números (formato original)
        pattern_6 = re.match(
            r"^(\d{2})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,]+?)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s+"
            r"([\d.,]+)\s*$",
            line
        )
        
        if pattern_6:
            code = pattern_6.group(1)
            species = pattern_6.group(2).strip()
            
            if self._should_skip_line(species):
                return None
            
            initial = self._parse_number(pattern_6.group(3))
            acquisitions = self._parse_number(pattern_6.group(4))
            births = self._parse_number(pattern_6.group(5))
            losses = self._parse_number(pattern_6.group(6))
            sales = self._parse_number(pattern_6.group(7))
            
            # Calcular estoque final
            final_stock = initial + acquisitions + births - losses - sales
            
            item_id = generate_item_id(f"livestock_{code}_{species}")
            
            return {
                "id": item_id,
                "code": code,
                "species": species,
                "initial_stock": initial,
                "acquisitions": acquisitions,
                "births": births,
                "consumption_and_losses": losses,
                "sales": sales,
                "final_stock": final_stock,
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
        """Parseia número com formato brasileiro (1.234,56 ou 1234)."""
        try:
            # Remover pontos de milhar e trocar vírgula por ponto
            clean_value = value.replace(".", "").replace(",", ".")
            return float(clean_value)
        except (ValueError, AttributeError):
            return 0.0
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CÓDIGO", "ESPÉCIE", "QUANTIDADE", "NASCIMENTO", "ESTOQUE"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        """Calcula totais e valida contra os totais do PDF.
        
        Args:
            items: Lista de itens extraídos
            pdf_totals: Lista de totais do PDF [est_ini, aquisic, nascim, perdas, vendas, est_final]
        """
        pdf_totals = pdf_totals or []
        
        # Somar valores extraídos
        sum_initial = sum(i.get("initial_stock", 0) for i in items)
        sum_acquisitions = sum(i.get("acquisitions", 0) for i in items)
        sum_births = sum(i.get("births", 0) for i in items)
        sum_losses = sum(i.get("consumption_and_losses", 0) for i in items)
        sum_sales = sum(i.get("sales", 0) for i in items)
        sum_final = sum(i.get("final_stock", 0) for i in items)
        
        # Totais do PDF (se disponíveis) - ordem pode variar conforme PDF
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
        """Extrai o TOTAL específico da seção de Movimentação do Rebanho.
        
        Busca a linha TOTAL apenas APÓS encontrar o marcador da seção.
        """
        lines = page_text.split("\n")
        in_section = False
        # Pattern unificado BR/US - BUG #81321 fix
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        
        for line in lines:
            upper_line = line.upper()
            
            # Entrar na seção
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if not in_section:
                continue
            
            # Sair se encontrar outra seção
            if any(end in upper_line for end in self.SECTION_END_MARKERS):
                break
            
            # Encontrar linha de TOTAL dentro da seção
            if upper_line.strip().startswith("TOTAL"):
                matches = re.findall(num_pattern, line)
                if matches:
                    return [self._parse_total_value(m) for m in matches]
        
        return []
    
    def _parse_total_value(self, value_str: str) -> float:
        """Converte string de valor brasileiro para float."""
        if not value_str:
            return 0.0
        cleaned = value_str.replace(".", "").replace(",", ".")
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
