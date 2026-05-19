from irpf_processor.domain.exceptions.domain_exceptions import DomainException


class AuthenticationError(DomainException):
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(code="AUTH_ERROR", message=message)


class InvalidApiKeyError(AuthenticationError):
    def __init__(self):
        super().__init__(message="Invalid or missing API key")


class ExpiredApiKeyError(AuthenticationError):
    def __init__(self):
        super().__init__(message="API key has expired")


class RevokedApiKeyError(AuthenticationError):
    def __init__(self):
        super().__init__(message="API key has been revoked")


class InsufficientScopeError(DomainException):
    def __init__(self, required_scope: str):
        super().__init__(
            code="INSUFFICIENT_SCOPE",
            message=f"API key lacks required scope: {required_scope}",
        )


class TenantMismatchError(DomainException):
    def __init__(self):
        super().__init__(
            code="TENANT_MISMATCH",
            message="API key tenant does not match requested resource",
        )
