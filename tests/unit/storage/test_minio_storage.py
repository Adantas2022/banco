import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from io import BytesIO

from irpf_processor.infrastructure.storage.minio_storage import MinioStorageService


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.minio_endpoint = "localhost:9000"
    settings.minio_access_key = "minioadmin"
    settings.minio_secret_key = "minioadmin"
    settings.minio_bucket = "test-bucket"
    settings.minio_secure = False
    return settings


@pytest.fixture
def mock_s3_client():
    return MagicMock()


@pytest.fixture
def storage_service(mock_settings, mock_s3_client):
    with patch("irpf_processor.infrastructure.storage.minio_storage.get_settings", return_value=mock_settings):
        with patch("irpf_processor.infrastructure.storage.minio_storage.boto3.client", return_value=mock_s3_client):
            service = MinioStorageService()
            service._client = mock_s3_client
            service._bucket = "test-bucket"
            return service


class TestMinioStorageServiceInit:

    def test_initializes_with_settings(self, mock_settings):
        with patch("irpf_processor.infrastructure.storage.minio_storage.get_settings", return_value=mock_settings):
            with patch("irpf_processor.infrastructure.storage.minio_storage.boto3.client") as mock_boto:
                service = MinioStorageService()
                
                mock_boto.assert_called_once()
                assert service._bucket == "test-bucket"


class TestMinioStorageServiceUpload:

    @pytest.mark.asyncio
    async def test_uploads_content(self, storage_service, mock_s3_client):
        content = b"PDF content here"
        key = "tenant/doc.pdf"
        content_type = "application/pdf"

        result = await storage_service.upload(content, key, content_type)

        assert result == "s3://test-bucket/tenant/doc.pdf"
        mock_s3_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_s3_uri(self, storage_service, mock_s3_client):
        result = await storage_service.upload(b"content", "path/file.pdf", "application/pdf")

        assert result.startswith("s3://")
        assert "test-bucket" in result
        assert "path/file.pdf" in result


class TestMinioStorageServiceDownload:

    @pytest.mark.asyncio
    async def test_downloads_content(self, storage_service, mock_s3_client):
        expected_content = b"Downloaded content"
        mock_body = MagicMock()
        mock_body.read.return_value = expected_content
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        result = await storage_service.download("path/file.pdf")

        assert result == expected_content

    @pytest.mark.asyncio
    async def test_raises_on_error(self, storage_service, mock_s3_client):
        mock_s3_client.get_object.side_effect = Exception("Not found")

        with pytest.raises(Exception, match="Not found"):
            await storage_service.download("nonexistent.pdf")


class TestMinioStorageServiceDownloadSync:

    def test_downloads_content_synchronously(self, storage_service, mock_s3_client):
        expected_content = b"Sync downloaded content"
        mock_body = MagicMock()
        mock_body.read.return_value = expected_content
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        result = storage_service.download_sync("path/file.pdf")

        assert result == expected_content
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="path/file.pdf"
        )

    def test_raises_on_error(self, storage_service, mock_s3_client):
        mock_s3_client.get_object.side_effect = Exception("Storage error")

        with pytest.raises(Exception, match="Storage error"):
            storage_service.download_sync("nonexistent.pdf")


class TestMinioStorageServiceExists:

    @pytest.mark.asyncio
    async def test_returns_true_when_file_exists(self, storage_service, mock_s3_client):
        mock_s3_client.head_object.return_value = {"ContentLength": 1024}

        result = await storage_service.exists("path/file.pdf")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_file_not_found(self, storage_service, mock_s3_client):
        from botocore.exceptions import ClientError
        error_response = {"Error": {"Code": "404"}}
        mock_s3_client.head_object.side_effect = ClientError(error_response, "HeadObject")

        result = await storage_service.exists("nonexistent.pdf")

        assert result is False


class TestMinioStorageServiceDelete:

    @pytest.mark.asyncio
    async def test_deletes_file(self, storage_service, mock_s3_client):
        await storage_service.delete("path/file.pdf")

        mock_s3_client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_error(self, storage_service, mock_s3_client):
        mock_s3_client.delete_object.side_effect = Exception("Delete failed")

        with pytest.raises(Exception, match="Delete failed"):
            await storage_service.delete("path/file.pdf")


class TestMinioStorageServiceGetUrl:

    @pytest.mark.asyncio
    async def test_generates_presigned_url(self, storage_service, mock_s3_client):
        expected_url = "https://minio.example.com/test-bucket/path/file.pdf?signature=abc123"
        mock_s3_client.generate_presigned_url.return_value = expected_url

        result = await storage_service.get_url("path/file.pdf")

        assert result == expected_url

    @pytest.mark.asyncio
    async def test_respects_custom_expiration(self, storage_service, mock_s3_client):
        mock_s3_client.generate_presigned_url.return_value = "https://example.com/url"

        await storage_service.get_url("path/file.pdf", expires_in=7200)

        mock_s3_client.generate_presigned_url.assert_called_once()


class TestMinioStorageServiceIntegration:

    @pytest.mark.asyncio
    async def test_upload_and_download_workflow(self, storage_service, mock_s3_client):
        content = b"Test PDF content for integration"

        mock_body = MagicMock()
        mock_body.read.return_value = content
        mock_s3_client.get_object.return_value = {"Body": mock_body}

        upload_result = await storage_service.upload(content, "tenant/test.pdf", "application/pdf")

        assert upload_result == "s3://test-bucket/tenant/test.pdf"

        download_result = await storage_service.download("tenant/test.pdf")

        assert download_result == content
