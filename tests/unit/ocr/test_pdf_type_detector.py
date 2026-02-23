from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from irpf_processor.infrastructure.extraction.ocr.models import (
    InvalidPdfError,
    PdfType,
    ProtectedPdfError,
)
from irpf_processor.infrastructure.extraction.ocr.pdf_type_detector import PdfTypeDetector


def _make_mock_page(char_count: int, image_coverage: float = 0.0, page_number: int = 1):
    page = MagicMock()
    page.width = 612.0
    page.height = 792.0
    page.page_number = page_number

    text = "x" * char_count if char_count > 0 else ""
    page.extract_text.return_value = text

    if image_coverage > 0:
        page_area = page.width * page.height
        img_area = page_area * image_coverage
        page.images = [{"width": img_area ** 0.5, "height": img_area ** 0.5}]
    else:
        page.images = []

    return page


def _make_mock_pdf(pages):
    pdf = MagicMock()
    pdf.pages = pages
    pdf.__enter__ = MagicMock(return_value=pdf)
    pdf.__exit__ = MagicMock(return_value=False)
    return pdf


class TestClassifyPage:

    @pytest.fixture
    def detector(self):
        return PdfTypeDetector()

    def test_high_text_low_image_is_digital(self, detector):
        assert detector._classify_page(500, 0.1) == PdfType.DIGITAL

    def test_low_text_high_image_is_image(self, detector):
        assert detector._classify_page(10, 0.9) == PdfType.IMAGE

    def test_high_text_high_image_is_digital(self, detector):
        assert detector._classify_page(500, 0.9) == PdfType.DIGITAL

    def test_no_text_no_image_is_image(self, detector):
        assert detector._classify_page(0, 0.0) == PdfType.IMAGE

    def test_ambiguous_low_chars_is_image(self, detector):
        assert detector._classify_page(20, 0.0) == PdfType.IMAGE

    def test_ambiguous_mid_chars_with_some_image_is_image(self, detector):
        assert detector._classify_page(60, 0.4) == PdfType.IMAGE

    def test_ambiguous_mid_chars_no_image_still_image(self, detector):
        assert detector._classify_page(60, 0.0) == PdfType.IMAGE

    def test_exactly_min_chars_is_digital(self, detector):
        assert detector._classify_page(100, 0.0) == PdfType.DIGITAL


class TestDetectWithConfidence:

    @pytest.fixture
    def detector(self):
        return PdfTypeDetector()

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_all_digital_pages(self, mock_pdfplumber, detector, tmp_path):
        pages = [_make_mock_page(500), _make_mock_page(600, page_number=2)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        pdf_path = tmp_path / "digital.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.DIGITAL
        assert result.confidence >= 0.90
        assert result.total_pages == 2

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_all_image_pages(self, mock_pdfplumber, detector, tmp_path):
        pages = [_make_mock_page(0, 0.9), _make_mock_page(5, 0.95, page_number=2)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        pdf_path = tmp_path / "scanned.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.IMAGE
        assert result.confidence >= 0.85

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_mixed_pages(self, mock_pdfplumber, detector, tmp_path):
        pages = [_make_mock_page(500, 0.0), _make_mock_page(5, 0.95, page_number=2)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        pdf_path = tmp_path / "mixed.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.MIXED
        assert result.confidence == 0.75

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_empty_pdf_raises_error(self, mock_pdfplumber, detector, tmp_path):
        mock_pdfplumber.open.return_value = _make_mock_pdf([])

        pdf_path = tmp_path / "empty.pdf"
        pdf_path.touch()

        with pytest.raises(InvalidPdfError):
            detector.detect_with_confidence(pdf_path)

    def test_nonexistent_file_raises_error(self, detector):
        with pytest.raises(InvalidPdfError):
            detector.detect_with_confidence(Path("/nonexistent/file.pdf"))

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_password_protected_raises_error(self, mock_pdfplumber, detector, tmp_path):
        mock_pdfplumber.open.side_effect = Exception("PDF is password protected")

        pdf_path = tmp_path / "protected.pdf"
        pdf_path.touch()

        with pytest.raises(ProtectedPdfError):
            detector.detect_with_confidence(pdf_path)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_corrupted_pdf_raises_error(self, mock_pdfplumber, detector, tmp_path):
        mock_pdfplumber.open.side_effect = Exception("Invalid PDF structure")

        pdf_path = tmp_path / "corrupted.pdf"
        pdf_path.touch()

        with pytest.raises(InvalidPdfError):
            detector.detect_with_confidence(pdf_path)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_sampled_pages_warning(self, mock_pdfplumber, detector, tmp_path):
        pages = [_make_mock_page(500, page_number=i + 1) for i in range(50)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        pdf_path = tmp_path / "large.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.total_pages == 50
        assert any("Sampled" in w for w in result.warnings)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_low_text_digital_reduces_confidence(self, mock_pdfplumber, detector, tmp_path):
        pages = [_make_mock_page(100, 0.0)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        pdf_path = tmp_path / "low_text.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.DIGITAL
        assert result.confidence == 0.95

        pages2 = [_make_mock_page(100, 0.0), _make_mock_page(50, 0.0, page_number=2)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages2)
        result2 = detector.detect_with_confidence(pdf_path)
        assert result2.confidence < 0.95


class TestDetect:

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_detect_returns_pdf_type(self, mock_pdfplumber, tmp_path):
        pages = [_make_mock_page(500)]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        detector = PdfTypeDetector()
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        result = detector.detect(pdf_path)

        assert result in [PdfType.DIGITAL, PdfType.IMAGE, PdfType.MIXED, PdfType.UNKNOWN]

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.pdfplumber")
    def test_detect_per_page_returns_list(self, mock_pdfplumber, tmp_path):
        pages = [
            _make_mock_page(500, 0.0),
            _make_mock_page(0, 0.9, page_number=2),
            _make_mock_page(400, 0.0, page_number=3),
        ]
        mock_pdfplumber.open.return_value = _make_mock_pdf(pages)

        detector = PdfTypeDetector()
        pdf_path = tmp_path / "multi.pdf"
        pdf_path.touch()

        result = detector.detect_per_page(pdf_path)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(t, PdfType) for t in result)
