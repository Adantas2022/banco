import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

from irpf_processor.domain.entities.document import Document
from irpf_processor.domain.enums import DocumentStatus, PdfType
from irpf_processor.infrastructure.persistence.document_repository import MongoDocumentRepository


@pytest.fixture
def mock_database():
    db = MagicMock()
    collection = MagicMock()
    collection.insert_one = AsyncMock()
    collection.find_one = AsyncMock()
    collection.update_one = AsyncMock()
    collection.delete_one = AsyncMock()
    db.__getitem__ = MagicMock(return_value=collection)
    return db, collection


@pytest.fixture
def sample_document():
    return Document(
        document_id="doc-123",
        tenant_id="tenant-456",
        filename="test.pdf",
        content_type="application/pdf",
        storage_uri="s3://bucket/test.pdf",
        sha256="abc123hash",
        status=DocumentStatus.RECEIVED,
    )


@pytest.fixture
def sample_document_dict():
    now = datetime.now(timezone.utc)
    return {
        "document_id": "doc-123",
        "tenant_id": "tenant-456",
        "filename": "test.pdf",
        "content_type": "application/pdf",
        "storage_uri": "s3://bucket/test.pdf",
        "sha256": "abc123hash",
        "status": "RECEIVED",
        "pdf_type": None,
        "confidence": None,
        "error_message": None,
        "created_at": now,
        "updated_at": now,
    }


class TestMongoDocumentRepositoryInit:

    def test_initializes_with_database(self, mock_database):
        db, collection = mock_database
        repo = MongoDocumentRepository(db)

        assert repo._db == db
        assert repo._collection == collection
        db.__getitem__.assert_called_once_with("documents")


class TestMongoDocumentRepositoryCreate:

    @pytest.mark.asyncio
    async def test_creates_document(self, mock_database, sample_document):
        db, collection = mock_database
        repo = MongoDocumentRepository(db)

        await repo.create(sample_document)

        collection.insert_one.assert_called_once()
        call_args = collection.insert_one.call_args[0][0]
        assert call_args["document_id"] == "doc-123"
        assert call_args["tenant_id"] == "tenant-456"
        assert call_args["filename"] == "test.pdf"
        assert call_args["status"] == "RECEIVED"

    @pytest.mark.asyncio
    async def test_creates_document_with_pdf_type(self, mock_database):
        db, collection = mock_database
        repo = MongoDocumentRepository(db)

        doc = Document(
            document_id="doc-123",
            tenant_id="tenant-456",
            filename="test.pdf",
            content_type="application/pdf",
            storage_uri="s3://bucket/test.pdf",
            pdf_type=PdfType.DIGITAL,
        )

        await repo.create(doc)

        call_args = collection.insert_one.call_args[0][0]
        assert call_args["pdf_type"] == "DIGITAL"


class TestMongoDocumentRepositoryGetById:

    @pytest.mark.asyncio
    async def test_returns_document_when_found(self, mock_database, sample_document_dict):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=sample_document_dict)
        repo = MongoDocumentRepository(db)

        result = await repo.get_by_id("doc-123", "tenant-456")

        assert result is not None
        assert result.document_id == "doc-123"
        assert result.tenant_id == "tenant-456"
        collection.find_one.assert_called_once_with({
            "document_id": "doc-123",
            "tenant_id": "tenant-456",
        })

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_database):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=None)
        repo = MongoDocumentRepository(db)

        result = await repo.get_by_id("nonexistent", "tenant-456")

        assert result is None


class TestMongoDocumentRepositoryGetBySha256:

    @pytest.mark.asyncio
    async def test_returns_document_when_found(self, mock_database, sample_document_dict):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=sample_document_dict)
        repo = MongoDocumentRepository(db)

        result = await repo.get_by_sha256("abc123hash", "tenant-456")

        assert result is not None
        assert result.sha256 == "abc123hash"
        collection.find_one.assert_called_once_with({
            "tenant_id": "tenant-456",
            "sha256": "abc123hash",
        })

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, mock_database):
        db, collection = mock_database
        collection.find_one = AsyncMock(return_value=None)
        repo = MongoDocumentRepository(db)

        result = await repo.get_by_sha256("nonexistent", "tenant-456")

        assert result is None


class TestMongoDocumentRepositoryUpdate:

    @pytest.mark.asyncio
    async def test_updates_document(self, mock_database, sample_document):
        db, collection = mock_database
        repo = MongoDocumentRepository(db)

        sample_document.status = DocumentStatus.READY
        sample_document.confidence = 0.95

        await repo.update(sample_document)

        collection.update_one.assert_called_once()
        call_args = collection.update_one.call_args
        assert call_args[0][0] == {
            "document_id": "doc-123",
            "tenant_id": "tenant-456"
        }
        assert call_args[0][1]["$set"]["status"] == "READY"
        assert call_args[0][1]["$set"]["confidence"] == 0.95


class TestMongoDocumentRepositoryDelete:

    @pytest.mark.asyncio
    async def test_deletes_document(self, mock_database):
        db, collection = mock_database
        repo = MongoDocumentRepository(db)

        await repo.delete("doc-123", "tenant-456")

        collection.delete_one.assert_called_once_with({
            "document_id": "doc-123",
            "tenant_id": "tenant-456",
        })


