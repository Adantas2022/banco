import pytest

from irpf_processor.infrastructure.extraction.ocr.models import (
    DetectionResult,
    OcrResult,
    PageResult,
    PdfType,
    TableData,
)


class TestPdfType:

    def test_pdf_type_has_expected_values(self):
        assert PdfType.DIGITAL.value == "DIGITAL"
        assert PdfType.IMAGE.value == "IMAGE"
        assert PdfType.MIXED.value == "MIXED"
        assert PdfType.UNKNOWN.value == "UNKNOWN"


class TestTableData:

    def test_table_data_creation(self):
        table = TableData(
            rows=3,
            columns=4,
            headers=["A", "B", "C", "D"],
            data=[["1", "2", "3", "4"], ["5", "6", "7", "8"], ["9", "10", "11", "12"]],
            confidence=0.85,
        )

        assert table.rows == 3
        assert table.columns == 4
        assert len(table.headers) == 4
        assert len(table.data) == 3

    def test_table_data_to_dict(self):
        table = TableData(
            rows=2,
            columns=2,
            headers=["X", "Y"],
            data=[["a", "b"], ["c", "d"]],
        )

        result = table.to_dict()

        assert "rows" in result
        assert "columns" in result
        assert "headers" in result
        assert "data" in result


class TestPageResult:

    def test_page_result_creation(self):
        page = PageResult(
            page_number=1,
            text="Sample text",
            confidence=0.9,
        )

        assert page.page_number == 1
        assert page.text == "Sample text"
        assert page.confidence == 0.9
        assert page.tables == []

    def test_page_result_with_tables(self):
        table = TableData(
            rows=1,
            columns=1,
            headers=["H"],
            data=[["V"]],
        )

        page = PageResult(
            page_number=1,
            text="Text",
            tables=[table],
            confidence=0.8,
        )

        assert len(page.tables) == 1
        assert page.tables[0].rows == 1

    def test_page_result_to_dict(self):
        page = PageResult(
            page_number=2,
            text="Test",
            confidence=0.75,
            warnings=["Low quality"],
        )

        result = page.to_dict()

        assert result["page_number"] == 2
        assert result["text"] == "Test"
        assert result["confidence"] == 0.75
        assert "Low quality" in result["warnings"]


class TestOcrResult:

    def test_ocr_result_creation(self):
        result = OcrResult(
            text="Full text",
            confidence=0.85,
            engine_used="tesseract",
            processing_time=2.5,
        )

        assert result.text == "Full text"
        assert result.confidence == 0.85
        assert result.engine_used == "tesseract"
        assert result.processing_time == 2.5

    def test_ocr_result_total_pages(self):
        pages = [
            PageResult(page_number=1, text="Page 1", confidence=0.9),
            PageResult(page_number=2, text="Page 2", confidence=0.8),
        ]

        result = OcrResult(text="All", pages=pages)

        assert result.total_pages == 2

    def test_ocr_result_has_tables(self):
        table = TableData(rows=1, columns=1, headers=["H"], data=[["V"]])
        page_with_table = PageResult(page_number=1, text="T", tables=[table])
        page_without_table = PageResult(page_number=2, text="T")

        result_with_tables = OcrResult(text="", pages=[page_with_table])
        result_without_tables = OcrResult(text="", pages=[page_without_table])

        assert result_with_tables.has_tables is True
        assert result_without_tables.has_tables is False

    def test_ocr_result_total_tables(self):
        table1 = TableData(rows=1, columns=1, headers=["H1"], data=[["V1"]])
        table2 = TableData(rows=1, columns=1, headers=["H2"], data=[["V2"]])
        table3 = TableData(rows=1, columns=1, headers=["H3"], data=[["V3"]])

        page1 = PageResult(page_number=1, text="", tables=[table1, table2])
        page2 = PageResult(page_number=2, text="", tables=[table3])

        result = OcrResult(text="", pages=[page1, page2])

        assert result.total_tables == 3

    def test_ocr_result_get_all_tables(self):
        table1 = TableData(rows=1, columns=1, headers=["H1"], data=[["V1"]])
        table2 = TableData(rows=2, columns=2, headers=["H2", "H3"], data=[["V2", "V3"]])

        page1 = PageResult(page_number=1, text="", tables=[table1])
        page2 = PageResult(page_number=2, text="", tables=[table2])

        result = OcrResult(text="", pages=[page1, page2])
        all_tables = result.get_all_tables()

        assert len(all_tables) == 2
        assert all_tables[0].rows == 1
        assert all_tables[1].rows == 2

    def test_ocr_result_to_dict(self):
        result = OcrResult(
            text="Sample",
            confidence=0.8,
            engine_used="docling",
            processing_time=5.0,
            pdf_type=PdfType.IMAGE,
            warnings=["Warning 1"],
        )

        output = result.to_dict()

        assert output["text"] == "Sample"
        assert output["confidence"] == 0.8
        assert output["engine_used"] == "docling"
        assert output["pdf_type"] == "IMAGE"
        assert "Warning 1" in output["warnings"]


class TestDetectionResult:

    def test_detection_result_creation(self):
        result = DetectionResult(
            pdf_type=PdfType.DIGITAL,
            confidence=0.95,
            text_ratio=0.9,
            image_ratio=0.1,
            total_pages=5,
        )

        assert result.pdf_type == PdfType.DIGITAL
        assert result.confidence == 0.95
        assert result.total_pages == 5

    def test_detection_result_with_page_types(self):
        result = DetectionResult(
            pdf_type=PdfType.MIXED,
            confidence=0.75,
            page_types=[PdfType.DIGITAL, PdfType.IMAGE, PdfType.DIGITAL],
            total_pages=3,
        )

        assert len(result.page_types) == 3
        assert result.page_types[1] == PdfType.IMAGE

    def test_detection_result_to_dict(self):
        result = DetectionResult(
            pdf_type=PdfType.IMAGE,
            confidence=0.9,
            page_types=[PdfType.IMAGE],
            text_ratio=0.05,
            image_ratio=0.95,
            total_pages=1,
            warnings=["Low text content"],
        )

        output = result.to_dict()

        assert output["pdf_type"] == "IMAGE"
        assert output["confidence"] == 0.9
        assert output["page_types"] == ["IMAGE"]
        assert output["total_pages"] == 1
