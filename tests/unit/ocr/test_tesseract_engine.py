import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path
import subprocess

from irpf_processor.infrastructure.extraction.ocr.tesseract_engine import TesseractEngine
from irpf_processor.infrastructure.extraction.ocr.models import (
    EngineNotAvailableError,
    OcrExtractionError,
    OcrTimeoutError,
    OcrResult,
    PageResult,
    PdfType,
)


class TestTesseractEngineInit:

    def test_default_initialization(self):
        engine = TesseractEngine()

        assert engine._lang == "por"
        assert engine._psm == 3
        assert engine._oem == 3
        assert engine._timeout == 120

    def test_custom_initialization(self):
        engine = TesseractEngine(
            lang="eng",
            psm=6,
            oem=1,
            timeout=60
        )

        assert engine._lang == "eng"
        assert engine._psm == 6
        assert engine._oem == 1
        assert engine._timeout == 60

    def test_constants(self):
        assert TesseractEngine.DEFAULT_TIMEOUT == 120
        assert TesseractEngine.DEFAULT_LANG == "por"
        assert TesseractEngine.DEFAULT_PSM == 3
        assert TesseractEngine.DEFAULT_OEM == 3


class TestTesseractEngineName:

    def test_name_property(self):
        engine = TesseractEngine()
        assert engine.name == "tesseract"


class TestTesseractEngineIsAvailable:

    @patch("irpf_processor.infrastructure.extraction.ocr.tesseract_engine.shutil.which")
    def test_is_available_when_installed(self, mock_which):
        mock_which.return_value = "/usr/bin/tesseract"
        engine = TesseractEngine()

        assert engine.is_available() is True
        mock_which.assert_called_once_with("tesseract")

    @patch("irpf_processor.infrastructure.extraction.ocr.tesseract_engine.shutil.which")
    def test_is_not_available_when_not_installed(self, mock_which):
        mock_which.return_value = None
        engine = TesseractEngine()

        assert engine.is_available() is False


class TestTesseractEngineExtract:

    @patch.object(TesseractEngine, "is_available", return_value=False)
    def test_raises_when_not_available(self, mock_is_available):
        engine = TesseractEngine()

        with pytest.raises(EngineNotAvailableError, match="Tesseract is not installed"):
            engine.extract(Path("/test.pdf"))

    @patch.object(TesseractEngine, "is_available", return_value=True)
    @patch.object(TesseractEngine, "_extract_pages")
    def test_extract_returns_ocr_result(self, mock_extract_pages, mock_is_available):
        mock_extract_pages.return_value = [
            PageResult(page_number=1, text="Test content", confidence=0.90),
            PageResult(page_number=2, text="More content", confidence=0.85),
        ]

        engine = TesseractEngine()
        result = engine.extract(Path("/test.pdf"))

        assert isinstance(result, OcrResult)
        assert result.engine_used == "tesseract"
        assert len(result.pages) == 2
        assert "Test content" in result.text


    @patch.object(TesseractEngine, "is_available", return_value=True)
    @patch.object(TesseractEngine, "_extract_pages")
    def test_extract_adds_warning_for_low_confidence(self, mock_extract_pages, mock_is_available):
        mock_extract_pages.return_value = [
            PageResult(page_number=1, text="Test", confidence=0.50),
        ]

        engine = TesseractEngine()
        result = engine.extract(Path("/test.pdf"))

        assert len(result.warnings) > 0
        assert "Low OCR confidence" in result.warnings[0]

    @patch.object(TesseractEngine, "is_available", return_value=True)
    @patch.object(TesseractEngine, "_extract_pages")
    def test_extract_handles_timeout(self, mock_extract_pages, mock_is_available):
        mock_extract_pages.side_effect = subprocess.TimeoutExpired("tesseract", 120)

        engine = TesseractEngine()

        with pytest.raises(OcrTimeoutError):
            engine.extract(Path("/test.pdf"))

    @patch.object(TesseractEngine, "is_available", return_value=True)
    @patch.object(TesseractEngine, "_extract_pages")
    def test_extract_handles_generic_error(self, mock_extract_pages, mock_is_available):
        mock_extract_pages.side_effect = Exception("Generic error")

        engine = TesseractEngine()

        with pytest.raises(OcrExtractionError):
            engine.extract(Path("/test.pdf"))

    @patch.object(TesseractEngine, "is_available", return_value=True)
    @patch.object(TesseractEngine, "_extract_pages")
    def test_extract_with_custom_timeout(self, mock_extract_pages, mock_is_available):
        mock_extract_pages.return_value = [
            PageResult(page_number=1, text="Test", confidence=0.90),
        ]

        engine = TesseractEngine(timeout=60)
        result = engine.extract(Path("/test.pdf"), timeout=30)

        mock_extract_pages.assert_called_once()
        call_args = mock_extract_pages.call_args
        assert call_args[0][1] == 30

    @patch.object(TesseractEngine, "is_available", return_value=True)
    @patch.object(TesseractEngine, "_extract_pages")
    def test_extract_empty_pages(self, mock_extract_pages, mock_is_available):
        mock_extract_pages.return_value = []

        engine = TesseractEngine()
        result = engine.extract(Path("/test.pdf"))

        assert result.confidence == 0.0
        assert result.text == ""


class TestTesseractEngineExtractPages:

    def test_extract_pages_method_exists(self):
        engine = TesseractEngine()
        assert hasattr(engine, "_extract_pages")


class TestTesseractEngineExtractPage:

    def test_extract_page_method_exists(self):
        engine = TesseractEngine()
        assert hasattr(engine, "_extract_page")


class TestOcrModels:

    def test_ocr_result_creation(self):
        result = OcrResult(
            text="Test",
            pages=[],
            confidence=0.90,
            engine_used="tesseract",
            processing_time=1.5,
            pdf_type=PdfType.IMAGE,
            warnings=[]
        )

        assert result.text == "Test"
        assert result.confidence == 0.90

    def test_page_result_creation(self):
        result = PageResult(
            page_number=1,
            text="Test",
            confidence=0.90
        )

        assert result.page_number == 1
        assert result.text == "Test"

    def test_pdf_type_values(self):
        assert PdfType.IMAGE.value == "IMAGE"
        assert PdfType.DIGITAL.value == "DIGITAL"
        assert PdfType.MIXED.value == "MIXED"
