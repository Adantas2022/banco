from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class PdfType(Enum):
    DIGITAL = "DIGITAL"
    IMAGE = "IMAGE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


@dataclass
class TableData:
    rows: int
    columns: int
    headers: list[str]
    data: list[list[str]]
    confidence: float = 0.0
    bounding_box: Optional[tuple[float, float, float, float]] = None

    def to_dict(self) -> dict:
        return {
            "rows": self.rows,
            "columns": self.columns,
            "headers": self.headers,
            "data": self.data,
            "confidence": self.confidence,
        }


@dataclass
class PageResult:
    page_number: int
    text: str
    tables: list[TableData] = field(default_factory=list)
    confidence: float = 0.0
    width: Optional[int] = None
    height: Optional[int] = None
    dpi: Optional[int] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_number": self.page_number,
            "text": self.text,
            "tables": [t.to_dict() for t in self.tables],
            "confidence": self.confidence,
            "warnings": self.warnings,
        }


@dataclass
class OcrResult:
    text: str
    pages: list[PageResult] = field(default_factory=list)
    confidence: float = 0.0
    engine_used: str = ""
    processing_time: float = 0.0
    pdf_type: PdfType = PdfType.UNKNOWN
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def has_tables(self) -> bool:
        return any(len(page.tables) > 0 for page in self.pages)

    @property
    def total_tables(self) -> int:
        return sum(len(page.tables) for page in self.pages)

    def get_all_tables(self) -> list[TableData]:
        tables = []
        for page in self.pages:
            tables.extend(page.tables)
        return tables

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "pages": [p.to_dict() for p in self.pages],
            "confidence": self.confidence,
            "engine_used": self.engine_used,
            "processing_time": self.processing_time,
            "pdf_type": self.pdf_type.value,
            "warnings": self.warnings,
            "total_pages": self.total_pages,
            "total_tables": self.total_tables,
        }


@dataclass
class DetectionResult:
    pdf_type: PdfType
    confidence: float
    page_types: list[PdfType] = field(default_factory=list)
    text_ratio: float = 0.0
    image_ratio: float = 0.0
    total_pages: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "pdf_type": self.pdf_type.value,
            "confidence": self.confidence,
            "page_types": [pt.value for pt in self.page_types],
            "text_ratio": self.text_ratio,
            "image_ratio": self.image_ratio,
            "total_pages": self.total_pages,
            "warnings": self.warnings,
        }


class OcrError(Exception):
    pass


class OcrTimeoutError(OcrError):
    pass


class OcrExtractionError(OcrError):
    pass


class InvalidPdfError(OcrError):
    pass


class ProtectedPdfError(OcrError):
    pass


class EngineNotAvailableError(OcrError):
    pass
