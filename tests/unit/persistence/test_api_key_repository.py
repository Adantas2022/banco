import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

from irpf_processor.domain.entities.api_key import ApiKey
from irpf_processor.infrastructure.persistence.api_key_repository import MongoApiKeyRepository


@pytest.fixture
def mock_database():
    db = MagicMock()
    collection = MagicMock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock()
    collection.update_one = AsyncMock()
    collection.delete_one = AsyncMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


@pytest.fixture
def sample_api_key():
    return ApiKey(
        api_key_id="key-123",
        tenant_id="tenant-456",
        name="Test API Key",
        key_prefix="irpf_",
        key_hash="hash123abc",
        scopes=["documents:read", "documents:write"],
        is_active=True,
        created_by="user-789",
    )


@pytest.fixture
def sample_api_key_dict():
    now = datetime.now(timezone.utc)
    return {
        "api_key_id": "key-123",
        "tenant_id": "tenant-456",
        "name": "Test API Key",
        "key_prefix": "irpf_",
        "key_hash": "hash123abc",
        "scopes": ["documents:read", "documents:write"],
        "expires_at": None,
        "is_active": True,
        "created_at": now,
        "last_used_at": None,
        "created_by": "user-789",
    }


class TestMongoApiKeyRepositoryInit:

    def test_initializes_with_database(self, mock_database):
        db, collection = mock_database
        repo = MongoApiKeyRepository(db)

        assert repo._db == db
        assert repo._collection == collection
        db.__getitem__.assert_called_once_with("api_keys")


class TestMongoApiKeyRepositoryCreate:

    @pytest.mark.asyncio
    async def test_creates_api_key(self, mock_database, sample_api_key):
        db, collection = mock_database
        repo = MongoApiKeyRepository(db)

        await repo.create(sample_api_key)

        collection.insert_one.assert_called_once()
        call_args = collection.insert_one.call_args[0][0]
        assert call_args["api_key_id"] == "key-123"
        assert call_args["tenant_id"] == "tenant-456"
        assert call_args["name"] == "Test API Key"
        assert call_args["key_hash"] == "hash123abc"
        assert call_args["scopes"] == ["documents:read", "documents:write"]

    @pytest.mark.asyncio
    async def test_creates_api_key_with_expiration(self, mock_database):
        db, collection = mock_database
        repo = MongoApiKeyRepository(db)

        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        api_key = ApiKey(
            tenant_id="tenant-456",
            name="Expiring Key",
            key_hash="hash123",
            scopes=["documents:read"],
            expires_at=expires_at,
        )

        await repo.create(api_key)

        call_args = collection.insert_one.call_args[0][0]
        assert call_args["expires_at"] == expires_at


class TestMongoApiKeyRepositoryGetByHash:

    @pytest.mark.asyncio
    async def test_returns_api_key_when_found(self, mock_database, sample_api_key_dict):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=sample_api_key_dict)
        repo = MongoApiKeyRepository(db)

        result = await repo.get_by_hash("hash123abc")

        assert result is not None
        assert result.key_hash == "hash123abc"
        assert result.tenant_id == "tenant-456"
        collection.find_one.assert_called_once_with({"key_hash": "hash123abc"})

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_database):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=None)
        repo = MongoApiKeyRepository(db)

        result = await repo.get_by_hash("nonexistent")

        assert result is None


class TestMongoApiKeyRepositoryGetById:

    @pytest.mark.asyncio
    async def test_returns_api_key_when_found(self, mock_database, sample_api_key_dict):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=sample_api_key_dict)
        repo = MongoApiKeyRepository(db)

        result = await repo.get_by_id("key-123", "tenant-456")

        assert result is not None
        assert result.api_key_id == "key-123"
        collection.find_one.assert_called_once_with({
            "api_key_id": "key-123",
            "tenant_id": "tenant-456",
        })

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_database):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=None)
        repo = MongoApiKeyRepository(db)

        result = await repo.get_by_id("nonexistent", "tenant-456")

        assert result is None


