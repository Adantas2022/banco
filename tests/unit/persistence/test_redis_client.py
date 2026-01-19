import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from irpf_processor.infrastructure.persistence import redis_client


@pytest.fixture
def reset_redis_state():
    original_redis = redis_client._redis
    redis_client._redis = None
    yield
    redis_client._redis = original_redis


class TestInitRedis:

    @pytest.mark.asyncio
    @patch("irpf_processor.infrastructure.persistence.redis_client.get_settings")
    @patch("irpf_processor.infrastructure.persistence.redis_client.redis.from_url")
    async def test_init_redis_creates_connection(self, mock_from_url, mock_settings, reset_redis_state):
        mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")

        mock_redis_instance = MagicMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_from_url.return_value = mock_redis_instance

        await redis_client.init_redis()

        mock_from_url.assert_called_once_with(
            "redis://localhost:6379",
            encoding="utf-8",
            decode_responses=True,
        )

    @pytest.mark.asyncio
    @patch("irpf_processor.infrastructure.persistence.redis_client.get_settings")
    @patch("irpf_processor.infrastructure.persistence.redis_client.redis.from_url")
    async def test_init_redis_pings_server(self, mock_from_url, mock_settings, reset_redis_state):
        mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")

        mock_redis_instance = MagicMock()
        mock_redis_instance.ping = AsyncMock(return_value=True)
        mock_from_url.return_value = mock_redis_instance

        await redis_client.init_redis()

        mock_redis_instance.ping.assert_called_once()


class TestGetRedis:

    @pytest.mark.asyncio
    async def test_get_redis_returns_redis_when_initialized(self, reset_redis_state):
        mock_redis = MagicMock()
        redis_client._redis = mock_redis

        result = await redis_client.get_redis()

        assert result == mock_redis

    @pytest.mark.asyncio
    @patch("irpf_processor.infrastructure.persistence.redis_client.init_redis")
    async def test_get_redis_initializes_when_none(self, mock_init, reset_redis_state):
        mock_redis = MagicMock()
        redis_client._redis = None

        async def set_redis():
            redis_client._redis = mock_redis

        mock_init.side_effect = set_redis

        result = await redis_client.get_redis()

        mock_init.assert_called_once()


class TestCloseRedis:

    @pytest.mark.asyncio
    async def test_close_redis_closes_connection(self, reset_redis_state):
        mock_redis = MagicMock()
        mock_redis.close = AsyncMock()
        redis_client._redis = mock_redis

        await redis_client.close_redis()

        mock_redis.close.assert_called_once()
        assert redis_client._redis is None

    @pytest.mark.asyncio
    async def test_close_redis_does_nothing_when_not_initialized(self, reset_redis_state):
        redis_client._redis = None

        await redis_client.close_redis()

        assert redis_client._redis is None


class TestRedisClientModule:

    def test_module_global_variable_exists(self):
        assert hasattr(redis_client, "_redis")

    def test_init_redis_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(redis_client.init_redis)

    def test_get_redis_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(redis_client.get_redis)

    def test_close_redis_is_async(self):
        import asyncio
        assert asyncio.iscoroutinefunction(redis_client.close_redis)
