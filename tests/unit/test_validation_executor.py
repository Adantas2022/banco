import pytest

from irpf_processor.infrastructure.extraction.validation_executor import (
    ValidationExecutor,
)


class MockExtractionContext:
    def __init__(self, pages_text: dict):
        self.pages_text = pages_text
        self.full_text = "\n".join(pages_text.values())
        self.warnings = []


class TestValidationExecutor:

    @pytest.fixture
    def executor(self) -> ValidationExecutor:
        return ValidationExecutor()

    @pytest.fixture
    def context(self) -> MockExtractionContext:
        return MockExtractionContext({
            1: """DECLARAÇÃO DE BENS E DIREITOS
            TOTAL  150.000,00  200.000,00"""
        })

    def test_validate_section_adds_valid_total_field(self, executor, context):
        extracted_data = {
            "items": [
                {"current_year_asset_value": 150000.00},
                {"current_year_asset_value": 50000.00},
            ]
        }

        result = executor.validate_section("assets_declaration", extracted_data, context)

        assert "valid_total" in result

    def test_validate_section_returns_unchanged_for_unknown_section(self, executor, context):
        extracted_data = {"items": []}

        result = executor.validate_section("unknown_section", extracted_data, context)

        assert result == extracted_data

    def test_validate_all_sections(self, executor, context):
        sections = {
            "assets_declaration": {
                "items": [{"current_year_asset_value": 200000.00}]
            },
            "taxpayer_identification": {
                "cpf": "123.456.789-00"
            },
        }

        result = executor.validate_all_sections(sections, context)

        assert "valid_total" in result["assets_declaration"]

    def test_get_validation_summary(self, executor):
        sections = {
            "assets_declaration": {"valid_total": True, "total_value": 200000.00},
            "debts_and_encumbrances": {"valid_total": False, "total_value": 50000.00},
            "taxpayer_identification": {"cpf": "123.456.789-00"},
        }

        summary = executor.get_validation_summary(sections)

        assert summary["total_sections"] == 3
        assert summary["valid_totals"] == 1
        assert summary["invalid_totals"] == 1
        assert summary["skipped"] == 1

    def test_validation_executor_has_guard_registry(self, executor):
        assert "assets_declaration" in executor.GUARD_REGISTRY
        assert "debts_and_encumbrances" in executor.GUARD_REGISTRY
        assert "income_from_legal_person_to_holder" in executor.GUARD_REGISTRY
