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

        # Keep page footer markers when present.
        normalized: list[str] = []
        for line in lines:
            if _PAGE_RE.match(line):
                normalized.append(line)
                continue
            normalized.append(re.sub(r"\s{2,}", " ", line))

        return "\n".join(normalized).strip()

    @staticmethod
    def _merge_currency_orphans(lines: list[str]) -> list[str]:
        """Attach loose value lines to previous rows when possible."""
        merged: list[str] = []
        for line in lines:
            if _CURRENCY_RE.match(line) and merged:
                prev = merged[-1]
                # Only merge when previous line does not already look complete
                # with two value columns.
                value_count = len(_CURRENCY_RE.findall(prev))
                if value_count < 2 and not _PAGE_RE.match(prev):
                    merged[-1] = f"{prev} {line}"
                    continue
            merged.append(line)
        return merged
