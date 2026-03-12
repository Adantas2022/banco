from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from .models import OcrResult


class IOcrEngine(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def extract(
        self,
        pdf_path: Path,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> OcrResult:
        pass


class IImagePreprocessor(ABC):

    @abstractmethod
    def preprocess(self, image_bytes: bytes) -> bytes:
        pass

    @abstractmethod
    def deskew(self, image_bytes: bytes) -> bytes:
        pass

    @abstractmethod
    def denoise(self, image_bytes: bytes) -> bytes:
        pass

    @abstractmethod
    def binarize(self, image_bytes: bytes) -> bytes:
        pass

    @abstractmethod
    def enhance_contrast(self, image_bytes: bytes) -> bytes:
        pass


class IPostProcessor(ABC):

    @abstractmethod
    def process(self, text: str, preserve_column_gaps: bool = False) -> str:
        pass

    @abstractmethod
    def fix_ocr_errors(self, text: str) -> str:
        pass

    @abstractmethod
    def fix_accents(self, text: str) -> str:
        pass

    @abstractmethod
    def normalize_whitespace(self, text: str) -> str:
        pass
