import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from irpf_processor.infrastructure.extraction.ocr.ocr_orchestrator import OcrOrchestrator
from irpf_processor.infrastructure.extraction.ocr.models import (
    OcrExtractionError,
    OcrResult,
    PdfType,
)


class TestOcrOrchestratorInit:

    def test_default_initialization(self):
        mock_engine = MagicMock()
        orchestrator = OcrOrchestrator(engines=[mock_engine])

        assert len(orchestrator.engines) == 1
        assert orchestrator._min_confidence == 0.5

    def test_custom_min_confidence(self):
        mock_engine = MagicMock()
        orchestrator = OcrOrchestrator(engines=[mock_engine], min_confidence=0.7)

        assert orchestrator._min_confidence == 0.7

    def test_constants(self):
        assert OcrOrchestrator.DEFAULT_MIN_CONFIDENCE == 0.5


class TestOcrOrchestratorEnginesProperty:

    def test_engines_property_returns_list(self):
        mock_engine1 = MagicMock()
        mock_engine2 = MagicMock()
        orchestrator = OcrOrchestrator(engines=[mock_engine1, mock_engine2])

        assert len(orchestrator.engines) == 2


class TestOcrOrchestratorAddEngine:

    def test_add_engine(self):
        mock_engine1 = MagicMock()
        mock_engine2 = MagicMock()
        orchestrator = OcrOrchestrator(engines=[mock_engine1])

        orchestrator.add_engine(mock_engine2)

        assert len(orchestrator.engines) == 2


class TestOcrOrchestratorRemoveEngine:

    def test_remove_engine_by_name(self):
        mock_engine1 = MagicMock()
        mock_engine1.name = "tesseract"
        mock_engine2 = MagicMock()
        mock_engine2.name = "docling"

        orchestrator = OcrOrchestrator(engines=[mock_engine1, mock_engine2])
        orchestrator.remove_engine("tesseract")

        assert len(orchestrator.engines) == 1
        assert orchestrator.engines[0].name == "docling"

    def test_remove_nonexistent_engine(self):
        mock_engine = MagicMock()
        mock_engine.name = "tesseract"

        orchestrator = OcrOrchestrator(engines=[mock_engine])
        orchestrator.remove_engine("docling")

        assert len(orchestrator.engines) == 1


