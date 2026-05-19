import pytest
import httpx


@pytest.mark.e2e
class TestAuthenticationRequired:

    def test_documents_upload_requires_auth(self, http_client: httpx.Client, test_pdf_path):
        with open(test_pdf_path, "rb") as f:
            files = {"file": (test_pdf_path.name, f, "application/pdf")}
            response = http_client.post("/v1/documents", files=files)
        
        assert response.status_code == 401
        assert "WWW-Authenticate" in response.headers

    def test_documents_status_requires_auth(self, http_client: httpx.Client):
        response = http_client.get("/v1/documents/some-id/status")
        
        assert response.status_code == 401

    def test_documents_result_requires_auth(self, http_client: httpx.Client):
        response = http_client.get("/v1/documents/some-id")
        
        assert response.status_code == 401

    def test_search_requires_auth(self, http_client: httpx.Client):
        response = http_client.get("/v1/irpf/search")
        
        assert response.status_code == 401

    def test_search_by_cpf_requires_auth(self, http_client: httpx.Client):
        response = http_client.get("/v1/irpf/search/by-cpf/12345678900")
        
        assert response.status_code == 401

    def test_stats_requires_auth(self, http_client: httpx.Client):
        response = http_client.get("/v1/irpf/stats")
        
        assert response.status_code == 401


@pytest.mark.e2e
class TestAuthMeEndpoint:

    def test_auth_me_returns_key_info(
        self,
        http_client: httpx.Client,
        auth_headers: dict,
    ):
        response = http_client.get("/v1/auth/me", headers=auth_headers)
        
        if response.status_code == 401:
            pytest.skip("E2E_API_KEY not configured - skipping auth/me test")
        
        assert response.status_code == 200
        data = response.json()
        assert "api_key_id" in data
        assert "tenant_id" in data
        assert "scopes" in data

    def test_auth_me_without_token_returns_401(self, http_client: httpx.Client):
        response = http_client.get("/v1/auth/me")
        
        assert response.status_code == 401


@pytest.mark.e2e
class TestInvalidAuth:

    def test_invalid_token_returns_401(self, http_client: httpx.Client):
        headers = {"Authorization": "Bearer invalid_token_12345"}
        response = http_client.get("/v1/documents/test/status", headers=headers)
        
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self, http_client: httpx.Client):
        headers = {"Authorization": "InvalidFormat token123"}
        response = http_client.get("/v1/documents/test/status", headers=headers)
        
        assert response.status_code in [401, 403]

    def test_empty_bearer_returns_401(self, http_client: httpx.Client):
        headers = {"Authorization": "Bearer "}
        response = http_client.get("/v1/documents/test/status", headers=headers)
        
        assert response.status_code == 401


@pytest.mark.e2e
class TestPublicEndpointsNoAuth:

    def test_health_does_not_require_auth(self, http_client: httpx.Client):
        response = http_client.get("/health")
        
        assert response.status_code == 200

    def test_ready_does_not_require_auth(self, http_client: httpx.Client):
        response = http_client.get("/ready")
        
        assert response.status_code == 200

    def test_metrics_does_not_require_auth(self, http_client: httpx.Client):
        response = http_client.get("/metrics")
        
        assert response.status_code == 200
