from irpf_processor.infrastructure.extraction.ocr.models import (
    OcrResult,
    PageResult,
    PdfType,
    WordBox,
)
from irpf_processor.infrastructure.extraction.ocr.pdfplumber_adapter import (
    OcrToPdfplumberAdapter,
)
from irpf_processor.infrastructure.extraction.ocr.spatial_text_reconstructor import (
    reconstruct_page_text,
)


def _word(text: str, left: float, top: float, right: float, bottom: float) -> WordBox:
    return WordBox(text=text, left=left, top=top, right=right, bottom=bottom, confidence=0.9)


def test_reconstruct_page_text_keeps_columns_with_spacing():
    page = PageResult(
        page_number=1,
        text="",
        words=[
            _word("01", 50, 100, 70, 120),
            _word("21", 140, 100, 160, 120),
            _word("Apartamento", 260, 100, 390, 120),
            _word("350.000,00", 620, 100, 760, 120),
            _word("360.000,00", 900, 100, 1040, 120),
        ],
        confidence=0.9,
    )

    text = reconstruct_page_text(page)

    assert "01" in text
    assert "21" in text
    assert "Apartamento" in text
    assert "350.000,00" in text
    assert "360.000,00" in text
    assert "   " in text


def test_adapter_convert_spatial_result():
    ocr_result = OcrResult(
        text="raw",
        pages=[
            PageResult(
                page_number=1,
                text="",
                words=[_word("IRPF", 50, 60, 110, 90), _word("2025", 150, 60, 210, 90)],
                confidence=0.9,
            )
        ],
        confidence=0.9,
        engine_used="documentai",
        pdf_type=PdfType.IMAGE,
    )

    adapter = OcrToPdfplumberAdapter()
    pages_text, full_text = adapter.convert(ocr_result)

    assert 1 in pages_text
    assert "IRPF" in pages_text[1]
    assert "2025" in pages_text[1]
    assert "IRPF" in full_text


def test_adapter_convert_flat_result():
    ocr_result = OcrResult(
        text="raw",
        pages=[PageResult(page_number=1, text="Linha 1", confidence=0.8)],
        confidence=0.8,
        engine_used="tesseract",
        pdf_type=PdfType.IMAGE,
    )

    adapter = OcrToPdfplumberAdapter()
    pages_text, full_text = adapter.convert(ocr_result)

    assert pages_text[1] == "Linha 1"
    assert full_text == "Linha 1"
