import pytest

from irpf_processor.infrastructure.extraction.guards import AssetsGuard, GuardStatus


class MockExtractionContext:
    def __init__(self, pages_text: dict):
        self.pages_text = pages_text
        self.full_text = "\n".join(pages_text.values())
        self.warnings = []


class TestAssetsGuard:

    @pytest.fixture
    def guard(self) -> AssetsGuard:
        return AssetsGuard()

    @pytest.fixture
    def context_with_total(self) -> MockExtractionContext:
        return MockExtractionContext({
            1: """DECLARAÇÃO DE BENS E DIREITOS
            01 - Imóvel  100.000,00  150.000,00
            02 - Veículo  50.000,00  50.000,00
            TOTAL  150.000,00  200.000,00"""
        })

    @pytest.fixture
    def context_without_total(self) -> MockExtractionContext:
        return MockExtractionContext({
            1: """DECLARAÇÃO DE BENS E DIREITOS
            01 - Imóvel  100.000,00  150.000,00"""
        })

    def test_validate_returns_passed_when_totals_match(self, guard, context_with_total):
        extracted_data = {
            "items": [
                {"current_year_asset_value": 150000.00},
                {"current_year_asset_value": 50000.00},
            ]
        }

        result = guard.validate(extracted_data, context_with_total)

        assert result.status == GuardStatus.PASSED
        assert result.valid_total is True
        assert result.extracted_sum == 200000.00
        assert result.pdf_total == 200000.00
        assert result.difference == 0.0

    def test_validate_returns_warning_when_totals_mismatch(self, guard, context_with_total):
        extracted_data = {
            "items": [
                {"current_year_asset_value": 150000.00},
            ]
        }

        result = guard.validate(extracted_data, context_with_total)

        assert result.status == GuardStatus.WARNING
        assert result.valid_total is False
        assert result.should_retry is True
        assert len(result.warnings) > 0

    def test_validate_returns_skipped_when_no_items(self, guard, context_with_total):
        extracted_data = {"items": []}

        result = guard.validate(extracted_data, context_with_total)

        assert result.status == GuardStatus.SKIPPED
        assert result.valid_total is None
        assert "no_items_extracted" in result.warnings

    def test_validate_returns_skipped_when_no_pdf_total(self, guard, context_without_total):
        extracted_data = {
            "items": [
                {"current_year_asset_value": 100000.00},
            ]
        }

        result = guard.validate(extracted_data, context_without_total)

        assert result.valid_total is None

    def test_section_name(self, guard):
        assert guard.section_name == "assets_declaration"

    def test_sum_fields(self, guard):
        assert "current_year_asset_value" in guard.sum_fields
        assert "before_year_asset_value" in guard.sum_fields
