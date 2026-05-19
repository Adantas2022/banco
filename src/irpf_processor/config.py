"""Configurações da aplicação usando Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ── Azure OpenAI Model Profiles ───────────────────────────────────────────────
# Maps profile name → env var suffix. Each profile reads from:
#   AZURE_OPENAI_ENDPOINT_<SUFFIX>, AZURE_OPENAI_API_KEY_<SUFFIX>,
#   AZURE_OPENAI_DEPLOYMENT_<SUFFIX>, AZURE_OPENAI_API_VERSION_<SUFFIX>,
#   AZURE_OPENAI_MAX_TOKENS_<SUFFIX>
# To add a new model, add an entry here + the corresponding fields in Settings.
AZURE_MODEL_PROFILES: dict[str, str] = {
    "gpt-4.1-mini": "gpt_4_1_mini",
    "gpt-5.4-mini": "gpt_5_4_mini",
}

# Fields resolved per profile (main field → profile-specific field)
_AZURE_PROFILE_FIELDS = [
    "azure_openai_endpoint",
    "azure_openai_api_key",
    "azure_openai_deployment",
    "azure_openai_api_version",
    "azure_openai_max_tokens",
]


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
    gcp_emulator_endpoint: str = ""

    # OCR
    ocr_engine: Literal["tesseract", "docling", "documentai"] = "tesseract"

    # ── Azure OpenAI ──────────────────────────────────────────────────────
    # Set AZURE_OPENAI_MODEL_PROFILE to a profile name (e.g. "gpt-4.1-mini")
    # to auto-fill endpoint, deployment, api_version, max_tokens from the profile.
    # Any explicit env var overrides the profile value.
    azure_openai_model_profile: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = ""
    azure_openai_deployment: str = ""
    azure_openai_deployment_fallback: str = ""
    azure_openai_max_tokens: int = 32768

    # Per-profile Azure OpenAI config (env var per model)
    azure_openai_endpoint_gpt_4_1_mini: str = ""
    azure_openai_api_key_gpt_4_1_mini: str = ""
    azure_openai_deployment_gpt_4_1_mini: str = ""
    azure_openai_api_version_gpt_4_1_mini: str = ""
    azure_openai_max_tokens_gpt_4_1_mini: int = 0

    azure_openai_endpoint_gpt_5_4_mini: str = ""
    azure_openai_api_key_gpt_5_4_mini: str = ""
    azure_openai_deployment_gpt_5_4_mini: str = ""
    azure_openai_api_version_gpt_5_4_mini: str = ""
    azure_openai_max_tokens_gpt_5_4_mini: int = 0

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

    # LLM Extraction — per-section toggles (env var = LLM_EXTRACTION_<SECTION_NAME>)
    llm_extraction_assets_declaration: bool = False
    llm_extraction_debts_and_encumbrances: bool = False
    llm_extraction_donations_made: bool = False
    llm_extraction_payments_made: bool = False
    llm_extraction_exempt_income: bool = False
    llm_extraction_exclusive_taxation_income: bool = False
    llm_extraction_equity_evolution_section: bool = False
    llm_extraction_income_from_legal_person_to_holder: bool = False
    llm_extraction_income_from_legal_person_to_dependents: bool = False
    llm_extraction_income_from_individual_to_holder: bool = False
    llm_extraction_income_from_individual_to_dependents: bool = False
    llm_extraction_income_from_legal_person_to_holder_with_suspended_requirements: bool = False
    llm_extraction_income_from_legal_person_to_dependents_with_suspended_requirements: bool = False
    llm_extraction_accumulated_income_from_legal_person_to_holder: bool = False
    llm_extraction_accumulated_income_from_legal_person_to_dependents: bool = False
    llm_extraction_taxpayer_identification: bool = False
    llm_extraction_receipt: bool = False
    llm_extraction_rural_activity_assets_in_brazil: bool = False
    llm_extraction_rural_activity_assets_abroad: bool = False
    llm_extraction_rural_activity_debts_in_brazil: bool = False
    llm_extraction_rural_activity_debts_abroad: bool = False
    llm_extraction_exploited_rural_properties_in_brazil: bool = False
    llm_extraction_exploited_rural_properties_abroad: bool = False
    llm_extraction_rural_income_and_expenditure_in_brazil: bool = False
    llm_extraction_rural_income_and_expenditure_abroad: bool = False
    llm_extraction_livestock_movement_in_brazil: bool = False
    llm_extraction_livestock_movement_abroad: bool = False
    llm_extraction_calculation_of_rural_results_in_brazil: bool = False
    llm_extraction_calculation_of_rural_results_abroad: bool = False

    # LLM Provider
    llm_max_images_per_call: int = 5
    
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

    @model_validator(mode="after")
    def _apply_model_profile(self) -> "Settings":
        """Fill blank Azure OpenAI fields from the selected model profile."""
        profile_name = self.azure_openai_model_profile
        if not profile_name:
            return self

        suffix = AZURE_MODEL_PROFILES.get(profile_name)
        if not suffix:
            raise ValueError(
                f"Unknown model profile '{profile_name}'. "
                f"Available: {list(AZURE_MODEL_PROFILES.keys())}"
            )

        for base_field in _AZURE_PROFILE_FIELDS:
            profile_field = f"{base_field}_{suffix}"
            profile_value = getattr(self, profile_field, None)
            if not profile_value:
                continue
            main_value = getattr(self, base_field)
            main_default = self.model_fields[base_field].default
            if main_value == main_default:
                object.__setattr__(self, base_field, profile_value)

        return self

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
