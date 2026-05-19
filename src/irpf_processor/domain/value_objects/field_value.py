"""Value Object FieldValue - valor extraído com metadados."""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class FieldValue:
    """Valor de um campo extraído com informações de confiança e origem."""

    value: Any
    confidence: float
    source: Literal["text", "ocr", "inferred"]
    raw_text: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

    def is_high_confidence(self, threshold: float = 0.95) -> bool:
        """Verifica se tem alta confiança."""
        return self.confidence >= threshold

    def is_from_ocr(self) -> bool:
        """Verifica se foi extraído via OCR."""
        return self.source == "ocr"

    def is_reliable(self, threshold: float = 0.8) -> bool:
        """Verifica se é confiável para uso."""
        return self.confidence >= threshold
