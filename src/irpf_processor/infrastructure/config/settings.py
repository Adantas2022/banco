from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields from .env
    )

    app_name: str = "document-extraction-service"
    app_env: str = "development"
    debug: bool = False
    log_level: str = "INFO"

    # ── Azure OpenAI ──────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2025-01-01-preview"
    azure_openai_deployment: str = ""
    azure_openai_deployment_fallback: str = ""

    # ── Doc-Extractor Settings ────────────────────────────────────────────
    de_azure_openai_api_version: str = "2024-12-01-preview"

    # LLM parameters
    llm_max_input_chars: int = 45000
    llm_max_output_tokens: int = 8000
    llm_temperature: float = 0.0
    llm_top_p: float = 1.0
    llm_timeout_seconds: int = 90

    # Server / limits
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_upload_mb: int = 50
    pdf_dpi: int = 200
    extraction_timeout: int = 120

    # Security — API keys (comma-separated), rate limiting
    api_keys: str = ""
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 10
    rate_limit_period: str = "minute"

    # Redis cache
    redis_enabled: bool = False
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    redis_ttl: int = 3600
    cache_version: str = "v2"

    # Observability
    log_format: str = "color"
    langfuse_enabled: bool = False
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

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
    return Settings()