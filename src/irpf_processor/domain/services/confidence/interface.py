"""Interface for confidence calculators - Strategy Pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ConfidenceResult:
    """Result of confidence calculation."""

    overall: float
    extraction_method: Literal["digital", "ocr", "mixed"]
    field_scores: dict[str, float] = field(default_factory=dict)
    penalties: dict[str, float] = field(default_factory=dict)
    bonuses: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.overall = max(0.0, min(1.0, self.overall))

    @property
    def level(self) -> str:
        if self.overall >= 0.85:
            return "excellent"
        if self.overall >= 0.70:
            return "good"
        if self.overall >= 0.50:
            return "medium"
        return "low"

    @property
    def level_pt(self) -> str:
        levels = {
            "excellent": "excelente",
            "good": "boa",
            "medium": "media",
            "low": "baixa",
        }
        return levels.get(self.level, "desconhecida")

    def is_acceptable(self, threshold: float = 0.5) -> bool:
        return self.overall >= threshold

    def get_low_confidence_fields(self, threshold: float = 0.7) -> list[str]:
        return [
            field_name
            for field_name, score in self.field_scores.items()
            if score < threshold
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "level": self.level,
            "level_pt": self.level_pt,
            "extraction_method": self.extraction_method,
            "field_scores": self.field_scores,
            "penalties": self.penalties,
            "bonuses": self.bonuses,
            "details": self.details,
        }


class IConfidenceCalculator(ABC):
    """Interface for confidence calculators (Strategy Pattern)."""

    @property
    @abstractmethod
    def document_type(self) -> str:
        """Type of document this calculator handles."""
        pass

    @abstractmethod
    def calculate(
        self,
        extracted_data: dict[str, Any],
        extraction_method: Literal["digital", "ocr", "mixed"] = "digital",
        **kwargs: Any,
    ) -> ConfidenceResult:
        """Calculate confidence score for extracted data."""
        pass

    @abstractmethod
    def get_required_fields(self) -> list[str]:
        """Return list of required fields for this document type."""
        pass

    @abstractmethod
    def get_optional_fields(self) -> list[str]:
        """Return list of optional fields for this document type."""
        pass
