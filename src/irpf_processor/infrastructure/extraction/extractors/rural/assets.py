"""Extrator de bens da atividade rural."""

import re
import unicodedata
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id, sum_currency_values
from ...validation_utils import create_validated_total


_ITEM_2VAL_RE = re.compile(r"^(\d{1,2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$")
_ITEM_1VAL_RE = re.compile(r"^(\d{1,2})\s+(.+?)\s+([\d.,]+)\s*$")
_PURE_VALUES_RE = re.compile(r"^[\d.,]+\s+[\d.,]+$")
_DIGITS_ONLY_RE = re.compile(r"^[\d.,/]+$")


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
        pdf_totals = []
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])

        in_section = False
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()

            if self.SECTION_MARKER in upper_text and "BRASIL" in upper_text and "EXTERIOR" not in upper_text:
                in_section = True

            if in_section:
                end_line_index = self._find_end_marker_line(page_text)

                page_items = self._extract_from_page(page_text, page_num, end_line_index)
                items.extend(page_items)

                if not pdf_totals:
                    page_totals = self._extract_section_total(page_text, end_line_index)
                    if page_totals:
                        pdf_totals = page_totals

                if end_line_index is not None:
                    break

        if not items:
            return None

        sum_before = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)

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

    @staticmethod
    def _strip_accents(text: str) -> str:
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")

    def _find_end_marker_line(self, page_text: str) -> Optional[int]:
        """Encontra o índice da linha onde aparece um marcador de fim de seção."""
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            upper_line = self._strip_accents(line.upper())
            for marker in self.SECTION_END_MARKERS:
                upper_marker = self._strip_accents(marker.upper())
                if upper_marker in upper_line:
                    return i
        return None

    def _extract_from_page(
        self,
        page_text: str,
        page_num: int,
        end_line_index: Optional[int] = None
    ) -> list[dict]:
        """Extrai itens de uma página."""
        items = []
        lines = page_text.split("\n")
        max_line = end_line_index if end_line_index is not None else len(lines)

        i = 0
        while i < max_line:
            line = lines[i].strip()
            upper_line = line.upper()

            if "CÓDIGO" in upper_line or upper_line.startswith("TOTAL"):
                i += 1
                continue

            match_2v = _ITEM_2VAL_RE.match(line)
            if match_2v:
                item = self._parse_asset(match_2v, lines, i, page_num, max_line)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue

            match_1v = _ITEM_1VAL_RE.match(line)
            if match_1v:
                desc_candidate = match_1v.group(2).strip()
                if len(desc_candidate) >= 3 and not _DIGITS_ONLY_RE.match(desc_candidate):
                    item = self._parse_asset_1val(
                        match_1v, lines, i, page_num, max_line
                    )
                    if item:
                        items.append(item)
                        i = item.pop("_next_index", i + 1)
                        continue

            i += 1

        return items

    def _collect_description_lines(
        self, lines: list[str], start: int, max_line: int
    ) -> tuple[list[str], int]:
        """Coleta linhas de continuação da descrição de um item.

        Returns:
            Tupla (desc_parts, next_index) onde desc_parts são as linhas
            de continuação e next_index é o índice da próxima linha a processar.
        """
        desc_parts: list[str] = []
        j = start

        while j < max_line:
            next_line = lines[j].strip()

            if next_line.upper().startswith("TOTAL"):
                break

            if _ITEM_2VAL_RE.match(next_line) and "CÓDIGO" not in next_line.upper():
                break

            match_1v = _ITEM_1VAL_RE.match(next_line)
            if match_1v and "CÓDIGO" not in next_line.upper():
                desc_cand = match_1v.group(2).strip()
                if len(desc_cand) >= 3 and not _DIGITS_ONLY_RE.match(desc_cand):
                    break

            if re.match(r"^Página\s+\d+\s+de", next_line, re.IGNORECASE):
                j += 1
                continue

            if next_line and not _PURE_VALUES_RE.match(next_line):
                desc_parts.append(next_line)

            j += 1

        return desc_parts, j

    def _build_description(self, desc_parts: list[str]) -> str:
        """Constrói descrição final a partir das partes coletadas."""
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"^\d{2}/\d{2}/\d{4}\s+\d{2}/\d{2}/\d{4}\s*", "", full_desc)
        full_desc = re.sub(r"^\d{2}/\d{2}/\d{4}\s*", "", full_desc)
        full_desc = re.sub(r"^\d{4}/\d{4}\s+", "", full_desc)
        full_desc = re.sub(r"^CHASSI\s+[A-Z0-9]+\s*", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"^[A-Z0-9]{15,}\s+", "", full_desc)
        return re.sub(r"\s+", " ", full_desc).strip()

    def _parse_asset(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int,
        max_line: Optional[int] = None
    ) -> dict:
        """Parse um item de bem da atividade rural."""
        code = match.group(1)
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))

        line_limit = max_line if max_line is not None else len(lines)
        continuation, j = self._collect_description_lines(lines, idx + 1, line_limit)

        full_desc = self._build_description([desc_start] + continuation)
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

    def _parse_asset_1val(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int,
        max_line: Optional[int] = None,
    ) -> dict:
        """Parse item com apenas 1 valor (OCR perdeu uma coluna)."""
        code = match.group(1)
        desc_start = match.group(2).strip()
        single_val = parse_currency(match.group(3))

        line_limit = max_line if max_line is not None else len(lines)
        continuation, j = self._collect_description_lines(lines, idx + 1, line_limit)

        full_desc = " ".join([desc_start] + continuation)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()

        normalized_desc = self._normalize_description(full_desc)
        item_id = generate_item_id(f"{code}{normalized_desc[:30]}")

        return {
            "code": code,
            "description": full_desc,
            "year_before_last_value": single_val,
            "last_year_value": single_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j,
        }

    def _normalize_description(self, desc: str) -> str:
        normalized = re.sub(r"\s+", " ", desc)
        return normalized.strip()

    def _extract_section_total(self, page_text: str, end_line_index: Optional[int] = None) -> list[float]:
        """Extrai o TOTAL específico da seção de Bens Rurais."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'

        max_line = end_line_index if end_line_index is not None else len(lines)

        for i, line in enumerate(lines):
            if i >= max_line:
                break

            upper_line = line.upper()

            if self.SECTION_MARKER in upper_line and "BRASIL" in upper_line and "EXTERIOR" not in upper_line:
                in_section = True
                continue

            if not in_section:
                continue

            if upper_line.strip().startswith("TOTAL"):
                matches = re.findall(num_pattern, line)
                if matches:
                    return [self._parse_currency(m) for m in matches]

        return []

    def _parse_currency(self, value_str: str) -> float:
        return parse_currency(value_str)
