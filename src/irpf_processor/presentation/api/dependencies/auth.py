from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from irpf_processor.application.services import AuthService
from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.exceptions import (
    AuthenticationError,
    InsufficientScopeError,
)
from irpf_processor.infrastructure.persistence import MongoApiKeyRepository
from irpf_processor.infrastructure.persistence.database import get_database
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

security = HTTPBearer(auto_error=False)


async def get_auth_service() -> AuthService:
    db = await get_database()
    repo = MongoApiKeyRepository(db)
    return AuthService(repo)


async def get_current_api_key(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(security)
    ],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiKey:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        api_key = await auth_service.validate_api_key(credentials.credentials)
        return api_key
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e.message,
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_scope(scope: str):
    async def scope_checker(
        api_key: Annotated[ApiKey, Depends(get_current_api_key)],
    ) -> ApiKey:
        if not api_key.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required scope: {scope}",
            )
        return api_key
    return scope_checker


async def get_tenant_from_key(
    api_key: Annotated[ApiKey, Depends(get_current_api_key)],
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-ID")] = None,
) -> str:
    if x_tenant_id and x_tenant_id != api_key.tenant_id:
        logger.warning(
            "Tenant mismatch between header and API key",
            header_tenant=x_tenant_id,
            key_tenant=api_key.tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="X-Tenant-ID header does not match API key tenant",
        )
    return api_key.tenant_id


CurrentApiKey = Annotated[ApiKey, Depends(get_current_api_key)]
CurrentTenant = Annotated[str, Depends(get_tenant_from_key)]
