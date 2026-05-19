import pytest
from unittest.mock import patch, MagicMock

from irpf_processor.infrastructure.storage import (
    get_storage_service,
    extract_storage_key,
    MinioStorageService,
    GCSStorageService,
)


class TestGetStorageService:

    def test_returns_minio_service_by_default(self):
        mock_settings = MagicMock()
        mock_settings.storage_type = "minio"
        mock_settings.minio_endpoint = "localhost:9000"
        mock_settings.minio_access_key = "minioadmin"
        mock_settings.minio_secret_key = "minioadmin"
        mock_settings.minio_bucket = "documents"
        mock_settings.minio_secure = False

        with patch("irpf_processor.infrastructure.storage.get_settings", return_value=mock_settings):
            with patch("irpf_processor.infrastructure.storage.minio_storage.get_settings", return_value=mock_settings):
                with patch("irpf_processor.infrastructure.storage.minio_storage.boto3.client"):
                    service = get_storage_service()

                    assert isinstance(service, MinioStorageService)

    def test_returns_gcs_service_when_configured(self):
        mock_settings = MagicMock()
        mock_settings.storage_type = "gcs"
        mock_settings.gcp_bucket = "test-bucket"
        mock_settings.gcp_credentials_path = ""
        mock_settings.gcp_auth_type = "adc"

        with patch("irpf_processor.infrastructure.storage.get_settings", return_value=mock_settings):
            with patch("irpf_processor.infrastructure.storage.gcs_storage.get_settings", return_value=mock_settings):
                with patch("irpf_processor.infrastructure.storage.gcs_storage.storage.Client"):
                    service = get_storage_service()

                    assert isinstance(service, GCSStorageService)


class TestExtractStorageKey:

    def test_extracts_key_from_s3_uri(self):
        uri = "s3://documents/tenant-123/doc-456/file.pdf"

        result = extract_storage_key(uri)

        assert result == "tenant-123/doc-456/file.pdf"

    def test_extracts_key_from_gs_uri(self):
        uri = "gs://my-bucket/tenant-123/doc-456/file.pdf"

        result = extract_storage_key(uri)

        assert result == "tenant-123/doc-456/file.pdf"

    def test_returns_original_if_no_scheme(self):
        uri = "tenant-123/doc-456/file.pdf"

        result = extract_storage_key(uri)

        assert result == "tenant-123/doc-456/file.pdf"

    def test_handles_empty_key(self):
        uri = "s3://documents"

        result = extract_storage_key(uri)

        assert result == ""

    def test_handles_bucket_only_with_slash(self):
        uri = "gs://bucket/"

        result = extract_storage_key(uri)

        assert result == ""

    def test_handles_nested_paths(self):
        uri = "s3://bucket/a/b/c/d/e/file.pdf"

        result = extract_storage_key(uri)

        assert result == "a/b/c/d/e/file.pdf"
