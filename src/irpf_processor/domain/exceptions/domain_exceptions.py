"""Exceções do domínio com códigos de erro padronizados."""


class DomainException(Exception):
    """Exceção base do domínio."""

    def __init__(self, message: str, code: str) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class DocumentNotFoundError(DomainException):
    """Documento não encontrado."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"Document '{document_id}' not found",
            code="DOCUMENT_NOT_FOUND",
        )
        self.document_id = document_id


class DocumentAlreadyExistsError(DomainException):
    """Documento já existe (duplicado)."""

    def __init__(self, sha256: str, existing_document_id: str) -> None:
        super().__init__(
            message=f"Document with SHA256 '{sha256[:16]}...' already exists as '{existing_document_id}'",
            code="DOCUMENT_ALREADY_EXISTS",
        )
        self.sha256 = sha256
        self.existing_document_id = existing_document_id


class ExtractionFailedError(DomainException):
    """Falha na extração do documento."""

    def __init__(self, document_id: str, reason: str) -> None:
        super().__init__(
            message=f"Extraction failed for document '{document_id}': {reason}",
            code="EXTRACTION_FAILED",
        )
        self.document_id = document_id
        self.reason = reason


class InvalidStateTransitionError(DomainException):
    """Transição de estado inválida."""

    def __init__(self, document_id: str, current_status: str, target_status: str) -> None:
        super().__init__(
            message=f"Invalid state transition for document '{document_id}': {current_status} -> {target_status}",
            code="INVALID_STATE_TRANSITION",
        )
        self.document_id = document_id
        self.current_status = current_status
        self.target_status = target_status


class LowConfidenceError(DomainException):
    """Confiança abaixo do threshold."""

    def __init__(self, document_id: str, confidence: float, threshold: float) -> None:
        super().__init__(
            message=f"Low confidence ({confidence:.2%}) for document '{document_id}', threshold is {threshold:.2%}",
            code="LOW_CONFIDENCE",
        )
        self.document_id = document_id
        self.confidence = confidence
        self.threshold = threshold
