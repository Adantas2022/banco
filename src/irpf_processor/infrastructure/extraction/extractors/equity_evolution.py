"""Extrator da seção Evolução Patrimonial (apêndice da declaração IRPF).

A seção EVOLUÇÃO PATRIMONIAL aparece no apêndice do PDF (geralmente na última
página) e lista os totais de bens/direitos e dívidas/ônus reais para o exercício
atual e o exercício anterior. O delta líquido é o "ganho/perda patrimonial" que a
Receita Federal exibe.

Layout típico (PDF da Receita):

    EVOLUÇÃO PATRIMONIAL
     Bens e direitos em 31/12/2023                                250.000,00
     Bens e direitos em 31/12/2024                                250.000,00
     Dívidas e ônus reais em 31/12/2023                                0,00
     Dívidas e ônus reais em 31/12/2024                                0,00

    OUTRAS INFORMAÇÕES
     ...
"""

import json
import os
import re
from typing import Any

from irpf_processor.shared.logging import get_logger

from ..table_extractor import generate_item_id, parse_currency
from .base import ExtractionContext, ISectionExtractor

logger = get_logger(__name__)


_DATE_RE = r"(\d{2})/(\d{2})/(\d{4})"
_VALUE_RE = r"([\d.]+,\d{2})"
_ASSETS_LINE_RE = re.compile(
    rf"BENS\s+E\s+DIREITOS\s+EM\s+{_DATE_RE}\s+{_VALUE_RE}",
    re.IGNORECASE,
)
_DEBTS_LINE_RE = re.compile(
    rf"D[ÍI]VIDAS\s+E\s+[ÔO]NUS\s+REAIS\s+EM\s+{_DATE_RE}\s+{_VALUE_RE}",
    re.IGNORECASE,
)


