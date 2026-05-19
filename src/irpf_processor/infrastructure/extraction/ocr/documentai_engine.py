"""Google Cloud Document AI OCR engine."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Optional

import fitz

from irpf_processor.shared.logging import get_logger

from .interfaces import IOcrEngine
from .models import (
    OcrExtractionError,
    OcrResult,
    OcrTimeoutError,
    PageResult,
    PdfType,
    WordBox,
)
from .watermark_remover import WatermarkRemover

logger = get_logger(__name__)

DEFAULT_LOCATION = "us"
DEFAULT_TIMEOUT = 300
MAX_PAGES_PER_REQUEST = 15


class DocumentAIEngine(IOcrEngine):
    def __init__(
        self,
        project_id: str = "",
        location: str = DEFAULT_LOCATION,
        processor_id: str = "",
        credentials_path: str = "",
        timeout: int = DEFAULT_TIMEOUT,
        preprocess_watermark: bool = True,
    ):
        self._project_id = project_id or os.environ.get("DOCUMENTAI_PROJECT_ID", "")
        self._location = location or os.environ.get("DOCUMENTAI_LOCATION", DEFAULT_LOCATION)
        self._processor_id = processor_id or os.environ.get("DOCUMENTAI_PROCESSOR_ID", "")
        self._credentials_path = credentials_path or os.environ.get(
            "GOOGLE_APPLICATION_CREDENTIALS", ""
        )
        self._timeout = timeout
        self._preprocess_watermark = preprocess_watermark
        self._watermark_remover = WatermarkRemover() if preprocess_watermark else None

    @property
    def name(self) -> str:
        return "documentai"

    def is_available(self) -> bool:
        try:
            from google.cloud import documentai as _  # noqa: F401
        except ImportError:
            logger.debug("google-cloud-documentai not installed")
            return False

        if not self._project_id or not self._processor_id:
            logger.debug(
                "Document AI missing config",
                project_id=bool(self._project_id),
                processor_id=bool(self._processor_id),
            )
            return False

        if self._credentials_path and not Path(self._credentials_path).is_file():
            logger.warning(
                "GOOGLE_APPLICATION_CREDENTIALS file not found",
                path=self._credentials_path,
            )
            return False

        return True

    def extract(
        self,
        pdf_path: Path,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> OcrResult:
        timeout = timeout or self._timeout
        start = time.perf_counter()

        pdf_bytes = pdf_path.read_bytes()

        # Pré-processar para remover marcas d'água se habilitado
        if self._watermark_remover and kwargs.get("preprocess_watermark", True):
            try:
                pdf_bytes = self._watermark_remover.clean_pdf_bytes(pdf_bytes)
                logger.info("Watermark removal applied")
            except Exception as e:
                logger.warning(
                    "Watermark removal failed, using original PDF",
                    error=str(e),
                )

        total_pages = self._count_pages(pdf_bytes)

        if total_pages <= MAX_PAGES_PER_REQUEST:
            pages = self._process_single(pdf_bytes, total_pages, timeout, start)
        else:
            pages = self._process_chunked(pdf_bytes, total_pages, timeout, start)

        processing_time = time.perf_counter() - start
        full_text = "\n\n".join(p.text for p in pages if p.text)
        avg_confidence = (
            sum(p.confidence for p in pages) / len(pages) if pages else 0.0
        )

        warnings: list[str] = []
        if avg_confidence < 0.7:
            warnings.append(f"Low average confidence: {avg_confidence:.2f}")

        return OcrResult(
            text=full_text,
            pages=pages,
            confidence=avg_confidence,
            engine_used=self.name,
            processing_time=processing_time,
            pdf_type=PdfType.IMAGE,
            warnings=warnings,
            metadata={
                "project_id": self._project_id,
                "processor_id": self._processor_id,
                "location": self._location,
                "chunked": total_pages > MAX_PAGES_PER_REQUEST,
            },
        )

    @staticmethod
    def _count_pages(pdf_bytes: bytes) -> int:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            return len(doc)

    def _process_single(
        self,
        pdf_bytes: bytes,
        total_pages: int,
        timeout: int,
        start: float,
    ) -> list[PageResult]:
        try:
            document = self._call_documentai(pdf_bytes, timeout)
        except Exception as e:
            elapsed = time.perf_counter() - start
            if elapsed >= timeout:
                raise OcrTimeoutError(f"Document AI timed out after {timeout}s")
            raise OcrExtractionError(f"Document AI failed: {e}")

        return self._extract_pages_from_document(
            document=document,
            page_offset=0,
            total_pages=total_pages,
        )

    def _process_chunked(
        self,
        pdf_bytes: bytes,
        total_pages: int,
        timeout: int,
        start: float,
    ) -> list[PageResult]:
        chunks = self._split_pdf(pdf_bytes, MAX_PAGES_PER_REQUEST)
        all_pages: list[PageResult] = []
        page_offset = 0

        for idx, (chunk_bytes, chunk_page_count) in enumerate(chunks):
            elapsed = time.perf_counter() - start
            remaining = timeout - elapsed
            if remaining <= 5:
                raise OcrTimeoutError(
                    f"Document AI timed out after {elapsed:.0f}s "
                    f"(processed {idx}/{len(chunks)} chunks)"
                )

            try:
                document = self._call_documentai(chunk_bytes, int(remaining))
            except Exception as e:
                elapsed = time.perf_counter() - start
                if elapsed >= timeout:
                    raise OcrTimeoutError(f"Document AI timed out after {timeout}s")
                raise OcrExtractionError(
                    f"Document AI failed on chunk {idx + 1}/{len(chunks)}: {e}"
                )

            chunk_pages = self._extract_pages_from_document(
                document=document,
                page_offset=page_offset,
                total_pages=total_pages,
            )
            all_pages.extend(chunk_pages)
            page_offset += chunk_page_count

        return all_pages

    @staticmethod
    def _split_pdf(
        pdf_bytes: bytes,
        max_pages: int,
    ) -> list[tuple[bytes, int]]:
        src = fitz.open(stream=pdf_bytes, filetype="pdf")
        total = len(src)
        chunks: list[tuple[bytes, int]] = []

        for start_page in range(0, total, max_pages):
            end_page = min(start_page + max_pages, total) - 1
            chunk_doc = fitz.open()
            chunk_doc.insert_pdf(src, from_page=start_page, to_page=end_page)
            chunk_bytes = chunk_doc.tobytes()
            chunk_doc.close()
            chunks.append((chunk_bytes, end_page - start_page + 1))

        src.close()
        return chunks

    def _extract_pages_from_document(
        self,
        document,
        page_offset: int,
        total_pages: int,
    ) -> list[PageResult]:
        pages: list[PageResult] = []

        for local_idx, page in enumerate(document.pages):
            page_num = page_offset + local_idx + 1
            page_text = self._get_page_text(document.text, page)
            page_text = self._postprocess(page_text, page_num, total_pages)
            confidence = self._page_confidence(page)
            words = self._extract_word_boxes(document.text, page)
            page_width = int(page.dimension.width) if page.dimension else None
            page_height = int(page.dimension.height) if page.dimension else None

            pages.append(
                PageResult(
                    page_number=page_num,
                    text=page_text,
                    confidence=confidence,
                    width=page_width,
                    height=page_height,
                    words=words,
                )
            )

        return pages

    @staticmethod
    def _extract_word_boxes(full_text: str, page) -> list[WordBox]:
        words: list[WordBox] = []
        page_w = float(page.dimension.width) if page.dimension else 1.0
        page_h = float(page.dimension.height) if page.dimension else 1.0
        tokens = getattr(page, "tokens", None) or []

        for token in tokens:
            layout = token.layout
            if not layout:
                continue

            token_text = ""
            if layout.text_anchor and layout.text_anchor.text_segments:
                for seg in layout.text_anchor.text_segments:
                    start = int(seg.start_index) if seg.start_index else 0
                    end = int(seg.end_index)
                    token_text += full_text[start:end]
            token_text = token_text.strip()
            if not token_text:
                continue

            bbox = _bounding_poly_to_pixels(layout.bounding_poly, page_w, page_h)
            if bbox is None:
                continue
            left, top, right, bottom = bbox
            conf = float(layout.confidence) if layout.confidence else 0.0

            words.append(
                WordBox(
                    text=token_text,
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                    confidence=conf,
                )
            )

        if not words:
            words = _extract_words_from_lines(full_text, page, page_w, page_h)

        return words

    def _call_documentai(self, pdf_bytes: bytes, timeout: int):
        from google.cloud import documentai

        if self._credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self._credentials_path

        client = documentai.DocumentProcessorServiceClient(
            client_options={
                "api_endpoint": f"{self._location}-documentai.googleapis.com",
            }
        )
        processor_name = client.processor_path(
            self._project_id, self._location, self._processor_id
        )
        raw_document = documentai.RawDocument(
            content=pdf_bytes,
            mime_type="application/pdf",
        )
        request = documentai.ProcessRequest(
            name=processor_name,
            raw_document=raw_document,
        )
        result = client.process_document(request=request, timeout=timeout)
        return result.document

    @staticmethod
    def _get_page_text(full_text: str, page) -> str:
        if not page.layout or not page.layout.text_anchor:
            return ""

        text_parts: list[str] = []
        for seg in page.layout.text_anchor.text_segments:
            start = int(seg.start_index) if seg.start_index else 0
            end = int(seg.end_index)
            text_parts.append(full_text[start:end])

        return "".join(text_parts)

    @staticmethod
    def _page_confidence(page) -> float:
        if not page.blocks:
            if page.layout and page.layout.confidence:
                return float(page.layout.confidence)
            return 0.5

        confidences = [
            float(block.layout.confidence)
            for block in page.blocks
            if block.layout and block.layout.confidence
        ]
        if not confidences:
            return 0.5
        return sum(confidences) / len(confidences)

    @classmethod
    def _postprocess(cls, text: str, page_number: int, total_pages: int) -> str:
        if not text:
            return ""
        text = cls._fix_currency_spacing(text)
        text = cls._ensure_page_footer(text, page_number, total_pages)
        return text.strip()

    @staticmethod
    def _fix_currency_spacing(text: str) -> str:
        # Corrigir espaço indevido em decimais: "1 ,00" -> "1,00" 
        text = re.sub(r"(\d)\s+,(\d{2})", r"\1,\2", text)
        # Corrigir espaço indevido em milhares: "1 .000" -> "1.000"
        text = re.sub(r"(\d)\s+\.(\d{3})", r"\1.\2", text)
        # Corrigir ponto usado como decimal em formato BR:
        # "0.00" isolado ou no final de uma sequência de valores -> "0,00"
        # Detecta padrão: dígito(s).DD onde DD são exatamente 2 dígitos
        # e o valor NÃO tem outros pontos antes (ou seja, não é 358.550.20)
        # Para valores como "358.550.20": último ".20" é decimal, converter para ",20"
        text = re.sub(
            r"(\d{1,3}(?:\.\d{3})*)\.(\d{2})(?=\s|$)",
            r"\1,\2",
            text,
        )
        return text

    @staticmethod
    def _ensure_page_footer(text: str, page_number: int, total_pages: int) -> str:
        page_pattern = re.compile(r"P[aá]gina\s*\d+\s*(?:de|DE)\s*\d+", re.IGNORECASE)
        if not page_pattern.search(text):
            text = f"{text}\nPagina {page_number} de {total_pages}"
        return text


def _bounding_poly_to_pixels(
    bounding_poly,
    page_w: float,
    page_h: float,
) -> tuple[float, float, float, float] | None:
    if not bounding_poly:
        return None

    normalized_vertices = getattr(bounding_poly, "normalized_vertices", None)
    if normalized_vertices and len(normalized_vertices) >= 4:
        xs = [vertex.x * page_w for vertex in normalized_vertices]
        ys = [vertex.y * page_h for vertex in normalized_vertices]
        return min(xs), min(ys), max(xs), max(ys)

    vertices = getattr(bounding_poly, "vertices", None)
    if vertices and len(vertices) >= 4:
        xs = [float(vertex.x) for vertex in vertices]
        ys = [float(vertex.y) for vertex in vertices]
        return min(xs), min(ys), max(xs), max(ys)

    return None


def _extract_words_from_lines(
    full_text: str,
    page,
    page_w: float,
    page_h: float,
) -> list[WordBox]:
    words: list[WordBox] = []
    lines = getattr(page, "lines", None) or []
    for line in lines:
        layout = line.layout
        if not layout:
            continue

        line_text = ""
        if layout.text_anchor and layout.text_anchor.text_segments:
            for seg in layout.text_anchor.text_segments:
                start = int(seg.start_index) if seg.start_index else 0
                end = int(seg.end_index)
                line_text += full_text[start:end]
        line_text = line_text.strip()
        if not line_text:
            continue

        bbox = _bounding_poly_to_pixels(layout.bounding_poly, page_w, page_h)
        if bbox is None:
            continue
        left, top, right, bottom = bbox
        conf = float(layout.confidence) if layout.confidence else 0.0

        tokens = line_text.split()
        if not tokens:
            continue

        total_chars = sum(len(token) for token in tokens)
        if total_chars == 0:
            continue

        line_width = right - left
        cursor = left
        for token in tokens:
            fraction = len(token) / total_chars
            token_width = line_width * fraction
            words.append(
                WordBox(
                    text=token,
                    left=cursor,
                    top=top,
                    right=cursor + token_width,
                    bottom=bottom,
                    confidence=conf,
                )
            )
            cursor += token_width

    return words
