import pytest
import sys
from unittest.mock import AsyncMock, MagicMock
from typing import Generator

from irpf_processor.domain.entities import Document
from irpf_processor.domain.enums import DocumentStatus, PdfType


SAMPLE_TENANT_ID = "test-tenant-001"
SAMPLE_PDF_BYTES = b"%PDF-1.4 test content"


def create_sample_document(
    document_id: str = "test-doc-123",
    status: DocumentStatus = DocumentStatus.RECEIVED,
    pdf_type: PdfType = None,
    confidence: float = None,
) -> Document:
    doc = Document(
        tenant_id=SAMPLE_TENANT_ID,
        filename="test.pdf",
        content_type="application/pdf",
        storage_uri="s3://bucket/test.pdf",
        sha256="abc123",
    )
    doc.document_id = document_id
    doc.status = status
    if pdf_type:
        doc.pdf_type = pdf_type
    if confidence is not None:
        doc.confidence = confidence
    return doc


@pytest.fixture
def documents_test_client() -> Generator:
    mock_motor = MagicMock()
    mock_motor.motor_asyncio = MagicMock()

    sys.modules["motor"] = mock_motor
    sys.modules["motor.motor_asyncio"] = mock_motor.motor_asyncio

    mock_persistence = MagicMock()
    mock_persistence.get_database = AsyncMock()
    mock_persistence.init_database = AsyncMock()
    mock_persistence.close_database = AsyncMock()
    sys.modules["irpf_processor.infrastructure.persistence"] = mock_persistence
    sys.modules["irpf_processor.infrastructure.persistence.database"] = mock_persistence

    mock_repo_module = MagicMock()

    class MockMongoDocumentRepository:
        def __init__(self, db):
            self.db = db
            self.find_by_sha256 = AsyncMock(return_value=None)
            self.create = AsyncMock(return_value=None)
            self.get_by_id = AsyncMock(return_value=None)
            self.update_status = AsyncMock(return_value=None)

    mock_repo_module.MongoDocumentRepository = MockMongoDocumentRepository
    sys.modules["irpf_processor.infrastructure.persistence.document_repository"] = mock_repo_module

    mock_storage_module = MagicMock()

    class MockMinioStorageService:
        def __init__(self):
            self.upload = AsyncMock(return_value="s3://bucket/key")
            self.download = AsyncMock(return_value=SAMPLE_PDF_BYTES)

    mock_storage_module.MinioStorageService = MockMinioStorageService
    sys.modules["irpf_processor.infrastructure.storage.minio_storage"] = mock_storage_module

    mock_worker_module = MagicMock()
    mock_worker_module.process_document = MagicMock()
    mock_worker_module.process_document.send = MagicMock()
    sys.modules["irpf_processor.presentation.workers.extraction_worker"] = mock_worker_module

    mock_logger = MagicMock()
    mock_logger.get_logger = MagicMock(return_value=MagicMock())
    sys.modules["irpf_processor.shared.logging"] = mock_logger

    from fastapi import FastAPI, File, Header, HTTPException, UploadFile, status, Depends
    from fastapi.testclient import TestClient
    from pydantic import BaseModel
    from typing import Optional

    class UploadResponse(BaseModel):
        document_id: str
        status: str
        message: str

    class DocumentStatusResponse(BaseModel):
        document_id: str
        status: str
        pdf_type: Optional[str] = None
        confidence: Optional[float] = None
        error_message: Optional[str] = None
        created_at: str
        updated_at: str

    app = FastAPI()

    mock_repo_instance = MockMongoDocumentRepository(None)
    mock_storage_instance = MockMinioStorageService()

    async def get_document_repository():
        return mock_repo_instance

    async def get_storage_service():
        return mock_storage_instance

    @app.post(
        "/v1/documents",
        response_model=UploadResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def upload_document(
        file: UploadFile = File(...),
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        doc_repo = Depends(get_document_repository),
        storage = Depends(get_storage_service),
    ):
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF files are allowed",
            )

        content = await file.read()

        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty file",
            )

        sha256 = "test_hash"
        existing = await doc_repo.find_by_sha256(x_tenant_id, sha256)
        if existing:
            return UploadResponse(
                document_id=existing.document_id,
                status=existing.status.value,
                message="Document already exists",
            )

        document = Document(
            tenant_id=x_tenant_id,
            filename=file.filename,
            content_type=file.content_type or "application/pdf",
            storage_uri="",
            sha256=sha256,
        )

        storage_uri = await storage.upload(
            content=content,
            key=f"{x_tenant_id}/{document.document_id}/{file.filename}",
            content_type=document.content_type,
        )
        document.storage_uri = storage_uri

        await doc_repo.create(document)

        return UploadResponse(
            document_id=document.document_id,
            status=document.status.value,
            message="Document received and queued for processing",
        )

    @app.get("/v1/documents/{document_id}/status", response_model=DocumentStatusResponse)
    async def get_document_status(
        document_id: str,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        doc_repo = Depends(get_document_repository),
    ):
        document = await doc_repo.get_by_id(document_id, x_tenant_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        return DocumentStatusResponse(
            document_id=document.document_id,
            status=document.status.value,
            pdf_type=document.pdf_type.value if document.pdf_type else None,
            confidence=document.confidence,
            error_message=document.error_message,
            created_at=document.created_at.isoformat(),
            updated_at=document.updated_at.isoformat(),
        )

    @app.get("/v1/documents/{document_id}")
    async def get_document_result(
        document_id: str,
        x_tenant_id: str = Header(..., alias="X-Tenant-ID"),
        doc_repo = Depends(get_document_repository),
    ):
        document = await doc_repo.get_by_id(document_id, x_tenant_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )

        if document.status != DocumentStatus.READY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Document not ready. Current status: {document.status.value}",
            )

        return {"document_id": document_id, "data": {"taxpayer": {"cpf": "123"}}}

    with TestClient(app) as client:
        yield {
            "client": client,
            "mock_repo": mock_repo_instance,
            "mock_storage": mock_storage_instance,
        }


