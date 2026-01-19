"""Testes de integração para endpoints de health check."""

import pytest
from httpx import AsyncClient


@pytest.mark.skip(reason="Requer API rodando - implementar fixtures de client")
@pytest.mark.integration
class TestHealthEndpoints:
    """Testes para endpoints de health check."""

    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient) -> None:
        """Testa endpoint /health."""
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_readiness_check(self, client: AsyncClient) -> None:
        """Testa endpoint /ready."""
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
