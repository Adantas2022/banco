import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from irpf_processor.presentation.api.dependencies.auth import (
    get_auth_service,
    get_current_api_key,
    require_scope,
    get_tenant_from_key,
)
from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.exceptions import AuthenticationError


class TestGetAuthService:

    @pytest.mark.asyncio
    @patch("irpf_processor.presentation.api.dependencies.auth.get_database")
    @patch("irpf_processor.presentation.api.dependencies.auth.MongoApiKeyRepository")
    @patch("irpf_processor.presentation.api.dependencies.auth.AuthService")
    async def test_creates_auth_service_with_repository(
        self, mock_auth_service, mock_repo, mock_get_db
    ):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance

        mock_service_instance = MagicMock()
        mock_auth_service.return_value = mock_service_instance

        result = await get_auth_service()

        mock_get_db.assert_called_once()
        mock_repo.assert_called_once_with(mock_db)
        mock_auth_service.assert_called_once_with(mock_repo_instance)
        assert result == mock_service_instance


class TestGetCurrentApiKey:

    @pytest.mark.asyncio
    async def test_raises_401_when_no_credentials(self):
        mock_auth_service = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_api_key(None, mock_auth_service)

        assert exc_info.value.status_code == 401
        assert "Missing authentication credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_returns_api_key_when_valid(self):
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="test-api-key"
        )

        mock_api_key = MagicMock()

        mock_auth_service = MagicMock()
        mock_auth_service.validate_api_key = AsyncMock(return_value=mock_api_key)

        result = await get_current_api_key(mock_credentials, mock_auth_service)

        assert result == mock_api_key
        mock_auth_service.validate_api_key.assert_called_once_with("test-api-key")

    @pytest.mark.asyncio
    async def test_raises_401_when_authentication_fails(self):
        mock_credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="invalid-key"
        )

        mock_auth_service = MagicMock()
        mock_auth_service.validate_api_key = AsyncMock(
            side_effect=AuthenticationError("Invalid API key")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_api_key(mock_credentials, mock_auth_service)

        assert exc_info.value.status_code == 401


class TestRequireScope:

    @pytest.mark.asyncio
    async def test_returns_api_key_when_has_scope(self):
        mock_api_key = MagicMock()
        mock_api_key.has_scope.return_value = True

        scope_checker = require_scope("read")
        result = await scope_checker(mock_api_key)

        assert result == mock_api_key
        mock_api_key.has_scope.assert_called_once_with("read")

    @pytest.mark.asyncio
    async def test_raises_403_when_missing_scope(self):
        mock_api_key = MagicMock()
        mock_api_key.has_scope.return_value = False

        scope_checker = require_scope("admin")

        with pytest.raises(HTTPException) as exc_info:
            await scope_checker(mock_api_key)

        assert exc_info.value.status_code == 403
        assert "lacks required scope" in exc_info.value.detail

    def test_require_scope_returns_callable(self):
        scope_checker = require_scope("read")
        assert callable(scope_checker)


class TestGetTenantFromKey:

    @pytest.mark.asyncio
    async def test_returns_tenant_id_from_api_key(self):
        mock_api_key = MagicMock()
        mock_api_key.tenant_id = "tenant-456"

        result = await get_tenant_from_key(mock_api_key, None)

        assert result == "tenant-456"

    @pytest.mark.asyncio
    async def test_returns_tenant_id_when_header_matches(self):
        mock_api_key = MagicMock()
        mock_api_key.tenant_id = "tenant-456"

        result = await get_tenant_from_key(mock_api_key, "tenant-456")

        assert result == "tenant-456"

    @pytest.mark.asyncio
    async def test_raises_403_when_tenant_mismatch(self):
        mock_api_key = MagicMock()
        mock_api_key.tenant_id = "tenant-456"

        with pytest.raises(HTTPException) as exc_info:
            await get_tenant_from_key(mock_api_key, "different-tenant")

        assert exc_info.value.status_code == 403
        assert "does not match" in exc_info.value.detail


class TestSecurityBearer:

    def test_security_is_http_bearer(self):
        from irpf_processor.presentation.api.dependencies.auth import security
        from fastapi.security import HTTPBearer

        assert isinstance(security, HTTPBearer)

    def test_security_auto_error_is_false(self):
        from irpf_processor.presentation.api.dependencies.auth import security

        assert security.auto_error is False


class TestTypeAliases:

    def test_current_api_key_alias_exists(self):
        from irpf_processor.presentation.api.dependencies.auth import CurrentApiKey
        assert CurrentApiKey is not None

    def test_current_tenant_alias_exists(self):
        from irpf_processor.presentation.api.dependencies.auth import CurrentTenant
        assert CurrentTenant is not None
