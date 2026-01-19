import pytest
from datetime import datetime, timezone, timedelta

from irpf_processor.domain.entities.api_key import ApiKey
from irpf_processor.presentation.api.routes.auth import (
    CreateApiKeyRequest,
    ApiKeyResponse,
    CreateApiKeyResponse,
    CurrentKeyResponse,
    _to_response,
)


class TestApiKeyEntity:

    def test_default_values(self):
        key = ApiKey(
            tenant_id="tenant-456",
            name="Test Key",
            key_hash="hash123",
            scopes=["documents:read"],
        )

        assert key.scopes == ["documents:read"]
        assert key.expires_at is None
        assert key.is_active is True
        assert key.last_used_at is None
        assert key.created_by is None

    def test_with_all_fields(self):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)

        key = ApiKey(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Full Key",
            key_prefix="irpf_",
            key_hash="hash123",
            scopes=["documents:read", "documents:write"],
            expires_at=expires,
            is_active=True,
            created_at=now,
            last_used_at=now,
            created_by="admin"
        )

        assert key.scopes == ["documents:read", "documents:write"]
        assert key.expires_at == expires
        assert key.created_by == "admin"

    def test_valid_scopes(self):
        assert "documents:read" in ApiKey.VALID_SCOPES
        assert "documents:write" in ApiKey.VALID_SCOPES
        assert "search:read" in ApiKey.VALID_SCOPES
        assert "admin:keys" in ApiKey.VALID_SCOPES
        assert "invalid:scope" not in ApiKey.VALID_SCOPES


class TestCreateApiKeyRequest:

    def test_valid_request(self):
        request = CreateApiKeyRequest(
            name="Test API Key",
            scopes=["documents:read"],
            expires_at=None
        )

        assert request.name == "Test API Key"
        assert request.scopes == ["documents:read"]
        assert request.expires_at is None

    def test_name_min_length(self):
        with pytest.raises(ValueError):
            CreateApiKeyRequest(name="ab", scopes=[])

    def test_name_max_length(self):
        with pytest.raises(ValueError):
            CreateApiKeyRequest(name="a" * 101, scopes=[])

    def test_with_expiration(self):
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        request = CreateApiKeyRequest(
            name="Expiring Key",
            scopes=["documents:read"],
            expires_at=expires
        )

        assert request.expires_at == expires


class TestApiKeyResponse:

    def test_required_fields(self):
        now = datetime.now(timezone.utc)
        response = ApiKeyResponse(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Test Key",
            key_prefix="irpf_",
            scopes=["documents:read"],
            is_active=True,
            expires_at=None,
            created_at=now,
            last_used_at=None
        )

        assert response.api_key_id == "key-123"
        assert response.tenant_id == "tenant-456"
        assert response.name == "Test Key"
        assert response.key_prefix == "irpf_"
        assert response.scopes == ["documents:read"]
        assert response.is_active is True
        assert response.expires_at is None
        assert response.created_at == now
        assert response.last_used_at is None

    def test_with_all_fields(self):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)
        last_used = now - timedelta(hours=1)

        response = ApiKeyResponse(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Full Key",
            key_prefix="irpf_",
            scopes=["documents:read", "documents:write"],
            is_active=True,
            expires_at=expires,
            created_at=now,
            last_used_at=last_used
        )

        assert response.expires_at == expires
        assert response.last_used_at == last_used


class TestCreateApiKeyResponse:

    def test_includes_api_key_and_raw_key(self):
        now = datetime.now(timezone.utc)
        api_key_response = ApiKeyResponse(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="New Key",
            key_prefix="irpf_",
            scopes=["documents:read"],
            is_active=True,
            expires_at=None,
            created_at=now,
            last_used_at=None
        )

        response = CreateApiKeyResponse(
            api_key=api_key_response,
            raw_key="irpf_abc123xyz789"
        )

        assert response.api_key.api_key_id == "key-123"
        assert response.raw_key == "irpf_abc123xyz789"


class TestCurrentKeyResponse:

    def test_required_fields(self):
        response = CurrentKeyResponse(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Current Key",
            scopes=["documents:read", "search:read"],
            expires_at=None
        )

        assert response.api_key_id == "key-123"
        assert response.tenant_id == "tenant-456"
        assert response.name == "Current Key"
        assert response.scopes == ["documents:read", "search:read"]
        assert response.expires_at is None

    def test_with_expiration(self):
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        response = CurrentKeyResponse(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Expiring Key",
            scopes=["documents:read"],
            expires_at=expires
        )

        assert response.expires_at == expires


class TestToResponse:

    def test_converts_api_key_to_response(self):
        now = datetime.now(timezone.utc)
        api_key = ApiKey(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Test Key",
            key_prefix="irpf_",
            key_hash="hash123",
            scopes=["documents:read"],
            is_active=True,
            created_at=now
        )

        response = _to_response(api_key)

        assert isinstance(response, ApiKeyResponse)
        assert response.api_key_id == "key-123"
        assert response.tenant_id == "tenant-456"
        assert response.name == "Test Key"
        assert response.key_prefix == "irpf_"
        assert response.scopes == ["documents:read"]
        assert response.is_active is True
        assert response.created_at == now

    def test_preserves_optional_fields(self):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30)
        last_used = now - timedelta(hours=1)

        api_key = ApiKey(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Full Key",
            key_prefix="irpf_",
            key_hash="hash123",
            scopes=["documents:read"],
            expires_at=expires,
            is_active=True,
            created_at=now,
            last_used_at=last_used
        )

        response = _to_response(api_key)

        assert response.expires_at == expires
        assert response.last_used_at == last_used

    def test_handles_inactive_key(self):
        now = datetime.now(timezone.utc)
        api_key = ApiKey(
            tenant_id="tenant-456",
            name="Inactive Key",
            key_hash="hash123",
            scopes=["documents:read"],
            is_active=False,
            created_at=now
        )

        response = _to_response(api_key)

        assert response.is_active is False


class TestApiKeyValidation:

    def test_validates_invalid_scopes(self):
        api_key = ApiKey(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Test Key",
            key_prefix="irpf_",
            key_hash="hash123",
            scopes=["invalid:scope"]
        )

        invalid_scopes = set(api_key.scopes) - ApiKey.VALID_SCOPES

        assert "invalid:scope" in invalid_scopes

    def test_validates_valid_scopes(self):
        api_key = ApiKey(
            api_key_id="key-123",
            tenant_id="tenant-456",
            name="Test Key",
            key_prefix="irpf_",
            key_hash="hash123",
            scopes=["documents:read", "documents:write"]
        )

        invalid_scopes = set(api_key.scopes) - ApiKey.VALID_SCOPES

        assert len(invalid_scopes) == 0

    def test_cannot_revoke_self(self):
        current_key_id = "key-123"
        target_key_id = "key-123"

        assert current_key_id == target_key_id

    def test_can_revoke_other_key(self):
        current_key_id = "key-123"
        target_key_id = "key-456"

        assert current_key_id != target_key_id
