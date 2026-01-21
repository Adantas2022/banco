import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone

from fastapi import HTTPException

from irpf_processor.presentation.api.routes.documents import (
    get_document_repository,
    get_storage_service_dependency,
    upload_document,
    get_document_status,
    get_document_result,
    UploadResponse,
    DocumentStatusResponse,
)
from irpf_processor.domain.enums import DocumentStatus, PdfType


class TestUploadResponse:

    def test_upload_response_creation(self):
        response = UploadResponse(
            document_id="doc-123",
            status="RECEIVED",
            message="Document received"
        )

        assert response.document_id == "doc-123"
        assert response.status == "RECEIVED"
        assert response.message == "Document received"


class TestDocumentStatusResponse:

    def test_document_status_response_creation(self):
        response = DocumentStatusResponse(
            document_id="doc-123",
            status="READY",
            pdf_type="DIGITAL",
            confidence=0.95,
            error_message=None,
            created_at="2026-01-19T00:00:00Z",
            updated_at="2026-01-19T01:00:00Z"
        )

        assert response.document_id == "doc-123"
        assert response.status == "READY"
        assert response.confidence == 0.95

    def test_document_status_response_with_optional_fields_none(self):
        response = DocumentStatusResponse(
            document_id="doc-123",
            status="RECEIVED",
            pdf_type=None,
            confidence=None,
            error_message=None,
            created_at="2026-01-19T00:00:00Z",
            updated_at="2026-01-19T00:00:00Z"
        )

        assert response.pdf_type is None
        assert response.confidence is None


class TestGetDocumentRepository:

    @pytest.mark.asyncio
    @patch("irpf_processor.presentation.api.routes.documents.get_database")
    @patch("irpf_processor.presentation.api.routes.documents.MongoDocumentRepository")
    async def test_creates_repository_with_database(self, mock_repo, mock_get_db):
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_repo_instance = MagicMock()
        mock_repo.return_value = mock_repo_instance

        result = await get_document_repository()

        mock_get_db.assert_called_once()
        mock_repo.assert_called_once_with(mock_db)
        assert result == mock_repo_instance


class TestGetStorageServiceDependency:

    @pytest.mark.asyncio
    @patch("irpf_processor.presentation.api.routes.documents.get_storage_service")
    async def test_creates_storage_service(self, mock_storage_factory):
        mock_storage_instance = MagicMock()
        mock_storage_factory.return_value = mock_storage_instance

        result = await get_storage_service_dependency()

        mock_storage_factory.assert_called_once()


class TestUploadDocument:

    @pytest.mark.asyncio
    async def test_rejects_non_pdf_file(self):
        mock_file = MagicMock()
        mock_file.filename = "document.txt"

        mock_repo = MagicMock()
        mock_storage = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                tenant_id="tenant-456",
                file=mock_file,
                doc_repo=mock_repo,
                storage=mock_storage
            )

        assert exc_info.value.status_code == 400
        assert "Only PDF files are allowed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_rejects_empty_file(self):
        mock_file = MagicMock()
        mock_file.filename = "document.pdf"
        mock_file.read = AsyncMock(return_value=b"")

        mock_repo = MagicMock()
        mock_storage = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                tenant_id="tenant-456",
                file=mock_file,
                doc_repo=mock_repo,
                storage=mock_storage
            )

        assert exc_info.value.status_code == 400
        assert "Empty file" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("irpf_processor.presentation.api.routes.documents.route_document")
    @patch("irpf_processor.presentation.api.routes.documents.record_document_upload")
    @patch("irpf_processor.presentation.api.routes.documents.Document")
    async def test_returns_existing_document_if_duplicate(
        self, mock_document_class, mock_record, mock_route
    ):
        mock_file = MagicMock()
        mock_file.filename = "document.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"PDF content")

        mock_existing = MagicMock()
        mock_existing.document_id = "existing-doc"
        mock_existing.status.value = "READY"

        mock_repo = MagicMock()
        mock_repo.find_by_sha256 = AsyncMock(return_value=mock_existing)

        mock_storage = MagicMock()

        mock_document_class.calculate_sha256.return_value = "hash123"

        result = await upload_document(
            tenant_id="tenant-456",
            file=mock_file,
            doc_repo=mock_repo,
            storage=mock_storage
        )

        assert result.document_id == "existing-doc"
        assert result.message == "Document already exists"


class TestGetDocumentStatus:

    @pytest.mark.asyncio
    async def test_returns_document_status(self):
        mock_document = MagicMock()
        mock_document.document_id = "doc-123"
        mock_document.status = DocumentStatus.READY
        mock_document.pdf_type = PdfType.DIGITAL
        mock_document.confidence = 0.95
        mock_document.error_message = None
        mock_document.created_at = datetime(2026, 1, 19, tzinfo=timezone.utc)
        mock_document.updated_at = datetime(2026, 1, 19, 1, 0, tzinfo=timezone.utc)

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        result = await get_document_status(
            document_id="doc-123",
            tenant_id="tenant-456",
            doc_repo=mock_repo
        )

        assert result.document_id == "doc-123"
        assert result.status == "READY"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_raises_404_when_document_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_document_status(
                document_id="nonexistent",
                tenant_id="tenant-456",
                doc_repo=mock_repo
            )

        assert exc_info.value.status_code == 404
        assert "Document not found" in exc_info.value.detail


class TestGetDocumentResult:

    @pytest.mark.asyncio
    async def test_raises_404_when_document_not_found(self):
        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_document_result(
                document_id="nonexistent",
                tenant_id="tenant-456",
                doc_repo=mock_repo
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_409_when_document_not_ready(self):
        mock_document = MagicMock()
        mock_document.status = DocumentStatus.ROUTED

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        with pytest.raises(HTTPException) as exc_info:
            await get_document_result(
                document_id="doc-123",
                tenant_id="tenant-456",
                doc_repo=mock_repo
            )

        assert exc_info.value.status_code == 409
        assert "not ready" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("irpf_processor.presentation.api.routes.documents.get_database")
    async def test_returns_extraction_result(self, mock_get_db):
        mock_document = MagicMock()
        mock_document.status = DocumentStatus.READY

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(return_value={
            "_id": "mongo-id",
            "document_id": "doc-123",
            "data": {"taxpayer": {"cpf": "12345678900"}}
        })
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        result = await get_document_result(
            document_id="doc-123",
            tenant_id="tenant-456",
            doc_repo=mock_repo
        )

        assert "_id" not in result
        assert result["document_id"] == "doc-123"

    @pytest.mark.asyncio
    @patch("irpf_processor.presentation.api.routes.documents.get_database")
    async def test_raises_404_when_extraction_not_found(self, mock_get_db):
        mock_document = MagicMock()
        mock_document.status = DocumentStatus.READY

        mock_repo = MagicMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_document)

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_db.__getitem__.return_value = mock_collection
        mock_get_db.return_value = mock_db

        with pytest.raises(HTTPException) as exc_info:
            await get_document_result(
                document_id="doc-123",
                tenant_id="tenant-456",
                doc_repo=mock_repo
            )

        assert exc_info.value.status_code == 404
        assert "Extraction result not found" in exc_info.value.detail


class TestRouter:

    def test_router_has_correct_prefix(self):
        from irpf_processor.presentation.api.routes.documents import router
        assert router.prefix == "/v1/documents"

    def test_router_has_correct_tags(self):
        from irpf_processor.presentation.api.routes.documents import router
        assert "Documents" in router.tags
