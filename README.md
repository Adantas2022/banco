# banco

"""Extrator de bens da atividade rural."""

import json
import os
import re
import unicodedata
from typing import Any

from irpf_processor.shared.logging import get_logger

from ...table_extractor import generate_item_id, parse_currency, sum_currency_values
from ...validation_utils import create_validated_total
from ..base import ExtractionContext, ISectionExtractor

logger = get_logger(__name__)

_ITEM_2VAL_RE = re.compile(r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$")
_ITEM_1VAL_RE = re.compile(r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s*$")
_PURE_VALUES_RE = re.compile(r"^[\d.,]+\s+[\d.,]+$")
_DIGITS_ONLY_RE = re.compile(r"^[\d.,/]+$")
_TOTAL_ROW_RE = re.compile(r"^TOTAL\s+[\d.,]+(?:\s+[\d.,]+)?\s*$", re.IGNORECASE)
_CURRENCY_VAL_RE = re.compile(r"\d[\d.,]*[.,]\d{2}")
_THOUSAND_BR_RE = re.compile(r"\d{1,3}(?:.\d{3})+,\d{2}") 
_VALUE_EPS = 0.005

# Bug #16736: linhas de continuação com estrutura "NN <texto> <valor>" geravam
# itens inexistentes (ex: "12 DE ABRIL DE 2022 R$ 50.000,00" vira item código 12
# com desc "DE ABRIL DE 2022 R$"). Descrições reais de bens rurais começam com
# substantivo (CASA, TRATOR, FAZENDA, COLHEITADEIRA…); fragmentos de continuação
# começam com preposição/artigo/conector/mês/marcador-de-valor.
_CONTINUATION_FIRST_WORDS = frozenset(
    {
        "DE", "DA", "DO", "DAS", "DOS", "EM", "NO", "NA", "NOS", "NAS", "POR",
        "PRO", "PARA", "ATE", "ATÉ", "AO", "AOS", "E", "OU", "COM", "CONTRA",
        "CONFORME", "CFE", "R$", "US$", "$", "NF", "VCTO", "ADQ", "ADQUIRIDA",
        "ADQUIRIDO", "FINANCIADO", "FINANCIADA", "SALDO", "VALOR", "MOD",
        "MODELO", "CHASSI", "ANO", "JANEIRO", "FEVEREIRO", "MARCO", "MARÇO",
        "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO",
        "NOVEMBRO", "DEZEMBRO",
    }
)


def _desc_looks_like_continuation(desc: str) -> bool:
    """True if desc starts with a preposition/conector/date-fragment — indicates
    continuation line wrongly picked as a new item."""
    parts = desc.split(maxsplit=1)
    if not parts:
        return False
    first = parts[0].upper().rstrip(",.;:")
    return first in _CONTINUATION_FIRST_WORDS


class RuralAssetsExtractor(ISectionExtractor):
    """Extrai bens da atividade rural."""

    SECTION_MARKER = "BENS DA ATIVIDADE RURAL"
    SECTION_MARKERS = ["BENS DA ATIVIDADE RURAL"]

    SECTION_END_MARKERS = [
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL",
        "BENS DA ATIVIDADE RURAL - EXTERIOR",
        "DEMONSTRATIVO DE ATIVIDADE RURAL - EXTERIOR",
    ]

    LLM_PROMPT = """
                ================================================================
                SEÇÃO - BENS DA ATIVIDADE RURAL (BRASIL)
                ================================================================
                REGRA: liste TODOS os bens da atividade rural da seção BRASIL.
                Cada linha da tabela = um objeto separado. Não omita nenhum item.

                {
                    "items": [
                        {
                            "code": "string (código do bem, 2 dígitos, ex: '11', '16')",
                            "description": "string - copie o texto EXATO da coluna discriminação",
                            "year_before_last_value": numero,
                            "last_year_value": numero,
                            "page": numero
                        }
                    ],
                    "year_before_last_total_value": numero,
                    "last_year_total_value": numero
                }

                REGRAS:
                - Extraia APENAS bens da seção "BENS DA ATIVIDADE RURAL - BRASIL"
                - NÃO inclua itens da seção "EXTERIOR"
                - O campo "code" deve ser STRING (ex: "11", "16", "99")
                - Valores monetários devem ser NÚMEROS (ex: 87624.85, não "87.624,85")
                - Se a descrição de um item ocupa múltiplas linhas, junte em uma única string
                - A página é encontrada no rodapé: "Página X de Y" (ex: page=3)
                """

    def __init__(self) -> None:
        super().__init__()
        self._section_started = False
        self._section_start_page = -1

    @property
    def section_name(self) -> str:
        return "rural_activity_assets_in_brazil"

    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()

    async def extract_with_llm(
        self,
        context: ExtractionContext,
        custom_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        try:
            extraction_result = await self.get_llm_extraction_data(context, custom_prompt)

            if not extraction_result or not isinstance(extraction_result, list):
                logger.warning(
                    "llm_extraction_no_data",
                    section_name=self.section_name,
                    reason="no_chunks_returned",
                    document_id=context.document_id,
                )
                return None

            section_pages = self.extract_section_pages(context)
            page_range = sorted(section_pages.keys()) if section_pages else []

            debug_base = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                ),
                "tmp",
                context.document_id or "unknown",
            )
            debug_chunks_dir = os.path.join(debug_base, "chunks", "rural_assets")
            debug_result_dir = os.path.join(debug_base, "result", "rural_assets")
            os.makedirs(debug_chunks_dir, exist_ok=True)
            os.makedirs(debug_result_dir, exist_ok=True)

            for idx, chunk in enumerate(extraction_result):
                chunk_path = os.path.join(debug_chunks_dir, f"chunk_{idx}.json")
                with open(chunk_path, "w", encoding="utf-8") as f:
                    f.write(json.dumps(chunk, indent=2, ensure_ascii=False))

            logger.info(
                "llm_rural_assets_extraction_start",
                section_name=self.section_name,
                document_id=context.document_id,
                chunk_count=len(extraction_result),
            )

            items: list[dict[str, Any]] = []
            pdf_year_before_last_total: float | None = None
            pdf_last_year_total: float | None = None

            for chunk_idx, chunk in enumerate(extraction_result):
                if not isinstance(chunk, dict):
                    continue

                chunk_items_raw = chunk.get("items", [])
                if not isinstance(chunk_items_raw, list):
                    continue

                chunk_items_deduped: dict[str, dict[str, Any]] = {}
                for entry_idx, entry in enumerate(chunk_items_raw):
                    if not isinstance(entry, dict):
                        logger.warning(
                            "llm_non_dict_entry_skipped",
                            section_name=self.section_name,
                            chunk_index=chunk_idx,
                            entry_index=entry_idx,
                            entry_type=type(entry).__name__,
                        )
                        continue

                    normalized = self._normalize_llm_item(entry, page_range)
                    chunk_items_deduped[normalized["id"]] = normalized

                chunk_items = list(chunk_items_deduped.values())

                if chunk_idx > 0 and chunk_items:
                    overlap_page = chunk_items[0].get("page")
                    if overlap_page is not None:
                        items = [it for it in items if it.get("page") != overlap_page]

                items.extend(chunk_items)

                logger.debug(
                    "llm_rural_assets_chunk_processed",
                    chunk_index=chunk_idx,
                    chunk_item_count=len(chunk_items),
                    overlap_pages=(
                        [chunk_items[0].get("page")] if chunk_idx > 0 and chunk_items else []
                    ),
                )

                if chunk.get("year_before_last_total_value") is not None:
                    pdf_year_before_last_total = self._parse_llm_currency(
                        chunk["year_before_last_total_value"]
                    )
                if chunk.get("last_year_total_value") is not None:
                    pdf_last_year_total = self._parse_llm_currency(chunk["last_year_total_value"])

            merged_path = os.path.join(debug_result_dir, "merged.json")
            with open(merged_path, "w", encoding="utf-8") as f:
                f.write(
                    json.dumps(
                        {
                            "items": items,
                            "year_before_last_total_value": pdf_year_before_last_total,
                            "last_year_total_value": pdf_last_year_total,
                            "chunks_count": len(extraction_result),
                            "items_count": len(items),
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )

            if not items and pdf_year_before_last_total is None and pdf_last_year_total is None:
                logger.warning(
                    "llm_extraction_empty_result",
                    section_name=self.section_name,
                    reason="no_items_no_totals",
                    document_id=context.document_id,
                )
                return None

            sum_before = sum_currency_values(
                [i["year_before_last_value"] for i in items], as_int=False
            )
            sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)

            totals = {
                "year_before_last_value": create_validated_total(
                    sum_before, pdf_year_before_last_total
                ),
                "last_year_value": create_validated_total(sum_last, pdf_last_year_total),
            }

            logger.info(
                "llm_rural_assets_extraction_complete",
                section_name=self.section_name,
                document_id=context.document_id,
                item_count=len(items),
                extraction_method="llm",
            )

            return {
                "section_name": "Bens da Atividade Rural - Brasil",
                "items": items,
                "total_values": totals,
                "extraction_method": "llm",
            }

        except Exception as exc:
            logger.warning(
                "llm_extraction_failed",
                section_name=self.section_name,
                error_type=type(exc).__name__,
                error_message=str(exc),
                document_id=context.document_id,
            )
            return None

    def _normalize_llm_item(self, item: dict[str, Any], page_range: list[int]) -> dict[str, Any]:
        code = str(item.get("code", "")).strip()
        if not code or not code.isdigit() or int(code) > 99:
            logger.warning(
                "llm_invalid_item_code",
                section_name=self.section_name,
                code=code,
            )

        description = str(item.get("description", "")).strip()
        description = re.sub(r"\s+", " ", description)

        before_val = self._parse_llm_currency(item.get("year_before_last_value"))
        last_val = self._parse_llm_currency(item.get("last_year_value"))

        if before_val > 1_000_000_000:
            logger.warning(
                "llm_currency_exceeds_limit",
                section_name=self.section_name,
                field="year_before_last_value",
                value=before_val,
            )
            before_val = 0.0
        if last_val > 1_000_000_000:
            logger.warning(
                "llm_currency_exceeds_limit",
                section_name=self.section_name,
                field="last_year_value",
                value=last_val,
            )
            last_val = 0.0

        page = item.get("page", 0)
        if isinstance(page, str):
            try:
                page = int(page)
            except (ValueError, TypeError):
                page = 0

        if page_range:
            if page <= 0:
                logger.warning(
                    "llm_invalid_page_number",
                    section_name=self.section_name,
                    page=page,
                    action="clamped_to_first",
                )
                page = page_range[0]
            elif page < page_range[0]:
                page = page_range[0]
            elif page > page_range[-1]:
                page = page_range[-1]

        nfkd_desc = unicodedata.normalize("NFKD", description).lower()
        nfkd_desc = re.sub(r"\s+", " ", nfkd_desc).strip()
        item_id = generate_item_id(f"{code}{nfkd_desc[:30]}")

        return {
            "code": code,
            "description": description,
            "year_before_last_value": before_val,
            "last_year_value": last_val,
            "id": item_id,
            "page": page,
        }

    def extract(self, context: ExtractionContext) -> dict[str, Any] | None:
        items = []
        pdf_totals = []
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])

        in_section = False
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()

            if (
                self.SECTION_MARKER in upper_text
                and "BRASIL" in upper_text
                and "EXTERIOR" not in upper_text
            ):
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
            "last_year_value": create_validated_total(sum_last, pdf_last),
        }

        return {
            "section_name": "Bens da Atividade Rural - Brasil",
            "items": items,
            "total_values": totals,
        }

    @staticmethod
    def _strip_accents(text: str) -> str:
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")

    def _find_end_marker_line(self, page_text: str) -> int | None:
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
        self, page_text: str, page_num: int, end_line_index: int | None = None
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
                desc_candidate = match_2v.group(2).strip()
                if not _desc_looks_like_continuation(desc_candidate):
                    item = self._parse_asset(match_2v, lines, i, page_num, max_line)
                    if item:
                        items.append(item)
                        i = item.pop("_next_index", i + 1)
                        continue

            match_1v = _ITEM_1VAL_RE.match(line)
            if match_1v:
                desc_candidate = match_1v.group(2).strip()
                if (
                    len(desc_candidate) >= 3
                    and not _DIGITS_ONLY_RE.match(desc_candidate)
                    and not _desc_looks_like_continuation(desc_candidate)
                ):
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

            if _TOTAL_ROW_RE.match(next_line):
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



    @staticmethod def _collect_monetary_tokens_no_percent(text: str) -> list[str]: 
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
        max_line: int | None = None,
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
            "_next_index": j,
        }

    def _parse_asset_1val(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int,
        max_line: int | None = None,
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
            "year_before_last_value": single_val,
            "last_year_value": single_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j,
        }

    def _normalize_description(self, desc: str) -> str:
        normalized = re.sub(r"\s+", " ", desc)
        return normalized.strip()

    def _extract_section_total(
        self, page_text: str, end_line_index: int | None = None
    ) -> list[float]:
        """Extrai o TOTAL específico da seção de Bens Rurais."""
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})"

        max_line = end_line_index if end_line_index is not None else len(lines)

        for i, line in enumerate(lines):
            if i >= max_line:
                break

            upper_line = line.upper()

            if (
                self.SECTION_MARKER in upper_line
                and "BRASIL" in upper_line
                and "EXTERIOR" not in upper_line
            ):
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
