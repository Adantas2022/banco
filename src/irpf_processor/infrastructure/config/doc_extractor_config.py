"""Compatibility shim — maps DOCSPJ Pydantic Settings to the interface expected by doc-extractor code.

doc-extractor originally used a frozen dataclass ``Settings`` with a module-level ``settings`` singleton.
This module provides the same interface backed by the main Pydantic Settings class so the migrated
code can continue using ``from src.infrastructure.config.doc_extractor_config import settings``.
"""

from __future__ import annotations

import ssl

# ---------------------------------------------------------------------------
# SSL bypass (corporate proxy / self-signed certificates)
# ---------------------------------------------------------------------------
_original_create_default_context = ssl.create_default_context


def _unverified_context(*args, **kwargs):  # type: ignore[no-untyped-def]
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


ssl.create_default_context = _unverified_context  # type: ignore[assignment]

import httpx  # noqa: E402

_original_httpx_client_init = httpx.Client.__init__


def _patched_httpx_client_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    kwargs["verify"] = False
    kwargs.setdefault("timeout", httpx.Timeout(300.0))
    _original_httpx_client_init(self, *args, **kwargs)


httpx.Client.__init__ = _patched_httpx_client_init  # type: ignore[assignment]

_original_httpx_async_init = httpx.AsyncClient.__init__


def _patched_httpx_async_init(self, *args, **kwargs):  # type: ignore[no-untyped-def]
    kwargs["verify"] = False
    kwargs.setdefault("timeout", httpx.Timeout(300.0))
    _original_httpx_async_init(self, *args, **kwargs)


httpx.AsyncClient.__init__ = _patched_httpx_async_init  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Facade — expose settings properties under the old attribute names
# ---------------------------------------------------------------------------
from irpf_processor.infrastructure.config.settings import get_settings as _get_settings  # noqa: E402


class _DocExtractorSettingsFacade:
    """Thin proxy that reads from the Pydantic Settings singleton."""

    @property
    def _s(self):  # type: ignore[no-untyped-def]
        return _get_settings()

    # Azure OpenAI
    @property
    def azure_openai_endpoint(self) -> str:
        return self._s.azure_openai_endpoint

    @property
    def azure_openai_api_key(self) -> str:
        return self._s.azure_openai_api_key

    @property
    def azure_openai_api_version(self) -> str:
        return self._s.de_azure_openai_api_version

    @property
    def azure_openai_deployment(self) -> str:
        return self._s.azure_openai_deployment

    # Server
    @property
    def host(self) -> str:
        return self._s.api_host

    @property
    def port(self) -> int:
        return self._s.api_port

    @property
    def log_level(self) -> str:
        return self._s.log_level

    @property
    def max_upload_mb(self) -> int:
        return self._s.max_upload_mb

    # PDF
    @property
    def pdf_dpi(self) -> int:
        return self._s.pdf_dpi

    # Security
    @property
    def api_keys(self) -> str:
        return self._s.api_keys

    @property
    def rate_limit_enabled(self) -> bool:
        return self._s.rate_limit_enabled

    @property
    def rate_limit_requests(self) -> int:
        return self._s.rate_limit_requests

    @property
    def rate_limit_period(self) -> str:
        return self._s.rate_limit_period

    @property
    def extraction_timeout(self) -> int:
        return self._s.extraction_timeout

    # Redis
    @property
    def redis_enabled(self) -> bool:
        return self._s.redis_enabled

    @property
    def redis_host(self) -> str:
        return self._s.redis_host

    @property
    def redis_port(self) -> int:
        return self._s.redis_port

    @property
    def redis_db(self) -> int:
        return self._s.redis_db

    @property
    def redis_password(self) -> str:
        return self._s.redis_password

    @property
    def redis_ttl(self) -> int:
        return self._s.redis_ttl

    @property
    def cache_version(self) -> str:
        return self._s.cache_version

    # Observability
    @property
    def log_format(self) -> str:
        return self._s.log_format

    @property
    def langfuse_enabled(self) -> bool:
        return self._s.langfuse_enabled

    # Derived
    @property
    def max_upload_bytes(self) -> int:
        return self._s.max_upload_bytes

    @property
    def valid_api_keys(self) -> set[str]:
        return self._s.valid_api_keys

    @property
    def requires_auth(self) -> bool:
        return self._s.requires_auth


settings = _DocExtractorSettingsFacade()
