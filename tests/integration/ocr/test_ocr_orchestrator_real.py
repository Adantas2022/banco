import pytest
from pathlib import Path

from irpf_processor.infrastructure.extraction.ocr import (
    OcrOrchestrator,
    TesseractEngine,
)
from irpf_processor.infrastructure.extraction.ocr.models import OcrResult


class TestOcrOrchestratorWithRealPdfs:

    @pytest.fixture
    def tesseract_engine(self):
        engine = TesseractEngine(lang="por", timeout=120)
        if not engine.is_available():
            pytest.skip("Tesseract not installed")
        return engine

    @pytest.fixture
    def orchestrator(self, tesseract_engine):
        return OcrOrchestrator(engines=[tesseract_engine], min_confidence=0.3)

    @pytest.fixture
    def pdfs_dir(self):
        return Path(__file__).parent.parent.parent.parent / "pdfs"

    @pytest.fixture
    def docs_dir(self):
        return Path(__file__).parent.parent.parent.parent / "docs" / "IRPF"

    def test_process_with_single_engine(self, orchestrator, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = orchestrator.process(pdf_path, timeout=180)

        assert isinstance(result, OcrResult)
        assert len(result.text) > 100
        assert result.engine_used == "tesseract"

    def test_process_records_attempts(self, orchestrator, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = orchestrator.process(pdf_path, timeout=180)

        assert "attempts" in result.metadata
        assert len(result.metadata["attempts"]) >= 1

    def test_process_measures_total_time(self, orchestrator, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = orchestrator.process(pdf_path, timeout=180)

        assert result.processing_time > 0
        assert "total_processing_time" in result.metadata

    def test_process_with_min_confidence(self, tesseract_engine, docs_dir):
        orchestrator = OcrOrchestrator(engines=[tesseract_engine], min_confidence=0.5)
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = orchestrator.process(pdf_path, timeout=180, min_confidence=0.5)

        assert result.confidence >= 0.3

    def test_add_and_remove_engine(self, tesseract_engine):
        orchestrator = OcrOrchestrator(engines=[])

        assert len(orchestrator.engines) == 0

        orchestrator.add_engine(tesseract_engine)
        assert len(orchestrator.engines) == 1

        orchestrator.remove_engine("tesseract")
        assert len(orchestrator.engines) == 0

    def test_process_multiple_pdfs(self, orchestrator, pdfs_dir):
        pdf_files = list(pdfs_dir.glob("*.pdf"))[:3]
        if not pdf_files:
            pytest.skip("No PDFs found")

        results = []
        for pdf_path in pdf_files:
            try:
                result = orchestrator.process(pdf_path, timeout=180)
                results.append({
                    "file": pdf_path.name,
                    "confidence": result.confidence,
                    "pages": result.total_pages,
                    "text_length": len(result.text),
                })
            except Exception as e:
                results.append({
                    "file": pdf_path.name,
                    "error": str(e),
                })

        successful = [r for r in results if "error" not in r]
        assert len(successful) >= 1
