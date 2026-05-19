"""Interface para serviço de storage (S3/MinIO)."""

from abc import abstractmethod
from typing import Protocol


class IStorageService(Protocol):
    """Interface para armazenamento de arquivos."""

    @abstractmethod
    async def upload(
        self,
        content: bytes,
        key: str,
        content_type: str,
    ) -> str:
        """Upload de arquivo. Retorna a URI de armazenamento."""
        ...

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Download de arquivo. Retorna bytes do conteúdo."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Verifica se arquivo existe."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove arquivo."""
        ...

    @abstractmethod
    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Gera URL pré-assinada para download."""
        ...
