from datetime import datetime, timezone
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from irpf_processor.domain.entities import ApiKey
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)


class MongoApiKeyRepository:

    COLLECTION_NAME = "api_keys"

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._db = database
        self._collection = database[self.COLLECTION_NAME]

    async def create(self, api_key: ApiKey) -> None:
        doc = {
            "api_key_id": api_key.api_key_id,
            "tenant_id": api_key.tenant_id,
            "name": api_key.name,
            "key_prefix": api_key.key_prefix,
            "key_hash": api_key.key_hash,
            "scopes": api_key.scopes,
            "expires_at": api_key.expires_at,
            "is_active": api_key.is_active,
            "created_at": api_key.created_at,
            "last_used_at": api_key.last_used_at,
            "created_by": api_key.created_by,
        }

        await self._collection.insert_one(doc)

        logger.info(
            "API key created",
            api_key_id=api_key.api_key_id,
            tenant_id=api_key.tenant_id,
            name=api_key.name,
        )

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        doc = await self._collection.find_one({"key_hash": key_hash})

        if not doc:
            return None

        return self._to_entity(doc)

    async def get_by_id(self, api_key_id: str, tenant_id: str) -> Optional[ApiKey]:
        doc = await self._collection.find_one({
            "api_key_id": api_key_id,
            "tenant_id": tenant_id,
        })

        if not doc:
            return None

        return self._to_entity(doc)

    async def list_by_tenant(
        self, tenant_id: str, include_inactive: bool = False
    ) -> list[ApiKey]:
        query: dict = {"tenant_id": tenant_id}

        if not include_inactive:
            query["is_active"] = True

        cursor = self._collection.find(query).sort("created_at", -1)

        keys = []
        async for doc in cursor:
            keys.append(self._to_entity(doc))

        return keys

    async def update(self, api_key: ApiKey) -> None:
        doc = {
            "name": api_key.name,
            "scopes": api_key.scopes,
            "expires_at": api_key.expires_at,
            "is_active": api_key.is_active,
            "last_used_at": api_key.last_used_at,
        }

        await self._collection.update_one(
            {"api_key_id": api_key.api_key_id, "tenant_id": api_key.tenant_id},
            {"$set": doc},
        )

        logger.info(
            "API key updated",
            api_key_id=api_key.api_key_id,
            is_active=api_key.is_active,
        )

    async def delete(self, api_key_id: str, tenant_id: str) -> None:
        await self._collection.delete_one({
            "api_key_id": api_key_id,
            "tenant_id": tenant_id,
        })

        logger.info(
            "API key deleted",
            api_key_id=api_key_id,
            tenant_id=tenant_id,
        )

    async def update_last_used(self, api_key_id: str) -> None:
        await self._collection.update_one(
            {"api_key_id": api_key_id},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}},
        )

    def _to_entity(self, doc: dict) -> ApiKey:
        return ApiKey(
            api_key_id=doc["api_key_id"],
            tenant_id=doc["tenant_id"],
            name=doc["name"],
            key_prefix=doc.get("key_prefix", ""),
            key_hash=doc["key_hash"],
            scopes=doc.get("scopes", []),
            expires_at=doc.get("expires_at"),
            is_active=doc.get("is_active", True),
            created_at=doc["created_at"],
            last_used_at=doc.get("last_used_at"),
            created_by=doc.get("created_by"),
        )