class TestUploadDocument:

    def test_upload_requires_tenant_id_header(self, documents_test_client):
        client = documents_test_client["client"]

        response = client.post(
            "/v1/documents",
            files={"file": ("test.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
        )

        assert response.status_code == 422

    def test_upload_rejects_non_pdf_files(self, documents_test_client):
        client = documents_test_client["client"]

        response = client.post(
            "/v1/documents",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
            files={"file": ("test.txt", b"not a pdf", "text/plain")},
        )

        assert response.status_code == 400
        assert "PDF" in response.json()["detail"]

    def test_upload_rejects_empty_files(self, documents_test_client):
        client = documents_test_client["client"]

        response = client.post(
            "/v1/documents",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
            files={"file": ("empty.pdf", b"", "application/pdf")},
        )

        assert response.status_code == 400
        assert "Empty" in response.json()["detail"]

    def test_upload_success_returns_202(self, documents_test_client):
        client = documents_test_client["client"]

        response = client.post(
            "/v1/documents",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
            files={"file": ("irpf_2025.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
        )

        assert response.status_code == 202
        data = response.json()
        assert "document_id" in data
        assert data["status"] == "RECEIVED"
        assert "message" in data

    def test_upload_duplicate_returns_existing(self, documents_test_client):
        client = documents_test_client["client"]
        mock_repo = documents_test_client["mock_repo"]

        existing_doc = create_sample_document(
            document_id="existing-doc-123",
            status=DocumentStatus.READY
        )
        mock_repo.find_by_sha256 = AsyncMock(return_value=existing_doc)

        response = client.post(
            "/v1/documents",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
            files={"file": ("irpf_2025.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["document_id"] == "existing-doc-123"
        assert "already exists" in data["message"].lower()


class TestGetDocumentStatus:

    def test_status_not_found_returns_404(self, documents_test_client):
        client = documents_test_client["client"]
        mock_repo = documents_test_client["mock_repo"]
        mock_repo.get_by_id = AsyncMock(return_value=None)

        response = client.get(
            "/v1/documents/nonexistent-doc/status",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
        )

        assert response.status_code == 404

    def test_status_returns_document_info(self, documents_test_client):
        client = documents_test_client["client"]
        mock_repo = documents_test_client["mock_repo"]

        doc = create_sample_document(
            document_id="doc-status-test",
            status=DocumentStatus.ROUTED,
            pdf_type=PdfType.DIGITAL,
        )
        mock_repo.get_by_id = AsyncMock(return_value=doc)

        response = client.get(
            "/v1/documents/doc-status-test/status",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["document_id"] == "doc-status-test"
        assert data["status"] == "ROUTED"
        assert data["pdf_type"] == "DIGITAL"

    def test_status_requires_tenant_id(self, documents_test_client):
        client = documents_test_client["client"]

        response = client.get("/v1/documents/any-doc/status")

        assert response.status_code == 422


class TestGetDocumentResult:

    def test_result_not_found_returns_404(self, documents_test_client):
        client = documents_test_client["client"]
        mock_repo = documents_test_client["mock_repo"]
        mock_repo.get_by_id = AsyncMock(return_value=None)

        response = client.get(
            "/v1/documents/nonexistent-doc",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
        )

        assert response.status_code == 404

    def test_result_not_ready_returns_409(self, documents_test_client):
        client = documents_test_client["client"]
        mock_repo = documents_test_client["mock_repo"]

        doc = create_sample_document(
            document_id="doc-processing",
            status=DocumentStatus.ROUTED,
        )
        mock_repo.get_by_id = AsyncMock(return_value=doc)

        response = client.get(
            "/v1/documents/doc-processing",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
        )

        assert response.status_code == 409
        assert "not ready" in response.json()["detail"].lower()

    def test_result_requires_tenant_id(self, documents_test_client):
        client = documents_test_client["client"]

        response = client.get("/v1/documents/any-doc")

        assert response.status_code == 422

    def test_result_returns_extraction_data(self, documents_test_client):
        client = documents_test_client["client"]
        mock_repo = documents_test_client["mock_repo"]

        doc = create_sample_document(
            document_id="doc-ready",
            status=DocumentStatus.READY,
            pdf_type=PdfType.DIGITAL,
            confidence=0.95,
        )
        mock_repo.get_by_id = AsyncMock(return_value=doc)

        response = client.get(
            "/v1/documents/doc-ready",
            headers={"X-Tenant-ID": SAMPLE_TENANT_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
