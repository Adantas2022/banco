"""Registry de templates com suporte a carregamento de YAML."""

import re
from abc import abstractmethod
from pathlib import Path
from typing import Optional, Protocol

import yaml

from irpf_processor.shared.logging import get_logger

from .models import (
    DetectionPattern,
    FieldDefinition,
    FieldType,
    IRPFTemplate,
    SectionDefinition,
    ValidationRule,
    ValidationType,
)

logger = get_logger(__name__)


class ITemplateRegistry(Protocol):
    """Interface para registry de templates."""

    @abstractmethod
    def get_template(self, version: str) -> Optional[IRPFTemplate]:
        """Busca template por versão."""
        ...

    @abstractmethod
    def list_versions(self) -> list[str]:
        """Lista versões disponíveis."""
        ...

    @abstractmethod
    def register_template(self, template: IRPFTemplate) -> None:
        """Registra template manualmente."""
        ...

    @abstractmethod
    def detect_version(self, text: str) -> Optional[str]:
        """Detecta versão a partir do texto do PDF."""
        ...

    @abstractmethod
    def get_latest_version(self) -> Optional[str]:
        """Retorna a versão mais recente."""
        ...


class YamlTemplateRegistry:
    """Registry que carrega templates de arquivos YAML."""

    def __init__(self, templates_dir: Optional[Path] = None) -> None:
        self._templates: dict[str, IRPFTemplate] = {}
        self._templates_dir = templates_dir or self._get_default_templates_dir()
        self._loaded = False

    def _get_default_templates_dir(self) -> Path:
        """Retorna diretório padrão de templates."""
        return Path(__file__).parent / "definitions"

    def _ensure_loaded(self) -> None:
        """Garante que templates foram carregados."""
        if not self._loaded:
            self._load_all_templates()
            self._loaded = True

    def _load_all_templates(self) -> None:
        """Carrega todos os templates do diretório."""
        if not self._templates_dir.exists():
            logger.warning(
                "Templates directory not found",
                path=str(self._templates_dir),
            )
            return

        for yaml_file in self._templates_dir.glob("irpf_*.yaml"):
            try:
                template = self._load_from_yaml(yaml_file)
                self._templates[template.version] = template
                logger.info(
                    "Template loaded",
                    version=template.version,
                    file=yaml_file.name,
                )
            except Exception as e:
                logger.error(
                    "Failed to load template",
                    file=yaml_file.name,
                    error=str(e),
                )

    def _load_from_yaml(self, path: Path) -> IRPFTemplate:
        """Carrega template de arquivo YAML."""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        metadata = data.get("metadata", {})

        detection_data = data.get("detection", {})
        detection = DetectionPattern(
            patterns=detection_data.get("patterns", []),
            exercise_year_regex=detection_data.get(
                "exercise_year_regex", r"Exercício\s+(\d{4})"
            ),
            calendar_year_regex=detection_data.get(
                "calendar_year_regex", r"Ano-calendário\s+(\d{4})"
            ),
        )

        sections: dict[str, SectionDefinition] = {}
        for section_name, section_data in data.get("sections", {}).items():
            sections[section_name] = self._parse_section(section_data)

        validations: list[ValidationRule] = []
        for val_data in data.get("validations", []):
            validations.append(
                ValidationRule(
                    type=ValidationType(val_data["type"]),
                    section=val_data["section"],
                    field=val_data.get("field"),
                    total_field=val_data.get("total_field"),
                    related_section=val_data.get("related_section"),
                    error_message=val_data.get("error_message"),
                )
            )

        return IRPFTemplate(
            version=metadata.get("version", "unknown"),
            exercise_year=metadata.get("exercise_year", ""),
            calendar_year=metadata.get("calendar_year", ""),
            description=metadata.get("description", ""),
            detection=detection,
            sections=sections,
            validations=validations,
        )

    def _parse_section(self, data: dict) -> SectionDefinition:
        """Parseia definição de seção."""
        fields: list[FieldDefinition] = []
        for field_data in data.get("fields", []):
            fields.append(
                FieldDefinition(
                    name=field_data["name"],
                    type=FieldType(field_data.get("type", "string")),
                    required=field_data.get("required", False),
                    pattern=field_data.get("pattern"),
                    validators=field_data.get("validators", []),
                    description=field_data.get("description"),
                )
            )

        subsections: list[SectionDefinition] = []
        for sub_data in data.get("subsections", []):
            if isinstance(sub_data, dict):
                subsections.append(self._parse_section(sub_data))

        return SectionDefinition(
            name=data.get("name", ""),
            code=data.get("code"),
            required=data.get("required", False),
            repeatable=data.get("repeatable", False),
            has_totals=data.get("has_totals", False),
            has_subsections=data.get("has_subsections", False),
            fields=fields,
            subsections=subsections,
            new_in_version=data.get("new_in_version"),
            removed_in_version=data.get("removed_in_version"),
            description=data.get("description"),
        )

    def get_template(self, version: str) -> Optional[IRPFTemplate]:
        """Busca template por versão."""
        self._ensure_loaded()
        return self._templates.get(version)

    def list_versions(self) -> list[str]:
        """Lista versões disponíveis ordenadas."""
        self._ensure_loaded()
        return sorted(self._templates.keys(), reverse=True)

    def register_template(self, template: IRPFTemplate) -> None:
        """Registra template manualmente."""
        self._templates[template.version] = template
        logger.info("Template registered", version=template.version)

    def detect_version(self, text: str) -> Optional[str]:
        """Detecta versão a partir do texto do PDF."""
        self._ensure_loaded()

        for version, template in self._templates.items():
            pattern = template.detection.exercise_year_regex
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                found_year = match.group(1)
                if found_year == template.exercise_year:
                    logger.info(
                        "Version detected",
                        version=version,
                        exercise_year=found_year,
                    )
                    return version

        for version, template in self._templates.items():
            for pattern in template.detection.patterns:
                if pattern.lower() in text.lower():
                    logger.info(
                        "Version detected by pattern",
                        version=version,
                        pattern=pattern,
                    )
                    return version

        logger.warning("Could not detect version from text")
        return None

    def get_latest_version(self) -> Optional[str]:
        """Retorna a versão mais recente."""
        versions = self.list_versions()
        return versions[0] if versions else None

    def get_template_or_latest(self, version: Optional[str]) -> Optional[IRPFTemplate]:
        """Busca template pela versão ou retorna o mais recente."""
        if version:
            template = self.get_template(version)
            if template:
                return template
            logger.warning(
                "Template not found, falling back to latest",
                requested_version=version,
            )

        latest = self.get_latest_version()
        if latest:
            return self.get_template(latest)

        return None
