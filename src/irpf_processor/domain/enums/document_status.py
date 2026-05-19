"""Enum DocumentStatus - estados do documento na máquina de estados."""

from enum import Enum


class DocumentStatus(str, Enum):
    """Estados possíveis de um documento no pipeline de processamento."""

    RECEIVED = "RECEIVED"
    ROUTED = "ROUTED"
    PROCESSING = "PROCESSING"
    EXTRACTED = "EXTRACTED"
    READY = "READY"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"

    def can_transition_to(self, target: "DocumentStatus") -> bool:
        """Verifica se a transição de estado é válida."""
        valid_transitions: dict[DocumentStatus, set[DocumentStatus]] = {
            DocumentStatus.RECEIVED: {
                DocumentStatus.ROUTED,
                DocumentStatus.FAILED,
                DocumentStatus.QUARANTINED,
            },
            DocumentStatus.ROUTED: {
                DocumentStatus.PROCESSING,
                DocumentStatus.EXTRACTED,
                DocumentStatus.FAILED,
                DocumentStatus.QUARANTINED,
            },
            DocumentStatus.PROCESSING: {
                DocumentStatus.EXTRACTED,
                DocumentStatus.READY,
                DocumentStatus.FAILED,
                DocumentStatus.QUARANTINED,
            },
            DocumentStatus.EXTRACTED: {
                DocumentStatus.READY,
                DocumentStatus.FAILED,
            },
            DocumentStatus.READY: set(),
            DocumentStatus.FAILED: {
                DocumentStatus.PROCESSING,  # allow Dramatiq retries
            },
            DocumentStatus.QUARANTINED: set(),
        }
        return target in valid_transitions.get(self, set())

    def is_terminal(self) -> bool:
        """Verifica se é um estado terminal."""
        return self in (DocumentStatus.READY, DocumentStatus.FAILED, DocumentStatus.QUARANTINED)

    def is_processable(self) -> bool:
        """Verifica se documento pode ser processado."""
        return self in (DocumentStatus.RECEIVED, DocumentStatus.ROUTED, DocumentStatus.PROCESSING, DocumentStatus.EXTRACTED)
