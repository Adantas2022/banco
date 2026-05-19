"""Modelos de dados para o sistema de confianca profissional."""

from dataclasses import dataclass, field
from typing import Any, Literal, Optional


@dataclass
class FieldConfidence:
    """Confianca de um campo individual."""
    
    field_path: str
    value: Any
    confidence: float
    validation_passed: bool
    validation_errors: list[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, self.confidence))
    
    @property
    def is_valid(self) -> bool:
        return self.validation_passed and self.confidence >= 0.7
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "field_path": self.field_path,
            "value": self.value,
            "confidence": self.confidence,
            "validation_passed": self.validation_passed,
            "validation_errors": self.validation_errors,
        }


@dataclass
class SectionConfidence:
    """Confianca de uma secao do documento."""
    
    section_name: str
    detected: bool
    extracted: bool
    field_count: int = 0
    fields_valid: int = 0
    confidence: float = 0.0
    
    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(1.0, self.confidence))
        if self.field_count > 0 and self.confidence == 0.0:
            self.confidence = self.fields_valid / self.field_count
    
    @property
    def coverage(self) -> float:
        if not self.detected:
            return 1.0
        return 1.0 if self.extracted else 0.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "section_name": self.section_name,
            "detected": self.detected,
            "extracted": self.extracted,
            "field_count": self.field_count,
            "fields_valid": self.fields_valid,
            "confidence": self.confidence,
            "coverage": self.coverage,
        }


@dataclass
class ReviewFlag:
    """Flag indicando necessidade de revisao humana."""
    
    severity: Literal["warning", "error", "critical"]
    message: str
    field_path: Optional[str] = None
    suggestion: Optional[str] = None
    
    @property
    def severity_weight(self) -> float:
        weights = {
            "warning": 0.05,
            "error": 0.15,
            "critical": 0.30,
        }
        return weights.get(self.severity, 0.0)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "message": self.message,
            "field_path": self.field_path,
            "suggestion": self.suggestion,
        }


@dataclass
class ValidationResult:
    """Resultado de uma validacao cruzada."""
    
    validation_name: str
    passed: bool
    penalty: float = 0.0
    message: Optional[str] = None
    affected_fields: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_name": self.validation_name,
            "passed": self.passed,
            "penalty": self.penalty,
            "message": self.message,
            "affected_fields": self.affected_fields,
        }
