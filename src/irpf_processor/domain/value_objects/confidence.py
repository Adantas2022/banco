"""Value Object Confidence - relatório de confiança da extração."""

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass(frozen=True)
class Confidence:
    """Relatório de confiança da extração de um documento."""

    overall: float
    extraction_method: Literal["digital", "ocr", "mixed"]
    by_field: dict[str, float] = field(default_factory=dict)
    ocr_quality: Optional[float] = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.overall <= 1.0:
            raise ValueError("Overall confidence must be between 0.0 and 1.0")

    def is_high(self, threshold: float = 0.95) -> bool:
        """Verifica se é alta confiança."""
        return self.overall >= threshold

    def is_acceptable(self, threshold: float = 0.6) -> bool:
        """Verifica se é aceitável."""
        return self.overall >= threshold

    def get_low_confidence_fields(self, threshold: float = 0.8) -> list[str]:
        """Retorna campos com baixa confiança."""
        return [
            field_name
            for field_name, confidence in self.by_field.items()
            if confidence < threshold
        ]

    def used_ocr(self) -> bool:
        """Verifica se usou OCR."""
        return self.extraction_method in ("ocr", "mixed")
