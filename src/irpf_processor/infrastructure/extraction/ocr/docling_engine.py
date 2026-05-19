import time
from pathlib import Path
from typing import Optional, Literal

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

    DEFAULT_TIMEOUT = 900
    
    VISION_MODELS = {
        "granite": "ibm-granite/granite-vision-3.2-2b",
        "smoldocling": "ds4sd/SmolDocling-256M-preview",
        "granite-docling": "ibm-granite/granite-docling-258M",
        "default": None,
    }

    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        use_gpu: bool = False,
        vision_model: Literal["granite", "smoldocling", "granite-docling", "default"] = "granite",
    ):
        self._timeout = timeout
        self._use_gpu = use_gpu
        self._vision_model = vision_model
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
    
    def _create_converter(self):
        from docling.document_converter import DocumentConverter
        
        if self._vision_model == "default" or self._vision_model is None:
            logger.info("Using Docling with Tesseract OCR (Portuguese)")
            try:
                from docling.datamodel.base_models import InputFormat
                from docling.document_converter import PdfFormatOption
                from docling.datamodel.pipeline_options import PdfPipelineOptions
                from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
                
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = True
                pipeline_options.do_table_structure = True
                
                try:
                    from docling.datamodel.pipeline_options import TesseractOcrOptions
                    pipeline_options.ocr_options = TesseractOcrOptions(lang=["por"])
                    logger.info("Tesseract OCR configured for Portuguese")
                except ImportError:
                    try:
                        from docling.datamodel.pipeline_options import EasyOcrOptions
                        pipeline_options.ocr_options = EasyOcrOptions(lang=["pt"])
                        logger.info("EasyOCR configured for Portuguese")
                    except ImportError:
                        logger.warning("No Portuguese OCR available, using default")
                
                return DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_options=pipeline_options,
                            backend=PyPdfiumDocumentBackend,
                        ),
                    }
                )
            except Exception as e:
                logger.warning("Failed to configure OCR pipeline", error=str(e))
                return DocumentConverter()
        
        try:
            from docling.datamodel.base_models import InputFormat
            from docling.document_converter import PdfFormatOption
            from docling.pipeline.vlm_pipeline import VlmPipeline
            from docling.datamodel.pipeline_options import VlmPipelineOptions
            from docling.datamodel import vlm_model_specs
            
            model_mapping = {
                "granite": vlm_model_specs.GRANITE_VISION_TRANSFORMERS,
                "smoldocling": vlm_model_specs.SMOLDOCLING_TRANSFORMERS,
                "granite-docling": vlm_model_specs.GRANITEDOCLING_TRANSFORMERS,
            }
            
            vlm_options = model_mapping.get(self._vision_model)
            
            if vlm_options:
                logger.info(
                    "Using VLM Pipeline with vision model",
                    model=self._vision_model,
                    repo_id=self.VISION_MODELS.get(self._vision_model),
                )
                
                pipeline_options = VlmPipelineOptions(vlm_options=vlm_options)
                
                return DocumentConverter(
                    format_options={
                        InputFormat.PDF: PdfFormatOption(
                            pipeline_cls=VlmPipeline,
                            pipeline_options=pipeline_options,
                        ),
                    }
                )
            
        except ImportError as e:
            logger.warning(
                "VLM Pipeline not available, falling back to default",
                error=str(e),
            )
        except Exception as e:
            logger.warning(
                "Failed to configure VLM Pipeline, falling back to default",
                error=str(e),
            )
        
        logger.info("Using default Docling pipeline (fallback)")
        return DocumentConverter()

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
            
            converter = self._create_converter()

            result = converter.convert(str(pdf_path))

            processing_time = time.perf_counter() - start_time

            if processing_time > timeout:
                raise OcrTimeoutError(f"Docling timed out after {timeout}s")

            doc = result.document
            logger.info(
                "Docling raw result",
                has_pages=hasattr(doc, 'pages'),
                pages_count=len(doc.pages) if hasattr(doc, 'pages') and doc.pages else 0,
                has_texts=hasattr(doc, 'texts'),
                texts_count=len(doc.texts) if hasattr(doc, 'texts') and doc.texts else 0,
                has_tables=hasattr(doc, 'tables'),
                tables_count=len(doc.tables) if hasattr(doc, 'tables') and doc.tables else 0,
            )

            pages = self._process_result(result)
            full_text = result.document.export_to_markdown()
            
            logger.info(
                "Markdown export completed",
                text_length=len(full_text),
                text_preview=full_text[:500] if full_text else "EMPTY",
            )

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
                vision_model=self._vision_model,
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
            
            total_pages = 1
            if hasattr(doc, 'pages') and doc.pages:
                total_pages = len(doc.pages)
                logger.info("Document pages detected", total_pages=total_pages)
            elif hasattr(doc, 'num_pages'):
                total_pages = doc.num_pages
                logger.info("Document num_pages detected", total_pages=total_pages)
            
            page_texts = {}
            if hasattr(doc, "texts"):
                for text_item in doc.texts:
                    page_no = 1
                    if hasattr(text_item, 'prov') and text_item.prov:
                        for prov in text_item.prov:
                            if hasattr(prov, 'page_no'):
                                page_no = prov.page_no
                                break
                    elif hasattr(text_item, "page_no"):
                        page_no = text_item.page_no
                    
                    if page_no not in page_texts:
                        page_texts[page_no] = []
                    page_texts[page_no].append(str(text_item.text))
            
            logger.info(
                "Texts collected by page",
                pages_with_text=list(page_texts.keys()),
                text_items_total=sum(len(v) for v in page_texts.values()),
            )

            page_tables = {}
            if hasattr(doc, "tables"):
                for table in doc.tables:
                    page_no = 1
                    if hasattr(table, 'prov') and table.prov:
                        for prov in table.prov:
                            if hasattr(prov, 'page_no'):
                                page_no = prov.page_no
                                break
                    elif hasattr(table, "page_no"):
                        page_no = table.page_no
                    
                    if page_no not in page_tables:
                        page_tables[page_no] = []
                    page_tables[page_no].append(self._convert_table(table))

            all_pages = set(page_texts.keys()) | set(page_tables.keys())
            
            if len(all_pages) < total_pages:
                logger.warning(
                    "Page mismatch detected",
                    detected_pages=len(all_pages),
                    total_pages=total_pages,
                )
                all_pages = set(range(1, total_pages + 1))
            
            if not all_pages:
                all_pages = {1}

            for page_no in sorted(all_pages):
                text = "\n".join(page_texts.get(page_no, []))
                tables = page_tables.get(page_no, [])

                pages.append(PageResult(
                    page_number=page_no,
                    text=text,
                    tables=tables,
                    confidence=0.85 if text else 0.5,
                ))
            
            logger.info(
                "Pages processed",
                total_pages_output=len(pages),
                pages_with_text=len([p for p in pages if p.text]),
                pages_with_tables=len([p for p in pages if p.tables]),
            )

        except Exception as e:
            logger.warning("Failed to process Docling result", error=str(e), exc_info=True)
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
