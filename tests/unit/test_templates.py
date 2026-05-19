"""Testes unitários para o sistema de templates."""

import pytest

from irpf_processor.templates import (
    FieldDefinition,
    FieldType,
    IRPFTemplate,
    SectionDefinition,
    ValidationRule,
    ValidationType,
)
from irpf_processor.templates.models import DetectionPattern
from irpf_processor.templates.registry import YamlTemplateRegistry


class TestFieldDefinition:
    """Testes para FieldDefinition."""
    
    def test_is_document_type_cpf(self):
        field = FieldDefinition(name="cpf", type=FieldType.CPF)
        assert field.is_document_type() is True
    
    def test_is_document_type_cnpj(self):
        field = FieldDefinition(name="cnpj", type=FieldType.CNPJ)
        assert field.is_document_type() is True
    
    def test_is_document_type_string(self):
        field = FieldDefinition(name="name", type=FieldType.STRING)
        assert field.is_document_type() is False
    
    def test_is_numeric_currency(self):
        field = FieldDefinition(name="value", type=FieldType.CURRENCY)
        assert field.is_numeric() is True
    
    def test_is_numeric_string(self):
        field = FieldDefinition(name="name", type=FieldType.STRING)
        assert field.is_numeric() is False


class TestSectionDefinition:
    """Testes para SectionDefinition."""
    
    def test_get_field_existing(self):
        section = SectionDefinition(
            name="Test",
            fields=[
                FieldDefinition(name="cpf", type=FieldType.CPF),
                FieldDefinition(name="name", type=FieldType.STRING),
            ],
        )
        
        field = section.get_field("cpf")
        assert field is not None
        assert field.name == "cpf"
    
    def test_get_field_not_found(self):
        section = SectionDefinition(name="Test", fields=[])
        assert section.get_field("nonexistent") is None
    
    def test_get_required_fields(self):
        section = SectionDefinition(
            name="Test",
            fields=[
                FieldDefinition(name="cpf", type=FieldType.CPF, required=True),
                FieldDefinition(name="name", type=FieldType.STRING, required=False),
            ],
        )
        
        required = section.get_required_fields()
        assert len(required) == 1
        assert required[0].name == "cpf"
    
    def test_is_new_in_version(self):
        section = SectionDefinition(
            name="Crypto",
            new_in_version="2025",
        )
        
        assert section.is_new_in("2025") is True
        assert section.is_new_in("2024") is False


class TestIRPFTemplate:
    """Testes para IRPFTemplate."""
    
    @pytest.fixture
    def template(self) -> IRPFTemplate:
        return IRPFTemplate(
            version="2025",
            exercise_year="2025",
            calendar_year="2024",
            description="Test Template",
            detection=DetectionPattern(patterns=["2025"]),
            sections={
                "taxpayer": SectionDefinition(
                    name="Taxpayer",
                    required=True,
                    fields=[
                        FieldDefinition(name="cpf", type=FieldType.CPF, required=True),
                    ],
                ),
                "assets": SectionDefinition(
                    name="Assets",
                    required=False,
                    fields=[],
                ),
            },
            validations=[
                ValidationRule(
                    type=ValidationType.SUM_CHECK,
                    section="assets",
                    field="value",
                    total_field="total_value",
                ),
            ],
        )
    
    def test_get_section_existing(self, template: IRPFTemplate):
        section = template.get_section("taxpayer")
        assert section is not None
        assert section.name == "Taxpayer"
    
    def test_get_section_not_found(self, template: IRPFTemplate):
        assert template.get_section("nonexistent") is None
    
    def test_is_section_required(self, template: IRPFTemplate):
        assert template.is_section_required("taxpayer") is True
        assert template.is_section_required("assets") is False
    
    def test_get_required_sections(self, template: IRPFTemplate):
        required = template.get_required_sections()
        assert len(required) == 1
        assert required[0].name == "Taxpayer"
    
    def test_get_optional_sections(self, template: IRPFTemplate):
        optional = template.get_optional_sections()
        assert len(optional) == 1
        assert optional[0].name == "Assets"
    
    def test_get_validations_for_section(self, template: IRPFTemplate):
        validations = template.get_validations_for_section("assets")
        assert len(validations) == 1
        assert validations[0].type == ValidationType.SUM_CHECK
    
    def test_list_section_names(self, template: IRPFTemplate):
        names = template.list_section_names()
        assert "taxpayer" in names
        assert "assets" in names


