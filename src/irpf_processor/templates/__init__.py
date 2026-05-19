"""Sistema de Templates Versionados para IRPF."""

from .models import (
    FieldDefinition,
    FieldType,
    IRPFTemplate,
    SectionDefinition,
    ValidationRule,
    ValidationType,
)
from .registry import ITemplateRegistry, YamlTemplateRegistry

__all__ = [
    # Models
    "IRPFTemplate",
    "SectionDefinition",
    "FieldDefinition",
    "FieldType",
    "ValidationRule",
    "ValidationType",
    # Registry
    "ITemplateRegistry",
    "YamlTemplateRegistry",
]
