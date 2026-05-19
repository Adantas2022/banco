import pytest
from unittest.mock import AsyncMock, MagicMock

from irpf_processor.domain.entities import Document
from irpf_processor.domain.enums import DocumentStatus, PdfType
from tests.fixtures.documents import (
    create_sample_document,
    SAMPLE_PDF_BYTES,
    SAMPLE_TENANT_ID,
    SAMPLE_DOCUMENT_ID,
)


@pytest.fixture
def tenant_id() -> str:
    return SAMPLE_TENANT_ID


@pytest.fixture
def document_id() -> str:
    return SAMPLE_DOCUMENT_ID


@pytest.fixture
def sample_pdf_content() -> bytes:
    return SAMPLE_PDF_BYTES


@pytest.fixture
def sample_document() -> Document:
    return create_sample_document()


@pytest.fixture
def sample_document_ready() -> Document:
    return create_sample_document(
        status=DocumentStatus.READY,
        pdf_type=PdfType.DIGITAL,
        confidence=0.95,
    )


@pytest.fixture
def mock_document_repository():
    mock_repo = AsyncMock()
    mock_repo.create = AsyncMock(return_value=None)
    mock_repo.get_by_id = AsyncMock(return_value=None)
    mock_repo.find_by_sha256 = AsyncMock(return_value=None)
    mock_repo.update_status = AsyncMock(return_value=None)
    mock_repo.list_by_tenant = AsyncMock(return_value=[])
    return mock_repo


@pytest.fixture
def mock_storage_service():
    mock_storage = AsyncMock()
    mock_storage.upload = AsyncMock(return_value="s3://documents/test/doc.pdf")
    mock_storage.download = AsyncMock(return_value=SAMPLE_PDF_BYTES)
    mock_storage.delete = AsyncMock(return_value=None)
    mock_storage.exists = AsyncMock(return_value=True)
    return mock_storage


@pytest.fixture
def mock_database():
    mock_db = MagicMock()
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="test_id"))
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    return mock_db


@pytest.fixture
def health_test_client():
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
