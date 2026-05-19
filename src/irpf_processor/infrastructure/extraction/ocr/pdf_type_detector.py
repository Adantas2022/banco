import random
from pathlib import Path
from statistics import median

import fitz  # pymupdf

from irpf_processor.shared.logging import get_logger

from .models import DetectionResult, InvalidPdfError, PdfType, ProtectedPdfError

logger = get_logger(__name__)


class PdfTypeDetector:

    MIN_CHARS_PER_PAGE = 500
    MAX_PAGES_TO_ANALYZE = 10  # Sample up to 10 non-last pages for type detection

    def detect(self, pdf_path: Path) -> PdfType:
        result = self.detect_with_confidence(pdf_path)
        return result.pdf_type

    def detect_with_confidence(self, pdf_path: Path) -> DetectionResult:
        if not pdf_path.exists():
            raise InvalidPdfError(f"PDF file not found: {pdf_path}")

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise ProtectedPdfError(f"PDF is password protected: {pdf_path}")
            raise InvalidPdfError(f"Failed to open PDF: {e}")

        try:
            return self._analyze_pdf(doc)
        finally:
            doc.close()

    def detect_per_page(self, pdf_path: Path) -> list[PdfType]:
        result = self.detect_with_confidence(pdf_path)
        return result.page_types

    def _analyze_pdf(self, doc: fitz.Document) -> DetectionResult:
        total_pages = doc.page_count
        if total_pages == 0:
            raise InvalidPdfError("PDF has no pages")

        warnings = []
        page_char_counts = [self._count_page_chars(doc[index]) for index in range(total_pages)]
        page_types = [self._classify_by_char_count(char_count) for char_count in page_char_counts]

        sample_indices = self._select_sample_page_indices(total_pages)
        sampled_char_counts = [page_char_counts[index] for index in sample_indices]
        median_char_count = median(sampled_char_counts)

        if total_pages == 1:
            warnings.append("Single-page PDF: analyzed the only page for detection")
        elif len(sample_indices) < total_pages - 1:
            warnings.append(
                f"Sampled {len(sample_indices)}/{total_pages - 1} non-last pages for detection"
            )

        analyzed_count = len(sample_indices)
        digital_pages = sum(1 for pt in page_types if pt == PdfType.DIGITAL)
        image_pages = sum(1 for pt in page_types if pt == PdfType.IMAGE)

        text_ratio = digital_pages / total_pages
        image_ratio = image_pages / total_pages

        pdf_type = self._classify_by_char_count(median_char_count)
        confidence = 0.95 if pdf_type == PdfType.DIGITAL else 0.90

        logger.info(
            "PDF type detected",
            pdf_type=pdf_type.value,
            confidence=confidence,
            total_pages=total_pages,
            analyzed_pages=analyzed_count,
            median_char_count=median_char_count,
            threshold=self.MIN_CHARS_PER_PAGE,
            digital_pages=digital_pages,
            image_pages=image_pages,
        )

        return DetectionResult(
            pdf_type=pdf_type,
            confidence=confidence,
            page_types=page_types,
            text_ratio=text_ratio,
            image_ratio=image_ratio,
            total_pages=total_pages,
            warnings=warnings,
        )

    def _select_sample_page_indices(self, total_pages: int) -> list[int]:
        if total_pages == 1:
            return [0]

        eligible_indices = list(range(total_pages - 1))
        if len(eligible_indices) <= self.MAX_PAGES_TO_ANALYZE:
            return eligible_indices

        return sorted(random.sample(eligible_indices, self.MAX_PAGES_TO_ANALYZE))

    def _count_page_chars(self, page: fitz.Page) -> int:
        text = page.get_text() or ""
        return len(text.strip())

    def _classify_by_char_count(self, char_count: float) -> PdfType:
        if char_count > self.MIN_CHARS_PER_PAGE:
            return PdfType.DIGITAL
        return PdfType.IMAGE

