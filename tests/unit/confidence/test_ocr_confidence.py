"""Testes unitarios para o sistema de confianca OCR."""

import pytest

from irpf_processor.domain.services.confidence.ocr_calculator import OcrConfidenceCalculator
from irpf_processor.domain.services.confidence.declaration_calculator import DeclarationConfidenceCalculator
from irpf_processor.domain.services.confidence.interface import ConfidenceResult
from irpf_processor.domain.services.confidence.models import ReviewFlag
from irpf_processor.domain.services.confidence.validators import (
    OcrGarbageCharsValidator,
    OcrRepeatedCharsValidator,
    OcrTruncatedValueValidator,
    OcrCpfConfusionValidator,
    OcrCurrencyConfusionValidator,
    OcrDateConfusionValidator,
    validate_ocr_field,
)


class TestOcrConfidenceCalculator:
    
    @pytest.fixture
    def base_calculator(self):
        return DeclarationConfidenceCalculator()
    
    @pytest.fixture
    def ocr_calculator(self, base_calculator):
        return OcrConfidenceCalculator(base_calculator)
    
    def test_applies_ocr_penalty(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "123.456.789-09",
                "name": "Test User",
                "exercise_year": 2024,
                "calendar_year": 2023,
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            detected_sections={"taxpayer_identification"},
        )
        
        assert "ocr_extraction" in result.penalties
        assert result.penalties["ocr_extraction"] == 0.10
    
    def test_applies_mixed_penalty(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "123.456.789-09",
                "name": "Test User",
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="mixed",
            detected_sections={"taxpayer_identification"},
        )
        
        assert "mixed_extraction" in result.penalties
        assert result.penalties["mixed_extraction"] == 0.05
    
    def test_propagates_professional_confidence_fields(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "529.982.247-25",
                "name": "Test User",
                "exercise_year": 2024,
                "calendar_year": 2023,
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            detected_sections={"taxpayer_identification"},
        )
        
        assert hasattr(result, "coverage_score")
        assert hasattr(result, "validation_score")
        assert hasattr(result, "section_scores")
        assert hasattr(result, "review_flags")
        assert hasattr(result, "validation_results")
        assert hasattr(result, "needs_review")
    
    def test_generates_ocr_review_flags(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "123.456.789-09",
                "name": "Test User",
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            detected_sections={"taxpayer_identification"},
        )
        
        ocr_flags = [f for f in result.review_flags if "OCR" in f.message or "ocr" in f.message.lower()]
        assert len(ocr_flags) > 0
    
    def test_critical_flag_for_very_low_ocr_confidence(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "123.456.789-09",
                "name": "Test User",
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            ocr_confidence=0.3,
            detected_sections={"taxpayer_identification"},
        )
        
        critical_flags = [f for f in result.review_flags if f.severity == "critical"]
        assert len(critical_flags) > 0
        assert result.needs_review is True
    
    def test_warning_flag_for_moderate_ocr_confidence(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "123.456.789-09",
                "name": "Test User",
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            ocr_confidence=0.6,
            detected_sections={"taxpayer_identification"},
        )
        
        warning_flags = [
            f for f in result.review_flags 
            if f.severity == "warning" and "moderada" in f.message.lower()
        ]
        assert len(warning_flags) > 0
    
    def test_caps_confidence_to_ocr_quality(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "529.982.247-25",
                "name": "Test User",
                "exercise_year": 2024,
                "calendar_year": 2023,
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            ocr_confidence=0.5,
            detected_sections={"taxpayer_identification"},
        )
        
        assert result.overall <= 0.5


