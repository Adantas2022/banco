"""Extrator de declaração de bens e direitos."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id, sum_currency_values
from ..validation_utils import extract_section_total, create_validated_total


class AssetsExtractor(ISectionExtractor):
    """Extrai declaração de bens e direitos."""
    
    # Marcadores incluindo variações OCR comuns (ex: "Ç" pode virar "G" no OCR)
    SECTION_MARKERS = [
        "DECLARAÇÃO DE BENS E DIREITOS",
        "DECLARACAO DE BENS E DIREITOS",
        "DECLARAGAO DE BENS E DIREITOS",  # OCR: Ç -> G
    ]
    SECTION_MARKER = "DECLARAÇÃO DE BENS E DIREITOS"  # Mantido para compatibilidade
    # IMPORTANTE: Apenas marcadores de seções que vêm DEPOIS de bens na declaração IRPF
    SECTION_END_MARKERS = [
        "DÍVIDAS E ÔNUS REAIS",
        "DIVIDAS E ONUS REAIS",
        "DiVIDAS E ONUS REAIS",  # OCR: variação
        "DOAÇÕES EFETUADAS",
        "DOACOES EFETUADAS",
    ]
    
    @property
    def section_name(self) -> str:
        return "assets_declaration"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_totals = []  # Totais do PDF
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            # Verificar todos os marcadores de seção (incluindo variações OCR)
            if any(marker in upper_text for marker in self.SECTION_MARKERS):
                in_section = True
            
            if not in_section:
                continue
            
            if self._has_section_end_heading(page_text):
                page_items = self._extract_from_page(page_text, page_num)
                items.extend(page_items)
                
                # Extrair total do PDF antes de sair da seção
                if not pdf_totals:
                    page_totals = extract_section_total(
                        page_text,
                        "TOTAL",
                        skip_keywords=["TOTAL DE BENS", "TOTAL DE DEDUÇÃO"]
                    )
                    if page_totals:
                        pdf_totals = page_totals
                break
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
            
            # Extrair total do PDF (geralmente na última página da seção)
            if not pdf_totals:
                page_totals = extract_section_total(
                    page_text,
                    "TOTAL",
                    skip_keywords=["TOTAL DE BENS", "TOTAL DE DEDUÇÃO"]
                )
                if page_totals:
                    pdf_totals = page_totals
        
        if not items:
            return None
        
        # Somar valores extraídos
        last_year_total = sum_currency_values([i["before_year_asset_value"] for i in items], as_int=False)
        current_year_total = sum_currency_values([i["current_year_asset_value"] for i in items], as_int=False)
        
        # Totais do PDF (se disponíveis)
        pdf_last_year = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_current_year = pdf_totals[1] if len(pdf_totals) > 1 else None
        
        return {
            "section_name": "Declaração de Bens e Direitos",
            "items": items,
            "last_year_total_value": last_year_total,
            "current_year_total_value": current_year_total,
            "total_values": {
                "before_year_asset_value": create_validated_total(last_year_total, pdf_last_year),
                "current_year_asset_value": create_validated_total(current_year_total, pdf_current_year)
            },
            "pages_with_problems": []
        }
    
    def _has_section_end_heading(self, page_text: str) -> bool:
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue
            for marker in self.SECTION_END_MARKERS:
                if stripped == marker or stripped.startswith(marker + " "):
                    next_lines = " ".join(lines[i+1:i+4]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
                        return True
                    if re.search(r"^\d{2}\s+", stripped[len(marker):].strip()):
                        return True
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            asset_match = re.match(
                r"^(?:\d+\s+)?(\d{2})\s+(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if asset_match:
                item = self._parse_asset_block(
                    lines, i, asset_match, page_num
                )
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items
    
    def _parse_asset_block(
        self, 
        lines: list[str], 
        start_idx: int,
        match: re.Match,
        page_num: int
    ) -> Optional[dict]:
        group_code = match.group(1)
        asset_code = match.group(2)
        description_start = match.group(3)
        before_value = parse_currency(match.group(4))
        current_value = parse_currency(match.group(5))
        
        description_parts = [description_start]
        country_code = "105"
        country_name = "BRASIL"
        
        j = start_idx + 1
        while j < len(lines):
            next_line = lines[j].strip()
            
            if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", next_line):
                break
            
            # Código de país: 3 dígitos seguido de nome do país (ex: "105 - BRASIL", "767 - SUÍÇA")
            # Não captura linhas como "250 - MOTOR 1812CC" que são continuação de descrição
            # Critérios: exatamente 3 dígitos, nome curto (≤3 palavras), sem números no nome
            country_match = re.match(r"^(\d{3})\s*[-–]\s*(.+)$", next_line)
            if country_match:
                potential_name = country_match.group(2).strip()
                # País: nome curto, sem números, sem múltiplos hífens
                if (len(potential_name.split()) <= 3 and 
                    not re.search(r'\d', potential_name) and
                    potential_name.count('-') == 0):
                    country_code = country_match.group(1)
                    country_name = potential_name
                    j += 1
                    continue
            
            if "Página" in next_line and "de" in next_line:
                break
            
            if next_line.upper().startswith("TOTAL") or next_line.upper().startswith("TOTAL DE BENS"):
                break
            
            if self._is_description_continuation(next_line):
                description_parts.append(next_line)
            
            j += 1
        
        full_description = " ".join(description_parts)
        full_description = re.sub(r"\s+", " ", full_description).strip()
        
        item_id = generate_item_id(f"{group_code}{asset_code}{full_description[:50]}")
        
        return {
            "id": item_id,
            "asset_group_code": group_code,
            "asset_code": asset_code,
            "asset_description": full_description,
            "before_year_asset_value": before_value,
            "current_year_asset_value": current_value,
            "country_code": country_code,
            "country_name": country_name,
            "country_valid": True,
            "page": page_num,
            "_next_index": j
        }
    
    def _is_description_continuation(self, line: str) -> bool:
        """Verifica se a linha é continuação da descrição do bem."""
        # Prefixos que indicam campos de metadados (não são continuação da descrição)
        skip_prefixes = (
            "Bem", "Inscrição", "Logradouro", "Comp", "Município",
            "Área", "Registrado", "Nome Cartório", "Nº", "RENAVAM",
            "Registro de Embarcação", "Matrícula", "Banco", "Agência",
            "Conta", "Negociados", "Código de Neg", "Autocustodiante",
            "CNPJ", "Lucro ou", "Valor Recebido", "Imposto",
            "CEI", "CNO", "CEI/CNO", "Aplicação Financeira", "UF",
            "Bairro", "Data de Aquisição", "CNPJ do Fundo", "CNPJ Custodiante",
            "CIB", "Nirf"
        )
        
        if not line or len(line) <= 3:
            return False
        
        if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", line):
            return False
        
        if re.match(r"^\d+$", line):
            return False
        
        # Tratamento especial para linhas que começam com "CPF":
        # - Metadados: "CPF: 123.456.789-00" ou "CPF 123.456.789-00" (apenas número)
        # - Narrativa: "CPF 593380401-00, POR FORCA DE..." (número + texto adicional)
        if line.startswith("CPF"):
            # Se é apenas CPF seguido de número (com ou sem pontuação), é metadado
            if re.match(r"^CPF[:\s]*[\d.-]+\s*$", line):
                return False
            # Caso contrário, é narrativa (CPF seguido de texto)
            return True
        
        if any(line.startswith(p) for p in skip_prefixes):
            return False
        
        if re.match(r"^CEI/?CNO[:\s]", line, re.IGNORECASE):
            return False
        
        # Linhas que começam com número seguido de hífen são continuação de descrição
        # Ex: "250 - MOTOR 1812CC - CHASSI F3X"
        if re.match(r"^\d+\s*-\s*[A-Z]", line):
            return True
        
        return True
