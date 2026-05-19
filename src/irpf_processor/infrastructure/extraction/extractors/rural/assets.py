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
_CURRENCY_VAL_RE = re.compile(r"\d[\d.,]*[.,]\d{2}")
_THOUSAND_BR_RE = re.compile(r"\d{1,3}(?:\.\d{3})+,\d{2}")
_VALUE_EPS = 0.005


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

    @staticmethod
    def _collect_monetary_tokens_no_percent(text: str) -> list[str]:
        out: list[str] = []
        for m in _CURRENCY_VAL_RE.finditer(text):
            rest = text[m.end():].lstrip()
            if rest.startswith("%"):
                continue
            out.append(m.group(0))
        return out

    @staticmethod
    def _token_financially_significant(tok: str, val: float) -> bool:
        if abs(val) < _VALUE_EPS:
            return False
        if val >= 1000.0:
            return True
        return bool(_THOUSAND_BR_RE.search(tok))

    @staticmethod
    def _remove_amount_tokens_from_end(text: str, tokens: list[str]) -> str:
        result = text
        for tok in reversed(tokens):
            pos = result.rfind(tok)
            if pos < 0:
                continue
            left = result[:pos].rstrip()
            right = result[pos + len(tok):].lstrip()
            if left and right:
                result = f"{left} {right}"
            else:
                result = left or right
        return re.sub(r"\s+", " ", result).strip()

    def _maybe_recover_zero_columns(
        self,
        first_line: str,
        full_desc: str,
        before_val: float,
        last_val: float,
    ) -> tuple[float, float, str]:
        if abs(before_val) >= _VALUE_EPS or abs(last_val) >= _VALUE_EPS:
            return before_val, last_val, full_desc

        tokens_line = self._collect_monetary_tokens_no_percent(first_line)
        p_line = [parse_currency(t) for t in tokens_line]
        if (
            len(tokens_line) >= 3
            and abs(p_line[-1]) < _VALUE_EPS
            and abs(p_line[-2]) < _VALUE_EPS
        ):
            t_core = list(tokens_line[:-2])
            p_core = list(p_line[:-2])
            while t_core and abs(p_core[-1]) < _VALUE_EPS:
                t_core.pop()
                p_core.pop()
            if t_core:
                if len(t_core) >= 2:
                    nb = parse_currency(t_core[-2])
                    nl = parse_currency(t_core[-1])
                    strip_tokens = [t_core[-2], t_core[-1]]
                else:
                    nb = nl = parse_currency(t_core[-1])
                    strip_tokens = [t_core[-1]]
                if abs(nb) >= _VALUE_EPS or abs(nl) >= _VALUE_EPS:
                    nd = self._remove_amount_tokens_from_end(full_desc, strip_tokens)
                    return nb, nl, self._normalize_description(nd)

        tokens_desc = self._collect_monetary_tokens_no_percent(full_desc)
        p_desc = [parse_currency(t) for t in tokens_desc]
        td = list(tokens_desc)
        pd = list(p_desc)
        while td and abs(pd[-1]) < _VALUE_EPS:
            td.pop()
            pd.pop()
        if not td:
            return before_val, last_val, full_desc
        if len(td) >= 2:
            t1, t2 = td[-2], td[-1]
            v1, v2 = parse_currency(t1), parse_currency(t2)
            if not (
                self._token_financially_significant(t1, v1)
                or self._token_financially_significant(t2, v2)
            ):
                return before_val, last_val, full_desc
            nb, nl = v1, v2
            strip_tokens = [t1, t2]
        else:
            t1 = td[-1]
            v1 = parse_currency(t1)
            if not self._token_financially_significant(t1, v1):
                return before_val, last_val, full_desc
            nb = nl = v1
            strip_tokens = [t1]
        nd = self._remove_amount_tokens_from_end(full_desc, strip_tokens)
        return nb, nl, self._normalize_description(nd)

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
        before_val, current_val, full_desc = self._maybe_recover_zero_columns(
            lines[idx].strip(), full_desc, before_val, current_val
        )
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

        if abs(single_val) < _VALUE_EPS:
            year_before_val, last_year_val, full_desc = self._maybe_recover_zero_columns(
                lines[idx].strip(), full_desc, single_val, single_val
            )
        else:
            year_before_val = last_year_val = single_val

        normalized_desc = self._normalize_description(full_desc)
        item_id = generate_item_id(f"{code}{normalized_desc[:30]}")

        return {
            "code": code,
            "description": full_desc,
            "year_before_last_value": year_before_val,
            "last_year_value": last_year_val,
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
