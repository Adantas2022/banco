"""Interface for confidence calculators - Strategy Pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import SectionConfidence, ReviewFlag, ValidationResult


@dataclass
class ConfidenceResult:
    """Result of confidence calculation."""

    overall: float
    extraction_method: Literal["digital", "ocr", "mixed"]
    field_scores: dict[str, float] = field(default_factory=dict)
    penalties: dict[str, float] = field(default_factory=dict)
    bonuses: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    
    coverage_score: float = 0.0
    validation_score: float = 0.0
    section_scores: dict[str, Any] = field(default_factory=dict)
    review_flags: list[Any] = field(default_factory=list)
    validation_results: list[Any] = field(default_factory=list)
    needs_review: bool = False

    def __post_init__(self) -> None:
        self.overall = max(0.0, min(1.0, self.overall))
        if not self.needs_review and self.review_flags:
            self.needs_review = any(
                getattr(f, 'severity', None) in ('error', 'critical') 
                for f in self.review_flags
            )

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
    
    def get_review_reasons(self) -> list[str]:
        return [
            getattr(f, 'message', str(f)) 
            for f in self.review_flags
        ]

    def to_dict(self) -> dict[str, Any]:
        section_scores_dict = {}
        for key, value in self.section_scores.items():
            if hasattr(value, 'to_dict'):
                section_scores_dict[key] = value.to_dict()
            else:
                section_scores_dict[key] = value
        
        review_flags_list = []
        for f in self.review_flags:
            if hasattr(f, 'to_dict'):
                review_flags_list.append(f.to_dict())
            else:
                review_flags_list.append(f)
        
        validation_results_list = []
        for v in self.validation_results:
            if hasattr(v, 'to_dict'):
                validation_results_list.append(v.to_dict())
            else:
                validation_results_list.append(v)
        
        return {
            "overall": self.overall,
            "level": self.level,
            "level_pt": self.level_pt,
            "extraction_method": self.extraction_method,
            "coverage_score": self.coverage_score,
            "validation_score": self.validation_score,
            "needs_review": self.needs_review,
            "field_scores": self.field_scores,
            "section_scores": section_scores_dict,
            "review_flags": review_flags_list,
            "validation_results": validation_results_list,
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
