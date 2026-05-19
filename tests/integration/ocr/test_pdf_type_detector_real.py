import pytest
from pathlib import Path

from irpf_processor.infrastructure.extraction.ocr import PdfTypeDetector
from irpf_processor.infrastructure.extraction.ocr.models import PdfType


class TestPdfTypeDetectorWithRealPdfs:

    @pytest.fixture
    def detector(self):
        return PdfTypeDetector()

    @pytest.fixture
    def pdfs_dir(self):
        return Path(__file__).parent.parent.parent.parent / "pdfs"

    @pytest.fixture
    def docs_dir(self):
        return Path(__file__).parent.parent.parent.parent / "docs" / "IRPF"

    def test_detect_digital_pdf_geral_irpf(self, detector, docs_dir):
        pdf_path = docs_dir / "Geral-IRPF-2025-2024.pdf"
        if not pdf_path.exists():
            pytest.skip(f"PDF not found: {pdf_path}")

        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type == PdfType.DIGITAL
        assert result.confidence >= 0.90

    def test_detect_real_irpf_declaration(self, detector, pdfs_dir):
        pdf_files = list(pdfs_dir.glob("*.pdf"))
        if not pdf_files:
            pytest.skip("No PDFs found in pdfs directory")

        pdf_path = pdf_files[0]
        result = detector.detect_with_confidence(pdf_path)

        assert result.pdf_type in [PdfType.DIGITAL, PdfType.IMAGE, PdfType.MIXED]
        assert result.confidence > 0.0
        assert result.total_pages > 0

    def test_detect_multiple_pdfs_batch(self, detector, pdfs_dir):
        pdf_files = list(pdfs_dir.glob("*.pdf"))[:5]
        if not pdf_files:
            pytest.skip("No PDFs found in pdfs directory")

        results = []
        for pdf_path in pdf_files:
            try:
                result = detector.detect_with_confidence(pdf_path)
                results.append({
                    "file": pdf_path.name,
                    "type": result.pdf_type.value,
                    "confidence": result.confidence,
                    "pages": result.total_pages,
                })
            except Exception as e:
                results.append({
                    "file": pdf_path.name,
                    "error": str(e),
                })

        assert len(results) > 0
        successful = [r for r in results if "error" not in r]
        assert len(successful) >= len(results) * 0.8

    def test_detect_per_page_multi_page_pdf(self, detector, pdfs_dir):
        pdf_files = list(pdfs_dir.glob("*.pdf"))
        if not pdf_files:
            pytest.skip("No PDFs found")

        multi_page_pdf = None
        for pdf in pdf_files:
            try:
                result = detector.detect_with_confidence(pdf)
                if result.total_pages > 3:
                    multi_page_pdf = pdf
                    break
            except Exception:
                continue

        if multi_page_pdf is None:
            pytest.skip("No multi-page PDF found")

        page_types = detector.detect_per_page(multi_page_pdf)

        assert len(page_types) > 3
        assert all(isinstance(pt, PdfType) for pt in page_types)

    def test_pdf_type_distribution(self, detector, pdfs_dir):
        pdf_files = list(pdfs_dir.glob("*.pdf"))[:10]
        if not pdf_files:
            pytest.skip("No PDFs found")

        types_count = {"DIGITAL": 0, "IMAGE": 0, "MIXED": 0, "UNKNOWN": 0}
        for pdf_path in pdf_files:
            try:
                result = detector.detect(pdf_path)
                types_count[result.value] += 1
            except Exception:
                continue

        total_detected = sum(types_count.values())
        assert total_detected >= len(pdf_files) * 0.5
        assert types_count["DIGITAL"] >= 1 or types_count["IMAGE"] >= 1
