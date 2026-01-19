import pytest
from pathlib import Path
from unittest.mock import MagicMock

from irpf_processor.infrastructure.extraction.table_extractor import (
    ExtractedTable,
    TableExtractor,
    parse_currency,
    generate_item_id,
)


class MockPage:
    def __init__(self, tables: list, text: str = ""):
        self._tables = tables
        self._text = text

    def extract_tables(self):
        return self._tables

    def extract_text(self):
        return self._text


class MockPdf:
    def __init__(self, pages: list):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class MockPdfPlumber:
    def __init__(self, pages: list):
        self._pages = pages

    def open(self, file):
        return MockPdf(self._pages)


class TestExtractedTable:

    def test_create_extracted_table(self):
        table = ExtractedTable(
            headers=["Name", "Value"],
            rows=[["Item 1", "100"], ["Item 2", "200"]],
            page_number=1
        )

        assert table.headers == ["Name", "Value"]
        assert len(table.rows) == 2
        assert table.page_number == 1

    def test_to_dicts(self):
        table = ExtractedTable(
            headers=["Name", "Value"],
            rows=[["Item 1", "100"], ["Item 2", "200"]],
            page_number=1
        )

        result = table.to_dicts()

        assert len(result) == 2
        assert result[0] == {"Name": "Item 1", "Value": "100"}
        assert result[1] == {"Name": "Item 2", "Value": "200"}

    def test_to_dicts_empty(self):
        table = ExtractedTable(
            headers=["A", "B"],
            rows=[],
            page_number=1
        )

        result = table.to_dicts()

        assert result == []


class TestTableExtractor:

    def test_extract_single_table(self):
        extractor = TableExtractor()
        mock_table = [
            ["Header 1", "Header 2"],
            ["Row 1 Col 1", "Row 1 Col 2"],
        ]
        mock_pages = [MockPage(tables=[mock_table])]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables("test.pdf")

        assert len(result) == 1
        assert result[0].headers == ["Header 1", "Header 2"]
        assert result[0].rows == [["Row 1 Col 1", "Row 1 Col 2"]]

    def test_extract_multiple_tables_multiple_pages(self):
        extractor = TableExtractor()
        table1 = [["A", "B"], ["1", "2"]]
        table2 = [["C", "D"], ["3", "4"]]
        mock_pages = [
            MockPage(tables=[table1]),
            MockPage(tables=[table2]),
        ]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables("test.pdf")

        assert len(result) == 2
        assert result[0].page_number == 1
        assert result[1].page_number == 2

    def test_extract_tables_specific_pages(self):
        extractor = TableExtractor()
        table1 = [["A", "B"], ["1", "2"]]
        table2 = [["C", "D"], ["3", "4"]]
        table3 = [["E", "F"], ["5", "6"]]
        mock_pages = [
            MockPage(tables=[table1]),
            MockPage(tables=[table2]),
            MockPage(tables=[table3]),
        ]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables("test.pdf", page_numbers=[1, 3])

        assert len(result) == 2
        assert result[0].page_number == 1
        assert result[1].page_number == 3

    def test_extract_tables_skips_empty_tables(self):
        extractor = TableExtractor()
        mock_pages = [MockPage(tables=[[], None, [["Header"]]])]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables("test.pdf")

        assert len(result) == 0

    def test_extract_tables_handles_none_cells(self):
        extractor = TableExtractor()
        mock_table = [
            ["Header 1", None, "Header 3"],
            [None, "Value", ""],
        ]
        mock_pages = [MockPage(tables=[mock_table])]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables("test.pdf")

        assert len(result) == 1
        assert result[0].headers == ["Header 1", "", "Header 3"]
        assert result[0].rows == [["", "Value", ""]]

    def test_extract_tables_skips_empty_rows(self):
        extractor = TableExtractor()
        mock_table = [
            ["Header 1", "Header 2"],
            ["", ""],
            ["Value 1", "Value 2"],
        ]
        mock_pages = [MockPage(tables=[mock_table])]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables("test.pdf")

        assert len(result) == 1
        assert len(result[0].rows) == 1
        assert result[0].rows[0] == ["Value 1", "Value 2"]

    def test_extract_text_by_page(self):
        extractor = TableExtractor()
        mock_pages = [
            MockPage(tables=[], text="Page 1 text"),
            MockPage(tables=[], text="Page 2 text"),
        ]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_text_by_page("test.pdf")

        assert result == {1: "Page 1 text", 2: "Page 2 text"}

    def test_extract_text_by_page_handles_none(self):
        extractor = TableExtractor()
        mock_pages = [MockPage(tables=[], text=None)]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_text_by_page("test.pdf")

        assert result == {1: ""}

    def test_extract_from_bytes(self):
        extractor = TableExtractor()
        mock_table = [["H1", "H2"], ["V1", "V2"]]
        mock_pages = [MockPage(tables=[mock_table])]
        extractor._pdfplumber = MockPdfPlumber(mock_pages)

        result = extractor.extract_tables(b"fake pdf bytes")

        assert len(result) == 1


class TestParseCurrency:

    def test_parse_currency_simple(self):
        assert parse_currency("100") == 100.0

    def test_parse_currency_with_symbol(self):
        assert parse_currency("R$ 1.234,56") == 1234.56

    def test_parse_currency_without_symbol(self):
        assert parse_currency("1.234,56") == 1234.56

    def test_parse_currency_large_value(self):
        assert parse_currency("R$ 25.040.026,18") == 25040026.18

    def test_parse_currency_empty_string(self):
        assert parse_currency("") == 0.0

    def test_parse_currency_none(self):
        assert parse_currency(None) == 0.0

    def test_parse_currency_invalid(self):
        assert parse_currency("invalid") == 0.0

    def test_parse_currency_negative(self):
        assert parse_currency("-1.234,56") == -1234.56


class TestGenerateItemId:

    def test_generate_item_id_consistent(self):
        id1 = generate_item_id("same content")
        id2 = generate_item_id("same content")

        assert id1 == id2

    def test_generate_item_id_different_content(self):
        id1 = generate_item_id("content 1")
        id2 = generate_item_id("content 2")

        assert id1 != id2

    def test_generate_item_id_is_hex(self):
        result = generate_item_id("test")

        assert len(result) == 32
        assert all(c in "0123456789abcdef" for c in result)
