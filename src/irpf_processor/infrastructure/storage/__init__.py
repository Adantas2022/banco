"""Adaptadores de storage (MinIO/S3/GCS)."""

from irpf_processor.application.interfaces import IStorageService
from irpf_processor.config import get_settings

from .minio_storage import MinioStorageService

__all__ = ["MinioStorageService", "get_storage_service", "extract_storage_key"]


def get_storage_service() -> IStorageService:
    settings = get_settings()

    if settings.storage_type == "gcs":
        from .gcs_storage import GCSStorageService
        return GCSStorageService()

    return MinioStorageService()


def extract_storage_key(storage_uri: str) -> str:
    if storage_uri.startswith("gs://"):
        parts = storage_uri[5:].split("/", 1)
        return parts[1] if len(parts) > 1 else ""

    if storage_uri.startswith("s3://"):
        parts = storage_uri[5:].split("/", 1)
        return parts[1] if len(parts) > 1 else ""

    return storage_uri
