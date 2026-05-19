import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.enums import AuthScope


@pytest.fixture
def valid_api_key():
    api_key, raw_key = ApiKey.create(
        tenant_id="test-tenant",
        name="Test Key",
        scopes=AuthScope.all_scopes(),
    )
    return api_key, raw_key


@pytest.fixture
def readonly_api_key():
    api_key, raw_key = ApiKey.create(
        tenant_id="test-tenant",
        name="Readonly Key",
        scopes=["documents:read", "search:read"],
    )
    return api_key, raw_key


@pytest.fixture
def mock_api_key_repo():
    return AsyncMock()


@pytest.fixture
def test_client(mock_api_key_repo, valid_api_key):
    api_key, _ = valid_api_key

    async def mock_get_by_hash(key_hash):
        return api_key

    mock_api_key_repo.get_by_hash = mock_get_by_hash
    mock_api_key_repo.update_last_used = AsyncMock()

    with patch("irpf_processor.presentation.api.dependencies.auth.get_database") as mock_db:
        mock_db.return_value = MagicMock()

        with patch("irpf_processor.infrastructure.persistence.MongoApiKeyRepository") as mock_repo_class:
            mock_repo_class.return_value = mock_api_key_repo

            from irpf_processor.main import app
            with TestClient(app) as client:
                yield client


class TestAuthMeEndpoint:

    def test_get_me_without_auth_returns_401(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get("/v1/auth/me")
            assert response.status_code == 401

    def test_get_me_with_invalid_token_returns_401(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get(
                "/v1/auth/me",
                headers={"Authorization": "Bearer invalid_token"}
            )
            assert response.status_code == 401


class TestProtectedEndpoints:

    def test_documents_upload_without_auth_returns_401(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.post("/v1/documents")
            assert response.status_code == 401

    def test_documents_status_without_auth_returns_401(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get("/v1/documents/some-id/status")
            assert response.status_code == 401

    def test_search_without_auth_returns_401(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get("/v1/irpf/search")
            assert response.status_code == 401


class TestPublicEndpoints:

    def test_health_is_public(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"

    def test_ready_is_public(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get("/ready")
            assert response.status_code == 200

    def test_metrics_is_public(self):
        from irpf_processor.main import app
        with TestClient(app) as client:
            response = client.get("/metrics")
            assert response.status_code == 200
