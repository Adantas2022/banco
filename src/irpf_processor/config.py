"""Configurações da aplicação usando Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas de variáveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "irpf_processor"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO (S3)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "documents"
    minio_secure: bool = False

    # OCR
    ocr_engine: Literal["tesseract", "docling"] = "tesseract"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    correlation_id_header: str = "X-Correlation-ID"

    # Workers
    dramatiq_processes: int = 2
    dramatiq_threads: int = 4

    # Extraction
    confidence_threshold: float = 0.6
    max_retry_attempts: int = 3

    # Tracing (OpenTelemetry)
    otel_enabled: bool = True
    otel_service_name: str = "irpf-processor"
    otel_exporter_endpoint: str = "http://jaeger:4317"
    otel_sample_rate: float = 1.0

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
