from pathlib import Path
from unittest.mock import patch

import pytest

from irpf_processor.infrastructure.extraction.ocr.models import (
    InvalidPdfError,
    PdfType,
    ProtectedPdfError,
)
from irpf_processor.infrastructure.extraction.ocr.pdf_type_detector import PdfTypeDetector


def _make_page_info(char_count: int, image_coverage: float = 0.0) -> dict:
    return {
        "page_index": 0,
        "width": 612.0,
        "height": 792.0,
        "char_count": char_count,
        "image_coverage": image_coverage,
    }


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

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_all_digital_pages(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(500), _make_page_info(600)],
            2,
            [],
        )
        pdf_path = tmp_path / "digital.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.DIGITAL
        assert result.confidence >= 0.90
        assert result.total_pages == 2

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_all_image_pages(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(0, 0.9), _make_page_info(5, 0.95)],
            2,
            [],
        )
        pdf_path = tmp_path / "scanned.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.IMAGE
        assert result.confidence >= 0.85

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_mixed_pages(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(500, 0.0), _make_page_info(5, 0.95)],
            2,
            [],
        )
        pdf_path = tmp_path / "mixed.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.MIXED
        assert result.confidence == 0.75

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_timeout_fallback_to_image(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [],
            0,
            ["PROCESS_TIMEOUT: Análise excedeu 120s"],
        )
        pdf_path = tmp_path / "timeout.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.IMAGE
        assert result.confidence == 0.6
        assert any("DETECTION_FALLBACK" in w for w in result.warnings)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_empty_pdf_raises_error(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = ([], 0, [])
        pdf_path = tmp_path / "empty.pdf"
        pdf_path.touch()

        with pytest.raises(InvalidPdfError):
            detector.detect_with_confidence(pdf_path)

    def test_nonexistent_file_raises_error(self, detector):
        with pytest.raises(InvalidPdfError):
            detector.detect_with_confidence(Path("/nonexistent/file.pdf"))

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_password_protected_raises_error(self, mock_analyze, detector, tmp_path):
        mock_analyze.side_effect = Exception("PDF is password protected")
        pdf_path = tmp_path / "protected.pdf"
        pdf_path.touch()

        with pytest.raises(ProtectedPdfError):
            detector.detect_with_confidence(pdf_path)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_corrupted_pdf_raises_error(self, mock_analyze, detector, tmp_path):
        mock_analyze.side_effect = Exception("Invalid PDF structure")
        pdf_path = tmp_path / "corrupted.pdf"
        pdf_path.touch()

        with pytest.raises(InvalidPdfError):
            detector.detect_with_confidence(pdf_path)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_sampled_pages_warning(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(500)] * 7,
            50,
            [],
        )
        pdf_path = tmp_path / "large.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.total_pages == 50
        assert any("Sampled" in w for w in result.warnings)

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_low_text_digital_reduces_confidence(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(100, 0.0)],
            1,
            [],
        )
        pdf_path = tmp_path / "low_text.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.DIGITAL
        assert result.confidence == 0.95

        mock_analyze.return_value = (
            [_make_page_info(100, 0.0), _make_page_info(50, 0.0)],
            2,
            [],
        )
        result2 = detector.detect_with_confidence(pdf_path)
        assert result2.confidence < 0.95

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_page_timeout_counted_as_image(self, mock_analyze, detector, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(500, 0.0)],
            2,
            ["TYPE_DETECT_TIMEOUT: Page 2 text extraction timed out"],
        )
        pdf_path = tmp_path / "partial_timeout.pdf"
        pdf_path.touch()

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.MIXED


class TestDetect:

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_detect_returns_pdf_type(self, mock_analyze, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(500)],
            1,
            [],
        )
        detector = PdfTypeDetector()
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        result = detector.detect(pdf_path)

        assert result in [PdfType.DIGITAL, PdfType.IMAGE, PdfType.MIXED, PdfType.UNKNOWN]

    @patch("irpf_processor.infrastructure.extraction.ocr.pdf_type_detector.analyze_pdf_pages")
    def test_detect_per_page_returns_list(self, mock_analyze, tmp_path):
        mock_analyze.return_value = (
            [_make_page_info(500, 0.0), _make_page_info(0, 0.9), _make_page_info(400, 0.0)],
            3,
            [],
        )
        detector = PdfTypeDetector()
        pdf_path = tmp_path / "multi.pdf"
        pdf_path.touch()

        result = detector.detect_per_page(pdf_path)

        assert isinstance(result, list)
        assert len(result) == 3
        assert all(isinstance(t, PdfType) for t in result)
