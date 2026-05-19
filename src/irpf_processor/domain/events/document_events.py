"""Eventos de domínio relacionados a documentos."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class DocumentEvent:
    """Evento base de documento."""

    document_id: str
    tenant_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def event_type(self) -> str:
        return self.__class__.__name__


@dataclass(frozen=True)
class DocumentUploaded(DocumentEvent):
    """Evento emitido quando um documento é enviado."""

    storage_uri: str = ""
    media_type: str = ""
    sha256: str = ""


@dataclass(frozen=True)
class DocumentRouted(DocumentEvent):
    """Evento emitido quando o tipo de documento é detectado."""

    pdf_type: str = ""
    message: str = ""


@dataclass(frozen=True)
class DocumentExtracted(DocumentEvent):
    """Evento emitido quando dados são extraídos do documento."""

    confidence: float = 0.0
    extraction_method: str = ""
    fields_extracted: int = 0
    warnings_count: int = 0


@dataclass(frozen=True)
class DocumentReady(DocumentEvent):
    """Evento emitido quando documento está pronto para consulta."""

    confidence: float = 0.0
    processing_time_ms: int = 0


@dataclass(frozen=True)
class DocumentFailed(DocumentEvent):
    """Evento emitido quando processamento falha."""

    step: str = ""
    error_code: str = ""
    error_message: str = ""
    attempt: int = 0


@dataclass(frozen=True)
class DocumentQuarantined(DocumentEvent):
    """Evento emitido quando documento é colocado em quarentena."""

    reason: str = ""
    confidence: Optional[float] = None
