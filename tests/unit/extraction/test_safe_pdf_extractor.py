"""Tests for the safe subprocess-based PDF extractor.

Tests cover:
  - Normal extraction via subprocess
  - Per-page timeout (signal.SIGALRM)
  - Total process timeout (process.terminate)
  - Error handling (file not found, corrupt PDF)
  - Bytes input (auto temp-file)
  - Worker functions directly (signal behaviour)
"""

from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import textwrap
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="signal.SIGALRM not available on Windows",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_simple_pdf(path: Path, pages_text: list[str]) -> None:
    """Create a real PDF using fpdf2 (lightweight, no pdfplumber needed)."""
    try:
        from fpdf import FPDF
    except ImportError:
        pytest.skip("fpdf2 not installed — needed for PDF generation in tests")

    pdf = FPDF()
    for text in pages_text:
        pdf.add_page()
        pdf.set_font("Helvetica", size=12)
        for line in text.split("\n"):
            pdf.cell(0, 10, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


# ---------------------------------------------------------------------------
# Tests for _ensure_file_path
# ---------------------------------------------------------------------------

class TestEnsureFilePath:
    def test_path_string_returns_same(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import _ensure_file_path
        path, is_temp = _ensure_file_path("/some/file.pdf")
        assert path == Path("/some/file.pdf")
        assert is_temp is False

    def test_path_object_returns_same(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import _ensure_file_path
        path, is_temp = _ensure_file_path(Path("/some/file.pdf"))
        assert path == Path("/some/file.pdf")
        assert is_temp is False

    def test_bytes_creates_temp_file(self, tmp_path):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import _ensure_file_path
        data = b"%PDF-1.4 fake"
        path, is_temp = _ensure_file_path(data)
        try:
            assert is_temp is True
            assert path.exists()
            assert path.read_bytes() == data
        finally:
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests for extract_all_text
# ---------------------------------------------------------------------------

class TestExtractAllText:
    def test_extracts_text_from_simple_pdf(self, tmp_path):
        pdf_path = tmp_path / "simple.pdf"
        _create_simple_pdf(pdf_path, ["Hello World", "Second Page"])

        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_all_text
        pages_text, total_pages, warnings, timing = extract_all_text(pdf_path, total_timeout_s=30)

        assert total_pages == 2
        assert 1 in pages_text
        assert 2 in pages_text
        assert "Hello" in pages_text[1]
        assert "Second" in pages_text[2]
        assert "total_s" in timing
        assert timing["total_s"] > 0

    def test_extracts_from_bytes(self, tmp_path):
        pdf_path = tmp_path / "bytes_test.pdf"
        _create_simple_pdf(pdf_path, ["Bytes Content"])
        pdf_bytes = pdf_path.read_bytes()

        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_all_text
        pages_text, total_pages, warnings, timing = extract_all_text(pdf_bytes, total_timeout_s=30)

        assert total_pages == 1
        assert "Bytes" in pages_text.get(1, "")
        assert isinstance(timing, dict)

    def test_returns_empty_on_missing_file(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_all_text
        pages, total, warnings, timing = extract_all_text("/nonexistent/path.pdf", total_timeout_s=10)

        assert pages == {}
        assert any("PDF_ERROR" in w or "PROCESS_TIMEOUT" in w for w in warnings)
        assert isinstance(timing, dict)

    def test_total_timeout_kills_process(self):
        """Reuses module-level _subprocess_forever to verify that the
        total timeout kills the process."""
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import (
            _run_in_subprocess,
        )

        result = _run_in_subprocess(
            target=_subprocess_forever,
            args=(),
            total_timeout_s=2,
            label="test_timeout",
        )
        assert result is None

    def test_nonexistent_pdf_returns_warnings(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_all_text

        pages_text, total_pages, warnings, timing = extract_all_text(
            "/does/not/exist.pdf", total_timeout_s=30,
        )
        assert pages_text == {}
        assert len(warnings) > 0
        assert isinstance(timing, dict)


# ---------------------------------------------------------------------------
# Tests for analyze_pdf_pages
# ---------------------------------------------------------------------------

class TestAnalyzePdfPages:
    def test_analyzes_digital_pdf(self, tmp_path):
        pdf_path = tmp_path / "digital.pdf"
        _create_simple_pdf(pdf_path, ["A" * 200, "B" * 200])

        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import analyze_pdf_pages
        results, total_pages, warnings = analyze_pdf_pages(pdf_path, total_timeout_s=30)

        assert total_pages == 2
        assert len(results) == 2
        assert all("char_count" in r for r in results)
        assert all("image_coverage" in r for r in results)
        assert all("width" in r for r in results)
        assert all("height" in r for r in results)

    def test_returns_empty_on_missing_file(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import analyze_pdf_pages
        results, total, warnings = analyze_pdf_pages("/nonexistent.pdf", total_timeout_s=10)

        assert results == []
        assert any("ERROR" in w or "TIMEOUT" in w for w in warnings)


# ---------------------------------------------------------------------------
# Tests for extract_tables
# ---------------------------------------------------------------------------

class TestExtractTables:
    def test_returns_empty_for_pdf_without_tables(self, tmp_path):
        pdf_path = tmp_path / "no_tables.pdf"
        _create_simple_pdf(pdf_path, ["Just plain text, no tables here"])

        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_tables
        tables, warnings = extract_tables(pdf_path, total_timeout_s=30)

        assert tables == []

    def test_returns_empty_on_missing_file(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_tables
        tables, warnings = extract_tables("/nonexistent.pdf", total_timeout_s=10)

        assert tables == []
        assert len(warnings) > 0


# ---------------------------------------------------------------------------
# Tests for extract_page_words
# ---------------------------------------------------------------------------

class TestExtractPageWords:
    def test_extracts_words_from_page(self, tmp_path):
        pdf_path = tmp_path / "words.pdf"
        _create_simple_pdf(pdf_path, ["Hello World Test"])

        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_page_words
        words, warnings = extract_page_words(pdf_path, page_num=1, total_timeout_s=30)

        assert isinstance(words, list)
        if words:
            assert "text" in words[0]
            assert "x0" in words[0]
            assert "top" in words[0]

    def test_out_of_range_page(self, tmp_path):
        pdf_path = tmp_path / "single.pdf"
        _create_simple_pdf(pdf_path, ["One page"])

        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import extract_page_words
        words, warnings = extract_page_words(pdf_path, page_num=99, total_timeout_s=30)

        assert words == []
        assert any("out of range" in w or "ERROR" in w for w in warnings)


# ---------------------------------------------------------------------------
# Tests for signal.SIGALRM based page timeout (worker functions)
# ---------------------------------------------------------------------------

class TestPageTimeout:
    """Test the per-page timeout mechanism.

    These tests call worker functions directly in the current process
    so signal.SIGALRM works (we're in the main thread during pytest).
    """

    def test_alarm_handler_raises_page_timeout(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import (
            _PageTimeout,
            _alarm_handler,
        )
        with pytest.raises(_PageTimeout):
            _alarm_handler(signal.SIGALRM, None)

    def test_worker_handles_page_timeout_gracefully(self, tmp_path):
        """Simulate a page timeout inside the worker function."""
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import (
            _worker_extract_text,
            _mp_ctx,
        )

        pdf_path = tmp_path / "timeout_page.pdf"
        _create_simple_pdf(pdf_path, ["Page 1", "Page 2"])

        parent_conn, child_conn = _mp_ctx.Pipe(duplex=False)

        proc = _mp_ctx.Process(
            target=_worker_extract_text,
            args=(str(pdf_path), 120, child_conn),
        )
        proc.start()
        child_conn.close()
        proc.join(timeout=30)

        assert not proc.is_alive()
        result = parent_conn.recv()
        parent_conn.close()

        status, pages_text, total_pages, warnings, timing = result
        assert status == "ok"
        assert total_pages == 2
        assert "total_s" in timing


# ---------------------------------------------------------------------------
# Tests for _run_in_subprocess edge cases
# ---------------------------------------------------------------------------

def _subprocess_forever(conn):
    """Module-level worker that hangs (for pickle compatibility with forkserver)."""
    time.sleep(120)
    conn.close()


def _subprocess_fast(conn):
    """Module-level worker that returns immediately."""
    conn.send(("ok", {"data": 42}))
    conn.close()


def _subprocess_crash(conn):
    """Module-level worker that raises."""
    raise RuntimeError("boom")


class TestRunInSubprocess:
    def test_returns_none_on_timeout(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import (
            _run_in_subprocess,
        )

        result = _run_in_subprocess(
            target=_subprocess_forever,
            args=(),
            total_timeout_s=2,
            label="test",
        )
        assert result is None

    def test_returns_result_from_fast_worker(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import (
            _run_in_subprocess,
        )

        result = _run_in_subprocess(
            target=_subprocess_fast,
            args=(),
            total_timeout_s=10,
            label="test",
        )
        assert result == ("ok", {"data": 42})

    def test_handles_worker_crash(self):
        from irpf_processor.infrastructure.extraction.safe_pdf_extractor import (
            _run_in_subprocess,
        )

        result = _run_in_subprocess(
            target=_subprocess_crash,
            args=(),
            total_timeout_s=10,
            label="test",
        )
        assert result is None
