from __future__ import annotations

from pathlib import Path

import pdfplumber

from irpf_processor.shared.logging import get_logger

from .models import DetectionResult, InvalidPdfError, PdfType, ProtectedPdfError

logger = get_logger(__name__)


class PdfTypeDetector:

    MIN_CHARS_PER_PAGE = 100
    IMAGE_COVERAGE_THRESHOLD = 0.8
    MAX_PAGES_TO_ANALYZE = 10

    AMBIGUOUS_CHAR_FLOOR = 30
    AMBIGUOUS_IMAGE_FLOOR = 0.3

    def detect(self, pdf_path: Path) -> PdfType:
        result = self.detect_with_confidence(pdf_path)
        return result.pdf_type

    def detect_with_confidence(self, pdf_path: Path) -> DetectionResult:
        if not pdf_path.exists():
            raise InvalidPdfError(f"PDF file not found: {pdf_path}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                return self._analyze_pdf(pdf)
        except (InvalidPdfError, ProtectedPdfError):
            raise
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise ProtectedPdfError(f"PDF is password protected: {pdf_path}")
            raise InvalidPdfError(f"Failed to open PDF: {e}")

    def detect_per_page(self, pdf_path: Path) -> list[PdfType]:
        result = self.detect_with_confidence(pdf_path)
        return result.page_types

    def _analyze_pdf(self, pdf: pdfplumber.PDF) -> DetectionResult:
        total_pages = len(pdf.pages)
        if total_pages == 0:
            raise InvalidPdfError("PDF has no pages")

        page_types = []
        total_text_chars = 0
        total_image_coverage = 0.0
        warnings = []

        pages_to_analyze = self._select_sample_pages(pdf.pages, total_pages)

        for page in pages_to_analyze:
            page_type, chars, img_coverage = self._analyze_page(page)
            page_types.append(page_type)
            total_text_chars += chars
            total_image_coverage += img_coverage

        analyzed_count = len(pages_to_analyze)
        digital_pages = sum(1 for pt in page_types if pt == PdfType.DIGITAL)
        image_pages = sum(1 for pt in page_types if pt == PdfType.IMAGE)

        if analyzed_count < total_pages:
            warnings.append(f"Sampled {analyzed_count}/{total_pages} pages for detection")

        text_ratio = digital_pages / analyzed_count
        image_ratio = image_pages / analyzed_count

        if digital_pages == analyzed_count:
            pdf_type = PdfType.DIGITAL
            confidence = 0.95
        elif image_pages == analyzed_count:
            pdf_type = PdfType.IMAGE
            confidence = 0.90
        elif digital_pages > 0 and image_pages > 0:
            pdf_type = PdfType.MIXED
            confidence = 0.75
            warnings.append(f"Mixed PDF: {digital_pages} digital, {image_pages} scanned pages")
        else:
            pdf_type = PdfType.UNKNOWN
            confidence = 0.5
            warnings.append("Could not determine PDF type")

        avg_chars_per_page = total_text_chars / analyzed_count
        if avg_chars_per_page < self.MIN_CHARS_PER_PAGE and pdf_type == PdfType.DIGITAL:
            confidence *= 0.8
            warnings.append(f"Low text content: {avg_chars_per_page:.0f} chars/page average")

        logger.info(
            "PDF type detected",
            pdf_type=pdf_type.value,
            confidence=confidence,
            total_pages=total_pages,
            analyzed_pages=analyzed_count,
            digital_pages=digital_pages,
            image_pages=image_pages,
            avg_chars_per_page=round(avg_chars_per_page, 1),
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

    def _select_sample_pages(self, pages: list, total_pages: int) -> list:
        if total_pages <= self.MAX_PAGES_TO_ANALYZE:
            return pages

        sample_indices = set()

        for i in range(min(3, total_pages)):
            sample_indices.add(i)

        middle = total_pages // 2
        sample_indices.add(middle)

        for i in range(max(0, total_pages - 3), total_pages):
            sample_indices.add(i)

        sorted_indices = sorted(sample_indices)
        return [pages[i] for i in sorted_indices]

    def _analyze_page(self, page) -> tuple[PdfType, int, float]:
        text = self._extract_text_safe(page)
        char_count = len(text.strip())

        images = page.images or []
        page_area = page.width * page.height
        image_coverage = 0.0

        if images and page_area > 0:
            total_image_area = sum(
                (img.get("width", 0) or 0) * (img.get("height", 0) or 0)
                for img in images
            )
            image_coverage = min(total_image_area / page_area, 1.0)

        page_type = self._classify_page(char_count, image_coverage)
        return page_type, char_count, image_coverage

    def _classify_page(self, char_count: int, image_coverage: float) -> PdfType:
        has_sufficient_text = char_count >= self.MIN_CHARS_PER_PAGE
        has_large_images = image_coverage >= self.IMAGE_COVERAGE_THRESHOLD

        if has_sufficient_text and not has_large_images:
            return PdfType.DIGITAL
        if has_large_images and not has_sufficient_text:
            return PdfType.IMAGE
        if has_sufficient_text and has_large_images:
            return PdfType.DIGITAL

        if char_count < self.AMBIGUOUS_CHAR_FLOOR:
            return PdfType.IMAGE
        if image_coverage >= self.AMBIGUOUS_IMAGE_FLOOR:
            return PdfType.IMAGE
        return PdfType.IMAGE

    def _extract_text_safe(self, page) -> str:
        try:
            return page.extract_text() or ""
        except Exception as e:
            logger.warning(
                "Page text extraction failed in PdfTypeDetector",
                page_number=getattr(page, "page_number", "?"),
                error=str(e),
            )
            return ""

    def _has_extractable_text(self, pdf_path: Path) -> bool:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:3]:
                    text = self._extract_text_safe(page)
                    if len(text.strip()) >= self.MIN_CHARS_PER_PAGE:
                        return True
            return False
        except Exception:
            return False

    def _analyze_images(self, pdf_path: Path) -> bool:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:3]:
                    images = page.images or []
                    if images:
                        page_area = page.width * page.height
                        total_image_area = sum(
                            (img.get("width", 0) or 0) * (img.get("height", 0) or 0)
                            for img in images
                        )
                        if page_area > 0 and total_image_area / page_area >= self.IMAGE_COVERAGE_THRESHOLD:
                            return True
            return False
        except Exception:
            return False
