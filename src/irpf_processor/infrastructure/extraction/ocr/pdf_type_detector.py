from pathlib import Path
from typing import Optional

import pdfplumber

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
            with pdfplumber.open(pdf_path) as pdf:
                return self._analyze_pdf(pdf)
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

        # Optimization: analyze only a sample of pages for large PDFs
        # Sample: first 3 pages, middle page, last 3 pages (max 10 pages)
        pages_to_analyze = self._select_sample_pages(pdf.pages, total_pages)
        
        for page in pages_to_analyze:
            page_type, chars, img_coverage = self._analyze_page(page)
            page_types.append(page_type)
            total_text_chars += chars
            total_image_coverage += img_coverage

        analyzed_count = len(pages_to_analyze)
        digital_pages = sum(1 for pt in page_types if pt == PdfType.DIGITAL)
        image_pages = sum(1 for pt in page_types if pt == PdfType.IMAGE)
        
        # If we sampled, extrapolate the page types for the full document
        if analyzed_count < total_pages:
            warnings.append(f"Sampled {analyzed_count}/{total_pages} pages for detection")

        # Calculate ratios based on analyzed pages
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
        """Select a representative sample of pages for analysis.
        
        For small PDFs (<=10 pages): analyze all pages
        For large PDFs: sample first 3, middle, and last 3 pages (max 10)
        
        This optimization significantly speeds up detection for large documents.
        """
        if total_pages <= self.MAX_PAGES_TO_ANALYZE:
            return pages
        
        sample_indices = set()
        
        # First 3 pages
        for i in range(min(3, total_pages)):
            sample_indices.add(i)
        
        # Middle page
        middle = total_pages // 2
        sample_indices.add(middle)
        
        # Last 3 pages
        for i in range(max(0, total_pages - 3), total_pages):
            sample_indices.add(i)
        
        # Sort indices and get corresponding pages
        sorted_indices = sorted(sample_indices)
        return [pages[i] for i in sorted_indices]

    def _analyze_page(self, page: pdfplumber.PDF) -> tuple[PdfType, int, float]:
        text = page.extract_text() or ""
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
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages[:3]:
                    text = page.extract_text() or ""
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
