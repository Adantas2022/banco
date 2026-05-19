"""Interfaces para repositórios."""

from abc import abstractmethod
from typing import Optional, Protocol

from irpf_processor.domain.entities import Document, ExtractionResult


class IDocumentRepository(Protocol):
    """Interface para repositório de documentos."""

    @abstractmethod
    async def create(self, document: Document) -> None:
        """Cria um novo documento."""
        ...

    @abstractmethod
    async def get_by_id(self, document_id: str, tenant_id: str) -> Optional[Document]:
        """Busca documento por ID."""
        ...

    @abstractmethod
    async def get_by_sha256(self, sha256: str, tenant_id: str) -> Optional[Document]:
        """Busca documento por SHA256 (deduplicação)."""
        ...

    @abstractmethod
    async def update(self, document: Document) -> None:
        """Atualiza documento existente."""
        ...

    @abstractmethod
    async def delete(self, document_id: str, tenant_id: str) -> None:
        """Remove documento."""
        ...

    @abstractmethod
    async def list_by_status(
        self, tenant_id: str, status: str, limit: int = 100
    ) -> list[Document]:
        """Lista documentos por status."""
        ...


class IExtractionResultRepository(Protocol):
    """Interface para repositório de resultados de extração."""

    @abstractmethod
    async def save(self, result: ExtractionResult) -> None:
        """Salva resultado de extração."""
        ...

    @abstractmethod
    async def get_by_document_id(
        self, document_id: str, tenant_id: str
    ) -> Optional[ExtractionResult]:
        """Busca resultado por ID do documento."""
        ...

    @abstractmethod
    async def delete(self, document_id: str, tenant_id: str) -> None:
        """Remove resultado de extração."""
        ...
