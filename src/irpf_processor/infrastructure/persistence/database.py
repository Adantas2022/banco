"""Conexão MongoDB usando Motor (async)."""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT

from irpf_processor.config import get_settings
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

_client: Optional[AsyncIOMotorClient] = None
_database: Optional[AsyncIOMotorDatabase] = None


async def init_database() -> None:
    """Inicializa conexão com MongoDB."""
    global _client, _database

    settings = get_settings()

    _client = AsyncIOMotorClient(settings.mongo_uri)
    _database = _client[settings.mongo_db]

    await _client.admin.command("ping")
    
    await _create_indexes(_database)


async def get_database() -> AsyncIOMotorDatabase:
    """Retorna instância do banco de dados."""
    if _database is None:
        await init_database()
    return _database  # type: ignore


async def close_database() -> None:
    """Fecha conexão com MongoDB."""
    global _client, _database

    if _client:
        _client.close()
        _client = None
        _database = None


async def _create_indexes(db: AsyncIOMotorDatabase) -> None:
    """Cria índices para otimizar buscas."""
    documents = db["documents"]
    await documents.create_index(
        [("tenant_id", ASCENDING), ("document_id", ASCENDING)],
        unique=True,
        name="idx_tenant_document",
    )
    await documents.create_index(
        [("tenant_id", ASCENDING), ("sha256", ASCENDING)],
        name="idx_tenant_sha256",
    )
    await documents.create_index(
        [("tenant_id", ASCENDING), ("status", ASCENDING)],
        name="idx_tenant_status",
    )

    extraction = db["extraction_results"]
    await extraction.create_index(
        [("tenant_id", ASCENDING), ("document_id", ASCENDING)],
        unique=True,
        name="idx_tenant_document",
    )
    await extraction.create_index(
        [("tenant_id", ASCENDING), ("data.taxpayer_identification.normalized_cpf", ASCENDING)],
        name="idx_tenant_cpf",
    )
    await extraction.create_index(
        [("tenant_id", ASCENDING), ("data.taxpayer_identification.exercise_year", DESCENDING)],
        name="idx_tenant_year",
    )
    await extraction.create_index(
        [("tenant_id", ASCENDING), ("data.taxpayer_identification.name", ASCENDING)],
        name="idx_tenant_name",
    )
    await extraction.create_index(
        [("tenant_id", ASCENDING), ("confidence", DESCENDING)],
        name="idx_tenant_confidence",
    )
    
    logger.info("Database indexes created")
