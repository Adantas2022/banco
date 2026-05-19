"""Dramatiq Workers - Processamento assincrono."""

from .broker import dramatiq_broker
from .extraction_worker import process_document
from .router_worker import route_document
from .ocr_worker import process_ocr_document

__all__ = [
    "dramatiq_broker",
    "process_document",
    "route_document",
    "process_ocr_document",
]
