import pytest

from irpf_processor.infrastructure.extraction.guards import ExclusiveIncomeGuard, GuardStatus


class MockExtractionContext:
    def __init__(self, pages_text: dict):
        self.pages_text = pages_text
        self.full_text = "\n".join(pages_text.values())
        self.warnings = []


class TestExclusiveIncomeGuard:

    @pytest.fixture
    def guard(self) -> ExclusiveIncomeGuard:
        return ExclusiveIncomeGuard()

    @pytest.fixture
    def mock_context(self) -> MockExtractionContext:
        return MockExtractionContext({
            1: "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA"
        })

    def test_validate_returns_passed_when_zero_totals(self, guard, mock_context):
        extracted_data = {
            "section_name": "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva",
            "total_value": 0.0,
            "valid_total": True,
            "subsections": {}
        }

        result = guard.validate(extracted_data, mock_context)

        assert result.status == GuardStatus.PASSED
        assert result.valid_total is True
        assert result.extracted_sum == 0.0
        assert result.pdf_total == 0.0
        assert result.difference == 0.0

    def test_validate_returns_passed_when_totals_match(self, guard, mock_context):
        extracted_data = {
            "section_name": "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva",
            "total_value": 1500.0,
            "valid_total": True,
            "subsections": {
                "thirteenth_salary": {
                    "total_value": 1500.0
                }
            }
        }

        result = guard.validate(extracted_data, mock_context)

        assert result.status == GuardStatus.PASSED
        assert result.valid_total is True
        assert result.extracted_sum == 1500.0
        assert result.pdf_total == 1500.0
        assert result.difference == 0.0

    def test_validate_returns_warning_when_totals_mismatch(self, guard, mock_context):
        extracted_data = {
            "section_name": "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva",
            "total_value": 2000.0,
            "valid_total": True,
            "subsections": {
                "thirteenth_salary": {
                    "total_value": 1500.0
                }
            }
        }

        result = guard.validate(extracted_data, mock_context)

        assert result.status == GuardStatus.WARNING
        assert result.valid_total is False
        assert result.should_retry is True
        assert len(result.warnings) > 0
        assert result.extracted_sum == 1500.0
        assert result.pdf_total == 2000.0

    def test_section_name(self, guard):
        assert guard.section_name == "exclusive_taxation_income"

    def test_sum_fields(self, guard):
        assert "total_value" in guard.sum_fields
        assert "value" in guard.sum_fields
