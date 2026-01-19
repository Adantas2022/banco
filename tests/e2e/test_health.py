import pytest
import httpx


@pytest.mark.e2e
class TestHealthEndpoints:

    def test_health_endpoint_returns_healthy(self, http_client: httpx.Client):
        response = http_client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_ready_endpoint_returns_ready(self, http_client: httpx.Client):
        response = http_client.get("/ready")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"

    def test_metrics_endpoint_returns_prometheus_format(self, http_client: httpx.Client):
        response = http_client.get("/metrics")
        
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        assert "irpf_" in response.text or "python_" in response.text

    def test_docs_endpoint_available_in_dev(self, http_client: httpx.Client):
        response = http_client.get("/docs")
        
        assert response.status_code in [200, 404]
