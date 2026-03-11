"""Small normalizer for Document AI OCR text quirks."""

from __future__ import annotations

import re


_CURRENCY_RE = re.compile(r"^-?\d[\d.,]*[.,]\d{2}$")
_PAGE_RE = re.compile(r"^P[aá]gina\s+\d+\s+de\s+\d+$", re.IGNORECASE)


class DocumentAINormalizer:
    """Normalizes Document AI pages to fit the parser's regex-oriented structure."""

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line]
        lines = self._merge_currency_orphans(lines)

        normalized: list[str] = []
        for line in lines:
            if _PAGE_RE.match(line):
                normalized.append(line)
                continue
            line = re.sub(r"\s{2,}", " ", line)
            line = self._fix_period_as_decimal(line)
            normalized.append(line)

        return "\n".join(normalized).strip()

    @staticmethod
    def _fix_period_as_decimal(line: str) -> str:
        """Corrige ponto usado como separador decimal (erro frequente do Document AI).

        Após remoção de marca d'água, o OCR pode confundir vírgula
        com ponto em valores monetários. Exemplos:
            '0.00' → '0,00'
            '358.550.20' → '358.550,20'
            '22.391.052.36' → '22.391.052,36'

        Padrão: dígitos com separadores de milhar (opcionais) seguidos
        de .DD onde DD são exatamente 2 dígitos no final da "palavra".
        """
        return re.sub(
            r"(\d{1,3}(?:\.\d{3})*)\.(\d{2})(?=\s|$)",
            r"\1,\2",
            line,
        )


    @staticmethod
    def _merge_currency_orphans(lines: list[str]) -> list[str]:
        """Attach loose value lines to previous rows when possible."""
        merged: list[str] = []
        for line in lines:
            if _CURRENCY_RE.match(line) and merged:
                prev = merged[-1]
                value_count = len(_CURRENCY_RE.findall(prev))
                if value_count < 2 and not _PAGE_RE.match(prev):
                    merged[-1] = f"{prev} {line}"
                    continue
            merged.append(line)
        return merged
