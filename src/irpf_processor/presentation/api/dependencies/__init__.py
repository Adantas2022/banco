"""Dependências de injeção para FastAPI."""

from .auth import (
    CurrentApiKey,
    CurrentTenant,
    get_auth_service,
    get_current_api_key,
    get_tenant_from_key,
    require_scope,
)

__all__ = [
    "CurrentApiKey",
    "CurrentTenant",
    "get_auth_service",
    "get_current_api_key",
    "get_tenant_from_key",
    "require_scope",
]
