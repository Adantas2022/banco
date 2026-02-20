"""Safe PDF extraction using subprocesses with signal-based timeouts.

All pdfplumber operations run in isolated subprocesses where signal.SIGALRM
reliably interrupts hangs — even inside C extensions like zlib. Subprocesses
can be killed via SIGTERM/SIGKILL when they exceed the total timeout.

This replaces the previous threading-based approach which caused zombie
threads, shared-state corruption, and GIL contention in Dramatiq workers.
"""

from __future__ import annotations

import multiprocessing
import os
import signal
import sys
from pathlib import Path
from typing import Any, Optional, Union

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

if sys.platform == "win32":
    _mp_ctx = multiprocessing.get_context("spawn")
else:
    _mp_ctx = multiprocessing.get_context("forkserver")

_HAS_SIGALRM = hasattr(signal, "SIGALRM")

DEFAULT_PAGE_TIMEOUT_S = 30
DEFAULT_TOTAL_TIMEOUT_S = 300
DEFAULT_OPEN_TIMEOUT_S = 60


class _PageTimeout(Exception):
    pass


def _alarm_handler(signum, frame):
    raise _PageTimeout()


def _set_alarm(seconds: int) -> None:
    if _HAS_SIGALRM:
        signal.alarm(seconds)


def _cancel_alarm() -> None:
    if _HAS_SIGALRM:
        signal.alarm(0)


def _install_alarm_handler() -> None:
    if _HAS_SIGALRM:
        signal.signal(signal.SIGALRM, _alarm_handler)


# ─── Subprocess workers (module-level for pickling) ───────────────────


def _worker_extract_text(pdf_path_str: str, page_timeout_s: int, conn) -> None:
    import time as _time

    _install_alarm_handler()
    pages_text: dict[int, str] = {}
    total_pages = 0
    warnings: list[str] = []
    pdf = None
    timing: dict[str, float] = {}
    t0 = _time.monotonic()

    try:
        import pdfplumber

        _set_alarm(DEFAULT_OPEN_TIMEOUT_S)
        pdf = pdfplumber.open(pdf_path_str)
        _cancel_alarm()
        timing["open_s"] = _time.monotonic() - t0

        t_pages = _time.monotonic()
        total_pages = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, 1):
            try:
                _set_alarm(page_timeout_s)
                text = page.extract_text() or ""
                _cancel_alarm()
                pages_text[page_num] = text
            except _PageTimeout:
                _cancel_alarm()
                warnings.append(
                    f"PAGE_TIMEOUT: Pagina {page_num} ignorada "
                    f"- extração excedeu {page_timeout_s}s"
                )
                pages_text[page_num] = ""
            except Exception as e:
                _cancel_alarm()
                warnings.append(
                    f"PAGE_ERROR: Pagina {page_num} ignorada - erro: {e}"
                )
                pages_text[page_num] = ""

        timing["pages_s"] = _time.monotonic() - t_pages
        timing["total_s"] = _time.monotonic() - t0

        conn.send(("ok", pages_text, total_pages, warnings, timing))
    except _PageTimeout:
        _cancel_alarm()
        timing["total_s"] = _time.monotonic() - t0
        conn.send((
            "error", {}, 0,
            [f"PDF_OPEN_TIMEOUT: pdfplumber.open() excedeu {DEFAULT_OPEN_TIMEOUT_S}s"],
            timing,
        ))
    except Exception as e:
        timing["total_s"] = _time.monotonic() - t0
        conn.send(("error", {}, total_pages, [f"PDF_ERROR: {e}"], timing))
    finally:
        _cancel_alarm()
        if pdf:
            pdf.close()
        conn.close()


