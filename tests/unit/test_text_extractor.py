import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from irpf_processor.domain.enums import PdfType


class MockPage:
    def __init__(self, text: str):
        self._text = text

    def extract_text(self):
        return self._text


class MockPdf:
    def __init__(self, pages_text: list):
        self.pages = [MockPage(text) for text in pages_text]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockPdfPlumber:
    def __init__(self, pages_text: list):
        self._pages_text = pages_text

    def open(self, file):
        return MockPdf(self._pages_text)


class TestPdfTextExtractor:

    def test_extract_text_single_page(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["Page 1 content"])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text("test.pdf")

        assert result == "Page 1 content"

    def test_extract_text_multiple_pages(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["Page 1", "Page 2", "Page 3"])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text("test.pdf")

        assert "Page 1" in result
        assert "Page 2" in result
        assert "Page 3" in result

    def test_extract_text_empty_page_skipped(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["Page 1", None, "Page 3"])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text("test.pdf")

        assert "Page 1" in result
        assert "Page 3" in result

    def test_extract_text_by_page(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["First page", "Second page"])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text_by_page("test.pdf")

        assert len(result) == 2
        assert result[0] == "First page"
        assert result[1] == "Second page"

    def test_extract_text_by_page_handles_none(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["Page 1", None])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text_by_page("test.pdf")

        assert len(result) == 2
        assert result[0] == "Page 1"
        assert result[1] == ""

    def test_detect_pdf_type_digital(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        long_text = "A" * 200
        mock_pdfplumber = MockPdfPlumber([long_text, long_text, long_text])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.detect_pdf_type("test.pdf")

        assert result == PdfType.DIGITAL

    def test_detect_pdf_type_image(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["", "", ""])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.detect_pdf_type("test.pdf")

        assert result == PdfType.IMAGE

    def test_detect_pdf_type_mixed(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        long_text = "A" * 200
        mock_pdfplumber = MockPdfPlumber([long_text, "", long_text, "", ""])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.detect_pdf_type("test.pdf")

        assert result == PdfType.MIXED

    def test_detect_pdf_type_unknown_no_pages(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber([])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.detect_pdf_type("test.pdf")

        assert result == PdfType.UNKNOWN

    def test_get_confidence_default(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()

        assert extractor.get_confidence() == 1.0

    def test_get_confidence_after_digital_detection(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        long_text = "A" * 200
        mock_pdfplumber = MockPdfPlumber([long_text])
        extractor._pdfplumber = mock_pdfplumber

        extractor.detect_pdf_type("test.pdf")

        assert extractor.get_confidence() == 1.0

    def test_get_confidence_after_image_detection(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber([""])
        extractor._pdfplumber = mock_pdfplumber

        extractor.detect_pdf_type("test.pdf")

        assert extractor.get_confidence() == 0.7

    def test_get_confidence_after_mixed_detection(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        long_text = "A" * 200
        mock_pdfplumber = MockPdfPlumber([long_text, ""])
        extractor._pdfplumber = mock_pdfplumber

        extractor.detect_pdf_type("test.pdf")

        assert extractor.get_confidence() == 0.8

    def test_extract_from_bytes(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["Content from bytes"])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text(b"fake pdf bytes")

        assert result == "Content from bytes"

    def test_extract_from_path_object(self):
        from irpf_processor.infrastructure.extraction.text_extractor import PdfTextExtractor

        extractor = PdfTextExtractor()
        mock_pdfplumber = MockPdfPlumber(["Content from path"])
        extractor._pdfplumber = mock_pdfplumber

        result = extractor.extract_text(Path("test.pdf"))

        assert result == "Content from path"
