"""Value Object TenantId."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantId:
    """Identificador de tenant para multi-tenancy."""

    value: str

    @classmethod
    def from_string(cls, value: str) -> "TenantId":
        """Cria TenantId a partir de string."""
        if not value or not value.strip():
            raise ValueError("TenantId cannot be empty")
        return cls(value=value.strip())

    def __str__(self) -> str:
        return self.value