class EquityEvolutionExtractor(ISectionExtractor):
    """Extrai a seção Evolução Patrimonial do apêndice da declaração."""

    SECTION_MARKERS = [
        "EVOLUÇÃO PATRIMONIAL",
        "EVOLUCAO PATRIMONIAL",
        # OCR variant: Ç → G (visto em outros extractors)
        "EVOLUGAO PATRIMONIAL",
    ]

    SECTION_END_MARKERS = [
        "OUTRAS INFORMAÇÕES",
        "OUTRAS INFORMACOES",
        # Variants já usadas pelo PDF post-processor
        "OUTRAS INFORMACOEs",
    ]

    LLM_PROMPT = """
================================================================
SECAO - EVOLUÇÃO PATRIMONIAL
================================================================
REGRA: extraia os 4 valores totais da secao EVOLUCAO PATRIMONIAL no apendice
da declaracao IRPF.

{
    "section_name": "Evolução Patrimonial",
    "assets_last_year": numero (Bens e direitos em 31/12/<ano-1>; converta '1.234,56' para 1234.56),
    "assets_current_year": numero (Bens e direitos em 31/12/<ano>),
    "debts_last_year": numero (Dividas e onus reais em 31/12/<ano-1>),
    "debts_current_year": numero (Dividas e onus reais em 31/12/<ano>),
    "year_last": numero (ano completo do exercicio anterior, ex 2023),
    "year_current": numero (ano completo do exercicio atual, ex 2024)
}

REGRAS IMPORTANTES:
- Os 4 valores aparecem em 4 linhas consecutivas, cada uma com formato
  "Bens e direitos em DD/MM/YYYY VALOR" ou "Dividas e onus reais em DD/MM/YYYY VALOR".
- Valores monetarios devem ser NUMEROS (87624.85, nao "87.624,85").
- Se algum dos 4 valores estiver ausente no PDF, retorne 0 (zero numerico).
- Os anos devem vir como inteiros de 4 digitos (2023, 2024). Use o que esta
  na propria coluna de data, nao infira.
"""

    @property
    def section_name(self) -> str:
        return "equity_evolution_section"

    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)

    def _section_text(self, context: ExtractionContext) -> str | None:
        """Retorna apenas o texto entre EVOLUÇÃO PATRIMONIAL e OUTRAS INFORMAÇÕES."""
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])

        in_section = False
        captured: list[str] = []

        for _page_num, page_text in sorted_pages:
            for line in page_text.split("\n"):
                upper = line.upper()

                if not in_section:
                    if any(m in upper for m in self.SECTION_MARKERS):
                        in_section = True
                    continue

                if any(m in upper for m in self.SECTION_END_MARKERS):
                    return "\n".join(captured) if captured else None

                captured.append(line)

        return "\n".join(captured) if captured else None

    def extract(self, context: ExtractionContext) -> dict[str, Any] | None:
        if not self.can_extract(context):
            return None

        section_text = self._section_text(context)
        if not section_text:
            return None

        assets_by_year: dict[int, float] = {}
        debts_by_year: dict[int, float] = {}

        for match in _ASSETS_LINE_RE.finditer(section_text):
            _, _, year_str, value_str = match.groups()
            year = int(year_str)
            assets_by_year[year] = parse_currency(value_str)

        for match in _DEBTS_LINE_RE.finditer(section_text):
            _, _, year_str, value_str = match.groups()
            year = int(year_str)
            debts_by_year[year] = parse_currency(value_str)

        if not assets_by_year and not debts_by_year:
            return None

        all_years = sorted(set(assets_by_year) | set(debts_by_year))
        if len(all_years) >= 2:
            year_last, year_current = all_years[0], all_years[-1]
        elif len(all_years) == 1:
            year_current = all_years[0]
            year_last = year_current - 1
        else:
            return None

        result = {
            "section_name": "Evolução Patrimonial",
            "assets_last_year": float(assets_by_year.get(year_last, 0.0)),
            "assets_current_year": float(assets_by_year.get(year_current, 0.0)),
            "debts_last_year": float(debts_by_year.get(year_last, 0.0)),
            "debts_current_year": float(debts_by_year.get(year_current, 0.0)),
            "year_last": year_last,
            "year_current": year_current,
        }
        result["computed_evolution"] = round(
            (result["assets_current_year"] - result["debts_current_year"])
            - (result["assets_last_year"] - result["debts_last_year"]),
            2,
        )
        result["id"] = generate_item_id(
            f"{year_current}{result['assets_current_year']}{result['debts_current_year']}"
        )
        return result

    # ------------------------------------------------------------------
    # LLM extraction (#19160) — mirrors rural_properties / exempt_income / exclusive_income
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_currency(value: Any) -> float:
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return 0.0
        try:
            return float(parse_currency(s))
        except Exception:
            try:
                return float(s.replace(",", "."))
            except Exception:
                return 0.0

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if s.isdigit() and len(s) == 4:
            return int(s)
        return None

    def _normalize_llm_chunk(self, chunk: dict) -> dict | None:
        """Normalize a raw LLM chunk into the same dict shape that ``extract()`` returns."""
        if not isinstance(chunk, dict):
            return None

        assets_last = self._parse_llm_currency(chunk.get("assets_last_year"))
        assets_current = self._parse_llm_currency(chunk.get("assets_current_year"))
        debts_last = self._parse_llm_currency(chunk.get("debts_last_year"))
        debts_current = self._parse_llm_currency(chunk.get("debts_current_year"))
        year_last = self._parse_year(chunk.get("year_last"))
        year_current = self._parse_year(chunk.get("year_current"))

        if (
            assets_last == 0.0
            and assets_current == 0.0
            and debts_last == 0.0
            and debts_current == 0.0
        ):
            return None

        if year_current is None and year_last is None:
            return None

        if year_current is None and year_last is not None:
            year_current = year_last + 1
        elif year_last is None and year_current is not None:
            year_last = year_current - 1

        result = {
            "section_name": "Evolução Patrimonial",
            "assets_last_year": assets_last,
            "assets_current_year": assets_current,
            "debts_last_year": debts_last,
            "debts_current_year": debts_current,
            "year_last": year_last,
            "year_current": year_current,
            "computed_evolution": round(
                (assets_current - debts_current) - (assets_last - debts_last),
                2,
            ),
        }
        result["id"] = generate_item_id(f"{year_current}{assets_current}{debts_current}")
        return result

    async def extract_with_llm(
        self,
        context: ExtractionContext,
        custom_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        """Extract the Evolução Patrimonial section using LLM.

        Mirrors the rural_properties / exempt_income / exclusive_income LLM pipeline.
        """
        try:
            extraction_result = await self.get_llm_extraction_data(context, custom_prompt)

            if not extraction_result or not isinstance(extraction_result, list):
                logger.warning(
                    "llm_extraction_no_data",
                    section_name=self.section_name,
                    reason="no_chunks_returned",
                    document_id=context.document_id,
                )
                context.add_warning("LLM extraction returned no chunks for equity_evolution")
                return None

            debug_base = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                ),
                "tmp",
                context.document_id or "unknown",
            )
            debug_chunks_dir = os.path.join(debug_base, "chunks", "equity_evolution")
            debug_result_dir = os.path.join(debug_base, "result", "equity_evolution")
            os.makedirs(debug_chunks_dir, exist_ok=True)
            os.makedirs(debug_result_dir, exist_ok=True)

            for idx, chunk in enumerate(extraction_result):
                chunk_path = os.path.join(debug_chunks_dir, f"chunk_{idx}.json")
                try:
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(json.dumps(chunk, indent=2, ensure_ascii=False))
                except Exception:
                    pass

            logger.info(
                "llm_equity_evolution_extraction_start",
                section_name=self.section_name,
                document_id=context.document_id,
                chunk_count=len(extraction_result),
            )

            # The section is total-only — pick the first chunk that yields a valid
            # normalized result. Subsequent chunks are typically duplicates produced
            # by chunk overlap.
            normalized: dict | None = None
            for chunk in extraction_result:
                normalized = self._normalize_llm_chunk(chunk)
                if normalized:
                    break

            if not normalized:
                logger.warning(
                    "llm_equity_evolution_extraction_empty_result",
                    document_id=context.document_id,
                )
                context.add_warning("LLM extraction returned no usable values for equity_evolution")
                return None

            normalized["extraction_method"] = "llm"

            try:
                with open(
                    os.path.join(debug_result_dir, "merged_result.json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(json.dumps(normalized, indent=2, ensure_ascii=False))
            except Exception:
                pass

            logger.info(
                "llm_equity_evolution_extraction_complete",
                document_id=context.document_id,
                computed_evolution=normalized["computed_evolution"],
            )

            return normalized

        except Exception as exc:
            logger.exception(
                "llm_equity_evolution_extraction_failed",
                document_id=context.document_id,
                error_type=type(exc).__name__,
            )
            context.add_warning(
                f"LLM extraction failed for equity_evolution: {type(exc).__name__}: {exc}"
            )
            return None
