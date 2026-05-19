"""Interfaces (Portas) da aplicação - Dependency Inversion."""

from .auth_repository import IApiKeyRepository
from .event_publisher import IEventPublisher
from .repositories import IDocumentRepository, IExtractionResultRepository
from .storage import IStorageService
from .template_engine import ITemplateEngine

__all__ = [
    "IApiKeyRepository",
    "IDocumentRepository",
    "IEventPublisher",
    "IExtractionResultRepository",
    "IStorageService",
    "ITemplateEngine",
]
