"""Implementação do serviço de storage usando MinIO/S3."""

import asyncio
import time
from functools import partial
from io import BytesIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from irpf_processor.application.interfaces import IStorageService
from irpf_processor.config import get_settings
from irpf_processor.shared.metrics import (
    STORAGE_OPERATIONS_TOTAL,
    STORAGE_OPERATION_DURATION_SECONDS,
)


class MinioStorageService:
    """Serviço de armazenamento usando MinIO (S3-compatible)."""

    def __init__(self) -> None:
        settings = get_settings()

        self._client = boto3.client(
            "s3",
            endpoint_url=f"http{'s' if settings.minio_secure else ''}://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = settings.minio_bucket

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
                    self._client.put_object,
                    Bucket=self._bucket,
                    Key=key,
                    Body=BytesIO(content),
                    ContentType=content_type,
                ),
            )
            return f"s3://{self._bucket}/{key}"
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="upload", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="upload").observe(duration)

    async def download(self, key: str) -> bytes:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
        status = "success"

        try:
            response = await loop.run_in_executor(
                None,
                partial(
                    self._client.get_object,
                    Bucket=self._bucket,
                    Key=key,
                ),
            )
            return response["Body"].read()
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="download", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="download").observe(duration)

    def download_sync(self, key: str) -> bytes:
        start_time = time.perf_counter()
        status = "success"

        try:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            return response["Body"].read()
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="download_sync", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="download_sync").observe(duration)

    async def exists(self, key: str) -> bool:
        """Verifica se arquivo existe no MinIO."""
        loop = asyncio.get_event_loop()

        try:
            await loop.run_in_executor(
                None,
                partial(
                    self._client.head_object,
                    Bucket=self._bucket,
                    Key=key,
                ),
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    async def delete(self, key: str) -> None:
        loop = asyncio.get_event_loop()
        start_time = time.perf_counter()
        status = "success"

        try:
            await loop.run_in_executor(
                None,
                partial(
                    self._client.delete_object,
                    Bucket=self._bucket,
                    Key=key,
                ),
            )
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            STORAGE_OPERATIONS_TOTAL.labels(operation="delete", status=status).inc()
            STORAGE_OPERATION_DURATION_SECONDS.labels(operation="delete").observe(duration)

    async def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Gera URL pré-assinada para download."""
        loop = asyncio.get_event_loop()

        url = await loop.run_in_executor(
            None,
            partial(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            ),
        )

        return url
