"""Entidade Document - representa um documento enviado para processamento."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid
import hashlib

from irpf_processor.domain.enums import DocumentStatus, PdfType


@dataclass
class Document:
    """Entidade que representa um documento no sistema."""

    tenant_id: str
    filename: str
    content_type: str
    storage_uri: str
    status: DocumentStatus = DocumentStatus.RECEIVED
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sha256: Optional[str] = None
    pdf_type: Optional[PdfType] = None
    confidence: Optional[float] = None
    content: Optional[bytes] = None
    attempts: int = 0
    error_step: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def mark_as_routed(self, pdf_type: PdfType) -> None:
        self.status = DocumentStatus.ROUTED
        self.pdf_type = pdf_type
        self.updated_at = datetime.utcnow()

    def mark_as_extracted(self, confidence: float) -> None:
        self.status = DocumentStatus.EXTRACTED
        self.confidence = confidence
        self.updated_at = datetime.utcnow()

    def mark_as_ready(self) -> None:
        self.status = DocumentStatus.READY
        self.updated_at = datetime.utcnow()

    def mark_as_failed(self, step: str, code: str, message: str) -> None:
        self.status = DocumentStatus.FAILED
        self.error_step = step
        self.error_code = code
        self.error_message = message
        self.attempts += 1
        self.updated_at = datetime.utcnow()

    def mark_as_quarantined(self, reason: str) -> None:
        self.status = DocumentStatus.QUARANTINED
        self.error_message = reason
        self.updated_at = datetime.utcnow()

    def can_retry(self, max_attempts: int) -> bool:
        return self.attempts < max_attempts

    def is_ready(self) -> bool:
        return self.status == DocumentStatus.READY

    def is_extractable(self) -> bool:
        return self.status == DocumentStatus.ROUTED
