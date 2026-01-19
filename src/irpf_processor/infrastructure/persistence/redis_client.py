"""Conexão Redis."""

from typing import Optional

import redis.asyncio as redis

from irpf_processor.config import get_settings

_redis: Optional[redis.Redis] = None


async def init_redis() -> None:
    """Inicializa conexão com Redis."""
    global _redis

    settings = get_settings()

    _redis = redis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )

    # Verificar conexão
    await _redis.ping()


async def get_redis() -> redis.Redis:
    """Retorna instância do Redis."""
    if _redis is None:
        await init_redis()
    return _redis  # type: ignore


async def close_redis() -> None:
    """Fecha conexão com Redis."""
    global _redis

    if _redis:
        await _redis.close()
        _redis = None
