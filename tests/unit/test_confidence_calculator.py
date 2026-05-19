"""Tests for confidence calculators."""

import pytest

from irpf_processor.domain.enums import DocumentCategory
from irpf_processor.domain.services import (
    ConfidenceCalculatorFactory,
    ConfidenceResult,
    DeclarationConfidenceCalculator,
    ReceiptConfidenceCalculator,
    OcrConfidenceCalculator,
    IConfidenceCalculator,
)


class TestConfidenceResult:

    def test_confidence_result_clamped_to_0_1(self):
        result = ConfidenceResult(overall=1.5, extraction_method="digital")
        assert result.overall == 1.0

        result = ConfidenceResult(overall=-0.5, extraction_method="digital")
        assert result.overall == 0.0

    def test_confidence_level_excellent(self):
        result = ConfidenceResult(overall=0.95, extraction_method="digital")
        assert result.level == "excellent"
        assert result.level_pt == "excelente"

    def test_confidence_level_good(self):
        result = ConfidenceResult(overall=0.75, extraction_method="digital")
        assert result.level == "good"
        assert result.level_pt == "boa"

    def test_confidence_level_medium(self):
        result = ConfidenceResult(overall=0.60, extraction_method="digital")
        assert result.level == "medium"
        assert result.level_pt == "media"

    def test_confidence_level_low(self):
        result = ConfidenceResult(overall=0.30, extraction_method="digital")
        assert result.level == "low"
        assert result.level_pt == "baixa"

    def test_is_acceptable_default_threshold(self):
        result_acceptable = ConfidenceResult(overall=0.6, extraction_method="digital")
        assert result_acceptable.is_acceptable() is True

        result_not_acceptable = ConfidenceResult(overall=0.4, extraction_method="digital")
        assert result_not_acceptable.is_acceptable() is False

    def test_is_acceptable_custom_threshold(self):
        result = ConfidenceResult(overall=0.6, extraction_method="digital")
        assert result.is_acceptable(threshold=0.7) is False
        assert result.is_acceptable(threshold=0.5) is True

    def test_get_low_confidence_fields(self):
        result = ConfidenceResult(
            overall=0.8,
            extraction_method="digital",
            field_scores={
                "cpf": 1.0,
                "name": 0.9,
                "address": 0.5,
                "phone": 0.3,
            }
        )
        low_fields = result.get_low_confidence_fields(threshold=0.7)
        assert "address" in low_fields
        assert "phone" in low_fields
        assert "cpf" not in low_fields
        assert "name" not in low_fields

    def test_to_dict(self):
        result = ConfidenceResult(
            overall=0.85,
            extraction_method="digital",
            field_scores={"cpf": 1.0},
            penalties={"ocr": 0.1},
            bonuses={"email": 0.02},
            details={"fields_found": 5},
        )
        result_dict = result.to_dict()
        
        assert result_dict["overall"] == 0.85
        assert result_dict["level"] == "excellent"
        assert result_dict["level_pt"] == "excelente"
        assert result_dict["extraction_method"] == "digital"
        assert result_dict["field_scores"] == {"cpf": 1.0}
        assert result_dict["penalties"] == {"ocr": 0.1}
        assert result_dict["bonuses"] == {"email": 0.02}
        assert result_dict["details"] == {"fields_found": 5}


