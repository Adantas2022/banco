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
    app_name: str = "document-extraction-service"
    app_env: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    debug: bool = False

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db: str = "irpf_processor"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_ttl: int = 3600
    cache_version: str = "v2"

    # Storage
    storage_type: Literal["minio", "gcs"] = "minio"

    # MinIO (S3)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "documents"
    minio_secure: bool = False

    # GCS (Google Cloud Storage)
    gcp_bucket: str = "irpf-documents"
    gcp_credentials_path: str = ""
    gcp_auth_type: Literal["adc", "service_account", "anonymous"] = "adc"
    gcp_emulator_endpoint: str = "http://localhost:4443"

    # OCR
    ocr_engine: Literal["tesseract", "docling", "documentai"] = "tesseract"

    # ── Azure OpenAI ──────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""
    azure_openai_deployment: str = ""
    azure_openai_deployment_fallback: str = ""
    azure_openai_max_tokens: int = 32768

    # LLM parameters
    llm_max_input_chars: int = 45000
    llm_max_output_tokens: int = 8000
    llm_temperature: float = 0.0
    llm_top_p: float = 1.0
    llm_timeout_seconds: int = 90

    # API / Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_upload_mb: int = 50
    correlation_id_header: str = "X-Correlation-ID"
    extraction_timeout: int = 120

    # PDF
    pdf_dpi: int = 200

    # Security — API keys (comma-separated), rate limiting
    api_keys: str = ""
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 10
    rate_limit_period: str = "minute"

    # Workers
    dramatiq_processes: int = 2
    dramatiq_threads: int = 4

    # Extraction
    confidence_threshold: float = 0.6
    max_retry_attempts: int = 3
    
    # Testing/Development flags
    skip_duplicate_check: bool = False  # Set to True to always reprocess documents (ignores SHA256 cache)

    # Tracing (OpenTelemetry)
    otel_enabled: bool = True
    otel_service_name: str = "irpf-processor"
    otel_exporter_endpoint: str = "http://jaeger:4317"
    otel_sample_rate: float = 1.0

    # Observability
    log_format: str = "color"
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def valid_api_keys(self) -> set[str]:
        if not self.api_keys:
            return set()
        return {key.strip() for key in self.api_keys.split(",") if key.strip()}

    @property
    def requires_auth(self) -> bool:
        return len(self.valid_api_keys) > 0


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada das configurações."""
    return Settings()