class TestMongoApiKeyRepositoryListByTenant:

    @pytest.mark.asyncio
    async def test_lists_active_api_keys_by_default(self, mock_database, sample_api_key_dict):
        db, collection = mock_database

        async def async_iter():
            yield sample_api_key_dict

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__ = lambda self: async_iter()

        collection.find.return_value = mock_cursor
        repo = MongoApiKeyRepository(db)

        result = await repo.list_by_tenant("tenant-456")

        assert len(result) == 1
        collection.find.assert_called_once_with({
            "tenant_id": "tenant-456",
            "is_active": True
        })

    @pytest.mark.asyncio
    async def test_includes_inactive_when_requested(self, mock_database, sample_api_key_dict):
        db, collection = mock_database

        async def async_iter():
            yield sample_api_key_dict

        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__ = lambda self: async_iter()

        collection.find.return_value = mock_cursor
        repo = MongoApiKeyRepository(db)

        await repo.list_by_tenant("tenant-456", include_inactive=True)

        collection.find.assert_called_once_with({"tenant_id": "tenant-456"})


class TestMongoApiKeyRepositoryUpdate:

    @pytest.mark.asyncio
    async def test_updates_api_key(self, mock_database, sample_api_key):
        db, collection = mock_database
        repo = MongoApiKeyRepository(db)

        sample_api_key.name = "Updated Name"
        sample_api_key.scopes = ["documents:read"]

        await repo.update(sample_api_key)

        collection.update_one.assert_called_once()
        call_args = collection.update_one.call_args
        assert call_args[0][0] == {
            "api_key_id": "key-123",
            "tenant_id": "tenant-456"
        }
        assert call_args[0][1]["$set"]["name"] == "Updated Name"
        assert call_args[0][1]["$set"]["scopes"] == ["documents:read"]


class TestMongoApiKeyRepositoryDelete:

    @pytest.mark.asyncio
    async def test_deletes_api_key(self, mock_database):
        db, collection = mock_database
        repo = MongoApiKeyRepository(db)

        await repo.delete("key-123", "tenant-456")

        collection.delete_one.assert_called_once_with({
            "api_key_id": "key-123",
            "tenant_id": "tenant-456",
        })


class TestMongoApiKeyRepositoryUpdateLastUsed:

    @pytest.mark.asyncio
    async def test_updates_last_used_timestamp(self, mock_database):
        db, collection = mock_database
        repo = MongoApiKeyRepository(db)

        await repo.update_last_used("key-123")

        collection.update_one.assert_called_once()
        call_args = collection.update_one.call_args
        assert call_args[0][0] == {"api_key_id": "key-123"}
        assert "last_used_at" in call_args[0][1]["$set"]


class TestMongoApiKeyRepositoryToEntity:

    def test_converts_dict_to_api_key(self, mock_database, sample_api_key_dict):
        db, _ = mock_database
        repo = MongoApiKeyRepository(db)

        result = repo._to_entity(sample_api_key_dict)

        assert isinstance(result, ApiKey)
        assert result.api_key_id == "key-123"
        assert result.tenant_id == "tenant-456"
        assert result.name == "Test API Key"
        assert result.key_hash == "hash123abc"
        assert result.scopes == ["documents:read", "documents:write"]
        assert result.is_active is True

    def test_handles_missing_optional_fields(self, mock_database):
        db, _ = mock_database
        repo = MongoApiKeyRepository(db)

        minimal_dict = {
            "api_key_id": "key-123",
            "tenant_id": "tenant-456",
            "name": "Minimal Key",
            "key_hash": "hash123",
            "created_at": datetime.now(timezone.utc),
        }

        result = repo._to_entity(minimal_dict)

        assert result.key_prefix == ""
        assert result.scopes == []
        assert result.expires_at is None
        assert result.is_active is True
        assert result.last_used_at is None
        assert result.created_by is None

    def test_converts_dict_with_expiration(self, mock_database, sample_api_key_dict):
        db, _ = mock_database
        repo = MongoApiKeyRepository(db)
        expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        sample_api_key_dict["expires_at"] = expires_at

        result = repo._to_entity(sample_api_key_dict)

        assert result.expires_at == expires_at
