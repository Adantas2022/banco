"""Reconstructs OCR word boxes into pdfplumber-like lines."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Optional

from .models import PageResult, WordBox


@dataclass
class ReconstructionConfig:
    row_tolerance_factor: float = 0.45
    min_row_tolerance: float = 5.0
    column_gap_chars: float = 2.0
    min_column_spaces: int = 3
    fallback_char_width: float = 8.5


DEFAULT_CONFIG = ReconstructionConfig()


def reconstruct_page_text(
    page: PageResult,
    config: Optional[ReconstructionConfig] = None,
) -> str:
    if not page.has_spatial_data:
        return page.text

    words = page.words
    if not words:
        return page.text

    cfg = config or DEFAULT_CONFIG
    rows = _group_into_rows(words, cfg)
    char_width = _estimate_char_width(words, cfg)
    lines = _render_rows(rows, char_width, cfg)

    return "\n".join(lines)


def _group_into_rows(
    words: list[WordBox],
    config: ReconstructionConfig,
) -> list[list[WordBox]]:
    if not words:
        return []

    avg_height = sum(w.height for w in words) / len(words)
    tolerance = max(
        avg_height * config.row_tolerance_factor,
        config.min_row_tolerance,
    )

    sorted_words = sorted(words, key=lambda w: (w.center_y, w.left))
    rows: list[list[WordBox]] = []
    current_row: list[WordBox] = [sorted_words[0]]
    current_y = sorted_words[0].center_y

    for word in sorted_words[1:]:
        if abs(word.center_y - current_y) <= tolerance:
            current_row.append(word)
        else:
            rows.append(current_row)
            current_row = [word]
            current_y = word.center_y

    rows.append(current_row)

    for row in rows:
        row.sort(key=lambda w: w.left)

    return rows


def _estimate_char_width(
    words: list[WordBox],
    config: ReconstructionConfig,
) -> float:
    samples = [
        w.width / len(w.text)
        for w in words
        if len(w.text) >= 2 and w.width > 0
    ]

    if len(samples) < 5:
        return config.fallback_char_width

    return float(median(samples))


def _render_rows(
    rows: list[list[WordBox]],
    char_width: float,
    config: ReconstructionConfig,
) -> list[str]:
    lines: list[str] = []
    gap_threshold = char_width * config.column_gap_chars

    for row in rows:
        if not row:
            continue

        parts: list[str] = [row[0].text]
        for i in range(1, len(row)):
            gap = row[i].left - row[i - 1].right
            if gap > gap_threshold:
                num_spaces = max(
                    int(round(gap / char_width)),
                    config.min_column_spaces,
                )
                parts.append(" " * num_spaces)
            else:
                parts.append(" ")
            parts.append(row[i].text)

        lines.append("".join(parts))

    return lines