class TestOcrValidators:
    
    def test_garbage_chars_validator_detects_invalid_chars(self):
        validator = OcrGarbageCharsValidator()
        
        passed, errors = validator.validate("Normal text")
        assert passed is True
        
        passed, errors = validator.validate("Text with \x00 null")
        assert passed is False
        assert len(errors) > 0
    
    def test_repeated_chars_validator_detects_anomalies(self):
        validator = OcrRepeatedCharsValidator()
        
        passed, errors = validator.validate("Normal text")
        assert passed is True
        
        passed, errors = validator.validate("Textttttt with repeated")
        assert passed is False
        assert len(errors) > 0
    
    def test_truncated_value_validator_detects_truncation(self):
        validator = OcrTruncatedValueValidator()
        
        passed, errors = validator.validate("1.234,56")
        assert passed is True
        
        passed, errors = validator.validate("1.234,5")
        assert passed is False
        assert "truncado" in errors[0].lower()
        
        passed, errors = validator.validate("1.234,")
        assert passed is False
    
    def test_cpf_confusion_validator_detects_letter_digit_confusion(self):
        validator = OcrCpfConfusionValidator()
        
        passed, errors = validator.validate("123456789")
        assert passed is True
        
        passed, errors = validator.validate("12345678O")
        assert passed is False
        assert len(errors) > 0
        
        passed, errors = validator.validate("l23456789")
        assert passed is False
    
    def test_currency_confusion_validator_detects_issues(self):
        validator = OcrCurrencyConfusionValidator()
        
        passed, errors = validator.validate("1.234,56")
        assert passed is True
        
        passed, errors = validator.validate("1.234.567,89")
        assert passed is True
        
        passed, errors = validator.validate("1.23O.567")
        assert passed is False
        
        passed, errors = validator.validate("1,2,3")
        assert passed is False
    
    def test_date_confusion_validator_detects_issues(self):
        validator = OcrDateConfusionValidator()
        
        passed, errors = validator.validate("31/12/2024")
        assert passed is True
        
        passed, errors = validator.validate("3l/12/2024")
        assert passed is False
        
        passed, errors = validator.validate("N/A")
        assert passed is True


class TestValidateOcrField:
    
    def test_validates_text_field(self):
        passed, errors = validate_ocr_field("Normal text", "text")
        assert passed is True
        
        passed, errors = validate_ocr_field("Texttttttttt", "text")
        assert passed is False
    
    def test_validates_cpf_field(self):
        passed, errors = validate_ocr_field("12345678901", "cpf")
        assert passed is True
        
        passed, errors = validate_ocr_field("12345678O01", "cpf")
        assert passed is False
    
    def test_validates_currency_field(self):
        passed, errors = validate_ocr_field("1.234,56", "currency")
        assert passed is True
        
        passed, errors = validate_ocr_field("1.234,5", "currency")
        assert passed is False
    
    def test_validates_date_field(self):
        passed, errors = validate_ocr_field("31/12/2024", "date")
        assert passed is True
        
        passed, errors = validate_ocr_field("3I/12/2024", "date")
        assert passed is False


class TestOcrConfidenceResultSerialization:
    
    @pytest.fixture
    def base_calculator(self):
        return DeclarationConfidenceCalculator()
    
    @pytest.fixture
    def ocr_calculator(self, base_calculator):
        return OcrConfidenceCalculator(base_calculator)
    
    def test_to_dict_includes_all_fields(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "529.982.247-25",
                "name": "Test User",
                "exercise_year": 2024,
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            ocr_confidence=0.8,
            detected_sections={"taxpayer_identification"},
        )
        
        result_dict = result.to_dict()
        
        assert "overall" in result_dict
        assert "level" in result_dict
        assert "extraction_method" in result_dict
        assert "coverage_score" in result_dict
        assert "validation_score" in result_dict
        assert "needs_review" in result_dict
        assert "review_flags" in result_dict
        assert "section_scores" in result_dict
        assert "penalties" in result_dict
        assert "details" in result_dict
    
    def test_review_flags_serialized_correctly(self, ocr_calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "123.456.789-09",
                "name": "Test User",
            }
        }
        
        result = ocr_calculator.calculate(
            extracted_data=data,
            extraction_method="ocr",
            ocr_confidence=0.4,
            detected_sections={"taxpayer_identification"},
        )
        
        result_dict = result.to_dict()
        
        for flag in result_dict["review_flags"]:
            assert "severity" in flag
            assert "message" in flag
