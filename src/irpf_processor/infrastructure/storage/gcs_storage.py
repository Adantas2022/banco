"""Implementação do serviço de storage usando Google Cloud Storage."""

from __future__ import annotations

import asyncio
import time
from functools import partial
from datetime import timedelta
from typing import TYPE_CHECKING

from google.cloud import storage
from google.cloud.exceptions import NotFound
from google.auth.credentials import AnonymousCredentials

from irpf_processor.application.interfaces import IStorageService
from irpf_processor.config import get_settings
from irpf_processor.shared.metrics import (
    STORAGE_OPERATIONS_TOTAL,
    STORAGE_OPERATION_DURATION_SECONDS,
)

if TYPE_CHECKING:
    from google.oauth2 import service_account


class GCSStorageService:
    """Serviço de armazenamento usando Google Cloud Storage."""

    def __init__(self) -> None:
        settings = get_settings()

        if settings.gcp_emulator_endpoint:
            self._client = storage.Client(
                credentials=AnonymousCredentials(),
                project="local-project",
            )
            self._client._http.mount("http://", self._client._http.adapters["https://"])
            self._client._base_connection.API_BASE_URL = settings.gcp_emulator_endpoint
        elif settings.gcp_auth_type == "service_account" and settings.gcp_credentials_path:
            from google.oauth2 import service_account as sa_module
            credentials = sa_module.Credentials.from_service_account_file(
                settings.gcp_credentials_path
            )
            self._client = storage.Client(credentials=credentials)
        elif settings.gcp_auth_type == "anonymous":
            self._client = storage.Client(
                credentials=AnonymousCredentials(),
                project="local-project",
            )
        else:
            self._client = storage.Client()

        self._bucket_name = settings.gcp_bucket
        self._bucket = self._client.bucket(self._bucket_name)

    async def upload(
        self,
        content: bytes,
        key: str,
        content_type: str,
    ) -> str:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
        status = "success"

        try:
            await loop.run_in_executor(
                None,
                partial(
                    self._upload_blob,
                    content=content,
                    key=key,
                    content_type=content_type,
                ),
            )
            return f"gs://{self._bucket_name}/{key}"
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="upload", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="upload").observe(duration)

    def _upload_blob(self, content: bytes, key: str, content_type: str) -> None:
        blob = self._bucket.blob(key)
        blob.upload_from_string(content, content_type=content_type)

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
        status = "success"

        try:
            result = await loop.run_in_executor(
                None,
                partial(self._download_blob, key=key),
            )
            return result
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="download", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="download").observe(duration)

    def _download_blob(self, key: str) -> bytes:
        blob = self._bucket.blob(key)
        return blob.download_as_bytes()

    def download_sync(self, key: str) -> bytes:
        start_time = time.perf_counter()
        status = "success"

        try:
            blob = self._bucket.blob(key)
            return blob.download_as_bytes()
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="download_sync", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="download_sync").observe(duration)

    async def exists(self, key: str) -> bool:
        loop = asyncio.get_event_loop()

        try:
            result = await loop.run_in_executor(
                None,
                partial(self._blob_exists, key=key),
            )
            return result
        except NotFound:
            return False

    def _blob_exists(self, key: str) -> bool:
        blob = self._bucket.blob(key)
        return blob.exists()

    async def delete(self, key: str) -> None:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
        status = "success"

        try:
            await loop.run_in_executor(
                None,
                partial(self._delete_blob, key=key),
            )
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="delete", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="delete").observe(duration)

    def _delete_blob(self, key: str) -> None:
        blob = self._bucket.blob(key)
        blob.delete()

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        loop = asyncio.get_event_loop()

        url = await loop.run_in_executor(
            None,
            partial(
                self._generate_signed_url,
                key=key,
                expires_in=expires_in,
            ),
        )

        return url

    def _generate_signed_url(self, key: str, expires_in: int) -> str:
        blob = self._bucket.blob(key)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expires_in),
            method="GET",
        )
        return url
