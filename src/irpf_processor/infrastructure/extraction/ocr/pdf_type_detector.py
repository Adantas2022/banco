from pathlib import Path
from typing import Optional

import fitz  # pymupdf

from irpf_processor.shared.logging import get_logger

from .models import DetectionResult, InvalidPdfError, PdfType, ProtectedPdfError

logger = get_logger(__name__)


class PdfTypeDetector:

    TEXT_RATIO_THRESHOLD = 0.1
    MIN_CHARS_PER_PAGE = 100
    IMAGE_COVERAGE_THRESHOLD = 0.8
    MAX_PAGES_TO_ANALYZE = 10  # Analyze max 10 pages for type detection (optimization)

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

        page_types = []
        total_text_chars = 0
        total_image_coverage = 0.0
        warnings = []

        pages_indices = list(range(total_pages))
        if total_pages > self.MAX_PAGES_TO_ANALYZE:
            sample = set()
            for i in range(min(3, total_pages)):
                sample.add(i)
            sample.add(total_pages // 2)
            for i in range(max(0, total_pages - 3), total_pages):
                sample.add(i)
            pages_indices = sorted(sample)
            warnings.append(f"Sampled {len(pages_indices)}/{total_pages} pages for detection")

        for idx in pages_indices:
            page_type, chars, img_coverage = self._analyze_page(doc[idx])
            page_types.append(page_type)
            total_text_chars += chars
            total_image_coverage += img_coverage

        analyzed_count = len(pages_indices)
        digital_pages = sum(1 for pt in page_types if pt == PdfType.DIGITAL)
        image_pages = sum(1 for pt in page_types if pt == PdfType.IMAGE)

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
        sample_indices.add(total_pages // 2)
        for i in range(max(0, total_pages - 3), total_pages):
            sample_indices.add(i)

        return [pages[i] for i in sorted(sample_indices)]

    def _analyze_page(self, page: fitz.Page) -> tuple[PdfType, int, float]:
        text = page.get_text() or ""
        char_count = len(text.strip())

        page_area = page.rect.width * page.rect.height
        image_coverage = 0.0
        if page_area > 0:
            total_image_area = 0.0
            for img in page.get_images(full=True):
                for rect in page.get_image_rects(img[0]):
                    total_image_area += rect.width * rect.height
            image_coverage = min(total_image_area / page_area, 1.0)

        has_sufficient_text = char_count >= self.MIN_CHARS_PER_PAGE
        has_large_images = image_coverage >= self.IMAGE_COVERAGE_THRESHOLD

        if has_sufficient_text and not has_large_images:
            return PdfType.DIGITAL, char_count, image_coverage
        elif has_large_images and not has_sufficient_text:
            return PdfType.IMAGE, char_count, image_coverage
        elif has_sufficient_text and has_large_images:
            return PdfType.DIGITAL, char_count, image_coverage
        else:
            if char_count > 50:
                return PdfType.DIGITAL, char_count, image_coverage
            return PdfType.IMAGE, char_count, image_coverage

    def _has_extractable_text(self, pdf_path: Path) -> bool:
        try:
            doc = fitz.open(str(pdf_path))
            for i in range(min(3, doc.page_count)):
                text = doc[i].get_text() or ""
                if len(text.strip()) >= self.MIN_CHARS_PER_PAGE:
                    doc.close()
                    return True
            doc.close()
            return False
        except Exception:
            return False

    def _analyze_images(self, pdf_path: Path) -> bool:
        try:
            doc = fitz.open(str(pdf_path))
            for i in range(min(3, doc.page_count)):
                page = doc[i]
                page_area = page.rect.width * page.rect.height
                if page_area > 0:
                    total_image_area = sum(
                        rect.width * rect.height
                        for img in page.get_images(full=True)
                        for rect in page.get_image_rects(img[0])
                    )
                    if total_image_area / page_area >= self.IMAGE_COVERAGE_THRESHOLD:
                        doc.close()
                        return True
            doc.close()
            return False
        except Exception:
            return False

