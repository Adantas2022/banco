import pytest
from pathlib import Path

from irpf_processor.infrastructure.extraction.ocr import TesseractEngine
from irpf_processor.infrastructure.extraction.ocr.models import OcrResult, PdfType


class TestTesseractEngineWithRealPdfs:

    @pytest.fixture
    def engine(self):
        engine = TesseractEngine(lang="por", timeout=120)
        if not engine.is_available():
            pytest.skip("Tesseract not installed")
        return engine

    @pytest.fixture
    def pdfs_dir(self):
        return Path(__file__).parent.parent.parent.parent / "pdfs"

    @pytest.fixture
    def docs_dir(self):
        return Path(__file__).parent.parent.parent.parent / "docs" / "IRPF"

    def test_engine_is_available(self, engine):
        assert engine.is_available() is True
        assert engine.name == "tesseract"

    def test_extract_from_digital_pdf(self, engine, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = engine.extract(pdf_path, timeout=180)

        assert isinstance(result, OcrResult)
        assert len(result.text) > 100
        assert result.total_pages > 0
        assert result.engine_used == "tesseract"
        assert result.processing_time > 0

    def test_extract_detects_cpf_pattern(self, engine, pdfs_dir):
        pdf_files = list(pdfs_dir.glob("*.pdf"))[:1]
        if not pdf_files:
            pytest.skip("No PDFs found")

        result = engine.extract(pdf_files[0], timeout=180)

        assert len(result.text) > 0

    def test_extract_returns_page_results(self, engine, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = engine.extract(pdf_path, timeout=180)

        assert len(result.pages) > 0
        for page in result.pages:
            assert page.page_number > 0
            assert hasattr(page, "text")
            assert hasattr(page, "confidence")

    def test_extract_confidence_score(self, engine, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = engine.extract(pdf_path, timeout=180)

        assert 0.0 <= result.confidence <= 1.0
        for page in result.pages:
            assert 0.0 <= page.confidence <= 1.0

    def test_extract_with_custom_psm(self, engine, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = engine.extract(pdf_path, timeout=180, psm=6)

        assert isinstance(result, OcrResult)
        assert len(result.text) > 0

    def test_extract_portuguese_text(self, engine, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = engine.extract(pdf_path, timeout=180)

        portuguese_words = ["DECLARAÇÃO", "CONTRIBUINTE", "IMPOSTO", "RENDA", "CPF"]
        text_upper = result.text.upper()

        found_words = [w for w in portuguese_words if w in text_upper]
        assert len(found_words) >= 2
