"""Extrator de declaração de bens e direitos."""

import os
import re
import json
import tempfile
import asyncio
from typing import Any, Optional

from irpf_processor.domain.entities import extraction_result

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id, sum_currency_values
from ..validation_utils import extract_section_total, create_validated_total
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


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

    LLM_PROMPT = """
                ================================================================
                SECAO 2 - DECLARACAO DE BENS E DIREITOS
                ================================================================
                REGRA: lista TODOS os bens. Cada linha = um objeto separado. Nao omita nenhum.

                {   
                    "section_name": "Declaração de Bens e Direitos",
                    "items": [
                    {
                        "id": "string (hash MD5 gerado com base no conteudo do item)",
                        "asset_group_code": "string (ex: '01', '02', '03')",
                        "asset_code": "string (ex: '01', '11')",
                        "asset_description": "string - copie o texto presente na terceira coluna da tabela, este texto descreve o que é o item",
                        "before_year_asset_value": numero,
                        "current_year_asset_value": numero,
                        "country_code": "string ex: '105'",
                        "country_name": "string em maiusculas ex: 'BRASIL'",
                        "additional_info": { <ver regras abaixo> },
                        "country_valid": true,
                        "page": numero
                    }
                    ],
                    "last_year_total_value": numero,
                    "current_year_total_value": numero,
                    "pages_with_problems": []
                }

                REGRAS DE additional_info, retorne apenas os campos presentes no documento, não use o campo descrição para deduzir os campos, caso o campo não esteja presente não retorne o campo, caso o campo esteja presente mas sem valor, preencha com null:
                
                "additional_info": {
                    "municipal_registration": "string ou null",
                    "street_address": "string ou null",
                    "complement": "string ou null",
                    "city": "string ou null",
                    "area": "string ou null",
                    "registered_at_registy_office": true | false | null,
                    "matriculation": "string ou null",
                    "number": "string ou null",
                    "neighborhood": "string ou null",
                    "state": "string 2 letras ou null",
                    "acquisition_date": "DD/MM/YYYY ou null",
                    "registry_office_name": "string ou null",
                    "zipcode": "string ou null",
                    "renavam": "string ou null",
                    "beneficiary": "string (ex: 'Titular') ou null",
                    "cnpj": "string com mascara ou null",
                    "cpf": "string com mascara ou null",
                    "bank": "string com mascara ou null",
                    "agency": "string com mascara ou null",
                    "account": "string com mascara ou null",
                    "is_payment_account": true or false,
                    "traded_on_stock_market": true or false
                }

                Extraia todos os BENS e seus respectivos detalhes.
                """
    
    def __init__(self):
        """Inicializa o extractor com rastreamento de estado da seção."""
        self._section_started = False
        self._section_start_page = -1
    
    @property
    def section_name(self) -> str:
        return "assets_declaration"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)

    async def extract_with_llm(
        self, 
        context: ExtractionContext,
        custom_prompt: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Extract assets section using LLM (with temp PDF from selected pages).
        
        This function:
        1. Extracts section page numbers from SECTION_MARKERS to SECTION_END_MARKERS
        2. Creates a temporary PDF with only the relevant pages
        3. Sends the temp PDF to IRProvider for LLM extraction
        4. Transforms the LLM response to match the expected format
        
        Args:
            context: ExtractionContext with document pages and PDF path
            custom_prompt: Optional custom prompt to pass to the LLM provider
            
        Returns:
            Dictionary with extracted data in the same format as extract() method,
            or None if extraction fails
        """
        try:
            # Step 1: Get LLM Extraction
            extraction_result = await self.get_llm_extraction_data(context, custom_prompt)
            
            if not extraction_result:
                context.add_warning("LLM extraction returned no chunks")
                return None

            # Step 2: Merge chunks — page-based overlap removal
            chunks = extraction_result  # list[dict]
            logger.info("llm_assets_chunks_received", chunks_count=len(chunks))

            items = []
            pdf_last_year = None
            pdf_current_year = None
            for chunk_idx, chunk in enumerate(chunks):
                if not isinstance(chunk, dict):
                    continue
                chunk_items = chunk.get("items", [])
                if not isinstance(chunk_items, list):
                    continue

                if chunk_idx > 0 and chunk_items:
                    # Overlap: a primeira página deste chunk = última do anterior
                    overlap_page = chunk_items[0].get("page")
                    if overlap_page is not None:
                        # Contar itens neste chunk com a página sobreposta
                        overlap_count = sum(
                            1 for it in chunk_items if it.get("page") == overlap_page
                        )
                        # Remover os últimos N itens do merged que têm essa página
                        removed = 0
                        while removed < overlap_count and items:
                            if items[-1].get("page") == overlap_page:
                                items.pop()
                                removed += 1
                            else:
                                break
                        logger.info("llm_assets_chunk_overlap", chunk_idx=chunk_idx, overlap_page=overlap_page, overlap_count=overlap_count, removed=removed)

                for item in chunk_items:
                    normalized_item = self._normalize_llm_item(item)
                    items.append(normalized_item)
                # Take last non-None totals (usually on final pages)
                if chunk.get("last_year_total_value") is not None:
                    pdf_last_year = chunk["last_year_total_value"]
                if chunk.get("current_year_total_value") is not None:
                    pdf_current_year = chunk["current_year_total_value"]

            logger.info("llm_assets_merge_complete", items_count=len(items), chunks_count=len(chunks))
            
            if not items:
                context.add_warning("LLM extraction returned no items")
                return None
            
            ## Step 3: Calculate totals
            last_year_total = sum_currency_values(
                [i.get("before_year_asset_value", 0) for i in items],
                as_int=False
            )
            current_year_total = sum_currency_values(
                [i.get("current_year_asset_value", 0) for i in items],
                as_int=False
            )
            
            return {
                "section_name": "Declaração de Bens e Direitos",
                "items": items,
                "last_year_total_value": last_year_total,
                "current_year_total_value": current_year_total,
                "total_values": {
                    "before_year_asset_value": create_validated_total(last_year_total, pdf_last_year),
                    "current_year_asset_value": create_validated_total(current_year_total, pdf_current_year)
                },
                "pages_with_problems": [],
                "extraction_method": "llm"
            }
        except Exception as e:
            context.add_warning(f"LLM extraction failed: {type(e).__name__}: {str(e)}")
            return None

    def _normalize_llm_item(self, item: dict) -> dict:
        """
        Normalize LLM extracted item to match expected format.
        
        Args:
            item: Dictionary from LLM containing asset information
            
        Returns:
            Normalized dictionary matching AssetsExtractor item format
        """
        # Ensure required fields exist
        group_code = str(item.get("asset_group_code", "00")).zfill(2)
        asset_code = str(item.get("asset_code", "00")).zfill(2)
        description = str(item.get("asset_description") or item.get("description", "")).strip()
        
        # Parse currency values
        before_value = self._parse_llm_currency(item.get("before_year_asset_value"))
        current_value = self._parse_llm_currency(item.get("current_year_asset_value"))
        
        item_id = generate_item_id(f"{group_code}{asset_code}{description[:50]}")
        
        return {
            "id": item_id,
            "asset_group_code": group_code,
            "asset_code": asset_code,
            "asset_description": description,
            "before_year_asset_value": before_value,
            "current_year_asset_value": current_value,
            "country_code": str(item.get("country_code", "105")).zfill(3),
            "country_name": str(item.get("country_name", "BRASIL")).upper(),
            "additional_info": item.get("additional_info", {}),
            "country_valid": item.get("country_valid", True),
            "page": item.get("page", 0),
        }
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_total_candidates = []
        
        self._section_started = False
        self._section_start_page = -1
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        for page_idx, (page_num, page_text) in enumerate(sorted_pages):
            upper_text = page_text.upper()
            
            if any(marker in upper_text for marker in self.SECTION_MARKERS):
                in_section = True
                if not self._section_started:
                    self._section_started = True
                    self._section_start_page = page_num
            
            if not in_section:
                continue
            
            next_page_text = (
                sorted_pages[page_idx + 1][1]
                if page_idx + 1 < len(sorted_pages)
                else None
            )
            
            if self._has_section_end_heading(page_text, page_num):
                page_items = self._extract_from_page(
                    page_text, page_num, next_page_text=next_page_text
                )
                items.extend(page_items)
                
                page_totals = self._extract_assets_total(page_text)
                if page_totals:
                    if len(page_totals) >= 2:
                        pdf_total_candidates.append((page_totals[0], page_totals[1]))
                    elif len(page_totals) == 1:
                        pdf_total_candidates.append((page_totals[0], None))
                break
            
            if items:
                orphan_lines = self._extract_orphan_address_lines(page_text)
                if orphan_lines and items[-1].get("additional_info"):
                    self._update_item_with_orphan_lines(items[-1], orphan_lines)
            
            page_items = self._extract_from_page(
                page_text, page_num, next_page_text=next_page_text
            )
            items.extend(page_items)
            
            page_totals = self._extract_assets_total(page_text)
            if page_totals:
                if len(page_totals) >= 2:
                    pdf_total_candidates.append((page_totals[0], page_totals[1]))
                elif len(page_totals) == 1:
                    pdf_total_candidates.append((page_totals[0], None))
        
        if not items:
            return None
        
        # Somar valores extraídos
        last_year_total = sum_currency_values([i["before_year_asset_value"] for i in items], as_int=False)
        current_year_total = sum_currency_values([i["current_year_asset_value"] for i in items], as_int=False)
        
        # Totais do PDF (se disponíveis) - escolher o TOTAL de bens e direitos
        # mais próximo da soma dos itens (before_year_asset_value).
        pdf_last_year = None
        pdf_current_year = None
        if pdf_total_candidates:
            best_before, best_current = min(
                pdf_total_candidates,
                key=lambda t: abs(t[0] - last_year_total),
            )
            pdf_last_year = best_before
            pdf_current_year = best_current
        
        return {
            "section_name": "Declaração de Bens e Direitos",
            "items": items,
            "last_year_total_value": last_year_total,
            "current_year_total_value": current_year_total,
            "total_values": {
                "before_year_asset_value": create_validated_total(last_year_total, pdf_last_year),
                "current_year_asset_value": create_validated_total(current_year_total, pdf_current_year)
            },
            "pages_with_problems": [],
            "extraction_method": "regex"
        }
    
    def _extract_assets_total(self, page_text: str) -> list[float]:
        lines = page_text.split("\n")
        skip_keywords = ["TOTAL DE BENS", "TOTAL DE DEDUÇÃO"]
        num_pattern = r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})"

        end_marker_idx = len(lines)
        for i, line in enumerate(lines):
            upper = line.strip().upper()
            for marker in self.SECTION_END_MARKERS:
                if marker in upper:
                    end_marker_idx = i
                    break
            if end_marker_idx != len(lines):
                break

        last_matches = None

        for line in lines[:end_marker_idx]:
            stripped = line.strip()
            if not stripped:
                continue
            upper = stripped.upper()

            if not upper.startswith("TOTAL"):
                continue

            if any(skip.upper() in upper for skip in skip_keywords):
                continue

            matches = re.findall(num_pattern, stripped)
            if len(matches) >= 2:
                last_matches = [parse_currency(m) for m in matches]

        return last_matches or []
    
    def _has_section_end_heading(self, page_text: str, page_num: int = 0) -> bool:
        """
        Verifica se há marcador de fim de seção na página.
        
        BUG #81620 fix: Só considera fim válido se:
        1. A seção já foi iniciada
        2. O marcador de fim está DEPOIS do marcador de início na página
           OU está em uma página posterior
        
        Args:
            page_text: Texto da página
            page_num: Número da página atual
            
        Returns:
            True se encontrar marcador de fim válido
        """
        # Só verificar fim se a seção já iniciou
        if not self._section_started:
            return False
        
        upper_text = page_text.upper()
        
        # Se estamos na mesma página que a seção iniciou,
        # verificar se o marcador de fim vem DEPOIS do marcador de início
        if page_num == self._section_start_page:
            # Encontrar posição do marcador de início
            section_start_pos = -1
            for marker in self.SECTION_MARKERS:
                pos = upper_text.find(marker)
                if pos != -1:
                    section_start_pos = pos
                    break
            
            if section_start_pos == -1:
                return False
            
            # Verificar marcadores de fim apenas APÓS o início da seção
            for marker in self.SECTION_END_MARKERS:
                end_pos = upper_text.find(marker)
                if end_pos != -1 and end_pos > section_start_pos:
                    # Confirmar que é início de nova seção (tem headers)
                    lines = page_text.split("\n")
                    for i, line in enumerate(lines):
                        if marker in line.upper():
                            next_lines = " ".join(lines[i+1:i+4]).upper()
                            if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
                                return True
                            if re.search(r"^\d{2}\s+", line.strip().upper()[len(marker):].strip()):
                                return True
            return False
        
        # Para páginas posteriores, usar lógica original
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
    
    # Aceita formato BR (150.000,00) E formato US (150,000.00)
    CURRENCY_RE = r"(\d[\d.]*,\d{2}|\d[\d,]*\.\d{2})"

    def _extract_from_page(
        self,
        page_text: str,
        page_num: int,
        next_page_text: Optional[str] = None,
    ) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        next_page_lines = next_page_text.split("\n") if next_page_text else []
        
        two_val = re.compile(
            rf"^(?:\d+\s+)?(\d{{2}})\s+(\d{{2}})\s+(.+?)\s+{self.CURRENCY_RE}\s+{self.CURRENCY_RE}\s*$"
        )
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            asset_match = two_val.match(line)
            
            if asset_match:
                item = self._parse_asset_block(
                    lines, i, asset_match, page_num
                )
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            if not asset_match:
                item = self._try_fallback_asset(
                    lines, i, page_num, next_page_lines=next_page_lines
                )
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            if not asset_match:
                item = self._try_bare_header_asset(
                    lines, i, page_num, next_page_lines=next_page_lines
                )
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items

    def _try_fallback_asset(
        self,
        lines: list[str],
        idx: int,
        page_num: int,
        next_page_lines: Optional[list[str]] = None,
    ) -> Optional[dict]:
        line = lines[idx].strip()
        
        header = re.match(r"^(?:\d+\s+)?(\d{2})\s+(\d{2})\s+(.+?)\s*$", line)
        if not header:
            return None
        
        group_code = header.group(1)
        asset_code = header.group(2)
        rest = header.group(3)
        
        if len(rest.strip()) < 3:
            return None
        
        vals = re.findall(self.CURRENCY_RE, rest)
        
        if len(vals) >= 2:
            v1, v2 = vals[-2], vals[-1]
            desc = rest[:rest.rfind(vals[-2])].strip()
            if len(desc) < 3:
                return None
        elif len(vals) == 1:
            v1 = vals[0]
            desc = rest[:rest.rfind(v1)].strip()
            if len(desc) < 5:
                return None
            v2 = self._find_orphan_value(lines, idx + 1)
            if not v2 and next_page_lines:
                v2 = self._find_orphan_value(next_page_lines, 0, max_lines=10)
            if not v2:
                v2 = v1
        else:
            desc = rest.strip()
            v1, v2 = self._find_two_orphan_values(lines, idx + 1)
            if (not v1 or not v2) and next_page_lines:
                v1_next, v2_next = self._find_two_orphan_values(
                    next_page_lines, 0, max_lines=10
                )
                if not v1:
                    v1 = v1_next
                if not v2:
                    v2 = v2_next
            if not v1 or not v2:
                return None
        
        class _FakeMatch:
            def __init__(self, groups):
                self._groups = groups
            def group(self, n):
                return self._groups[n]
        
        fake = _FakeMatch({1: group_code, 2: asset_code, 3: desc, 4: v1, 5: v2})
        return self._parse_asset_block(lines, idx, fake, page_num)

    def _try_bare_header_asset(
        self,
        lines: list[str],
        idx: int,
        page_num: int,
        next_page_lines: Optional[list[str]] = None,
    ) -> Optional[dict]:
        """Handle OCR artifacts where group code appears alone on a line.

        Pattern: ``07 POR\\n01 TREND OURO FIM 156.438,76 199.019,06``
        The group code (07) is on its own line (possibly with short OCR noise),
        and the asset code + description + values appear on the next line.
        """
        line = lines[idx].strip()
        bare = re.match(r"^(\d{2})(?:\s+\S{1,5})?\s*$", line)
        if not bare:
            return None
        group_code = bare.group(1)

        for j in range(idx + 1, min(idx + 3, len(lines))):
            nxt = lines[j].strip()
            if not nxt:
                continue
            code_rest = re.match(r"^(\d{2})\s+(.+)", nxt)
            if not code_rest:
                continue
            asset_code = code_rest.group(1)
            rest = code_rest.group(2)
            vals = re.findall(self.CURRENCY_RE, rest)
            if len(vals) >= 2:
                v1, v2 = vals[-2], vals[-1]
                desc = rest[:rest.rfind(vals[-2])].strip()
            elif len(vals) == 1:
                v1 = vals[0]
                desc = rest[:rest.rfind(v1)].strip()
                v2 = self._find_orphan_value(lines, j + 1)
                if not v2 and next_page_lines:
                    v2 = self._find_orphan_value(next_page_lines, 0, max_lines=10)
                if not v2:
                    v2 = v1
            else:
                desc = rest.strip()
                v1, v2 = self._find_two_orphan_values(lines, j + 1)
                if not v1 or not v2:
                    continue
            if len(desc) < 3:
                continue

            class _FakeMatch:
                def __init__(self, groups):
                    self._groups = groups
                def group(self, n):
                    return self._groups[n]

            fake = _FakeMatch({1: group_code, 2: asset_code, 3: desc, 4: v1, 5: v2})
            item = self._parse_asset_block(lines, idx, fake, page_num)
            if item:
                item["_next_index"] = j + 1
            return item
        return None

    def _find_orphan_value(self, lines: list[str], start: int, max_lines: int = 25) -> Optional[str]:
        for j in range(start, min(start + max_lines, len(lines))):
            s = lines[j].strip()
            if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", s):
                break
            m = re.match(rf"^{self.CURRENCY_RE}\s*$", s)
            if m:
                return m.group(1)
        return None

    def _find_two_orphan_values(
        self, lines: list[str], start: int, max_lines: int = 25
    ) -> tuple[Optional[str], Optional[str]]:
        found: list[str] = []
        for j in range(start, min(start + max_lines, len(lines))):
            s = lines[j].strip()
            if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", s):
                break
            two_on_line = re.match(
                rf"^{self.CURRENCY_RE}\s+{self.CURRENCY_RE}\s*$", s
            )
            if two_on_line:
                return two_on_line.group(1), two_on_line.group(2)
            m = re.match(rf"^{self.CURRENCY_RE}\s*$", s)
            if m:
                found.append(m.group(1))
                if len(found) == 2:
                    return found[0], found[1]
        if len(found) == 1:
            return found[0], None
        return None, None
    
    def _parse_asset_block(
        self, 
        lines: list[str], 
        start_idx: int,
        match,
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
        raw_lines = []
        
        # NOTA: Removido bloco que adicionava prev_line com campos bancários.
        # Esse bloco estava incorreto pois capturava campos do item ANTERIOR,
        # causando desalinhamento de bank/agency/account em 28 itens.
        # Os campos bancários são capturados corretamente no loop abaixo.
        
        j = start_idx + 1
        while j < len(lines):
            next_line = lines[j].strip()
            
            if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", next_line):
                break
            
            if (
                re.match(r"^\d{2}(?:\s+\S{1,5})?\s*$", next_line)
                and j + 1 < len(lines)
                and re.match(r"^\d{2}\s+", lines[j + 1].strip())
            ):
                break

            if re.match(r"^\d{2}\s+\d{2}\s*$", next_line):
                break
            
            # Código de país: 3 dígitos seguido de nome do país (ex: "105 - BRASIL", "767 - SUÍÇA")
            # Não captura linhas como "250 - MOTOR 1812CC" que são continuação de descrição
            # Critérios: exatamente 3 dígitos, nome curto (≤3 palavras), sem números no nome
            country_match = re.match(r"^(\d{3})\s*[-–]?\s+(.+)$", next_line)
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
            
            raw_lines.append(next_line)
            
            if self._is_description_continuation(next_line):
                description_parts.append(next_line)
            
            j += 1
        
        full_description = " ".join(description_parts)
        full_description = re.sub(r"\s+", " ", full_description).strip()
        # Bug #86842: Remover valores monetários US-format residuais do final da descrição
        # Ex: "AERONAVE 200,000.00" → "AERONAVE", "LOJA EM SAO PAULO 180,000.00" → "LOJA EM SAO PAULO"
        # Também remove padrões como "COME - COTAS 16,000.00" → "COME - COTAS"
        full_description = re.sub(r"\s+\d[\d,]*\.\d{2}\s*$", "", full_description).strip()

        upper_desc = full_description.upper()
        legal_marker_variants = [
            "OPÇÃO PELA ATUALIZAÇÃO DO VALOR DO BEM OU DIREITO NO EXTERIOR",
            "OPCAO PELA ATUALIZACAO DO VALOR DO BEM OU DIREITO NO EXTERIOR",
        ]
        for marker in legal_marker_variants:
            idx = upper_desc.find(marker)
            if idx != -1:
                full_description = full_description[:idx].rstrip()
                break

        law_option_pattern = re.compile(
            r"\s+\d{1,4}[.,]?\d{0,3}\s*,?\s+de\s+\d{4}\s*:\s*(?:Sim|N[ãa]o)\s*$",
            re.IGNORECASE,
        )
        full_description = law_option_pattern.sub("", full_description).strip()
        
        additional_info = self._build_additional_info(
            group_code, raw_lines, full_description
        )
        
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
            "additional_info": additional_info,
            "country_valid": True,
            "page": page_num,
            "_next_index": j
        }
    
    def _build_additional_info(
        self, 
        group_code: str, 
        raw_lines: list[str],
        description: str
    ) -> dict:
        raw_text = " ".join(raw_lines)
        
        # Grupos de imóveis: 01 (urbanos), 12 (casas), 13 (terrenos), 14 (rurais), 15 (atividade rural)
        if group_code in ("01", "12", "13", "14", "15"):
            return self._extract_real_estate_info(raw_lines, raw_text, description)
        elif group_code == "02":
            return self._extract_vehicle_info(raw_lines, raw_text)
        elif group_code in ("03", "04", "05"):
            return self._extract_participation_info(raw_lines, raw_text, description)
        elif group_code == "06":
            return self._extract_deposit_info(raw_lines, raw_text, description)
        elif group_code == "07":
            return self._extract_fund_info(raw_lines, raw_text)
        elif group_code == "08":
            return self._extract_crypto_info(raw_lines, raw_text)
        else:
            return self._extract_generic_info(raw_lines, raw_text)
    
    def _extract_real_estate_info(
        self, 
        lines: list[str], 
        raw_text: str,
        description: str
    ) -> dict:
        info = {
            "municipal_registration": None,
            "street_address": None,
            "complement": None,
            "city": None,
            "area": None,
            "registered_at_registy_office": False,
            "matriculation": None,
            "number": None,
            "neighborhood": None,
            "state": None,
            "acquisition_date": None,
            "registry_office_name": None,
            "zipcode": None,
            "cei_cno": None,
            "cib_nirf": None
        }
        
        # Juntar linhas consecutivas para capturar valores em linhas separadas
        # Ex: "Área Total:" em uma linha, "82,0 ha" na próxima
        for i, line in enumerate(lines):
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            
            if "Inscrição Municipal" in line:
                m = re.search(r"Inscrição Municipal[^:]*[:\s]+([\d.-]+)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2:
                        info["municipal_registration"] = val
            
            if "Logradouro" in line:
                m = re.search(r"Logradouro[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s.,]+?)(?:\s+Nº|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2 and not val.startswith("Nº"):
                        info["street_address"] = val
            
            if "Nº" in line:
                m = re.search(r"Nº[:\s]*([A-Z0-9]+)", line)
                if m:
                    val = m.group(1).strip()
                    if val and val != ":" and len(val) >= 1:
                        info["number"] = val
            
            if "Comp" in line and (":" in line or "Complemento" in line):
                m = re.search(r"Comp[^:]*[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s.,0-9]+?)(?:\s+Bairro|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2 and val not in (":", "Bairro:", "Bairro"):
                        info["complement"] = val
            
            if "Bairro" in line:
                # Formato: "Bairro: ZONA RURAL" ou "Comp.: PROGRESSO Bairro: ZONA RURAL"
                m = re.search(r"Bairro[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s]+?)(?:\s+UF|\s*$)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2 and val != ":":
                        info["neighborhood"] = val
            
            # Município - formatos:
            # 1. "Município: SORRISO UF:" (Município antes de UF)
            # 2. "UF: MT	Município: NOVO SANTO ANTÔNIO CEP:" (UF antes de Município)
            if "Município" in line:
                # Primeiro tenta formato com UF depois
                m = re.search(r"Município[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s]+?)(?:\s+UF|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 1:
                        info["city"] = val
                else:
                    # Formato: "UF: XX\tMunicípio: CIDADE CEP:" (UF antes, CEP depois)
                    m = re.search(r"Município[:\s]+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s]+?)(?:\s+CEP|\s*$)", line)
                    if m:
                        val = m.group(1).strip()
                        if val and len(val) > 1:
                            info["city"] = val
            
            # UF - extrair de qualquer formato
            if re.search(r"\bUF\b", line):
                m = re.search(r"\bUF[:\s]+([A-Z]{2})(?:\s|\t|$)", line)
                if m:
                    state_val = m.group(1)
                    # Evitar capturar "CE" de "CEP" se estiver logo após
                    if state_val not in ("CE", "EP"):
                        info["state"] = state_val
                    elif "CEP" not in line[:line.find("UF")+5]:
                        info["state"] = state_val
            
            if "CEP" in line:
                m = re.search(r"CEP[:\s]*([\d]{5}-?[\d]{3})", line)
                if m:
                    info["zipcode"] = m.group(1).strip()
            
            # Área - formatos:
            # 1. "Área Total: 529,5 m²" (na mesma linha)
            # 2. "Área Total:" em uma linha, valor na próxima linha
            # 3. "Data de Aquisição: / /	82,0 ha" (área junto com data)
            # 4. "Área Total: 0,0" (sem unidade - Bug #86842)
            if "Área" in line or "Area" in line:
                # Primeiro tenta na mesma linha com unidade
                m = re.search(r"[ÁA]rea[^:]*[:\s]*([\d.,]+\s*(?:m[²2]|ha))", line, re.IGNORECASE)
                if m:
                    info["area"] = m.group(1).strip()
                elif not info["area"]:
                    # Fallback: capturar valor sem unidade (ex: "0,0")
                    m_no_unit = re.search(r"[ÁA]rea[^:]*[:\s]*([\d]+[.,][\d]+)", line, re.IGNORECASE)
                    if m_no_unit:
                        info["area"] = m_no_unit.group(1).strip()
                    else:
                        # Área na próxima linha (formato: "Área Total:" sozinho)
                        # A área pode estar na linha de "Data de Aquisição"
                        for j in range(i + 1, min(i + 3, len(lines))):
                            area_m = re.search(r"([\d.,]+)\s*(ha|m[²2])", lines[j], re.IGNORECASE)
                            if area_m:
                                info["area"] = f"{area_m.group(1)} {area_m.group(2)}"
                                break
            
            # Capturar área de linha "Data de Aquisição: / /	82,0 ha"
            if "Data de Aquisição" in line:
                m = re.search(r"Data de Aquisição[:\s]*(\d{2}/\d{2}/\d{4})", line)
                if m:
                    info["acquisition_date"] = m.group(1)
                # Área pode estar nesta linha após a data
                if not info["area"]:
                    area_m = re.search(r"([\d.,]+)\s*(ha|m[²2])", line, re.IGNORECASE)
                    if area_m:
                        info["area"] = f"{area_m.group(1)} {area_m.group(2)}"
            
            if "Registrado" in line and "Cartório" in line:
                info["registered_at_registy_office"] = "Sim" in line
            
            if "Nome Cartório" in line or "Nome Cartorio" in line:
                # Ex: "Nome Cartório: 13 OFICIAL DE REGISTRO DE IMOVEIS DA COMARCA DE SAO PAULO"
                m = re.search(r"Nome Cart[óo]rio[:\s]+([A-ZÀ-Ú0-9][A-Za-zÀ-ÿ\s0-9.-]+?)(?:\s+Matr[íi]cula|$)", line, re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2:
                        info["registry_office_name"] = val
                else:
                    # Formato onde cartório está depois sem matrícula
                    m = re.search(r"Nome Cart[óo]rio[:\s]+(.+?)$", line, re.IGNORECASE)
                    if m:
                        val = m.group(1).strip()
                        if val and len(val) > 2:
                            info["registry_office_name"] = val
            
            if "Matrícula" in line or "Matricula" in line:
                # Capturar matrículas completas incluindo múltiplos números
                # Ex: "Matrícula: 15722/15723", "Matrícula: 1116, 1458, 1459, 1460, 1461 E 1462"
                m = re.search(r"Matr[íi]cula[:\s]*([\d.,/\sE]+)", line, re.IGNORECASE)
                if m:
                    matriculation = m.group(1).strip()
                    # Limpar espaços extras mas manter separadores
                    matriculation = re.sub(r"\s+", " ", matriculation)
                    # Remover espaços desnecessários ao redor de separadores
                    matriculation = re.sub(r"\s*([,/])\s*", r"\1", matriculation)
                    matriculation = re.sub(r"\s+E\s+", " E ", matriculation)
                    if matriculation and len(matriculation) >= 1:
                        info["matriculation"] = matriculation
            
            if "CEI" in line or "CNO" in line:
                m = re.search(r"(?:CEI/?CNO|CEI|CNO)[:\s]*([\d./-]+)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2:
                        info["cei_cno"] = val
            
            if "CIB" in line or "Nirf" in line:
                m = re.search(r"(?:CIB|Nirf)[^:]*[:\s]*([\d.-]+)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2:
                        info["cib_nirf"] = val
        
        return info
    
    def _extract_from_description(self, info: dict, description: str) -> None:
        city_state = re.search(r"(?:EM|LOCALIZADO\s+EM|MUNICIPIO\s+DE)\s+([A-Z][A-Za-zÀ-ÿ\s]+?)[\s-]+([A-Z]{2})(?:\.|,|\s|$)", description, re.IGNORECASE)
        if city_state:
            if info["city"] is None:
                info["city"] = city_state.group(1).strip().upper()
            if info["state"] is None:
                info["state"] = city_state.group(2).upper()
        
        city_slash = re.search(r"([A-Z][A-Za-zÀ-ÿ\s]+)\s*/\s*([A-Z]{2})", description)
        if city_slash:
            if info["state"] is None:
                info["state"] = city_slash.group(2)
            if info["city"] is None:
                info["city"] = city_slash.group(1).strip()
        
        number_desc = re.search(r"(?:NR\.?|N\.?|NUMERO)\s*(\d+)", description, re.IGNORECASE)
        if number_desc and info["number"] is None:
            info["number"] = number_desc.group(1)
        
        street_desc = re.search(r"(?:SITO\s+(?:A|NA)\s+)?(?:RUA|AV\.?|AVENIDA|ESTRADA)\s+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s]+?)(?:\s+(?:NR|N\.|NUMERO)|,|\s+\d)", description, re.IGNORECASE)
        if street_desc and info["street_address"] is None:
            info["street_address"] = street_desc.group(1).strip()
        
        mat_desc = re.search(r"(?:MAT\.?|MATR[IÍ]CULA)\s*[:\s]*(\d+[\d./]*)", description, re.IGNORECASE)
        if mat_desc and info["matriculation"] is None:
            info["matriculation"] = mat_desc.group(1)
            info["registered_at_registy_office"] = True
        
        cri_desc = re.search(r"(?:MAT\.?\s*)?(\d+[\d.]*)\s*(?:DO\s+)?C[RI]{2}[IO]?\s+(?:DE\s+)?([A-ZÀ-Ú][A-Za-zÀ-ÿ\s]+?)(?:\s*[-–]\s*[A-Z]{2})?(?:\.|,|$)", description, re.IGNORECASE)
        if cri_desc and info["registry_office_name"] is None:
            office_name = f"CRI DE {cri_desc.group(2).strip().upper()}"
            info["registry_office_name"] = office_name
            info["registered_at_registy_office"] = True
            if info["matriculation"] is None:
                info["matriculation"] = cri_desc.group(1)
        
        area_ha = re.search(r"(?:C/?\s*|COM\s+|AREA\s+(?:DE\s+)?)([\d.,]+)\s*(?:HAS?|HECTARES?)", description, re.IGNORECASE)
        if area_ha and info["area"] is None:
            info["area"] = f"{area_ha.group(1)} ha"
        
        area_m2 = re.search(r"([\d.,]+)\s*M[²2]", description, re.IGNORECASE)
        if area_m2 and info["area"] is None:
            info["area"] = f"{area_m2.group(1)} m²"
        
        adq_date = re.search(r"ADQ\.?\s+EM\s+(\d{2}[/.-]\d{2}[/.-]\d{4})", description, re.IGNORECASE)
        if adq_date and info["acquisition_date"] is None:
            date_str = adq_date.group(1).replace(".", "/").replace("-", "/")
            info["acquisition_date"] = date_str
        
        cei_desc = re.search(r"(?:CEI|CNO)[:\s]*([\d./-]+)", description, re.IGNORECASE)
        if cei_desc and info["cei_cno"] is None:
            info["cei_cno"] = cei_desc.group(1).strip()
    
    def _extract_vehicle_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        for line in lines:
            upper_line = line.upper()
            
            # RENAVAM - formato: "RENAVAM: 00000110809" ou "RENAVAM 01386728052"
            if "RENAVAM" in upper_line:
                m = re.search(r"RENAVAM[:\s]*(\d+)", line, re.IGNORECASE)
                if m:
                    info["renavam"] = m.group(1)
            
            # Registro de Embarcação
            elif "REGISTRO DE EMBARCAÇÃO" in upper_line or "REGISTRO DE EMBARCACAO" in upper_line:
                m = re.search(r"Registro de Embarca[çc][ãa]o[:\s]*(.+)", line, re.IGNORECASE)
                if m:
                    info["vessel_registration"] = m.group(1).strip()
            
            # Registro de Aeronave - formato: "Registro de Aeronave: PSECD"
            elif "REGISTRO DE AERONAVE" in upper_line:
                m = re.search(r"Registro de Aeronave[:\s]*([A-Z0-9]+)", line, re.IGNORECASE)
                if m:
                    info["airship_registration"] = m.group(1).strip()
        
        # Fallback: buscar no raw_text se não encontrou nos lines
        if "renavam" not in info:
            m = re.search(r"RENAVAM[:\s]*(\d+)", raw_text, re.IGNORECASE)
            if m:
                info["renavam"] = m.group(1)
        
        if "airship_registration" not in info:
            m = re.search(r"Registro de Aeronave[:\s]*([A-Z0-9]+)", raw_text, re.IGNORECASE)
            if m:
                info["airship_registration"] = m.group(1).strip()
        
        return info
    
    def _extract_participation_info(self, lines: list[str], raw_text: str, description: str = "") -> dict:
        info = {
            "beneficiary": None,
            "cpf": None
        }
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        # Prioriza CNPJ em linhas específicas (metadata) sobre CNPJ no texto
        cnpj_found = None
        for line in lines:
            if line.strip().upper().startswith("CNPJ"):
                m = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", line)
                if m:
                    cnpj_found = m.group(1)
                    break
        
        if not cnpj_found:
            cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
            if cnpj:
                cnpj_found = cnpj.group(1)
            else:
                cnpj_raw = re.search(r"CNPJ[:\s]*(\d{11,14})", raw_text)
                if cnpj_raw:
                    cnpj_found = cnpj_raw.group(1)
        
        if cnpj_found:
            info["cnpj"] = cnpj_found
        
        for line in lines:
            if "CPF" in line:
                cpf_match = re.search(
                    r"CPF[:\s]*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})",
                    line,
                )
                if cpf_match:
                    info["cpf"] = cpf_match.group(1)
                    break
        
        traded_match = re.search(r"Negociad[oa]s em Bolsa[:\s]*(Sim|Não)", raw_text)
        if traded_match:
            info["traded_on_stock_market"] = traded_match.group(1) == "Sim"
        
        trading_code_match = re.search(r"Código de Negociação[:\s]*([A-Z0-9]+)", raw_text)
        if trading_code_match:
            info["trading_code"] = trading_code_match.group(1)
        
        trading_code_desc = re.search(r"(?:TICKER|CÓDIGO)[:\s]*([A-Z]{4}\d+)", raw_text, re.IGNORECASE)
        if trading_code_desc and "trading_code" not in info:
            info["trading_code"] = trading_code_desc.group(1)
        
        bank = re.search(r"[B8]anco[:\s]*(\d+)", raw_text)
        if bank:
            info["bank"] = bank.group(1)
        
        agency = re.search(r"Ag[êe]ncia[:\s]*(\d+[-\d]*)", raw_text)
        if agency:
            info["agency"] = agency.group(1)
        
        account = re.search(r"Conta[:\s]*([\d-]+)", raw_text)
        if account:
            info["account"] = account.group(1)
        
        if bank or agency or account:
            self._extract_bank_info_from_description(info, description)
        
        return info
    
    def _extract_deposit_info(self, lines: list[str], raw_text: str, description: str = "") -> dict:
        info = {
            "beneficiary": "N/A",
            "cpf": "N/A"
        }
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj:
            info["cnpj"] = cnpj.group(1)
        
        bank = re.search(r"[B8]anco[:\s]*(\d+)", raw_text)
        if bank:
            info["bank"] = bank.group(1)
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        agency = re.search(r"Ag[êe]ncia[:\s]*(\d+[-\d]*)", raw_text)
        if agency:
            info["agency"] = agency.group(1)
        
        account = re.search(r"Conta[:\s]*([\d-]+)", raw_text)
        if account:
            info["account"] = account.group(1)
        
        if "Conta Pagamento" in raw_text:
            info["is_payment_account"] = "Sim" in raw_text.split("Conta Pagamento")[1][:20]
        else:
            info["is_payment_account"] = False
        
        # Fallback: extrair bank e account da descrição quando não existem nos metadados
        self._extract_bank_info_from_description(info, description)
        
        return info
    
    def _extract_fund_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.?\d{3}\.?\d{3}-?\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        cnpj_fund = re.search(r"CNPJ do Fundo[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj_fund:
            info["cnpj"] = cnpj_fund.group(1)
        else:
            cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
            if cnpj:
                info["cnpj"] = cnpj.group(1)
            else:
                cnpj_raw = re.search(r"CNPJ[:\s]*(\d{14})", raw_text)
                if cnpj_raw:
                    info["cnpj"] = cnpj_raw.group(1)
        
        custodian_cnpj = re.search(r"CNPJ (?:do )?Custodiante[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if custodian_cnpj:
            info["custodian_cnpj"] = custodian_cnpj.group(1)
        
        if "Autocustodiante" in raw_text:
            info["self_custodian"] = "Sim" in raw_text.split("Autocustodiante")[1][:20]
        elif "Próprio Custodiante" in raw_text:
            info["self_custodian"] = "Sim" in raw_text.split("Próprio Custodiante")[1][:20]
        
        if "Negociados em Bolsa" in raw_text:
            info["traded_on_stock_market"] = "Sim" in raw_text
        
        trading_code = re.search(r"Código de Negociação[:\s]*([A-Z0-9]+)", raw_text)
        if trading_code:
            info["trading_code"] = trading_code.group(1)
        
        profit_loss = re.search(r"Lucro ou Prejuízo[:\s]*([\d.,]+)", raw_text)
        tax_abroad = re.search(r"Imposto Pago no Exterior[:\s]*([\d.,]+)", raw_text)
        
        if profit_loss or tax_abroad:
            info["financial_application"] = {
                "items": {
                    "profit_or_loss": parse_currency(profit_loss.group(1)) if profit_loss else 0.0,
                    "tax_paid_abroad": parse_currency(tax_abroad.group(1)) if tax_abroad else 0.0
                }
            }
        
        value_received = re.search(r"Valor Recebido[:\s]*([\d.,]+)", raw_text)
        irrf_abroad = re.search(r"Imposto Pago Exterior/IRRF Brasil[:\s]*([\d.,]+)", raw_text)
        
        if value_received or irrf_abroad:
            info["profits_and_dividends"] = {
                "items": {
                    "value_received": parse_currency(value_received.group(1)) if value_received else 0.0,
                    "tax_paid_abroad_irrf": parse_currency(irrf_abroad.group(1)) if irrf_abroad else 0.0
                }
            }
        
        return info
    
    def _extract_crypto_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cnpj = re.search(r"(?<!Custodiante[:\s])CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        info["cnpj"] = cnpj.group(1) if cnpj else "N/A"
        
        custodian = re.search(r"CNPJ Custodiante[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if custodian:
            info["custodian_cnpj"] = custodian.group(1)
        
        if "Autocustodiante" in raw_text:
            info["self_custodian"] = "Sim" in raw_text.split("Autocustodiante")[1][:10]
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.\d{3}\.\d{3}-\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        return info
    
    def _extract_generic_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj:
            info["cnpj"] = cnpj.group(1)
        
        return info
    
    def _extract_bank_info_from_description(self, info: dict, description: str) -> None:
        """
        Extrai bank e account da descrição quando não existem nos metadados estruturados.
        Usado como fallback para itens que não têm linha "Banco:", "Agência:", "Conta:".
        """
        if not description:
            return
        
        desc_upper = description.upper()
        
        # Extrair account de padrões como "C/C 27509-3", "C/C 10461-2"
        if info.get("account") is None:
            # Padrão: C/C seguido de número com hífen
            account_match = re.search(r"C\s*/\s*C\s*([\d]+-[\d]+)", desc_upper)
            if account_match:
                info["account"] = account_match.group(1)
        
        # Inferir bank do nome do banco na descrição
        if info.get("bank") is None:
            bank_patterns = [
                (r"SICREDI|COOP\.?\s*CRED\.?\s*POUP|SICRED", "748"),
                (r"BCO\.?\s*BRASIL|BB\s*SA|BANCO\s+DO\s+BRASIL", "001"),
                (r"CEF|CAIXA\s*ECON[OÔ]MICA", "104"),
                (r"BRADESCO", "237"),
                (r"ITA[UÚ]", "341"),
                (r"SANTANDER", "033"),
                (r"SAFRA", "422"),
                (r"FIBRA", "224"),
                (r"AMAZONIA|BASA", "003"),
                (r"RABOBANK", "747"),
            ]
            for pattern, bank_code in bank_patterns:
                if re.search(pattern, desc_upper):
                    info["bank"] = bank_code
                    break
    
    def _find_beneficiary(self, lines: list[str]) -> Optional[str]:
        for line in lines:
            if "Bem" in line and "Titular" in line:
                return "Titular"
            if "Bem" in line and "Dependente" in line:
                return "Dependente"
        return None
    
    def _is_description_continuation(self, line: str) -> bool:
        # NOTA: "CPF" foi removido de skip_prefixes pois linhas como
        # "CPF 593380401-00, POR FORCA DE CONTRATO PARTICULAR DE"
        # são parte da descrição narrativa, não metadados.
        # Metadados de CPF são tratados separadamente abaixo.
        skip_prefixes = (
            "Bem", "Inscrição", "Logradouro", "Comp", "Município",
            "Área", "Registrado", "Nome Cartório", "Nº", "RENAVAM",
            "Registro de Embarcação", "Registro de Aeronave", "Matrícula",
            "Banco", "8anco", "Agência",
            "Conta", "Negociados", "Código de Neg", "Autocustodiante",
            "CNPJ", "Lucro ou", "Valor Recebido", "Imposto",
            "CEI", "CNO", "CEI/CNO", "CEP", "Aplicação Financeira", "UF",
            "Bairro", "Data de Aquisição", "CNPJ do Fundo", "CNPJ Custodiante",
            "CIB", "Nirf", "Opção pela", "Opcao pela", "Opgao pela"
        )
        
        if not line or len(line) <= 3:
            return False
        
        if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", line):
            return False
        
        if re.match(r"^\d+$", line):
            return False
        
        # Bug #86842: Linhas que são apenas valores monetários US-format não são descrição
        # Ex: "200,000.00", "180,000.00", "16,000.00"
        if re.match(r"^\d[\d,]*\.\d{2}\s*$", line):
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
        
        if re.match(
            r"^\d{1,4}[.,]?\d{0,3}\s*,?\s+de\s+\d{4}\s*:\s*(?:Sim|N[ãa]o)\s*$",
            line,
            re.IGNORECASE,
        ):
            return False
        
        # Linhas que começam com número seguido de hífen são continuação de descrição
        # Ex: "250 - MOTOR 1812CC - CHASSI F3X"
        if re.match(r"^\d+\s*-\s*[A-Z]", line):
            return True
        
        return True
    
    def _extract_orphan_address_lines(self, page_text: str) -> list[str]:
        lines = page_text.split("\n")
        orphan_lines = []
        started = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if "GRUPO" in line and "CÓDIGO" in line:
                started = True
                continue
            
            if not started:
                continue
            
            if re.match(r"^(?:\d+\s+)?\d{2}\s+\d{2}\s+", line):
                break
            
            # Inclui campos de endereço E campos bancários
            orphan_prefixes = [
                "Logradouro", "Comp", "Município", "Área", "Bairro", "UF", "CEP", 
                "Data de Aquisição", "Banco", "Agência", "Conta"
            ]
            if any(prefix in line for prefix in orphan_prefixes):
                orphan_lines.append(line)
        
        return orphan_lines
    
    def _update_item_with_orphan_lines(self, item: dict, orphan_lines: list[str]) -> None:
        info = item.get("additional_info", {})
        if not info:
            return
        
        for line in orphan_lines:
            if "Logradouro" in line:
                m = re.search(r"Logradouro[:\s]*(.+?)(?:\s+Nº[:\s]|$)", line)
                if m:
                    info["street_address"] = m.group(1).strip() or "N/A"
                
                m = re.search(r"Nº[:\s]*(\S+)", line)
                if m:
                    info["number"] = m.group(1).strip() or "N/A"
            
            if "Comp" in line:
                m = re.search(r"Comp[^:]*[:\s]*(.+?)(?:\s+Bairro[:\s]|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2 and val not in (":", "Bairro:", "Bairro"):
                        info["complement"] = val
            
            if "Bairro" in line:
                m = re.search(r"Bairro[:\s]*(.+?)(?:\s+UF[:\s]|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 2 and val != ":":
                        info["neighborhood"] = val
            
            if "Município" in line:
                m = re.search(r"Município[:\s]*(.+?)(?:\s+UF[:\s]|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val:
                        info["city"] = val
            
            if "UF" in line:
                m = re.search(r"UF[:\s]*([A-Z]{2})", line)
                if m:
                    info["state"] = m.group(1)
            
            if "CEP" in line:
                m = re.search(r"CEP[:\s]*([\d-]+)", line)
                if m:
                    info["zipcode"] = m.group(1).strip()
            
            if "Área" in line:
                m = re.search(r"Área[^:]*[:\s]*([\d.,]+\s*m²?)", line)
                if m:
                    info["area"] = m.group(1).strip()
            
            if "Data de Aquisição" in line:
                m = re.search(r"Data de Aquisição[:\s]*(\d{2}/\d{2}/\d{4})", line)
                if m:
                    info["acquisition_date"] = m.group(1)
            
            # Campos bancários órfãos (quando a quebra de página separa do item)
            if re.search(r"[B8]anco", line):
                m = re.search(r"[B8]anco[:\s]*(\d+)", line)
                if m:
                    info["bank"] = m.group(1)
            
            if "Agência" in line:
                m = re.search(r"Ag[êe]ncia[:\s]*(\d+[-\d]*)", line)
                if m:
                    info["agency"] = m.group(1)
            
            if "Conta" in line and "Conta Pagamento" not in line:
                m = re.search(r"Conta[:\s]*([\d-]+)", line)
                if m:
                    info["account"] = m.group(1)
