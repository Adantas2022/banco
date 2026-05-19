from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from irpf_processor.infrastructure.extraction.ocr.models import (
    InvalidPdfError,
    PdfType,
    ProtectedPdfError,
)
from irpf_processor.infrastructure.extraction.ocr.pdf_type_detector import PdfTypeDetector


class TestPdfTypeDetector:

    @pytest.fixture
    def detector(self):
        return PdfTypeDetector()

    @pytest.fixture
    def mock_digital_page(self):
        page = MagicMock()
        page.extract_text.return_value = "A" * 500
        page.images = []
        page.width = 612
        page.height = 792
        return page

    @pytest.fixture
    def mock_scanned_page(self):
        page = MagicMock()
        page.extract_text.return_value = ""
        page.images = [{"width": 600, "height": 780}]
        page.width = 612
        page.height = 792
        return page

    @pytest.fixture
    def mock_mixed_page_digital(self):
        page = MagicMock()
        page.extract_text.return_value = "A" * 200
        page.images = [{"width": 100, "height": 100}]
        page.width = 612
        page.height = 792
        return page

    def test_detect_returns_pdf_type(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "A" * 500
            mock_page.images = []
            mock_page.width = 612
            mock_page.height = 792
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "test.pdf"
            pdf_path.touch()

            result = detector.detect(pdf_path)

            assert result in [PdfType.DIGITAL, PdfType.IMAGE, PdfType.MIXED, PdfType.UNKNOWN]

    def test_detect_digital_pdf_with_text_layer(self, detector, tmp_path, mock_digital_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_digital_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "digital.pdf"
            pdf_path.touch()

            result = detector.detect(pdf_path)

            assert result == PdfType.DIGITAL

    def test_detect_scanned_pdf_no_text_layer(self, detector, tmp_path, mock_scanned_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_scanned_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "scanned.pdf"
            pdf_path.touch()

            result = detector.detect(pdf_path)

            assert result == PdfType.IMAGE

    def test_detect_mixed_pdf_some_pages_scanned(
        self, detector, tmp_path, mock_digital_page, mock_scanned_page
    ):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_digital_page, mock_scanned_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "mixed.pdf"
            pdf_path.touch()

            result = detector.detect(pdf_path)

            assert result == PdfType.MIXED

    def test_detect_with_confidence_returns_detection_result(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "A" * 500
            mock_page.images = []
            mock_page.width = 612
            mock_page.height = 792
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "test.pdf"
            pdf_path.touch()

            result = detector.detect_with_confidence(pdf_path)

            assert hasattr(result, "pdf_type")
            assert hasattr(result, "confidence")
            assert 0.0 <= result.confidence <= 1.0

    def test_detect_confidence_high_for_clear_digital(self, detector, tmp_path, mock_digital_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_digital_page] * 3
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "digital.pdf"
            pdf_path.touch()

            result = detector.detect_with_confidence(pdf_path)

            assert result.confidence >= 0.90

    def test_detect_confidence_high_for_clear_scan(self, detector, tmp_path, mock_scanned_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_scanned_page] * 3
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "scanned.pdf"
            pdf_path.touch()

            result = detector.detect_with_confidence(pdf_path)

            assert result.confidence >= 0.85

    def test_detect_per_page_returns_page_types(
        self, detector, tmp_path, mock_digital_page, mock_scanned_page
    ):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_digital_page, mock_scanned_page, mock_digital_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "multi.pdf"
            pdf_path.touch()

            result = detector.detect_per_page(pdf_path)

            assert isinstance(result, list)
            assert len(result) == 3
            assert all(isinstance(t, PdfType) for t in result)

    def test_detect_handles_nonexistent_file(self, detector):
        with pytest.raises(InvalidPdfError):
            detector.detect(Path("/nonexistent/path/file.pdf"))

    def test_detect_handles_empty_pdf(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = []
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "empty.pdf"
            pdf_path.touch()

            with pytest.raises(InvalidPdfError):
                detector.detect(pdf_path)

    def test_detect_handles_password_protected_pdf(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_open.side_effect = Exception("PDF is password protected")

            pdf_path = tmp_path / "protected.pdf"
            pdf_path.touch()

            with pytest.raises(ProtectedPdfError):
                detector.detect(pdf_path)

    def test_detect_handles_corrupted_pdf(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_open.side_effect = Exception("Invalid PDF structure")

            pdf_path = tmp_path / "corrupted.pdf"
            pdf_path.touch()

            with pytest.raises(InvalidPdfError):
                detector.detect(pdf_path)

    def test_has_extractable_text_returns_true_for_digital(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "A" * 500
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "digital.pdf"
            pdf_path.touch()

            result = detector._has_extractable_text(pdf_path)

            assert result is True

    def test_has_extractable_text_returns_false_for_image(self, detector, tmp_path):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_page.extract_text.return_value = ""
            mock_pdf.pages = [mock_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "scanned.pdf"
            pdf_path.touch()

            result = detector._has_extractable_text(pdf_path)

            assert result is False

    def test_analyze_images_detects_full_page_images(self, detector, tmp_path, mock_scanned_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_scanned_page]
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "scanned.pdf"
            pdf_path.touch()

            result = detector._analyze_images(pdf_path)

            assert result is True

    def test_detection_result_includes_text_ratio(self, detector, tmp_path, mock_digital_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_digital_page] * 2
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "digital.pdf"
            pdf_path.touch()

            result = detector.detect_with_confidence(pdf_path)

            assert hasattr(result, "text_ratio")
            assert 0.0 <= result.text_ratio <= 1.0

    def test_detection_result_includes_total_pages(self, detector, tmp_path, mock_digital_page):
        with patch("pdfplumber.open") as mock_open:
            mock_pdf = MagicMock()
            mock_pdf.pages = [mock_digital_page] * 5
            mock_open.return_value.__enter__.return_value = mock_pdf

            pdf_path = tmp_path / "multi.pdf"
            pdf_path.touch()

            result = detector.detect_with_confidence(pdf_path)

            assert result.total_pages == 5
