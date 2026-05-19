import shutil
import subprocess
import tempfile
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
)

logger = get_logger(__name__)


class TesseractEngine(IOcrEngine):

    DEFAULT_TIMEOUT = 120
    DEFAULT_LANG = "por"
    DEFAULT_PSM = 3
    DEFAULT_OEM = 3

    def __init__(
        self,
        lang: str = DEFAULT_LANG,
        psm: int = DEFAULT_PSM,
        oem: int = DEFAULT_OEM,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self._lang = lang
        self._psm = psm
        self._oem = oem
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "tesseract"

    def is_available(self) -> bool:
        return shutil.which("tesseract") is not None

    def extract(
        self,
        pdf_path: Path,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> OcrResult:
        if not self.is_available():
            raise EngineNotAvailableError("Tesseract is not installed")

        timeout = timeout or self._timeout
        start_time = time.perf_counter()

        try:
            pages = self._extract_pages(pdf_path, timeout, **kwargs)
            processing_time = time.perf_counter() - start_time

            full_text = "\n\n".join(page.text for page in pages)
            avg_confidence = (
                sum(p.confidence for p in pages) / len(pages) if pages else 0.0
            )

            warnings = []
            if avg_confidence < 0.7:
                warnings.append(f"Low OCR confidence: {avg_confidence:.2f}")

            logger.info(
                "Tesseract extraction completed",
                pages=len(pages),
                confidence=avg_confidence,
                processing_time=processing_time,
            )

            return OcrResult(
                text=full_text,
                pages=pages,
                confidence=avg_confidence,
                engine_used=self.name,
                processing_time=processing_time,
                pdf_type=PdfType.IMAGE,
                warnings=warnings,
            )

        except subprocess.TimeoutExpired:
            raise OcrTimeoutError(f"Tesseract timed out after {timeout}s")
        except Exception as e:
            logger.error("Tesseract extraction failed", error=str(e))
            raise OcrExtractionError(f"Tesseract extraction failed: {e}")

    def _extract_pages(
        self,
        pdf_path: Path,
        timeout: int,
        **kwargs,
    ) -> list[PageResult]:
        try:
            from pdf2image import convert_from_path

            images = convert_from_path(pdf_path, dpi=300)
        except ImportError:
            raise OcrExtractionError("pdf2image is not installed")
        except Exception as e:
            raise OcrExtractionError(f"Failed to convert PDF to images: {e}")

        pages = []
        psm = kwargs.get("psm", self._psm)
        oem = kwargs.get("oem", self._oem)
        config = kwargs.get("config", "")

        for idx, image in enumerate(images):
            page_result = self._extract_page(image, idx + 1, psm, oem, config, timeout)
            pages.append(page_result)

        return pages

    def _extract_page(
        self,
        image,
        page_number: int,
        psm: int,
        oem: int,
        config: str,
        timeout: int,
    ) -> PageResult:
        try:
            import pytesseract

            custom_config = f"--psm {psm} --oem {oem} {config}".strip()

            text = pytesseract.image_to_string(
                image,
                lang=self._lang,
                config=custom_config,
                timeout=timeout,
            )

            data = pytesseract.image_to_data(
                image,
                lang=self._lang,
                config=custom_config,
                output_type=pytesseract.Output.DICT,
                timeout=timeout,
            )

            confidences = [
                int(c) for c in data["conf"] if c != "-1" and str(c).isdigit()
            ]
            avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0

            warnings = []
            if avg_confidence < 0.6:
                warnings.append(f"Page {page_number}: Low confidence {avg_confidence:.2f}")

            return PageResult(
                page_number=page_number,
                text=text.strip(),
                confidence=avg_confidence,
                width=image.width,
                height=image.height,
                warnings=warnings,
            )

        except ImportError:
            raise OcrExtractionError("pytesseract is not installed")
        except Exception as e:
            logger.warning("Page extraction failed", page=page_number, error=str(e))
            return PageResult(
                page_number=page_number,
                text="",
                confidence=0.0,
                warnings=[f"Extraction failed: {e}"],
            )