class TestYamlTemplateRegistry:
    """Testes para YamlTemplateRegistry."""
    
    def test_register_and_get_template(self):
        registry = YamlTemplateRegistry()
        
        template = IRPFTemplate(
            version="2025",
            exercise_year="2025",
            calendar_year="2024",
            description="Test",
            detection=DetectionPattern(patterns=["2025"]),
            sections={},
            validations=[],
        )
        
        registry.register_template(template)
        
        retrieved = registry.get_template("2025")
        assert retrieved is not None
        assert retrieved.version == "2025"
    
    def test_get_template_not_found(self):
        registry = YamlTemplateRegistry()
        assert registry.get_template("9999") is None
    
    def test_list_versions(self):
        registry = YamlTemplateRegistry()
        
        for year in ["2023", "2024", "2025"]:
            template = IRPFTemplate(
                version=year,
                exercise_year=year,
                calendar_year=str(int(year) - 1),
                description=f"Test {year}",
                detection=DetectionPattern(patterns=[year]),
                sections={},
                validations=[],
            )
            registry.register_template(template)
        
        versions = registry.list_versions()
        assert "2025" in versions
        assert "2024" in versions
        assert "2023" in versions
    
    def test_get_latest_version(self):
        registry = YamlTemplateRegistry()
        
        for year in ["2023", "2024", "2025"]:
            template = IRPFTemplate(
                version=year,
                exercise_year=year,
                calendar_year=str(int(year) - 1),
                description=f"Test {year}",
                detection=DetectionPattern(patterns=[year]),
                sections={},
                validations=[],
            )
            registry.register_template(template)
        
        latest = registry.get_latest_version()
        assert latest == "2025"
    
    def test_detect_version_from_text(self):
        registry = YamlTemplateRegistry()
        
        template = IRPFTemplate(
            version="2025",
            exercise_year="2025",
            calendar_year="2024",
            description="Test",
            detection=DetectionPattern(
                patterns=["DECLARAÇÃO 2025"],
                exercise_year_regex=r"Exercício\s+(\d{4})",
            ),
            sections={},
            validations=[],
        )
        registry.register_template(template)
        
        text = "DECLARAÇÃO DE AJUSTE ANUAL\nExercício 2025"
        detected = registry.detect_version(text)
        
        assert detected == "2025"
    
    def test_detect_version_not_found(self):
        registry = YamlTemplateRegistry()
        
        detected = registry.detect_version("Texto sem versão")
        assert detected is None

    def test_detect_version_by_pattern(self):
        registry = YamlTemplateRegistry()
        registry._loaded = True

        template = IRPFTemplate(
            version="2030",
            exercise_year="2030",
            calendar_year="2029",
            description="Test",
            detection=DetectionPattern(
                patterns=["DECLARAÇÃO IRPF 2030", "ANO CALENDÁRIO 2029"],
                exercise_year_regex=r"Exercício\s+(\d{4})",
            ),
            sections={},
            validations=[],
        )
        registry.register_template(template)

        text = "Este documento contém DECLARAÇÃO IRPF 2030"
        detected = registry.detect_version(text)

        assert detected == "2030"

    def test_get_template_or_latest_with_version(self):
        registry = YamlTemplateRegistry()

        template = IRPFTemplate(
            version="2025",
            exercise_year="2025",
            calendar_year="2024",
            description="Test",
            detection=DetectionPattern(patterns=["2025"]),
            sections={},
            validations=[],
        )
        registry.register_template(template)

        result = registry.get_template_or_latest("2025")

        assert result is not None
        assert result.version == "2025"

    def test_get_template_or_latest_fallback_to_latest(self):
        registry = YamlTemplateRegistry()

        template = IRPFTemplate(
            version="2025",
            exercise_year="2025",
            calendar_year="2024",
            description="Test",
            detection=DetectionPattern(patterns=["2025"]),
            sections={},
            validations=[],
        )
        registry.register_template(template)

        result = registry.get_template_or_latest("9999")

        assert result is not None
        assert result.version == "2025"

    def test_get_template_or_latest_with_none(self):
        registry = YamlTemplateRegistry()

        template = IRPFTemplate(
            version="2025",
            exercise_year="2025",
            calendar_year="2024",
            description="Test",
            detection=DetectionPattern(patterns=["2025"]),
            sections={},
            validations=[],
        )
        registry.register_template(template)

        result = registry.get_template_or_latest(None)

        assert result is not None
        assert result.version == "2025"

    def test_get_template_or_latest_empty_registry(self):
        registry = YamlTemplateRegistry()
        registry._loaded = True

        result = registry.get_template_or_latest(None)

        assert result is None

    def test_get_latest_version_empty_registry(self):
        registry = YamlTemplateRegistry()
        registry._loaded = True

        result = registry.get_latest_version()

        assert result is None

    def test_load_templates_from_nonexistent_dir(self):
        from pathlib import Path

        registry = YamlTemplateRegistry(templates_dir=Path("/nonexistent/dir"))
        registry._load_all_templates()

        assert len(registry._templates) == 0

    def test_section_with_subsections(self):
        section = SectionDefinition(
            name="Parent",
            has_subsections=True,
            subsections=[
                SectionDefinition(name="Child1"),
                SectionDefinition(name="Child2"),
            ],
        )

        assert section.has_subsections is True
        assert len(section.subsections) == 2
        assert section.subsections[0].name == "Child1"