class TestDeclarationConfidenceCalculator:

    @pytest.fixture
    def calculator(self):
        return DeclarationConfidenceCalculator()

    def test_implements_interface(self, calculator):
        assert isinstance(calculator, IConfidenceCalculator)

    def test_document_type(self, calculator):
        assert calculator.document_type == "DECLARACAO"

    def test_required_fields(self, calculator):
        required = calculator.get_required_fields()
        assert "taxpayer_identification.normalized_cpf" in required
        assert "taxpayer_identification.name" in required

    def test_optional_fields(self, calculator):
        optional = calculator.get_optional_fields()
        assert "assets_declaration" in optional
        assert "income_from_legal_person_to_holder" in optional

    def test_full_data_excellent_confidence(self, calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
                "exercise_year": "2025",
                "calendar_year": "2024",
            },
            "assets_declaration": {"items": [{"code": "01", "value": 1000}]},
            "income_from_legal_person_to_holder": [{"source": "Company", "value": 50000}],
            "exempt_income": [{"type": "savings", "value": 1000}],
            "exclusive_taxation_income": [{"type": "13th", "value": 5000}],
            "debts_and_encumbrances": [{"type": "loan", "value": 10000}],
        }
        
        result = calculator.calculate(data)
        
        assert result.overall >= 0.85
        assert result.level == "excellent"

    def test_minimal_data_good_confidence(self, calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "52998224725",
                "cpf": "529.982.247-25",
                "name": "Test User",
            },
        }
        
        result = calculator.calculate(data)
        
        assert result.overall >= 0.7
        assert result.field_scores["taxpayer_identification.normalized_cpf"] == 1.0
        assert result.field_scores["taxpayer_identification.name"] == 1.0
        assert result.field_scores["assets_declaration"] == 0.0

    def test_empty_data_low_confidence(self, calculator):
        data = {}
        
        result = calculator.calculate(data)
        
        assert result.overall < 0.5
        assert result.level == "low"
        assert result.needs_review is True

    def test_ocr_extraction_penalty(self, calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        digital_result = calculator.calculate(data, extraction_method="digital")
        ocr_result = calculator.calculate(data, extraction_method="ocr")
        
        assert ocr_result.overall < digital_result.overall
        assert "ocr_extraction" in ocr_result.penalties

    def test_mixed_extraction_penalty(self, calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        digital_result = calculator.calculate(data, extraction_method="digital")
        mixed_result = calculator.calculate(data, extraction_method="mixed")
        
        assert mixed_result.overall < digital_result.overall
        assert "mixed_extraction" in mixed_result.penalties

    def test_email_bonus(self, calculator):
        data_without_email = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        data_with_email = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
                "contact_and_address": {
                    "email": "test@example.com",
                },
            },
        }
        
        result_without = calculator.calculate(data_without_email)
        result_with = calculator.calculate(data_with_email)
        
        assert "has_email" not in result_without.bonuses
        assert "has_email" in result_with.bonuses
        assert result_with.bonuses["has_email"] == 0.02


class TestReceiptConfidenceCalculator:

    @pytest.fixture
    def calculator(self):
        return ReceiptConfidenceCalculator()

    def test_implements_interface(self, calculator):
        assert isinstance(calculator, IConfidenceCalculator)

    def test_document_type(self, calculator):
        assert calculator.document_type == "RECIBO"

    def test_required_fields(self, calculator):
        required = calculator.get_required_fields()
        assert "normalized_cpf" in required
        assert "taxpayer_name" in required
        assert "exercise_year" in required

    def test_full_receipt_excellent_confidence(self, calculator):
        data = {
            "normalized_cpf": "12345678901",
            "taxpayer_name": "Test User",
            "exercise_year": "2025",
            "calendar_year": "2024",
            "transmission_datetime": "2025-05-15 14:30:00",
            "receipt_number": "1234567890",
            "tax_refund": 1500.0,
            "refund_bank_code": "001",
        }
        
        result = calculator.calculate(data)
        
        assert result.overall >= 0.85
        assert result.level == "excellent"

    def test_minimal_receipt_data(self, calculator):
        data = {
            "normalized_cpf": "12345678901",
            "taxpayer_name": "Test User",
            "exercise_year": "2025",
        }
        
        result = calculator.calculate(data)
        
        assert result.overall >= 0.5
        assert result.field_scores["normalized_cpf"] == 1.0
        assert result.field_scores["taxpayer_name"] == 1.0
        assert result.field_scores["exercise_year"] == 1.0

    def test_empty_receipt_zero_confidence(self, calculator):
        data = {}
        
        result = calculator.calculate(data)
        
        assert result.overall == 0.0

    def test_refund_with_bank_info_bonus(self, calculator):
        data_basic = {
            "normalized_cpf": "12345678901",
            "taxpayer_name": "Test User",
            "exercise_year": "2025",
            "tax_refund": 1500.0,
        }
        
        data_with_bank = {
            "normalized_cpf": "12345678901",
            "taxpayer_name": "Test User",
            "exercise_year": "2025",
            "tax_refund": 1500.0,
            "refund_bank_code": "001",
        }
        
        result_basic = calculator.calculate(data_basic)
        result_with_bank = calculator.calculate(data_with_bank)
        
        assert "complete_refund_info" not in result_basic.bonuses
        assert "complete_refund_info" in result_with_bank.bonuses
        assert result_with_bank.bonuses["complete_refund_info"] == 0.03

    def test_transmission_datetime_bonus(self, calculator):
        data_without = {
            "normalized_cpf": "12345678901",
            "taxpayer_name": "Test User",
            "exercise_year": "2025",
        }
        
        data_with = {
            "normalized_cpf": "12345678901",
            "taxpayer_name": "Test User",
            "exercise_year": "2025",
            "transmission_datetime": "2025-05-15 14:30:00",
        }
        
        result_without = calculator.calculate(data_without)
        result_with = calculator.calculate(data_with)
        
        assert "has_datetime" not in result_without.bonuses
        assert "has_datetime" in result_with.bonuses
        assert result_with.bonuses["has_datetime"] == 0.02


