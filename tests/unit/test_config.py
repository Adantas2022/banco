import pytest
from unittest.mock import patch
import os

from irpf_processor.config import Settings, get_settings


class TestSettings:

    def test_settings_has_app_env(self):
        settings = Settings()

        assert hasattr(settings, "app_env")
        assert settings.app_env in ["development", "staging", "production"]

    def test_settings_has_log_level(self):
        settings = Settings()

        assert hasattr(settings, "log_level")
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    def test_settings_has_mongo_config(self):
        settings = Settings()

        assert hasattr(settings, "mongo_uri")
        assert hasattr(settings, "mongo_db")
        assert settings.mongo_uri.startswith("mongodb://")

    def test_settings_has_redis_config(self):
        settings = Settings()

        assert hasattr(settings, "redis_url")
        assert settings.redis_url.startswith("redis://")

    def test_settings_has_minio_config(self):
        settings = Settings()

        assert hasattr(settings, "minio_endpoint")
        assert hasattr(settings, "minio_access_key")
        assert hasattr(settings, "minio_secret_key")
        assert hasattr(settings, "minio_bucket")
        assert hasattr(settings, "minio_secure")

    def test_ocr_defaults(self):
        settings = Settings()

        assert settings.ocr_engine == "tesseract"

    def test_ocr_engine_documentai(self):
        settings = Settings(ocr_engine="documentai")
        assert settings.ocr_engine == "documentai"

    def test_api_defaults(self):
        settings = Settings()

        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.correlation_id_header == "X-Correlation-ID"

    def test_worker_defaults(self):
        settings = Settings()

        assert settings.dramatiq_processes == 2
        assert settings.dramatiq_threads == 4

    def test_extraction_defaults(self):
        settings = Settings()

        assert settings.confidence_threshold == 0.6
        assert settings.max_retry_attempts == 3

    def test_is_development_true(self):
        settings = Settings(app_env="development")

        assert settings.is_development is True
        assert settings.is_production is False

    def test_is_production_true(self):
        settings = Settings(app_env="production")

        assert settings.is_production is True
        assert settings.is_development is False

    def test_is_staging(self):
        settings = Settings(app_env="staging")

        assert settings.is_development is False
        assert settings.is_production is False

    def test_custom_log_level(self):
        settings = Settings(log_level="DEBUG")

        assert settings.log_level == "DEBUG"

    def test_custom_mongo_settings(self):
        settings = Settings(
            mongo_uri="mongodb://custom:27017",
            mongo_db="custom_db"
        )

        assert settings.mongo_uri == "mongodb://custom:27017"
        assert settings.mongo_db == "custom_db"


class TestGetSettings:

    def test_returns_settings_instance(self):
        get_settings.cache_clear()

        settings = get_settings()

        assert isinstance(settings, Settings)

    def test_returns_cached_instance(self):
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2
