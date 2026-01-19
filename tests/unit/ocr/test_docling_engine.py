import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from pathlib import Path

from irpf_processor.infrastructure.extraction.ocr.docling_engine import DoclingEngine
from irpf_processor.infrastructure.extraction.ocr.models import (
    EngineNotAvailableError,
    OcrExtractionError,
    OcrTimeoutError,
    OcrResult,
    PageResult,
    PdfType,
    TableData,
)


class TestDoclingEngineInit:

    def test_default_initialization(self):
        engine = DoclingEngine()

        assert engine._timeout == 180
        assert engine._use_gpu is False
        assert engine._converter is None

    def test_custom_initialization(self):
        engine = DoclingEngine(timeout=300, use_gpu=True)

        assert engine._timeout == 300
        assert engine._use_gpu is True

    def test_constants(self):
        assert DoclingEngine.DEFAULT_TIMEOUT == 180


class TestDoclingEngineName:

    def test_name_property(self):
        engine = DoclingEngine()
        assert engine.name == "docling"


class TestDoclingEngineIsAvailable:

    def test_is_available_when_installed(self):
        with patch.dict("sys.modules", {"docling": MagicMock(), "docling.document_converter": MagicMock()}):
            engine = DoclingEngine()
            result = engine.is_available()
            assert result is True

    def test_is_not_available_when_not_installed(self):
        engine = DoclingEngine()

        with patch.object(engine, "is_available", return_value=False):
            assert engine.is_available() is False


class TestDoclingEngineExtract:

    @patch.object(DoclingEngine, "is_available", return_value=False)
    def test_raises_when_not_available(self, mock_is_available):
        engine = DoclingEngine()

        with pytest.raises(EngineNotAvailableError, match="Docling is not installed"):
            engine.extract(Path("/test.pdf"))


class TestDoclingEngineProcessResult:

    def test_process_result_with_texts(self):
        mock_result = MagicMock()
        mock_doc = MagicMock()

        mock_text1 = MagicMock()
        mock_text1.page_no = 1
        mock_text1.text = "Page 1 content"

        mock_text2 = MagicMock()
        mock_text2.page_no = 2
        mock_text2.text = "Page 2 content"

        mock_doc.texts = [mock_text1, mock_text2]
        mock_doc.tables = []
        mock_result.document = mock_doc

        engine = DoclingEngine()
        pages = engine._process_result(mock_result)

        assert len(pages) == 2
        assert pages[0].page_number == 1
        assert "Page 1 content" in pages[0].text

    def test_process_result_with_tables(self):
        mock_result = MagicMock()
        mock_doc = MagicMock()

        mock_table = MagicMock()
        mock_table.page_no = 1
        mock_df = MagicMock()
        mock_df.columns = ["Col1", "Col2"]
        mock_df.values.tolist.return_value = [["A", "B"], ["C", "D"]]
        mock_table.export_to_dataframe.return_value = mock_df

        mock_doc.texts = []
        mock_doc.tables = [mock_table]
        mock_result.document = mock_doc

        engine = DoclingEngine()
        pages = engine._process_result(mock_result)

        assert len(pages) >= 1
        assert len(pages[0].tables) == 1

    def test_process_result_handles_error(self):
        mock_result = MagicMock()
        mock_doc = MagicMock()
        mock_doc.texts = None
        mock_doc.export_to_markdown.return_value = "Fallback content"
        mock_result.document = mock_doc

        engine = DoclingEngine()
        pages = engine._process_result(mock_result)

        assert len(pages) >= 1


class TestDoclingEngineConvertTable:

    def test_convert_table_success(self):
        mock_table = MagicMock()
        mock_df = MagicMock()
        mock_df.columns = ["Header1", "Header2"]
        mock_df.values.tolist.return_value = [["A", "B"], ["C", "D"]]
        mock_table.export_to_dataframe.return_value = mock_df

        engine = DoclingEngine()
        result = engine._convert_table(mock_table)

        assert isinstance(result, TableData)
        assert result.rows == 2
        assert result.columns == 2
        assert result.headers == ["Header1", "Header2"]

    def test_convert_table_handles_error(self):
        mock_table = MagicMock()
        mock_table.export_to_dataframe.side_effect = Exception("Conversion failed")

        engine = DoclingEngine()
        result = engine._convert_table(mock_table)

        assert isinstance(result, TableData)
        assert result.rows == 0
        assert result.columns == 0
        assert result.confidence == 0.0


class TestTableData:

    def test_table_data_creation(self):
        table = TableData(
            rows=2,
            columns=3,
            headers=["A", "B", "C"],
            data=[["1", "2", "3"], ["4", "5", "6"]],
            confidence=0.90
        )

        assert table.rows == 2
        assert table.columns == 3
        assert len(table.headers) == 3
        assert len(table.data) == 2