class TestOcrConfidenceCalculator:

    @pytest.fixture
    def base_calculator(self):
        return DeclarationConfidenceCalculator()

    @pytest.fixture
    def ocr_calculator(self, base_calculator):
        return OcrConfidenceCalculator(base_calculator)

    def test_implements_interface(self, ocr_calculator):
        assert isinstance(ocr_calculator, IConfidenceCalculator)

    def test_document_type_suffix(self, ocr_calculator):
        assert ocr_calculator.document_type == "DECLARACAO_OCR"

    def test_applies_ocr_penalty(self, base_calculator, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        base_result = base_calculator.calculate(data)
        ocr_result = ocr_calculator.calculate(data, extraction_method="ocr")
        
        assert ocr_result.overall < base_result.overall
        assert "ocr_extraction" in ocr_result.penalties

    def test_ocr_quality_cap(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        result = ocr_calculator.calculate(
            data, 
            extraction_method="ocr",
            ocr_confidence=0.5,
        )
        
        assert result.overall <= 0.5
        assert "ocr_quality_cap" in result.penalties

    def test_very_low_ocr_quality_extra_penalty(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        result_normal = ocr_calculator.calculate(
            data,
            extraction_method="ocr",
            ocr_confidence=0.6,
        )
        
        result_low = ocr_calculator.calculate(
            data,
            extraction_method="ocr",
            ocr_confidence=0.2,
        )
        
        assert result_low.overall < result_normal.overall
        assert "ocr_quality_very_low" in result_low.penalties

    def test_custom_penalty_values(self, base_calculator):
        custom_calculator = OcrConfidenceCalculator(
            base_calculator,
            ocr_penalty=0.20,
            mixed_penalty=0.10,
        )
        
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "12345678901",
                "name": "Test User",
            },
        }
        
        result = custom_calculator.calculate(data, extraction_method="ocr")
        
        assert result.penalties.get("ocr_extraction") == 0.20


class TestConfidenceCalculatorFactory:

    def test_factory_for_declaration_digital(self):
        calculator = ConfidenceCalculatorFactory.for_declaration(use_ocr=False)
        assert isinstance(calculator, DeclarationConfidenceCalculator)

    def test_factory_for_declaration_ocr(self):
        calculator = ConfidenceCalculatorFactory.for_declaration(use_ocr=True)
        assert isinstance(calculator, OcrConfidenceCalculator)

    def test_factory_for_receipt_digital(self):
        calculator = ConfidenceCalculatorFactory.for_receipt(use_ocr=False)
        assert isinstance(calculator, ReceiptConfidenceCalculator)

    def test_factory_for_receipt_ocr(self):
        calculator = ConfidenceCalculatorFactory.for_receipt(use_ocr=True)
        assert isinstance(calculator, OcrConfidenceCalculator)

    def test_get_calculator_declaracao_digital(self):
        calculator = ConfidenceCalculatorFactory.get_calculator(
            document_category=DocumentCategory.DECLARACAO,
            extraction_method="digital",
        )
        assert isinstance(calculator, DeclarationConfidenceCalculator)

    def test_get_calculator_recibo_digital(self):
        calculator = ConfidenceCalculatorFactory.get_calculator(
            document_category=DocumentCategory.RECIBO,
            extraction_method="digital",
        )
        assert isinstance(calculator, ReceiptConfidenceCalculator)

    def test_get_calculator_declaracao_ocr(self):
        calculator = ConfidenceCalculatorFactory.get_calculator(
            document_category=DocumentCategory.DECLARACAO,
            extraction_method="ocr",
        )
        assert isinstance(calculator, OcrConfidenceCalculator)

    def test_get_calculator_unknown_defaults_to_declaration(self):
        calculator = ConfidenceCalculatorFactory.get_calculator(
            document_category=DocumentCategory.UNKNOWN,
            extraction_method="digital",
        )
        assert isinstance(calculator, DeclarationConfidenceCalculator)

    def test_factory_caches_calculators(self):
        ConfidenceCalculatorFactory.reset()
        
        calc1 = ConfidenceCalculatorFactory.for_declaration(use_ocr=False)
        calc2 = ConfidenceCalculatorFactory.for_declaration(use_ocr=False)
        
        assert calc1 is calc2

    def test_factory_reset_clears_cache(self):
        calc1 = ConfidenceCalculatorFactory.for_declaration(use_ocr=False)
        ConfidenceCalculatorFactory.reset()
        calc2 = ConfidenceCalculatorFactory.for_declaration(use_ocr=False)
        
        assert calc1 is not calc2
