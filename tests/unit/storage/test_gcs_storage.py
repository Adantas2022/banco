import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import timedelta

from irpf_processor.infrastructure.storage.gcs_storage import GCSStorageService


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.gcp_bucket = "test-bucket"
    settings.gcp_credentials_path = ""
    settings.gcp_auth_type = "adc"
    return settings


@pytest.fixture
def mock_settings_service_account():
    settings = MagicMock()
    settings.gcp_bucket = "test-bucket"
    settings.gcp_credentials_path = "/path/to/credentials.json"
    settings.gcp_auth_type = "service_account"
    return settings


@pytest.fixture
def mock_gcs_client():
    return MagicMock()


@pytest.fixture
def mock_bucket():
    return MagicMock()


@pytest.fixture
def storage_service(mock_settings, mock_gcs_client, mock_bucket):
    with patch("irpf_processor.infrastructure.storage.gcs_storage.get_settings", return_value=mock_settings):
        with patch("irpf_processor.infrastructure.storage.gcs_storage.storage.Client", return_value=mock_gcs_client):
            mock_gcs_client.bucket.return_value = mock_bucket
            service = GCSStorageService()
            service._client = mock_gcs_client
            service._bucket = mock_bucket
            service._bucket_name = "test-bucket"
            return service


class TestGCSStorageServiceInit:

    def test_initializes_with_adc_settings(self, mock_settings):
        with patch("irpf_processor.infrastructure.storage.gcs_storage.get_settings", return_value=mock_settings):
            with patch("irpf_processor.infrastructure.storage.gcs_storage.storage.Client") as mock_client:
                mock_bucket = MagicMock()
                mock_client.return_value.bucket.return_value = mock_bucket

                service = GCSStorageService()

                mock_client.assert_called_once_with()
                assert service._bucket_name == "test-bucket"

    def test_initializes_with_service_account(self, mock_settings_service_account):
        with patch("irpf_processor.infrastructure.storage.gcs_storage.get_settings", return_value=mock_settings_service_account):
            with patch("irpf_processor.infrastructure.storage.gcs_storage.storage.Client") as mock_client:
                with patch("irpf_processor.infrastructure.storage.gcs_storage.service_account.Credentials.from_service_account_file") as mock_creds:
                    mock_credentials = MagicMock()
                    mock_creds.return_value = mock_credentials
                    mock_bucket = MagicMock()
                    mock_client.return_value.bucket.return_value = mock_bucket

                    service = GCSStorageService()

                    mock_creds.assert_called_once_with("/path/to/credentials.json")
                    mock_client.assert_called_once_with(credentials=mock_credentials)


class TestGCSStorageServiceUpload:

    @pytest.mark.asyncio
    async def test_uploads_content(self, storage_service, mock_bucket):
        content = b"PDF content here"
        key = "tenant/doc.pdf"
        content_type = "application/pdf"
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = await storage_service.upload(content, key, content_type)

        assert result == "gs://test-bucket/tenant/doc.pdf"
        mock_bucket.blob.assert_called_with(key)
        mock_blob.upload_from_string.assert_called_once_with(content, content_type=content_type)

    @pytest.mark.asyncio
    async def test_returns_gs_uri(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        result = await storage_service.upload(b"content", "path/file.pdf", "application/pdf")

        assert result.startswith("gs://")
        assert "test-bucket" in result
        assert "path/file.pdf" in result


class TestGCSStorageServiceDownload:

    @pytest.mark.asyncio
    async def test_downloads_content(self, storage_service, mock_bucket):
        expected_content = b"Downloaded content"
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = expected_content
        mock_bucket.blob.return_value = mock_blob

        result = await storage_service.download("path/file.pdf")

        assert result == expected_content

    @pytest.mark.asyncio
    async def test_raises_on_error(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.side_effect = Exception("Not found")
        mock_bucket.blob.return_value = mock_blob

        with pytest.raises(Exception, match="Not found"):
            await storage_service.download("nonexistent.pdf")


class TestGCSStorageServiceDownloadSync:

    def test_downloads_content_synchronously(self, storage_service, mock_bucket):
        expected_content = b"Sync downloaded content"
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = expected_content
        mock_bucket.blob.return_value = mock_blob

        result = storage_service.download_sync("path/file.pdf")

        assert result == expected_content
        mock_bucket.blob.assert_called_with("path/file.pdf")

    def test_raises_on_error(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.side_effect = Exception("Storage error")
        mock_bucket.blob.return_value = mock_blob

        with pytest.raises(Exception, match="Storage error"):
            storage_service.download_sync("nonexistent.pdf")


class TestGCSStorageServiceExists:

    @pytest.mark.asyncio
    async def test_returns_true_when_file_exists(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_blob.exists.return_value = True
        mock_bucket.blob.return_value = mock_blob

        result = await storage_service.exists("path/file.pdf")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_file_not_found(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob

        result = await storage_service.exists("nonexistent.pdf")

        assert result is False


class TestGCSStorageServiceDelete:

    @pytest.mark.asyncio
    async def test_deletes_file(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob

        await storage_service.delete("path/file.pdf")

        mock_blob.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_on_error(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_blob.delete.side_effect = Exception("Delete failed")
        mock_bucket.blob.return_value = mock_blob

        with pytest.raises(Exception, match="Delete failed"):
            await storage_service.delete("path/file.pdf")


class TestGCSStorageServiceGetUrl:

    @pytest.mark.asyncio
    async def test_generates_signed_url(self, storage_service, mock_bucket):
        expected_url = "https://storage.googleapis.com/test-bucket/path/file.pdf?signature=abc123"
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = expected_url
        mock_bucket.blob.return_value = mock_blob

        result = await storage_service.get_url("path/file.pdf")

        assert result == expected_url

    @pytest.mark.asyncio
    async def test_respects_custom_expiration(self, storage_service, mock_bucket):
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://example.com/url"
        mock_bucket.blob.return_value = mock_blob

        await storage_service.get_url("path/file.pdf", expires_in=7200)

        mock_blob.generate_signed_url.assert_called_once_with(
            version="v4",
            expiration=timedelta(seconds=7200),
            method="GET",
        )


class TestGCSStorageServiceIntegration:

    @pytest.mark.asyncio
    async def test_upload_and_download_workflow(self, storage_service, mock_bucket):
        content = b"Test PDF content for integration"

        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = content
        mock_bucket.blob.return_value = mock_blob

        upload_result = await storage_service.upload(content, "tenant/test.pdf", "application/pdf")

        assert upload_result == "gs://test-bucket/tenant/test.pdf"

        download_result = await storage_service.download("tenant/test.pdf")

        assert download_result == content
