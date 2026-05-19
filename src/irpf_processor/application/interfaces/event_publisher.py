"""Interface para publicador de eventos."""

from abc import abstractmethod
from typing import Optional, Protocol

from irpf_processor.domain.events import DocumentEvent


class IEventPublisher(Protocol):
    """Interface para publicação de eventos."""

    @abstractmethod
    async def publish(self, event: DocumentEvent) -> str:
        """Publica evento. Retorna o ID do evento."""
        ...

    @abstractmethod
    async def get_events(
        self,
        document_id: str,
        since_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Busca eventos de um documento."""
        ...
