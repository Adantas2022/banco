from __future__ import annotations

from pathlib import Path

from irpf_processor.infrastructure.extraction.safe_pdf_extractor import analyze_pdf_pages
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
            return self._detect_via_subprocess(pdf_path)
        except (InvalidPdfError, ProtectedPdfError):
            raise
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise ProtectedPdfError(f"PDF is password protected: {pdf_path}")
            raise InvalidPdfError(f"Failed to analyze PDF: {e}")

    def detect_per_page(self, pdf_path: Path) -> list[PdfType]:
        result = self.detect_with_confidence(pdf_path)
        return result.page_types

    def _detect_via_subprocess(self, pdf_path: Path) -> DetectionResult:
        page_infos, total_pages, warnings = analyze_pdf_pages(
            pdf_path,
            max_sample=self.MAX_PAGES_TO_ANALYZE,
            page_timeout_s=15,
            total_timeout_s=120,
        )

        if total_pages == 0 and not page_infos:
            if any("TIMEOUT" in w for w in warnings):
                logger.warning(
                    "PDF analysis timed out, classifying as IMAGE for OCR safety",
                    pdf_path=str(pdf_path),
                    warnings=warnings,
                )
                return DetectionResult(
                    pdf_type=PdfType.IMAGE,
                    confidence=0.6,
                    page_types=[],
                    text_ratio=0.0,
                    image_ratio=1.0,
                    total_pages=0,
                    warnings=warnings + ["DETECTION_FALLBACK: timeout -> IMAGE"],
                )
            raise InvalidPdfError(f"PDF has no pages or could not be opened: {warnings}")

        page_types = []
        total_text_chars = 0
        total_image_coverage = 0.0

        for info in page_infos:
            char_count = info.get("char_count", 0)
            image_coverage = info.get("image_coverage", 0.0)

            page_type = self._classify_page(char_count, image_coverage)
            page_types.append(page_type)
            total_text_chars += char_count
            total_image_coverage += image_coverage

        for w in warnings:
            if "TYPE_DETECT_TIMEOUT" in w:
                page_types.append(PdfType.IMAGE)

        analyzed_count = len(page_types) or 1
        digital_pages = sum(1 for pt in page_types if pt == PdfType.DIGITAL)
        image_pages = sum(1 for pt in page_types if pt == PdfType.IMAGE)

        if analyzed_count < total_pages:
            warnings.append(f"Sampled {len(page_infos)}/{total_pages} pages for detection")

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
            analyzed_pages=len(page_infos),
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
