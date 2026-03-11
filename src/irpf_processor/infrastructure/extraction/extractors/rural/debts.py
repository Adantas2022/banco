"""Extrator de dívidas da atividade rural."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id, sum_currency_values
from ...validation_utils import extract_section_total, create_validated_total


_WATERMARK_WORDS = {"PROTEGIDA", "SIGILO", "FISCAL", "SIGN", "SIGILOFISCAL"}

_ITEM_3VAL_RE = re.compile(
    r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$"
)
_ITEM_2VAL_RE = re.compile(
    r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$"
)
_ITEM_START_RE = re.compile(r"^(\d{1,3})\s+")

# Padrão para extrair valores monetários do final da linha (fallback robusto)
_CURRENCY_VAL_RE = re.compile(r"\d[\d.,]*[.,]\d{2}")


class RuralDebtsExtractor(ISectionExtractor):
    """Extrai dívidas vinculadas à atividade rural."""
    
    SECTION_MARKER = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL"
    
    @property
    def section_name(self) -> str:
        return "rural_activity_debts_in_brazil"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        pdf_totals: list[float] = []
        
        for page_num, page_text in context.pages_text.items():
            upper_text = page_text.upper()
            
            if self.SECTION_MARKER not in upper_text:
                continue
            
            if "EXTERIOR" in upper_text and "BRASIL" not in upper_text:
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
            
            if not pdf_totals:
                page_totals = self._extract_section_total(page_text)
                if page_totals:
                    pdf_totals = page_totals
        
        if not items:
            return None
        
        sum_before = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        sum_paid = sum_currency_values([i["paid_value_in_last_year"] for i in items], as_int=False)
        
        # Atribuir pdf_totals às colunas corretas.
        # Quando o OCR perde 1 dos 3 valores do TOTAL, precisamos
        # identificar qual coluna cada valor pertence via matching
        # contra as somas dos itens.
        pdf_before, pdf_last, pdf_paid = self._match_totals_to_columns(
            pdf_totals, sum_before, sum_last, sum_paid
        )
        
        totals = {
            "year_before_last_value": create_validated_total(sum_before, pdf_before),
            "last_year_value": create_validated_total(sum_last, pdf_last),
            "paid_value_in_last_year": create_validated_total(sum_paid, pdf_paid)
        }
        
        return {
            "section_name": "Dívidas Vinculadas à Atividade Rural - Brasil",
            "items": items,
            "total_values": totals
        }
    
    @staticmethod
    def _match_totals_to_columns(
        pdf_totals: list[float],
        sum_before: float,
        sum_last: float,
        sum_paid: float,
    ) -> tuple[float | None, float | None, float | None]:
        """Atribui valores do TOTAL às colunas corretas.
        
        Com 3 valores, assume ordem posicional (before, last, paid).
        Com 2 valores, usa matching por menor diferença contra as somas.
        Com 0-1 valores, retorna None para os faltantes.
        """
        if len(pdf_totals) >= 3:
            return pdf_totals[0], pdf_totals[1], pdf_totals[2]
        
        if len(pdf_totals) == 0:
            return None, None, None
        
        if len(pdf_totals) == 1:
            # Tentar identificar a coluna pelo valor mais próximo
            val = pdf_totals[0]
            sums = [sum_before, sum_last, sum_paid]
            diffs = [abs(val - s) for s in sums]
            best = diffs.index(min(diffs))
            result = [None, None, None]
            result[best] = val
            return result[0], result[1], result[2]
        
        # 2 valores: testar todas as 3 combinações possíveis
        # e escolher a que minimiza a soma das diferenças
        v0, v1 = pdf_totals[0], pdf_totals[1]
        sums = [sum_before, sum_last, sum_paid]
        
        # Combinação 1: (before, last, _)
        # Combinação 2: (before, _, paid)
        # Combinação 3: (_, last, paid)
        combos = [
            ((0, 1), (v0, v1, None)),  # before=v0, last=v1
            ((0, 2), (v0, None, v1)),  # before=v0, paid=v1
            ((1, 2), (None, v0, v1)),  # last=v0, paid=v1
        ]
        
        best_score = float("inf")
        best_result = (v0, v1, None)
        
        for (i0, i1), result in combos:
            score = abs(v0 - sums[i0]) + abs(v1 - sums[i1])
            if score < best_score:
                best_score = score
                best_result = result
        
        return best_result

    
    # ------------------------------------------------------------------
    # Extração de total
    # ------------------------------------------------------------------

    def _extract_section_total(self, page_text: str) -> list[float]:
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            if self._is_section_header_line(line) and "EXTERIOR" not in upper_line:
                in_section = True
                continue
            
            if in_section and self._is_section_header_line(line) and "EXTERIOR" in upper_line:
                break
            
            if not in_section:
                continue
            
            if self._is_section_total_line(line):
                matches = re.findall(num_pattern, line)
                if matches:
                    parsed = [parse_currency(m) for m in matches]
                    # Se OCR perdeu um dos 3 valores, paddar com None
                    # para que a validação funcione parcialmente
                    return parsed
            
            # Fallback: "TOTAL" sozinho + próxima linha com ≥2 valores
            stripped = line.strip()
            if stripped.upper() == "TOTAL":
                for j in range(i + 1, min(i + 3, len(lines))):
                    next_stripped = lines[j].strip()
                    if not next_stripped:
                        continue
                    vals = _CURRENCY_VAL_RE.findall(next_stripped)
                    if len(vals) >= 2:
                        matches = re.findall(num_pattern, next_stripped)
                        return [parse_currency(m) for m in matches]
        
        return []
    
    # ------------------------------------------------------------------
    # Extração de itens
    # ------------------------------------------------------------------

    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items: list[dict] = []
        lines = page_text.split("\n")
        
        in_section = False
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            if self._is_section_header_line(line) and "EXTERIOR" not in upper_line:
                in_section = True
                i += 1
                continue
            
            if in_section and self._is_section_header_line(line) and "EXTERIOR" in upper_line:
                break
            
            if in_section and self._is_section_total_line(line):
                break
            
            if not in_section:
                i += 1
                continue
            
            if "ITEM" in upper_line and "DISCRIMINAÇÃO" in upper_line:
                i += 1
                continue
            
            cleaned = self._clean_ocr_prefix(line)
            
            m3 = _ITEM_3VAL_RE.match(cleaned)
            if m3:
                item = self._parse_debt_3val(m3, lines, i, page_num)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            # Fallback: tentar extrair 3 valores do final da linha
            # mesmo quando _ITEM_3VAL_RE falha (ex: descrição com
            # dígitos/vírgulas como '16,66%' que confundem .+?)
            item_start = _ITEM_START_RE.match(cleaned)
            if item_start and not m3:
                item = self._try_parse_trailing_3val(
                    cleaned, item_start, lines, i, page_num
                )
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            m2 = _ITEM_2VAL_RE.match(cleaned)
            if m2:
                item = self._parse_debt_2val(m2, lines, i, page_num)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items
    
    # ------------------------------------------------------------------
    # Helpers de detecção
    # ------------------------------------------------------------------

    def _is_section_total_line(self, line: str) -> bool:
        """True somente para linhas 'TOTAL  val  val  val' (total da seção).
        
        Requer ≥3 valores monetários (year_before, last_year, paid) para
        evitar falso positivo com descrições como 'TOTAL 830.317,36'.
        """
        stripped = line.strip()
        upper = stripped.upper()
        if not upper.startswith("TOTAL"):
            return False
        rest = re.sub(r"^TOTAL\s*", "", stripped, flags=re.IGNORECASE)
        if not rest.strip():
            return False  # Bug #82852: TOTAL sozinho NÃO é total de seção
        # Considerar como total se tiver ≥2 valores monetários.
        # Document AI pode perder 1 dos 3 valores devido a marca d'água.
        if re.match(r"^[\d.,\s]+$", rest):
            vals = _CURRENCY_VAL_RE.findall(rest)
            return len(vals) >= 2
        return False
    
    def _is_section_header_line(self, line: str) -> bool:
        """Distingue header de seção de itens com descrição similar.
        
        Retorna True para headers reais como:
            'DÍVIDAS VINCULADAS À ATIVIDADE RURAL - BRASIL (Valores em Reais)'
        Retorna False para itens cujo texto contém o marker:
            '1 DÍVIDAS VINCULADAS À ATIVIDADE RURAL 100,000.00 120,000.00 20,000.00'
        """
        stripped = line.strip()
        upper = stripped.upper()
        if self.SECTION_MARKER not in upper:
            return False
        # Se a linha começa com número de item, é um item, não header
        if re.match(r"^\d{1,3}\s+", stripped):
            return False
        return True
    
    def _clean_ocr_prefix(self, line: str) -> str:
        """Remove prefixos OCR espúrios antes do número do item (ex: 'CO 6' -> '6')."""
        return re.sub(r"^[A-Z]{1,3}\s+(?=\d+\s+)", "", line.strip())
    
    def _is_watermark(self, line: str) -> bool:
        return line.strip().upper() in _WATERMARK_WORDS
    
    def _line_starts_new_item(self, line: str) -> bool:
        cleaned = self._clean_ocr_prefix(line)
        return bool(_ITEM_START_RE.match(cleaned))
    
    # ------------------------------------------------------------------
    # Parsing de itens
    # ------------------------------------------------------------------

    def _parse_debt_3val(
        self, match: re.Match, lines: list[str], idx: int, page_num: int
    ) -> dict:
        item_num = int(match.group(1))
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        paid_val = parse_currency(match.group(5))
        
        desc_parts = [desc_start]
        j = self._collect_description_lines(lines, idx + 1, desc_parts)
        full_desc = self._build_description(desc_parts)
        item_id = generate_item_id(
            f"{item_num}|{full_desc[:30]}|{before_val}|{current_val}|{paid_val}"
        )
        
        return {
            "item": item_num,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "paid_value_in_last_year": paid_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _parse_debt_2val(
        self, match: re.Match, lines: list[str], idx: int, page_num: int
    ) -> dict:
        """Parseia item com apenas 2 valores (OCR perdeu coluna year_before_last)."""
        item_num = int(match.group(1))
        desc_start = match.group(2).strip()
        val1 = parse_currency(match.group(3))
        val2 = parse_currency(match.group(4))
        
        desc_parts = [desc_start]
        j = self._collect_description_lines(lines, idx + 1, desc_parts)
        full_desc = self._build_description(desc_parts)
        item_id = generate_item_id(f"{item_num}|{full_desc[:30]}|{val1}|{val2}")
        
        return {
            "item": item_num,
            "description": full_desc,
            "year_before_last_value": 0.0,
            "last_year_value": val1,
            "paid_value_in_last_year": val2,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _try_parse_trailing_3val(
        self,
        cleaned: str,
        item_start: re.Match,
        lines: list[str],
        idx: int,
        page_num: int,
    ) -> Optional[dict]:
        """Fallback robusto: extrai 3 valores monetários do final da linha.
        
        Usado quando _ITEM_3VAL_RE falha (ex: descrição contém
        dígitos/vírgulas como '16,66%' que confundem o lazy .+?).
        Usa re.findall para encontrar todos os padrões monetários
        e pega os 3 últimos.
        """
        all_vals = _CURRENCY_VAL_RE.findall(cleaned)
        if len(all_vals) < 3:
            return None
        
        # Os 3 últimos valores são: before, current, paid
        v1_str, v2_str, v3_str = all_vals[-3], all_vals[-2], all_vals[-1]
        
        # Encontrar onde o primeiro dos 3 valores começa na linha
        # para separar a descrição
        v1_pos = cleaned.rfind(v1_str, 0, cleaned.rfind(v2_str))
        if v1_pos < 0:
            v1_pos = cleaned.find(v1_str)
        
        item_num = int(item_start.group(1))
        desc_start = cleaned[item_start.end():v1_pos].strip()
        
        if not desc_start:
            return None
        
        before_val = parse_currency(v1_str)
        current_val = parse_currency(v2_str)
        paid_val = parse_currency(v3_str)
        
        desc_parts = [desc_start]
        j = self._collect_description_lines(lines, idx + 1, desc_parts)
        full_desc = self._build_description(desc_parts)
        item_id = generate_item_id(
            f"{item_num}|{full_desc[:30]}|{before_val}|{current_val}|{paid_val}"
        )
        
        return {
            "item": item_num,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "paid_value_in_last_year": paid_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    # ------------------------------------------------------------------
    # Coleta de descrição
    # ------------------------------------------------------------------

    def _collect_description_lines(
        self, lines: list[str], start: int, desc_parts: list[str]
    ) -> int:
        j = start
        while j < len(lines):
            next_line = lines[j].strip()
            
            if self._line_starts_new_item(next_line):
                break
            
            if self._is_section_total_line(next_line):
                break
            
            if self._is_section_header_line(next_line):
                break
            
            if re.match(r"^Página\s+\d+\s+de", next_line, re.IGNORECASE):
                j += 1
                continue
            
            if self._is_watermark(next_line):
                j += 1
                continue
            
            is_pure_values = (
                re.match(r"^[\d.,\s]+$", next_line) and "," in next_line
            )
            if next_line and not is_pure_values:
                desc_parts.append(next_line)
            
            j += 1
        return j
    
    def _build_description(self, desc_parts: list[str]) -> str:
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(
            r"\s*Página\s+\d+\s+de\s*\d+\s*", " ", full_desc, flags=re.IGNORECASE
        )
        for wm in _WATERMARK_WORDS:
            full_desc = re.sub(rf"\b{wm}\b", "", full_desc, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", full_desc).strip()
