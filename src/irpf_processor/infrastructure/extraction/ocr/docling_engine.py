import time
from pathlib import Path
from typing import Optional

from irpf_processor.shared.logging import get_logger

from .interfaces import IOcrEngine
from .models import (
    EngineNotAvailableError,
    OcrExtractionError,
    OcrResult,
    OcrTimeoutError,
    PageResult,
    PdfType,
    TableData,
)

logger = get_logger(__name__)


class DoclingEngine(IOcrEngine):

    DEFAULT_TIMEOUT = 180

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        use_gpu: bool = False,
    ):
        self._timeout = timeout
        self._use_gpu = use_gpu
        self._converter = None

    @property
    def name(self) -> str:
        return "docling"

    def is_available(self) -> bool:
        try:
            from docling.document_converter import DocumentConverter
            return True
        except ImportError:
            return False

    def extract(
        self,
        pdf_path: Path,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> OcrResult:
        if not self.is_available():
            raise EngineNotAvailableError("Docling is not installed")

        timeout = timeout or self._timeout
        start_time = time.perf_counter()

        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()

            result = converter.convert(str(pdf_path))

            processing_time = time.perf_counter() - start_time

            if processing_time > timeout:
                raise OcrTimeoutError(f"Docling timed out after {timeout}s")

            pages = self._process_result(result)
            full_text = result.document.export_to_markdown()

            avg_confidence = (
                sum(p.confidence for p in pages) / len(pages) if pages else 0.85
            )

            warnings = []
            if avg_confidence < 0.7:
                warnings.append(f"Low OCR confidence: {avg_confidence:.2f}")

            logger.info(
                "Docling extraction completed",
                pages=len(pages),
                confidence=avg_confidence,
                processing_time=processing_time,
                tables_found=sum(len(p.tables) for p in pages),
            )

            return OcrResult(
                text=full_text,
                pages=pages,
                confidence=avg_confidence,
                engine_used=self.name,
                processing_time=processing_time,
                pdf_type=PdfType.IMAGE,
                warnings=warnings,
                metadata={"has_layout": True},
            )

        except ImportError as e:
            raise EngineNotAvailableError(f"Docling dependency missing: {e}")
        except OcrTimeoutError:
            raise
        except Exception as e:
            logger.error("Docling extraction failed", error=str(e))
            raise OcrExtractionError(f"Docling extraction failed: {e}")

    def _process_result(self, result) -> list[PageResult]:
        pages = []

        try:
            doc = result.document

            page_texts = {}
            if hasattr(doc, "texts"):
                for text_item in doc.texts:
                    page_no = getattr(text_item, "page_no", 1)
                    if page_no not in page_texts:
                        page_texts[page_no] = []
                    page_texts[page_no].append(str(text_item.text))

            page_tables = {}
            if hasattr(doc, "tables"):
                for table in doc.tables:
                    page_no = getattr(table, "page_no", 1)
                    if page_no not in page_tables:
                        page_tables[page_no] = []
                    page_tables[page_no].append(self._convert_table(table))

            all_pages = set(page_texts.keys()) | set(page_tables.keys())
            if not all_pages:
                all_pages = {1}

            for page_no in sorted(all_pages):
                text = "\n".join(page_texts.get(page_no, []))
                tables = page_tables.get(page_no, [])

                pages.append(PageResult(
                    page_number=page_no,
                    text=text,
                    tables=tables,
                    confidence=0.85,
                ))

        except Exception as e:
            logger.warning("Failed to process Docling result", error=str(e))
            pages.append(PageResult(
                page_number=1,
                text=str(result.document.export_to_markdown()) if result.document else "",
                confidence=0.7,
                warnings=[f"Partial processing: {e}"],
            ))

        return pages

    def _convert_table(self, table) -> TableData:
        try:
            df = table.export_to_dataframe()
            headers = list(df.columns)
            data = df.values.tolist()

            return TableData(
                rows=len(data),
                columns=len(headers),
                headers=headers,
                data=[[str(cell) for cell in row] for row in data],
                confidence=0.80,
            )
        except Exception as e:
            logger.warning("Failed to convert table", error=str(e))
            return TableData(
                rows=0,
                columns=0,
                headers=[],
                data=[],
                confidence=0.0,
            )
