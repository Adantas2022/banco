"""Value Object DocumentId."""

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class DocumentId:
    """Identificador único de documento."""

    value: str

    @classmethod
    def generate(cls) -> "DocumentId":
        """Gera um novo DocumentId."""
        return cls(value=str(uuid4()))

    @classmethod
    def from_string(cls, value: str) -> "DocumentId":
        """Cria DocumentId a partir de string."""
        if not value or not value.strip():
            raise ValueError("DocumentId cannot be empty")
        return cls(value=value.strip())

    def __str__(self) -> str:
        return self.value
