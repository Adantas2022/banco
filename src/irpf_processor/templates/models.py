"""Modelos para o sistema de templates versionados."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class FieldType(str, Enum):
    """Tipos de campo suportados."""

    STRING = "string"
    TEXT = "text"
    CPF = "cpf"
    CNPJ = "cnpj"
    CURRENCY = "currency"
    DATE = "date"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"


class ValidationType(str, Enum):
    """Tipos de validação."""

    SUM_CHECK = "sum_check"
    REQUIRED_FIELD = "required_field"
    PATTERN_MATCH = "pattern_match"
    CROSS_REFERENCE = "cross_reference"


@dataclass
class FieldDefinition:
    """Definição de um campo no template."""

    name: str
    type: FieldType
    required: bool = False
    pattern: Optional[str] = None
    validators: list[str] = field(default_factory=list)
    description: Optional[str] = None

    def is_document_type(self) -> bool:
        """Verifica se é um campo de documento (CPF/CNPJ)."""
        return self.type in (FieldType.CPF, FieldType.CNPJ)

    def is_numeric(self) -> bool:
        """Verifica se é um campo numérico."""
        return self.type in (FieldType.CURRENCY, FieldType.INTEGER, FieldType.FLOAT)


@dataclass
class SectionDefinition:
    """Definição de uma seção no template."""

    name: str
    code: Optional[str] = None
    required: bool = False
    repeatable: bool = False
    has_totals: bool = False
    has_subsections: bool = False
    fields: list[FieldDefinition] = field(default_factory=list)
    subsections: list["SectionDefinition"] = field(default_factory=list)
    new_in_version: Optional[str] = None
    removed_in_version: Optional[str] = None
    description: Optional[str] = None

    def get_field(self, field_name: str) -> Optional[FieldDefinition]:
        """Busca definição de campo pelo nome."""
        for f in self.fields:
            if f.name == field_name:
                return f
        return None

    def get_required_fields(self) -> list[FieldDefinition]:
        """Retorna campos obrigatórios da seção."""
        return [f for f in self.fields if f.required]

    def is_new_in(self, version: str) -> bool:
        """Verifica se a seção é nova na versão especificada."""
        return self.new_in_version == version

    def is_removed_in(self, version: str) -> bool:
        """Verifica se a seção foi removida na versão especificada."""
        return self.removed_in_version == version


@dataclass
class ValidationRule:
    """Regra de validação."""

    type: ValidationType
    section: str
    field: Optional[str] = None
    total_field: Optional[str] = None
    related_section: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class DetectionPattern:
    """Padrão para detecção de versão."""

    patterns: list[str] = field(default_factory=list)
    exercise_year_regex: str = r"Exercício\s+(\d{4})"
    calendar_year_regex: str = r"Ano-calendário\s+(\d{4})"


@dataclass
class IRPFTemplate:
    """Template completo para uma versão de declaração IRPF."""

    version: str
    exercise_year: str
    calendar_year: str
    description: str
    detection: DetectionPattern
    sections: dict[str, SectionDefinition]
    validations: list[ValidationRule] = field(default_factory=list)

    def get_section(self, name: str) -> Optional[SectionDefinition]:
        """Busca seção pelo nome."""
        return self.sections.get(name)

    def is_section_required(self, name: str) -> bool:
        """Verifica se seção é obrigatória."""
        section = self.get_section(name)
        return section.required if section else False

    def get_required_sections(self) -> list[SectionDefinition]:
        """Retorna seções obrigatórias."""
        return [s for s in self.sections.values() if s.required]

    def get_optional_sections(self) -> list[SectionDefinition]:
        """Retorna seções opcionais."""
        return [s for s in self.sections.values() if not s.required]

    def get_new_sections(self) -> list[SectionDefinition]:
        """Retorna seções novas nesta versão."""
        return [s for s in self.sections.values() if s.new_in_version == self.version]

    def get_validations_for_section(self, section_name: str) -> list[ValidationRule]:
        """Retorna validações aplicáveis a uma seção."""
        return [v for v in self.validations if v.section == section_name]

    def list_section_names(self) -> list[str]:
        """Lista nomes de todas as seções."""
        return list(self.sections.keys())
