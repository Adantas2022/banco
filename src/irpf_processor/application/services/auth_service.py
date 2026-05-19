from datetime import datetime, timezone
from typing import Optional

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.exceptions import (
    ExpiredApiKeyError,
    InsufficientScopeError,
    InvalidApiKeyError,
    RevokedApiKeyError,
    TenantMismatchError,
)
from irpf_processor.infrastructure.persistence import MongoApiKeyRepository
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


class AuthService:

    def __init__(self, api_key_repository: MongoApiKeyRepository) -> None:
        self._repo = api_key_repository

    async def validate_api_key(
        self,
        raw_key: str,
        required_scope: Optional[str] = None,
        required_tenant: Optional[str] = None,
    ) -> ApiKey:
        if not raw_key:
            logger.warning("Empty API key provided")
            raise InvalidApiKeyError()

        key_hash = ApiKey.hash_key(raw_key)
        api_key = await self._repo.get_by_hash(key_hash)

        if not api_key:
            logger.warning("API key not found", key_prefix=raw_key[:16] if len(raw_key) > 16 else "***")
            raise InvalidApiKeyError()

        if not api_key.is_active:
            logger.warning("Revoked API key used", api_key_id=api_key.api_key_id)
            raise RevokedApiKeyError()

        if api_key.expires_at and datetime.now(timezone.utc) > api_key.expires_at:
            logger.warning("Expired API key used", api_key_id=api_key.api_key_id)
            raise ExpiredApiKeyError()

        if required_tenant and api_key.tenant_id != required_tenant:
            logger.warning(
                "Tenant mismatch",
                api_key_tenant=api_key.tenant_id,
                required_tenant=required_tenant,
            )
            raise TenantMismatchError()

        if required_scope and not api_key.has_scope(required_scope):
            logger.warning(
                "Insufficient scope",
                api_key_id=api_key.api_key_id,
                required_scope=required_scope,
                available_scopes=api_key.scopes,
            )
            raise InsufficientScopeError(required_scope)

        await self._repo.update_last_used(api_key.api_key_id)

        logger.info(
            "API key validated",
            api_key_id=api_key.api_key_id,
            tenant_id=api_key.tenant_id,
        )

        return api_key

    async def create_api_key(
        self,
        tenant_id: str,
        name: str,
        scopes: list[str],
        expires_at: Optional[datetime] = None,
        created_by: Optional[str] = None,
    ) -> tuple[ApiKey, str]:
        api_key, raw_key = ApiKey.create(
            tenant_id=tenant_id,
            name=name,
            scopes=scopes,
            expires_at=expires_at,
            created_by=created_by,
        )

        await self._repo.create(api_key)

        logger.info(
            "API key created",
            api_key_id=api_key.api_key_id,
            tenant_id=tenant_id,
            name=name,
            scopes=scopes,
        )

        return api_key, raw_key

    async def revoke_api_key(self, api_key_id: str, tenant_id: str) -> bool:
        api_key = await self._repo.get_by_id(api_key_id, tenant_id)

        if not api_key:
            return False

        api_key.revoke()
        await self._repo.update(api_key)

        logger.info(
            "API key revoked",
            api_key_id=api_key_id,
            tenant_id=tenant_id,
        )

        return True

    async def list_api_keys(
        self, tenant_id: str, include_inactive: bool = False
    ) -> list[ApiKey]:
        return await self._repo.list_by_tenant(tenant_id, include_inactive)
