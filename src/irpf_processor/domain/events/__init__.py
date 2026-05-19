"""Eventos de domínio."""

from .document_events import (
    DocumentEvent,
    DocumentExtracted,
    DocumentFailed,
    DocumentQuarantined,
    DocumentReady,
    DocumentRouted,
    DocumentUploaded,
)

__all__ = [
    "DocumentEvent",
    "DocumentUploaded",
    "DocumentRouted",
    "DocumentExtracted",
    "DocumentReady",
    "DocumentFailed",
    "DocumentQuarantined",
]
