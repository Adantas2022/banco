"""Exceções do domínio."""

from .auth_exceptions import (
    AuthenticationError,
    ExpiredApiKeyError,
    InsufficientScopeError,
    InvalidApiKeyError,
    RevokedApiKeyError,
    TenantMismatchError,
)
from .domain_exceptions import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DomainException,
    ExtractionFailedError,
    InvalidStateTransitionError,
    LowConfidenceError,
)

__all__ = [
    "AuthenticationError",
    "DomainException",
    "DocumentAlreadyExistsError",
    "DocumentNotFoundError",
    "ExpiredApiKeyError",
    "ExtractionFailedError",
    "InsufficientScopeError",
    "InvalidApiKeyError",
    "InvalidStateTransitionError",
    "LowConfidenceError",
    "RevokedApiKeyError",
    "TenantMismatchError",
]
