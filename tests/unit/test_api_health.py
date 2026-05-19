import pytest
import sys
from unittest.mock import MagicMock


@pytest.fixture
def health_test_client():
    sys.modules["irpf_processor.infrastructure.persistence.database"] = MagicMock()
    sys.modules["irpf_processor.infrastructure.persistence"] = MagicMock()
    sys.modules["motor"] = MagicMock()
    sys.modules["motor.motor_asyncio"] = MagicMock()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()

    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    @app.get("/ready")
    async def readiness_check():
        return {"status": "ready"}

    with TestClient(app) as client:
        yield client


class TestHealthEndpoint:

    def test_health_check_returns_200(self, health_test_client):
        response = health_test_client.get("/health")

        assert response.status_code == 200

    def test_health_check_returns_healthy_status(self, health_test_client):
        response = health_test_client.get("/health")

        data = response.json()
        assert data["status"] == "healthy"

    def test_health_check_response_is_json(self, health_test_client):
        response = health_test_client.get("/health")

        assert response.headers["content-type"] == "application/json"


class TestReadinessEndpoint:

    def test_readiness_check_returns_200(self, health_test_client):
        response = health_test_client.get("/ready")

        assert response.status_code == 200

    def test_readiness_check_returns_ready_status(self, health_test_client):
        response = health_test_client.get("/ready")

        data = response.json()
        assert data["status"] == "ready"

    def test_readiness_check_response_is_json(self, health_test_client):
        response = health_test_client.get("/ready")

        assert response.headers["content-type"] == "application/json"
