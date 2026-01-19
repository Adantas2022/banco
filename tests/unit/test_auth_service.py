import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import sys

mock_motor = MagicMock()
sys.modules["motor"] = mock_motor
sys.modules["motor.motor_asyncio"] = mock_motor

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.exceptions import (
    ExpiredApiKeyError,
    InsufficientScopeError,
    InvalidApiKeyError,
    RevokedApiKeyError,
    TenantMismatchError,
)


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def auth_service(mock_repo):
    from irpf_processor.application.services import AuthService
    return AuthService(mock_repo)


@pytest.fixture
def valid_api_key():
    api_key, raw_key = ApiKey.create(
        tenant_id="tenant-1",
        name="Test Key",
        scopes=["documents:read", "documents:write"],
    )
    return api_key, raw_key


class TestAuthServiceValidation:

    @pytest.mark.asyncio
    async def test_validate_api_key_success(self, auth_service, mock_repo, valid_api_key):
        api_key, raw_key = valid_api_key
        mock_repo.get_by_hash.return_value = api_key

        result = await auth_service.validate_api_key(raw_key)

        assert result.api_key_id == api_key.api_key_id
        mock_repo.update_last_used.assert_called_once_with(api_key.api_key_id)

    @pytest.mark.asyncio
    async def test_validate_api_key_empty_raises(self, auth_service):
        with pytest.raises(InvalidApiKeyError):
            await auth_service.validate_api_key("")

    @pytest.mark.asyncio
    async def test_validate_api_key_not_found_raises(self, auth_service, mock_repo):
        mock_repo.get_by_hash.return_value = None

        with pytest.raises(InvalidApiKeyError):
            await auth_service.validate_api_key("invalid_key")

    @pytest.mark.asyncio
    async def test_validate_api_key_revoked_raises(self, auth_service, mock_repo, valid_api_key):
        api_key, raw_key = valid_api_key
        api_key.revoke()
        mock_repo.get_by_hash.return_value = api_key

        with pytest.raises(RevokedApiKeyError):
            await auth_service.validate_api_key(raw_key)

    @pytest.mark.asyncio
    async def test_validate_api_key_expired_raises(self, auth_service, mock_repo):
        api_key, raw_key = ApiKey.create(
            tenant_id="tenant-1",
            name="Expired Key",
            scopes=["documents:read"],
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        mock_repo.get_by_hash.return_value = api_key

        with pytest.raises(ExpiredApiKeyError):
            await auth_service.validate_api_key(raw_key)

    @pytest.mark.asyncio
    async def test_validate_api_key_tenant_mismatch_raises(self, auth_service, mock_repo, valid_api_key):
        api_key, raw_key = valid_api_key
        mock_repo.get_by_hash.return_value = api_key

        with pytest.raises(TenantMismatchError):
            await auth_service.validate_api_key(raw_key, required_tenant="other-tenant")

    @pytest.mark.asyncio
    async def test_validate_api_key_insufficient_scope_raises(self, auth_service, mock_repo, valid_api_key):
        api_key, raw_key = valid_api_key
        mock_repo.get_by_hash.return_value = api_key

        with pytest.raises(InsufficientScopeError):
            await auth_service.validate_api_key(raw_key, required_scope="admin:keys")

    @pytest.mark.asyncio
    async def test_validate_api_key_with_required_scope(self, auth_service, mock_repo, valid_api_key):
        api_key, raw_key = valid_api_key
        mock_repo.get_by_hash.return_value = api_key

        result = await auth_service.validate_api_key(raw_key, required_scope="documents:read")

        assert result.api_key_id == api_key.api_key_id


class TestAuthServiceCRUD:

    @pytest.mark.asyncio
    async def test_create_api_key(self, auth_service, mock_repo):
        api_key, raw_key = await auth_service.create_api_key(
            tenant_id="tenant-1",
            name="New Key",
            scopes=["documents:read"],
        )

        assert api_key.tenant_id == "tenant-1"
        assert api_key.name == "New Key"
        assert raw_key.startswith("irpf_ak_")
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_api_key_success(self, auth_service, mock_repo, valid_api_key):
        api_key, _ = valid_api_key
        mock_repo.get_by_id.return_value = api_key

        result = await auth_service.revoke_api_key(api_key.api_key_id, "tenant-1")

        assert result is True
        mock_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_revoke_api_key_not_found(self, auth_service, mock_repo):
        mock_repo.get_by_id.return_value = None

        result = await auth_service.revoke_api_key("nonexistent", "tenant-1")

        assert result is False
        mock_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_api_keys(self, auth_service, mock_repo, valid_api_key):
        api_key, _ = valid_api_key
        mock_repo.list_by_tenant.return_value = [api_key]

        keys = await auth_service.list_api_keys("tenant-1")

        assert len(keys) == 1
        assert keys[0].api_key_id == api_key.api_key_id
        mock_repo.list_by_tenant.assert_called_once_with("tenant-1", False)