class TestOcrOrchestratorProcess:

    def test_raises_when_no_engines_available(self):
        mock_engine = MagicMock()
        mock_engine.is_available.return_value = False

        orchestrator = OcrOrchestrator(engines=[mock_engine])

        with pytest.raises(OcrExtractionError, match="No OCR engines available"):
            orchestrator.process(Path("/test.pdf"))

    def test_uses_first_successful_high_confidence_engine(self):
        mock_engine1 = MagicMock()
        mock_engine1.name = "tesseract"
        mock_engine1.is_available.return_value = True
        mock_result1 = OcrResult(
            text="Test",
            pages=[],
            confidence=0.90,
            engine_used="tesseract",
            processing_time=1.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine1.extract.return_value = mock_result1

        mock_engine2 = MagicMock()
        mock_engine2.name = "docling"
        mock_engine2.is_available.return_value = True

        orchestrator = OcrOrchestrator(engines=[mock_engine1, mock_engine2])
        result = orchestrator.process(Path("/test.pdf"))

        assert result.engine_used == "tesseract"
        mock_engine2.extract.assert_not_called()

    def test_falls_back_to_second_engine_on_failure(self):
        mock_engine1 = MagicMock()
        mock_engine1.name = "tesseract"
        mock_engine1.is_available.return_value = True
        mock_engine1.extract.side_effect = Exception("OCR failed")

        mock_engine2 = MagicMock()
        mock_engine2.name = "docling"
        mock_engine2.is_available.return_value = True
        mock_result2 = OcrResult(
            text="Test",
            pages=[],
            confidence=0.85,
            engine_used="docling",
            processing_time=2.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine2.extract.return_value = mock_result2

        orchestrator = OcrOrchestrator(engines=[mock_engine1, mock_engine2])
        result = orchestrator.process(Path("/test.pdf"))

        assert result.engine_used == "docling"

    def test_tries_all_engines_for_higher_confidence(self):
        mock_engine1 = MagicMock()
        mock_engine1.name = "tesseract"
        mock_engine1.is_available.return_value = True
        mock_result1 = OcrResult(
            text="Test",
            pages=[],
            confidence=0.60,
            engine_used="tesseract",
            processing_time=1.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine1.extract.return_value = mock_result1

        mock_engine2 = MagicMock()
        mock_engine2.name = "docling"
        mock_engine2.is_available.return_value = True
        mock_result2 = OcrResult(
            text="Test",
            pages=[],
            confidence=0.75,
            engine_used="docling",
            processing_time=2.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine2.extract.return_value = mock_result2

        orchestrator = OcrOrchestrator(engines=[mock_engine1, mock_engine2])
        result = orchestrator.process(Path("/test.pdf"))

        assert result.engine_used == "docling"
        assert result.confidence == 0.75

    def test_raises_when_all_engines_fail(self):
        mock_engine1 = MagicMock()
        mock_engine1.name = "tesseract"
        mock_engine1.is_available.return_value = True
        mock_engine1.extract.side_effect = Exception("OCR failed")

        mock_engine2 = MagicMock()
        mock_engine2.name = "docling"
        mock_engine2.is_available.return_value = True
        mock_engine2.extract.side_effect = Exception("OCR failed")

        orchestrator = OcrOrchestrator(engines=[mock_engine1, mock_engine2])

        with pytest.raises(OcrExtractionError, match="All OCR engines failed"):
            orchestrator.process(Path("/test.pdf"))

    def test_raises_when_confidence_below_threshold(self):
        mock_engine = MagicMock()
        mock_engine.name = "tesseract"
        mock_engine.is_available.return_value = True
        mock_result = OcrResult(
            text="Test",
            pages=[],
            confidence=0.30,
            engine_used="tesseract",
            processing_time=1.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine.extract.return_value = mock_result

        orchestrator = OcrOrchestrator(engines=[mock_engine], min_confidence=0.5)

        with pytest.raises(OcrExtractionError, match="All OCR engines failed or returned low confidence"):
            orchestrator.process(Path("/test.pdf"))

    def test_custom_min_confidence_in_process(self):
        mock_engine = MagicMock()
        mock_engine.name = "tesseract"
        mock_engine.is_available.return_value = True
        mock_result = OcrResult(
            text="Test",
            pages=[],
            confidence=0.40,
            engine_used="tesseract",
            processing_time=1.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine.extract.return_value = mock_result

        orchestrator = OcrOrchestrator(engines=[mock_engine], min_confidence=0.5)
        result = orchestrator.process(Path("/test.pdf"), min_confidence=0.3)

        assert result is not None

    def test_passes_timeout_to_engine(self):
        mock_engine = MagicMock()
        mock_engine.name = "tesseract"
        mock_engine.is_available.return_value = True
        mock_result = OcrResult(
            text="Test",
            pages=[],
            confidence=0.90,
            engine_used="tesseract",
            processing_time=1.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine.extract.return_value = mock_result

        orchestrator = OcrOrchestrator(engines=[mock_engine])
        orchestrator.process(Path("/test.pdf"), timeout=60)

        mock_engine.extract.assert_called_once()
        call_kwargs = mock_engine.extract.call_args[1]
        assert call_kwargs["timeout"] == 60

    def test_records_attempts_in_metadata(self):
        mock_engine = MagicMock()
        mock_engine.name = "tesseract"
        mock_engine.is_available.return_value = True
        mock_result = OcrResult(
            text="Test",
            pages=[],
            confidence=0.90,
            engine_used="tesseract",
            processing_time=1.0,
            pdf_type=PdfType.IMAGE,
            warnings=[],
            metadata={}
        )
        mock_engine.extract.return_value = mock_result

        orchestrator = OcrOrchestrator(engines=[mock_engine])
        result = orchestrator.process(Path("/test.pdf"))

        assert "attempts" in result.metadata
        assert "total_processing_time" in result.metadata


class TestOcrOrchestratorGetBestResult:

    def test_returns_highest_confidence_result(self):
        results = [
            OcrResult(
                text="Low",
                pages=[],
                confidence=0.60,
                engine_used="engine1",
                processing_time=1.0,
                pdf_type=PdfType.IMAGE,
                warnings=[],
            ),
            OcrResult(
                text="High",
                pages=[],
                confidence=0.90,
                engine_used="engine2",
                processing_time=1.0,
                pdf_type=PdfType.IMAGE,
                warnings=[],
            ),
            OcrResult(
                text="Medium",
                pages=[],
                confidence=0.75,
                engine_used="engine3",
                processing_time=1.0,
                pdf_type=PdfType.IMAGE,
                warnings=[],
            ),
        ]

        orchestrator = OcrOrchestrator(engines=[])
        best = orchestrator._get_best_result(results)

        assert best.engine_used == "engine2"
        assert best.confidence == 0.90
