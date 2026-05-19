from abc import abstractmethod
from typing import Optional, Protocol

from irpf_processor.domain.entities import ApiKey


class IApiKeyRepository(Protocol):

    @abstractmethod
    async def create(self, api_key: ApiKey) -> None:
        ...

    @abstractmethod
    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        ...

    @abstractmethod
    async def get_by_id(self, api_key_id: str, tenant_id: str) -> Optional[ApiKey]:
        ...

    @abstractmethod
    async def list_by_tenant(
        self, tenant_id: str, include_inactive: bool = False
    ) -> list[ApiKey]:
        ...

    @abstractmethod
    async def update(self, api_key: ApiKey) -> None:
        ...

    @abstractmethod
    async def delete(self, api_key_id: str, tenant_id: str) -> None:
        ...

    @abstractmethod
    async def update_last_used(self, api_key_id: str) -> None:
        ...