class TestMongoDocumentRepositoryUpdateStatus:

    @pytest.mark.asyncio
    async def test_updates_status_only(self, mock_database):
        db, collection = mock_database
        mock_result = MagicMock()
        mock_result.modified_count = 1
        collection.update_one = AsyncMock(return_value=mock_result)
        repo = MongoDocumentRepository(db)

        result = await repo.update_status("doc-123", "tenant-456", DocumentStatus.READY)

        assert result is True
        call_args = collection.update_one.call_args
        assert call_args[0][1]["$set"]["status"] == "READY"
        assert "updated_at" in call_args[0][1]["$set"]

    @pytest.mark.asyncio
    async def test_updates_status_with_pdf_type(self, mock_database):
        db, collection = mock_database
        mock_result = MagicMock()
        mock_result.modified_count = 1
        collection.update_one = AsyncMock(return_value=mock_result)
        repo = MongoDocumentRepository(db)

        result = await repo.update_status(
            "doc-123", "tenant-456", DocumentStatus.ROUTED, pdf_type="DIGITAL"
        )

        assert result is True
        call_args = collection.update_one.call_args
        assert call_args[0][1]["$set"]["pdf_type"] == "DIGITAL"

    @pytest.mark.asyncio
    async def test_updates_status_with_confidence(self, mock_database):
        db, collection = mock_database
        mock_result = MagicMock()
        mock_result.modified_count = 1
        collection.update_one = AsyncMock(return_value=mock_result)
        repo = MongoDocumentRepository(db)

        result = await repo.update_status(
            "doc-123", "tenant-456", DocumentStatus.READY, confidence=0.92
        )

        assert result is True
        call_args = collection.update_one.call_args
        assert call_args[0][1]["$set"]["confidence"] == 0.92

    @pytest.mark.asyncio
    async def test_updates_status_with_error_message(self, mock_database):
        db, collection = mock_database
        mock_result = MagicMock()
        mock_result.modified_count = 1
        collection.update_one = AsyncMock(return_value=mock_result)
        repo = MongoDocumentRepository(db)

        result = await repo.update_status(
            "doc-123", "tenant-456", DocumentStatus.FAILED, error_message="Processing error"
        )

        assert result is True
        call_args = collection.update_one.call_args
        assert call_args[0][1]["$set"]["error_message"] == "Processing error"

    @pytest.mark.asyncio
    async def test_returns_false_when_not_modified(self, mock_database):
        db, collection = mock_database
        mock_result = MagicMock()
        mock_result.modified_count = 0
        collection.update_one = AsyncMock(return_value=mock_result)
        repo = MongoDocumentRepository(db)

        result = await repo.update_status("nonexistent", "tenant-456", DocumentStatus.READY)

        assert result is False


class TestMongoDocumentRepositoryListByTenant:

    @pytest.mark.asyncio
    async def test_lists_documents_for_tenant(self, mock_database, sample_document_dict):
        db, collection = mock_database

        async def async_iter():
            yield sample_document_dict

        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__ = lambda self: async_iter()

        collection.find.return_value = mock_cursor
        repo = MongoDocumentRepository(db)

        result = await repo.list_by_tenant("tenant-456")

        assert len(result) == 1
        assert result[0].tenant_id == "tenant-456"
        collection.find.assert_called_once_with({"tenant_id": "tenant-456"})

    @pytest.mark.asyncio
    async def test_lists_documents_with_status_filter(self, mock_database, sample_document_dict):
        db, collection = mock_database

        async def async_iter():
            yield sample_document_dict

        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__ = lambda self: async_iter()

        collection.find.return_value = mock_cursor
        repo = MongoDocumentRepository(db)

        result = await repo.list_by_tenant("tenant-456", status=DocumentStatus.RECEIVED)

        collection.find.assert_called_once_with({
            "tenant_id": "tenant-456",
            "status": "RECEIVED"
        })

    @pytest.mark.asyncio
    async def test_respects_limit_and_skip(self, mock_database):
        db, collection = mock_database

        async def async_iter():
            return
            yield

        mock_cursor = MagicMock()
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.__aiter__ = lambda self: async_iter()

        collection.find.return_value = mock_cursor
        repo = MongoDocumentRepository(db)

        await repo.list_by_tenant("tenant-456", limit=50, skip=10)

        mock_cursor.skip.assert_called_once_with(10)
        mock_cursor.limit.assert_called_once_with(50)


class TestMongoDocumentRepositoryToEntity:

    def test_converts_dict_to_document(self, mock_database, sample_document_dict):
        db, _ = mock_database
        repo = MongoDocumentRepository(db)

        result = repo._to_entity(sample_document_dict)

        assert isinstance(result, Document)
        assert result.document_id == "doc-123"
        assert result.tenant_id == "tenant-456"
        assert result.status == DocumentStatus.RECEIVED
        assert result.pdf_type is None

    def test_converts_dict_with_pdf_type(self, mock_database, sample_document_dict):
        db, _ = mock_database
        repo = MongoDocumentRepository(db)
        sample_document_dict["pdf_type"] = "DIGITAL"

        result = repo._to_entity(sample_document_dict)

        assert result.pdf_type == PdfType.DIGITAL

    def test_converts_dict_with_confidence(self, mock_database, sample_document_dict):
        db, _ = mock_database
        repo = MongoDocumentRepository(db)
        sample_document_dict["confidence"] = 0.95

        result = repo._to_entity(sample_document_dict)

        assert result.confidence == 0.95
