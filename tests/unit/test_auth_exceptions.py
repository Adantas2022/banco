import pytest

from irpf_processor.domain.exceptions import (
    AuthenticationError,
    ExpiredApiKeyError,
    InsufficientScopeError,
    InvalidApiKeyError,
    RevokedApiKeyError,
    TenantMismatchError,
)


class TestAuthExceptions:

    def test_authentication_error(self):
        error = AuthenticationError("Custom message")

        assert error.code == "AUTH_ERROR"
        assert error.message == "Custom message"

    def test_invalid_api_key_error(self):
        error = InvalidApiKeyError()

        assert error.code == "AUTH_ERROR"
        assert "Invalid" in error.message

    def test_expired_api_key_error(self):
        error = ExpiredApiKeyError()

        assert error.code == "AUTH_ERROR"
        assert "expired" in error.message.lower()

    def test_revoked_api_key_error(self):
        error = RevokedApiKeyError()

        assert error.code == "AUTH_ERROR"
        assert "revoked" in error.message.lower()

    def test_insufficient_scope_error(self):
        error = InsufficientScopeError("documents:write")

        assert error.code == "INSUFFICIENT_SCOPE"
        assert "documents:write" in error.message

    def test_tenant_mismatch_error(self):
        error = TenantMismatchError()

        assert error.code == "TENANT_MISMATCH"
        assert "tenant" in error.message.lower()
