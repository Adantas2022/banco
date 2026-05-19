import pytest
from datetime import datetime, timedelta, timezone

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.enums import AuthScope


class TestApiKeyEntity:

    def test_generate_key_returns_tuple(self):
        full_key, prefix, key_hash = ApiKey.generate_key()

        assert full_key.startswith("irpf_ak_")
        assert len(full_key) > 40
        assert prefix == full_key[:16]
        assert len(key_hash) == 64

    def test_hash_key_is_consistent(self):
        key = "irpf_ak_test123"
        hash1 = ApiKey.hash_key(key)
        hash2 = ApiKey.hash_key(key)

        assert hash1 == hash2
        assert len(hash1) == 64

    def test_create_returns_entity_and_raw_key(self):
        api_key, raw_key = ApiKey.create(
            tenant_id="tenant-1",
            name="Test Key",
            scopes=["documents:read"],
        )

        assert api_key.tenant_id == "tenant-1"
        assert api_key.name == "Test Key"
        assert api_key.scopes == ["documents:read"]
        assert api_key.is_active is True
        assert api_key.expires_at is None
        assert raw_key.startswith("irpf_ak_")

    def test_create_with_invalid_scopes_raises(self):
        with pytest.raises(ValueError, match="Invalid scopes"):
            ApiKey.create(
                tenant_id="tenant-1",
                name="Bad Key",
                scopes=["invalid:scope"],
            )

    def test_is_valid_returns_true_for_active_key(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Valid Key",
            scopes=AuthScope.default_scopes(),
        )

        assert api_key.is_valid() is True

    def test_is_valid_returns_false_for_inactive_key(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Inactive Key",
            scopes=AuthScope.default_scopes(),
        )
        api_key.revoke()

        assert api_key.is_valid() is False

    def test_is_valid_returns_false_for_expired_key(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Expired Key",
            scopes=AuthScope.default_scopes(),
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

        assert api_key.is_valid() is False

    def test_has_scope_returns_true_when_present(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Key",
            scopes=["documents:read", "documents:write"],
        )

        assert api_key.has_scope("documents:read") is True
        assert api_key.has_scope("documents:write") is True

    def test_has_scope_returns_false_when_missing(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Key",
            scopes=["documents:read"],
        )

        assert api_key.has_scope("documents:write") is False
        assert api_key.has_scope("admin:keys") is False

    def test_has_any_scope_returns_true_when_any_match(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Key",
            scopes=["documents:read"],
        )

        assert api_key.has_any_scope(["documents:read", "documents:write"]) is True

    def test_has_any_scope_returns_false_when_none_match(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Key",
            scopes=["documents:read"],
        )

        assert api_key.has_any_scope(["admin:keys", "search:read"]) is False

    def test_revoke_sets_inactive(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Key",
            scopes=AuthScope.default_scopes(),
        )

        api_key.revoke()

        assert api_key.is_active is False

    def test_record_usage_updates_last_used_at(self):
        api_key, _ = ApiKey.create(
            tenant_id="tenant-1",
            name="Key",
            scopes=AuthScope.default_scopes(),
        )

        assert api_key.last_used_at is None

        api_key.record_usage()

        assert api_key.last_used_at is not None


class TestAuthScope:

    def test_all_scopes(self):
        scopes = AuthScope.all_scopes()

        assert "documents:read" in scopes
        assert "documents:write" in scopes
        assert "search:read" in scopes
        assert "admin:keys" in scopes
        assert len(scopes) == 4

    def test_default_scopes_excludes_admin(self):
        scopes = AuthScope.default_scopes()

        assert "admin:keys" not in scopes
        assert "documents:read" in scopes
        assert "documents:write" in scopes
        assert "search:read" in scopes
