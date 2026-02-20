"""Adapts OCR output to the same page-text structure produced by pdfplumber."""

from __future__ import annotations

from typing import Optional

from .documentai_normalizer import DocumentAINormalizer
from .models import OcrResult
from .post_processor import PostProcessor
from .spatial_text_reconstructor import ReconstructionConfig, reconstruct_page_text


class OcrToPdfplumberAdapter:
    """Converts ``OcrResult`` into ``{page_number: page_text}``."""

    def __init__(
        self,
        post_processor: Optional[PostProcessor] = None,
        reconstruction_config: Optional[ReconstructionConfig] = None,
        documentai_normalizer: Optional[DocumentAINormalizer] = None,
    ):
        self._post_processor = post_processor or PostProcessor(lang="pt-BR")
        self._reconstruction_config = reconstruction_config
        self._documentai_normalizer = documentai_normalizer or DocumentAINormalizer()

    def convert(self, ocr_result: OcrResult) -> tuple[dict[int, str], str]:
        pages_text: dict[int, str] = {}

        for page in ocr_result.pages:
            if page.has_spatial_data:
                page_text = reconstruct_page_text(page, self._reconstruction_config)
            else:
                page_text = page.text

            page_text = self._post_processor.process(page_text)
            if self._is_documentai(ocr_result.engine_used):
                page_text = self._documentai_normalizer.normalize(page_text)

            pages_text[page.page_number] = page_text

        full_text = "\n".join(
            pages_text[k] for k in sorted(pages_text.keys())
        )
        return pages_text, full_text

    @staticmethod
    def _is_documentai(engine_used: str) -> bool:
        return engine_used.lower().startswith("documentai")
