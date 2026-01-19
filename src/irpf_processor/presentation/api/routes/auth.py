from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from irpf_processor.application.services import AuthService
from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.enums import AuthScope
from irpf_processor.presentation.api.dependencies import (
    CurrentApiKey,
    get_auth_service,
    require_scope,
)
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["Authentication"])


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=100, description="Nome identificador da API Key")
    scopes: list[str] = Field(
        default_factory=AuthScope.default_scopes,
        description="Escopos de permissão",
    )
    expires_at: Optional[datetime] = Field(None, description="Data de expiração (opcional)")


class ApiKeyResponse(BaseModel):
    api_key_id: str
    tenant_id: str
    name: str
    key_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]


class CreateApiKeyResponse(BaseModel):
    api_key: ApiKeyResponse
    raw_key: str = Field(..., description="Chave completa - salve agora, nao sera exibida novamente")


class CurrentKeyResponse(BaseModel):
    api_key_id: str
    tenant_id: str
    name: str
    scopes: list[str]
    expires_at: Optional[datetime]


def _to_response(api_key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        api_key_id=api_key.api_key_id,
        tenant_id=api_key.tenant_id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        scopes=api_key.scopes,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
    )


@router.get(
    "/me",
    response_model=CurrentKeyResponse,
    summary="Informacoes da API Key atual",
    description="Retorna informacoes sobre a API Key usada na requisicao.",
)
async def get_current_key_info(
    api_key: CurrentApiKey,
) -> CurrentKeyResponse:
    return CurrentKeyResponse(
        api_key_id=api_key.api_key_id,
        tenant_id=api_key.tenant_id,
        name=api_key.name,
        scopes=api_key.scopes,
        expires_at=api_key.expires_at,
    )


@router.post(
    "/keys",
    response_model=CreateApiKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar nova API Key",
    description="Cria uma nova API Key para o tenant. Requer scope admin:keys.",
)
async def create_api_key(
    request: CreateApiKeyRequest,
    current_key: Annotated[ApiKey, Depends(require_scope(AuthScope.ADMIN_KEYS.value))],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> CreateApiKeyResponse:
    invalid_scopes = set(request.scopes) - ApiKey.VALID_SCOPES
    if invalid_scopes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid scopes: {list(invalid_scopes)}",
        )

    api_key, raw_key = await auth_service.create_api_key(
        tenant_id=current_key.tenant_id,
        name=request.name,
        scopes=request.scopes,
        expires_at=request.expires_at,
        created_by=current_key.api_key_id,
    )

    logger.info(
        "API key created via API",
        new_key_id=api_key.api_key_id,
        created_by=current_key.api_key_id,
    )

    return CreateApiKeyResponse(
        api_key=_to_response(api_key),
        raw_key=raw_key,
    )


@router.get(
    "/keys",
    response_model=list[ApiKeyResponse],
    summary="Listar API Keys do tenant",
    description="Lista todas as API Keys do tenant. Requer scope admin:keys.",
)
async def list_api_keys(
    current_key: Annotated[ApiKey, Depends(require_scope(AuthScope.ADMIN_KEYS.value))],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    include_inactive: bool = False,
) -> list[ApiKeyResponse]:
    keys = await auth_service.list_api_keys(
        tenant_id=current_key.tenant_id,
        include_inactive=include_inactive,
    )
    return [_to_response(k) for k in keys]


@router.delete(
    "/keys/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revogar API Key",
    description="Revoga uma API Key existente. Requer scope admin:keys.",
)
async def revoke_api_key(
    api_key_id: str,
    current_key: Annotated[ApiKey, Depends(require_scope(AuthScope.ADMIN_KEYS.value))],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> None:
    if api_key_id == current_key.api_key_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot revoke the API key currently in use",
        )

    success = await auth_service.revoke_api_key(
        api_key_id=api_key_id,
        tenant_id=current_key.tenant_id,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )

    logger.info(
        "API key revoked via API",
        revoked_key_id=api_key_id,
        revoked_by=current_key.api_key_id,
    )
