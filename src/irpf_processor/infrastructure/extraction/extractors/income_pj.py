"""Extrator de rendimentos tributáveis de pessoa jurídica."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id
from ..validation_utils import extract_section_total, create_validated_total


_NUM = r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})"
_NAME_CHAR = r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d]"
_NAME_CONT = r"[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\d\s.,\-/&]"
_CNPJ_RE = re.compile(
    r"(\d{2}\.\d{3}\.\d{3})\s*/\s*(\d{4}-\d{2})|(\d{3}\.\d{3}\.\d{3}-\d{2})"
)

_LINE_5VAL_RE = re.compile(
    rf"^({_NAME_CHAR}{_NAME_CONT}+?)\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s*$"
)
_LINE_4VAL_RE = re.compile(
    rf"^({_NAME_CHAR}{_NAME_CONT}+?)\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s*$"
)
_LINE_4VAL_ONLY_RE = re.compile(
    rf"^{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s*$"
)
_LINE_NAME_1VAL_RE = re.compile(
    rf"^({_NAME_CHAR}{_NAME_CONT}+?)\s+{_NUM}\s*$"
)
_MONEY_RE = re.compile(_NUM)


def _find_cnpj(line: str) -> str:
    m = _CNPJ_RE.search(line)
    if not m:
        return ""
    if m.group(3):
        return m.group(3)
    return f"{m.group(1)}/{m.group(2)}"


class IncomePJExtractor(ISectionExtractor):
    """Extrai rendimentos tributáveis de pessoa jurídica pelo titular."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELO TITULAR"
    ]
    HOLDER_MARKER = "PELO TITULAR"
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES",
        "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELOS DEPENDENTES",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "PAGAMENTOS EFETUADOS"
    ]
    
    @property
    def section_name(self) -> str:
        return "income_from_legal_person_to_holder"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals: list[float] = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            page_items = self._extract_from_page(
                page_text=page_text,
                page_num=page_num,
                seen_ids=seen_ids,
                assume_in_section=in_section,
            )
            items.extend(page_items)
            
            if not pdf_totals:
                page_totals = self._extract_totals_with_ocr_fallback(page_text)
                if page_totals:
                    pdf_totals = page_totals
            
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
        if not items:
            return None
        
        totals = self._calculate_totals(items, pdf_totals)
        
        return {
            "section_name": "Rendimentos Tributáveis Recebidos de Pessoa Jurídica pelo Titular",
            "items": items,
            "total_values": totals
        }
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        upper_text = page_text.upper()
        return any(marker in upper_text for marker in self.SECTION_END_MARKERS)
    
    def _extract_from_page(
        self,
        page_text: str,
        page_num: int,
        seen_ids: set,
        assume_in_section: bool = False,
    ) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        in_section = assume_in_section
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                continue
            
            if in_section:
                if any(end in upper_line for end in self.SECTION_END_MARKERS):
                    break
                if "SEM INFORMAÇÕES" in upper_line:
                    continue
            
            if "CNPJ" in upper_line or "CÓDIGO" in upper_line:
                in_section = True
                continue
            
            item = self._try_parse_income_line(line, lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
        
        return items
    
    def _try_parse_income_line(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        stripped = line.strip()
        
        m5 = _LINE_5VAL_RE.match(stripped)
        if m5:
            return self._build_item_5val(m5, lines, idx, page_num)
        
        m4 = _LINE_4VAL_RE.match(stripped)
        if m4:
            return self._build_item_4val(m4, lines, idx, page_num)

        split_item = self._try_parse_split_row(lines, idx, page_num)
        if split_item:
            return split_item
        
        return None

    def _try_parse_split_row(
        self,
        lines: list[str],
        idx: int,
        page_num: int,
    ) -> Optional[dict]:
        if idx + 1 >= len(lines):
            return None

        curr = lines[idx].strip()
        nxt = lines[idx + 1].strip()

        vals_match = _LINE_4VAL_ONLY_RE.match(curr)
        name_val_match = _LINE_NAME_1VAL_RE.match(nxt)

        if not vals_match or not name_val_match:
            return None

        payer_name = name_val_match.group(1).strip()
        if self._should_skip_line(payer_name):
            return None

        name_parts = [payer_name]
        cnpj = self._find_cnpj_nearby(lines, idx + 1, name_parts)
        if not cnpj:
            return None

        full_name = " ".join(name_parts)
        income = parse_currency(name_val_match.group(2))
        contrib = parse_currency(vals_match.group(1))
        irrf = parse_currency(vals_match.group(2))
        thirteenth = parse_currency(vals_match.group(3))
        irrf_thirteenth = parse_currency(vals_match.group(4))

        item_id = generate_item_id(
            f"{cnpj}{full_name}{income}{contrib}{irrf}{thirteenth}{irrf_thirteenth}{page_num}"
        )

        return {
            "payer_name": full_name,
            "income_from_legal_person": income,
            "official_social_security_contribution": contrib,
            "tax_withheld_at_source": irrf,
            "thirteenth_salary": thirteenth,
            "irrf_on_thirteenth_salary": irrf_thirteenth,
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num,
        }
    
    def _build_item_5val(
        self, match: re.Match, lines: list[str], idx: int, page_num: int
    ) -> Optional[dict]:
        payer_name_start = match.group(1).strip()
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = self._find_cnpj_nearby(lines, idx, name_parts)
        if not cnpj:
            return None
        
        full_name = " ".join(name_parts)
        item_id = generate_item_id(f"{cnpj}{full_name}{match.group(2)}{match.group(3)}{page_num}")
        
        return {
            "payer_name": full_name,
            "income_from_legal_person": parse_currency(match.group(2)),
            "official_social_security_contribution": parse_currency(match.group(3)),
            "tax_withheld_at_source": parse_currency(match.group(4)),
            "thirteenth_salary": parse_currency(match.group(5)),
            "irrf_on_thirteenth_salary": parse_currency(match.group(6)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
    
    def _build_item_4val(
        self, match: re.Match, lines: list[str], idx: int, page_num: int
    ) -> Optional[dict]:
        """Constrói item quando OCR perdeu uma das 5 colunas (ficou com 4)."""
        payer_name_start = match.group(1).strip()
        if self._should_skip_line(payer_name_start):
            return None
        
        name_parts = [payer_name_start]
        cnpj = self._find_cnpj_nearby(lines, idx, name_parts)
        if not cnpj:
            return None
        
        full_name = " ".join(name_parts)
        item_id = generate_item_id(f"{cnpj}{full_name}{match.group(2)}{match.group(3)}{page_num}")
        
        return {
            "payer_name": full_name,
            "income_from_legal_person": parse_currency(match.group(2)),
            "official_social_security_contribution": 0.0,
            "tax_withheld_at_source": parse_currency(match.group(3)),
            "thirteenth_salary": parse_currency(match.group(4)),
            "irrf_on_thirteenth_salary": parse_currency(match.group(5)),
            "cpf_cnpj": cnpj,
            "id": item_id,
            "page": page_num
        }
    
    def _find_cnpj_nearby(
        self, lines: list[str], idx: int, name_parts: list[str]
    ) -> str:
        for j in range(idx + 1, min(idx + 6, len(lines))):
            next_line = lines[j].strip()
            
            cnpj = _find_cnpj(next_line)
            if cnpj:
                return cnpj
            
            if self._is_name_continuation(next_line):
                name_parts.append(next_line)
        return ""
    
    def _should_skip_line(self, text: str) -> bool:
        skip_keywords = ["TOTAL", "CNPJ", "NOME DA", "REND.", "CÓDIGO"]
        return any(kw in text.upper() for kw in skip_keywords)
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        if "TOTAL" in line.upper() or "CNPJ" in line.upper():
            return False
        if re.match(r"^\d{2}\.\d{3}\.\d{3}", line):
            return False
        if re.match(rf"^{_NAME_CHAR}{_NAME_CONT}+$", line):
            return True
        return False
    
    def _calculate_totals(self, items: list[dict], pdf_totals: list[float] = None) -> dict:
        pdf_totals = pdf_totals or []
        
        sum_income = round(sum(i["income_from_legal_person"] for i in items), 2)
        sum_contrib = round(sum(i["official_social_security_contribution"] for i in items), 2)
        sum_irrf = round(sum(i["tax_withheld_at_source"] for i in items), 2)
        sum_13 = round(sum(i["thirteenth_salary"] for i in items), 2)
        sum_irrf_13 = round(sum(i["irrf_on_thirteenth_salary"] for i in items), 2)
        
        pdf_income = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_contrib = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_irrf = pdf_totals[2] if len(pdf_totals) > 2 else None
        pdf_13 = pdf_totals[3] if len(pdf_totals) > 3 else None
        pdf_irrf_13 = pdf_totals[4] if len(pdf_totals) > 4 else None
        
        return {
            "income_from_legal_person": create_validated_total(sum_income, pdf_income),
            "official_social_security_contribution": create_validated_total(sum_contrib, pdf_contrib),
            "tax_withheld_at_source": create_validated_total(sum_irrf, pdf_irrf),
            "thirteenth_salary": create_validated_total(sum_13, pdf_13),
            "irrf_on_thirteenth_salary": create_validated_total(sum_irrf_13, pdf_irrf_13)
        }

    def _extract_totals_with_ocr_fallback(self, page_text: str) -> list[float]:
        totals = extract_section_total(
            page_text,
            "TOTAL",
            skip_keywords=["TOTAL DE DEDUÇÃO", "TOTAL DO"],
        )
        if len(totals) >= 5:
            return totals[:5]
        if len(totals) != 1:
            return totals

        lines = page_text.split("\n")
        total_line_idx = self._find_total_line_index(lines)
        if total_line_idx is None:
            return totals

        neighbor_vals = self._find_neighbor_four_totals(lines, total_line_idx)
        if len(neighbor_vals) != 4:
            return totals

        return [totals[0], *neighbor_vals]

    def _find_total_line_index(self, lines: list[str]) -> Optional[int]:
        for idx, line in enumerate(lines):
            upper = line.strip().upper()
            if not upper.startswith("TOTAL"):
                continue
            if "TOTAL DE DEDUÇÃO" in upper or "TOTAL DO" in upper:
                continue
            return idx
        return None

    def _find_neighbor_four_totals(self, lines: list[str], total_idx: int) -> list[float]:
        for offset in range(1, 4):
            prev_idx = total_idx - offset
            if prev_idx >= 0:
                prev_vals = self._parse_four_values_line(lines[prev_idx])
                if prev_vals:
                    return prev_vals

            next_idx = total_idx + offset
            if next_idx < len(lines):
                next_vals = self._parse_four_values_line(lines[next_idx])
                if next_vals:
                    return next_vals
        return []

    def _parse_four_values_line(self, line: str) -> list[float]:
        stripped = line.strip()
        if not stripped:
            return []
        upper = stripped.upper()
        invalid_markers = [
            "CNPJ",
            "CPF",
            "TITULAR",
            "DEPENDENTE",
            "NOME",
            "FONTE",
            "PAGADORA",
            "REND",
            "JURIDICA",
            "JURÍDICA",
            "OFICIAL",
            "NA FONTE",
            "SALÁRIO",
            "SALARIO",
        ]
        if any(marker in upper for marker in invalid_markers):
            return []

        matches = _MONEY_RE.findall(stripped)
        if len(matches) != 4:
            return []
        return [parse_currency(v) for v in matches]