def _worker_analyze_pages(
    pdf_path_str: str, max_sample: int, page_timeout_s: int, conn
) -> None:
    _install_alarm_handler()
    results: list[dict] = []
    total_pages = 0
    warnings: list[str] = []
    pdf = None

    try:
        import pdfplumber

        _set_alarm(DEFAULT_OPEN_TIMEOUT_S)
        pdf = pdfplumber.open(pdf_path_str)
        _cancel_alarm()

        total_pages = len(pdf.pages)

        if total_pages <= max_sample:
            indices = list(range(total_pages))
        else:
            idx_set: set[int] = set()
            for i in range(min(3, total_pages)):
                idx_set.add(i)
            idx_set.add(total_pages // 2)
            for i in range(max(0, total_pages - 3), total_pages):
                idx_set.add(i)
            indices = sorted(idx_set)

        for idx in indices:
            page = pdf.pages[idx]
            info: dict[str, Any] = {
                "page_index": idx,
                "width": float(page.width),
                "height": float(page.height),
                "char_count": 0,
                "image_coverage": 0.0,
            }

            try:
                images = page.images or []
                page_area = page.width * page.height
                if images and page_area > 0:
                    total_img_area = sum(
                        (img.get("width", 0) or 0) * (img.get("height", 0) or 0)
                        for img in images
                    )
                    info["image_coverage"] = min(total_img_area / page_area, 1.0)
            except Exception:
                pass

            try:
                _set_alarm(page_timeout_s)
                text = page.extract_text() or ""
                _cancel_alarm()
                info["char_count"] = len(text.strip())
            except _PageTimeout:
                _cancel_alarm()
                warnings.append(
                    f"TYPE_DETECT_TIMEOUT: Page {idx + 1} text extraction timed out"
                )
            except Exception:
                _cancel_alarm()

            results.append(info)

        conn.send(("ok", results, total_pages, warnings))
    except _PageTimeout:
        _cancel_alarm()
        conn.send((
            "error", [], 0,
            [f"PDF_OPEN_TIMEOUT: pdfplumber.open() excedeu {DEFAULT_OPEN_TIMEOUT_S}s"],
        ))
    except Exception as e:
        conn.send(("error", [], total_pages, [f"PDF_ANALYZE_ERROR: {e}"]))
    finally:
        _cancel_alarm()
        if pdf:
            pdf.close()
        conn.close()


def _worker_extract_tables(
    pdf_path_str: str,
    page_numbers: Optional[list[int]],
    page_timeout_s: int,
    conn,
) -> None:
    _install_alarm_handler()
    tables: list[dict] = []
    warnings: list[str] = []
    pdf = None

    try:
        import pdfplumber

        _set_alarm(DEFAULT_OPEN_TIMEOUT_S)
        pdf = pdfplumber.open(pdf_path_str)
        _cancel_alarm()

        for page_num, page in enumerate(pdf.pages, 1):
            if page_numbers and page_num not in page_numbers:
                continue
            try:
                _set_alarm(page_timeout_s)
                page_tables = page.extract_tables()
                _cancel_alarm()
                for table in page_tables:
                    if table and len(table) >= 2:
                        tables.append({"data": table, "page_number": page_num})
            except _PageTimeout:
                _cancel_alarm()
                warnings.append(
                    f"TABLE_TIMEOUT: Tabelas da página {page_num} "
                    f"ignoradas ({page_timeout_s}s)"
                )
            except Exception as e:
                _cancel_alarm()
                warnings.append(f"TABLE_ERROR: Página {page_num}: {e}")

        conn.send(("ok", tables, warnings))
    except _PageTimeout:
        _cancel_alarm()
        conn.send((
            "error", [],
            [f"PDF_OPEN_TIMEOUT: pdfplumber.open() excedeu {DEFAULT_OPEN_TIMEOUT_S}s"],
        ))
    except Exception as e:
        conn.send(("error", [], [f"PDF_TABLE_ERROR: {e}"]))
    finally:
        _cancel_alarm()
        if pdf:
            pdf.close()
        conn.close()


def _worker_extract_words(
    pdf_path_str: str, page_num: int, timeout_s: int, conn
) -> None:
    _install_alarm_handler()
    pdf = None

    try:
        import pdfplumber

        _set_alarm(DEFAULT_OPEN_TIMEOUT_S)
        pdf = pdfplumber.open(pdf_path_str)
        _cancel_alarm()

        if page_num < 1 or page_num > len(pdf.pages):
            conn.send((
                "error",
                [],
                [f"Page {page_num} out of range (1-{len(pdf.pages)})"],
            ))
            return

        page = pdf.pages[page_num - 1]
        _set_alarm(timeout_s)
        words_raw = page.extract_words()
        _cancel_alarm()

        words = [
            {
                "text": w["text"],
                "x0": w["x0"],
                "top": w["top"],
                "x1": w["x1"],
                "bottom": w["bottom"],
            }
            for w in words_raw
        ]
        conn.send(("ok", words, []))
    except _PageTimeout:
        _cancel_alarm()
        conn.send((
            "ok",
            [],
            [f"WORDS_TIMEOUT: Page {page_num} timed out ({timeout_s}s)"],
        ))
    except Exception as e:
        conn.send(("error", [], [f"WORDS_ERROR: {e}"]))
    finally:
        _cancel_alarm()
        if pdf:
            pdf.close()
        conn.close()


# ─── Internal helpers ─────────────────────────────────────────────────


def _ensure_file_path(
    pdf_source: Union[str, Path, bytes],
) -> tuple[Path, bool]:
    if isinstance(pdf_source, bytes):
        import tempfile

        tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        tmp.write(pdf_source)
        tmp.close()
        return Path(tmp.name), True
    return Path(pdf_source), False


def _run_in_subprocess(
    target,
    args: tuple,
    total_timeout_s: int,
    label: str,
) -> Any:
    parent_conn, child_conn = _mp_ctx.Pipe(duplex=False)
    process = _mp_ctx.Process(target=target, args=(*args, child_conn))
    process.start()
    child_conn.close()

    process.join(timeout=total_timeout_s)

    if process.is_alive():
        logger.warning(
            "%s: subprocess exceeded total timeout, terminating",
            label,
            timeout_s=total_timeout_s,
            pid=process.pid,
        )
        process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join(1)
        parent_conn.close()
        return None

    try:
        if parent_conn.poll(timeout=1):
            return parent_conn.recv()
    except (EOFError, OSError) as e:
        logger.warning("%s: IPC error: %s", label, e)
    finally:
        parent_conn.close()

    return None


# ─── Public API ───────────────────────────────────────────────────────


def extract_all_text(
    pdf_source: Union[str, Path, bytes],
    page_timeout_s: int = DEFAULT_PAGE_TIMEOUT_S,
    total_timeout_s: int = DEFAULT_TOTAL_TIMEOUT_S,
) -> tuple[dict[int, str], int, list[str], dict[str, float]]:
    """Extract text from every page of a PDF in an isolated subprocess.

    Returns ``(pages_text, total_pages, warnings, timing)``.
    ``timing`` contains ``open_s``, ``pages_s``, ``total_s`` when available.
    """
    path, is_temp = _ensure_file_path(pdf_source)
    try:
        result = _run_in_subprocess(
            target=_worker_extract_text,
            args=(str(path), page_timeout_s),
            total_timeout_s=total_timeout_s,
            label="extract_all_text",
        )
        if result is None:
            return (
                {},
                0,
                [f"PROCESS_TIMEOUT: Extração total excedeu {total_timeout_s}s"],
                {"timed_out": True},
            )
        status, pages_text, total_pages, warnings, timing = result
        if status == "ok":
            return pages_text, total_pages, warnings, timing
        timing["had_error"] = True
        return {}, total_pages, warnings, timing
    finally:
        if is_temp:
            path.unlink(missing_ok=True)


def analyze_pdf_pages(
    pdf_source: Union[str, Path, bytes],
    max_sample: int = 10,
    page_timeout_s: int = DEFAULT_PAGE_TIMEOUT_S,
    total_timeout_s: int = 120,
) -> tuple[list[dict], int, list[str]]:
    """Analyze pages for PDF type detection in an isolated subprocess.

    Returns ``(page_infos, total_pages, warnings)`` where each
    ``page_info`` has keys ``char_count``, ``image_coverage``,
    ``width``, ``height``.
    """
    path, is_temp = _ensure_file_path(pdf_source)
    try:
        result = _run_in_subprocess(
            target=_worker_analyze_pages,
            args=(str(path), max_sample, page_timeout_s),
            total_timeout_s=total_timeout_s,
            label="analyze_pdf_pages",
        )
        if result is None:
            return [], 0, [f"PROCESS_TIMEOUT: Análise excedeu {total_timeout_s}s"]
        status, page_infos, total_pages, warnings = result
        if status == "ok":
            return page_infos, total_pages, warnings
        return [], total_pages, warnings
    finally:
        if is_temp:
            path.unlink(missing_ok=True)


def extract_tables(
    pdf_source: Union[str, Path, bytes],
    page_numbers: Optional[list[int]] = None,
    page_timeout_s: int = DEFAULT_PAGE_TIMEOUT_S,
    total_timeout_s: int = DEFAULT_TOTAL_TIMEOUT_S,
) -> tuple[list[dict], list[str]]:
    """Extract tables from a PDF in an isolated subprocess.

    Returns ``(tables, warnings)`` where each table dict has keys
    ``data`` (list-of-lists) and ``page_number``.
    """
    path, is_temp = _ensure_file_path(pdf_source)
    try:
        result = _run_in_subprocess(
            target=_worker_extract_tables,
            args=(str(path), page_numbers, page_timeout_s),
            total_timeout_s=total_timeout_s,
            label="extract_tables",
        )
        if result is None:
            return [], [f"PROCESS_TIMEOUT: Extração de tabelas excedeu {total_timeout_s}s"]
        status, tables, warnings = result
        if status == "ok":
            return tables, warnings
        return [], warnings
    finally:
        if is_temp:
            path.unlink(missing_ok=True)


def extract_page_words(
    pdf_source: Union[str, Path, bytes],
    page_num: int,
    timeout_s: int = 60,
    total_timeout_s: int = 120,
) -> tuple[list[dict], list[str]]:
    """Extract words from one page of a PDF in an isolated subprocess.

    Returns ``(words, warnings)`` where each word dict has keys
    ``text``, ``x0``, ``top``, ``x1``, ``bottom``.
    """
    path, is_temp = _ensure_file_path(pdf_source)
    try:
        result = _run_in_subprocess(
            target=_worker_extract_words,
            args=(str(path), page_num, timeout_s),
            total_timeout_s=total_timeout_s,
            label="extract_page_words",
        )
        if result is None:
            return [], [f"PROCESS_TIMEOUT: Extração de palavras excedeu {total_timeout_s}s"]
        status, words, warnings = result
        if status == "ok":
            return words, warnings
        return [], warnings
    finally:
        if is_temp:
            path.unlink(missing_ok=True)
