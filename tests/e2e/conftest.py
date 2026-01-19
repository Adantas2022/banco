import os
import asyncio
from pathlib import Path
from typing import Generator
from datetime import datetime, timezone

import pytest
import httpx

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.enums import AuthScope


E2E_BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8000")
E2E_TENANT_ID = os.environ.get("E2E_TENANT_ID", f"e2e-test-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
E2E_TIMEOUT = int(os.environ.get("E2E_TIMEOUT", "300"))
E2E_POLL_INTERVAL = int(os.environ.get("E2E_POLL_INTERVAL", "2"))


def get_test_pdf_path() -> Path:
    project_root = Path(__file__).parent.parent.parent
    test_pdf = project_root / "docs" / "IRPF" / "Geral-IRPF-2025-2024.pdf"
    if test_pdf.exists():
        return test_pdf
    
    pdfs_dir = project_root / "pdfs"
    if pdfs_dir.exists():
        pdfs = list(pdfs_dir.glob("*.pdf"))
        if pdfs:
            return pdfs[0]
    
    raise FileNotFoundError("No test PDF found")


@pytest.fixture(scope="session")
def base_url() -> str:
    return E2E_BASE_URL


@pytest.fixture(scope="session")
def tenant_id() -> str:
    return E2E_TENANT_ID


@pytest.fixture(scope="session")
def test_pdf_path() -> Path:
    return get_test_pdf_path()


@pytest.fixture(scope="session")
def api_key_raw() -> str:
    key = os.environ.get("E2E_API_KEY")
    if key:
        return key
    
    _, _, key_hash = ApiKey.generate_key()
    return f"irpf_ak_test_{key_hash[:32]}"


@pytest.fixture(scope="session")
def auth_headers(api_key_raw: str) -> dict:
    return {"Authorization": f"Bearer {api_key_raw}"}


@pytest.fixture(scope="session")
def http_client(base_url: str) -> Generator[httpx.Client, None, None]:
    with httpx.Client(base_url=base_url, timeout=60.0) as client:
        yield client


@pytest.fixture(scope="session")
def async_http_client(base_url: str) -> Generator[httpx.AsyncClient, None, None]:
    async def create_client():
        return httpx.AsyncClient(base_url=base_url, timeout=60.0)
    
    client = asyncio.get_event_loop().run_until_complete(create_client())
    yield client
    asyncio.get_event_loop().run_until_complete(client.aclose())


class E2EHelpers:
    
    def __init__(self, client: httpx.Client, auth_headers: dict, tenant_id: str):
        self.client = client
        self.auth_headers = auth_headers
        self.tenant_id = tenant_id
    
    def upload_document(self, pdf_path: Path) -> dict:
        with open(pdf_path, "rb") as f:
            files = {"file": (pdf_path.name, f, "application/pdf")}
            response = self.client.post(
                "/v1/documents",
                headers=self.auth_headers,
                files=files,
            )
        response.raise_for_status()
        return response.json()
    
    def get_status(self, document_id: str) -> dict:
        response = self.client.get(
            f"/v1/documents/{document_id}/status",
            headers=self.auth_headers,
        )
        response.raise_for_status()
        return response.json()
    
    def get_result(self, document_id: str) -> dict:
        response = self.client.get(
            f"/v1/documents/{document_id}",
            headers=self.auth_headers,
        )
        response.raise_for_status()
        return response.json()
    
    def wait_for_ready(
        self,
        document_id: str,
        max_wait: int = E2E_TIMEOUT,
        poll_interval: int = E2E_POLL_INTERVAL,
    ) -> dict:
        import time
        
        terminal_statuses = {"READY", "FAILED", "QUARANTINED"}
        start_time = time.time()
        
        while True:
            elapsed = time.time() - start_time
            if elapsed > max_wait:
                raise TimeoutError(f"Document {document_id} not ready after {max_wait}s")
            
            status_data = self.get_status(document_id)
            current_status = status_data.get("status", "UNKNOWN")
            
            if current_status in terminal_statuses:
                return status_data
            
            time.sleep(poll_interval)
    
    def search_by_cpf(self, cpf: str) -> list:
        response = self.client.get(
            f"/v1/irpf/search/by-cpf/{cpf}",
            headers=self.auth_headers,
        )
        response.raise_for_status()
        return response.json()
    
    def search(self, **filters) -> dict:
        response = self.client.get(
            "/v1/irpf/search",
            headers=self.auth_headers,
            params=filters,
        )
        response.raise_for_status()
        return response.json()


@pytest.fixture(scope="session")
def e2e_helpers(http_client: httpx.Client, auth_headers: dict, tenant_id: str) -> E2EHelpers:
    return E2EHelpers(http_client, auth_headers, tenant_id)
