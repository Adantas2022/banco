"""Testes para o sistema de confianca profissional."""

import pytest

from irpf_processor.domain.services.confidence import (
    ConfidenceResult,
    FieldConfidence,
    SectionConfidence,
    ReviewFlag,
    ValidationResult,
    CpfValidator,
    CnpjValidator,
    YearValidator,
    CurrencyValidator,
    DateValidator,
    StateValidator,
    SectionCoverageCalculator,
    CrossValidationCalculator,
    ReviewFlagGenerator,
    DeclarationConfidenceCalculator,
)


class TestFieldConfidence:
    """Testes para FieldConfidence dataclass."""
    
    def test_create_valid_field_confidence(self):
        fc = FieldConfidence(
            field_path="taxpayer.cpf",
            value="12345678901",
            confidence=0.95,
            validation_passed=True
        )
        
        assert fc.field_path == "taxpayer.cpf"
        assert fc.confidence == 0.95
        assert fc.is_valid is True
    
    def test_confidence_clamped_to_range(self):
        fc = FieldConfidence(
            field_path="test",
            value="x",
            confidence=1.5,
            validation_passed=True
        )
        
        assert fc.confidence == 1.0
        
        fc2 = FieldConfidence(
            field_path="test",
            value="x",
            confidence=-0.5,
            validation_passed=True
        )
        
        assert fc2.confidence == 0.0
    
    def test_is_valid_requires_high_confidence(self):
        fc = FieldConfidence(
            field_path="test",
            value="x",
            confidence=0.5,
            validation_passed=True
        )
        
        assert fc.is_valid is False


class TestSectionConfidence:
    """Testes para SectionConfidence dataclass."""
    
    def test_create_section_confidence(self):
        sc = SectionConfidence(
            section_name="assets_declaration",
            detected=True,
            extracted=True,
            field_count=10,
            fields_valid=8
        )
        
        assert sc.section_name == "assets_declaration"
        assert sc.confidence == 0.8
        assert sc.coverage == 1.0
    
    def test_coverage_when_not_extracted(self):
        sc = SectionConfidence(
            section_name="exempt_income",
            detected=True,
            extracted=False
        )
        
        assert sc.coverage == 0.0


class TestReviewFlag:
    """Testes para ReviewFlag dataclass."""
    
    def test_severity_weights(self):
        warning = ReviewFlag(severity="warning", message="test")
        error = ReviewFlag(severity="error", message="test")
        critical = ReviewFlag(severity="critical", message="test")
        
        assert warning.severity_weight == 0.05
        assert error.severity_weight == 0.15
        assert critical.severity_weight == 0.30


class TestCpfValidator:
    """Testes para CpfValidator."""
    
    @pytest.fixture
    def validator(self):
        return CpfValidator()
    
    def test_valid_cpf(self, validator):
        passed, errors = validator.validate("529.982.247-25")
        assert passed is True
        assert errors == []
    
    def test_valid_cpf_unformatted(self, validator):
        passed, errors = validator.validate("52998224725")
        assert passed is True
    
    def test_invalid_cpf_wrong_digit(self, validator):
        passed, errors = validator.validate("529.982.247-26")
        assert passed is False
        assert len(errors) > 0
    
    def test_invalid_cpf_all_same_digits(self, validator):
        passed, errors = validator.validate("111.111.111-11")
        assert passed is False
    
    def test_invalid_cpf_wrong_length(self, validator):
        passed, errors = validator.validate("1234567")
        assert passed is False
    
    def test_none_value(self, validator):
        passed, errors = validator.validate(None)
        assert passed is False


class TestCnpjValidator:
    """Testes para CnpjValidator."""
    
    @pytest.fixture
    def validator(self):
        return CnpjValidator()
    
    def test_valid_cnpj(self, validator):
        passed, errors = validator.validate("11.222.333/0001-81")
        assert passed is True
    
    def test_invalid_cnpj(self, validator):
        passed, errors = validator.validate("11.222.333/0001-82")
        assert passed is False


class TestYearValidator:
    """Testes para YearValidator."""
    
    @pytest.fixture
    def validator(self):
        return YearValidator()
    
    def test_valid_year(self, validator):
        passed, errors = validator.validate("2024")
        assert passed is True
    
    def test_invalid_year_too_old(self, validator):
        passed, errors = validator.validate("1990")
        assert passed is False
    
    def test_invalid_year_string(self, validator):
        passed, errors = validator.validate("abc")
        assert passed is False


class TestCurrencyValidator:
    """Testes para CurrencyValidator."""
    
    @pytest.fixture
    def validator(self):
        return CurrencyValidator()
    
    def test_valid_positive_value(self, validator):
        passed, errors = validator.validate(1500.50)
        assert passed is True
    
    def test_invalid_negative_value(self, validator):
        passed, errors = validator.validate(-100.0)
        assert passed is False
    
    def test_allows_zero(self, validator):
        passed, errors = validator.validate(0.0)
        assert passed is True
    
    def test_allows_negative_when_configured(self):
        validator = CurrencyValidator(allow_negative=True)
        passed, errors = validator.validate(-100.0)
        assert passed is True


class TestDateValidator:
    """Testes para DateValidator."""
    
    @pytest.fixture
    def validator(self):
        return DateValidator()
    
    def test_valid_date(self, validator):
        passed, errors = validator.validate("15/06/2023")
        assert passed is True
    
    def test_invalid_format(self, validator):
        passed, errors = validator.validate("2023-06-15")
        assert passed is False
    
    def test_invalid_date(self, validator):
        passed, errors = validator.validate("32/13/2023")
        assert passed is False


class TestStateValidator:
    """Testes para StateValidator."""
    
    @pytest.fixture
    def validator(self):
        return StateValidator()
    
    def test_valid_state(self, validator):
        passed, errors = validator.validate("SP")
        assert passed is True
    
    def test_invalid_state(self, validator):
        passed, errors = validator.validate("XX")
        assert passed is False
    
    def test_case_insensitive(self, validator):
        passed, errors = validator.validate("sp")
        assert passed is True


class TestSectionCoverageCalculator:
    """Testes para SectionCoverageCalculator."""
    
    @pytest.fixture
    def calculator(self):
        return SectionCoverageCalculator()
    
    def test_full_coverage(self, calculator):
        detected = {"taxpayer_identification", "assets_declaration"}
        extracted_data = {
            "taxpayer_identification": {"cpf": "123.456.789-00", "name": "Test"},
            "assets_declaration": {"items": [{"id": "1"}]}
        }
        
        coverage, sections = calculator.calculate(detected, extracted_data)
        
        assert coverage == 1.0
        assert sections["taxpayer_identification"].extracted is True
        assert sections["assets_declaration"].extracted is True
    
    def test_partial_coverage(self, calculator):
        detected = {"taxpayer_identification", "assets_declaration", "exempt_income"}
        extracted_data = {
            "taxpayer_identification": {"cpf": "123.456.789-00"},
            "assets_declaration": {"items": [{"id": "1"}]},
            "exempt_income": None
        }
        
        coverage, sections = calculator.calculate(detected, extracted_data)
        
        assert coverage < 1.0
        assert sections["exempt_income"].extracted is False


class TestCrossValidationCalculator:
    """Testes para CrossValidationCalculator."""
    
    @pytest.fixture
    def calculator(self):
        return CrossValidationCalculator()
    
    def test_valid_data_high_score(self, calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "529.982.247-25",
                "exercise_year": "2024",
                "calendar_year": "2023"
            },
            "assets_declaration": {
                "items": [
                    {"current_year_asset_value": 100000},
                    {"current_year_asset_value": 50000}
                ],
                "current_year_total_value": 150000
            }
        }
        
        score, results = calculator.calculate(data)
        
        assert score >= 0.8
    
    def test_invalid_cpf_penalty(self, calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "111.111.111-11",
            }
        }
        
        score, results = calculator.calculate(data)
        
        cpf_result = next((r for r in results if r.validation_name == "cpf_valid"), None)
        assert cpf_result is not None
        assert cpf_result.passed is False
    
    def test_year_inconsistency(self, calculator):
        data = {
            "taxpayer_identification": {
                "cpf": "529.982.247-25",
                "exercise_year": "2024",
                "calendar_year": "2022"
            }
        }
        
        score, results = calculator.calculate(data)
        
        year_result = next((r for r in results if r.validation_name == "year_consistency"), None)
        assert year_result is not None
        assert year_result.passed is False


class TestReviewFlagGenerator:
    """Testes para ReviewFlagGenerator."""
    
    @pytest.fixture
    def generator(self):
        return ReviewFlagGenerator()
    
    def test_critical_flag_for_low_confidence(self, generator):
        flags = generator.generate(
            overall_confidence=0.3,
            coverage_score=0.5,
            validation_score=0.5,
            section_scores={},
            validation_results=[],
            extracted_data={}
        )
        
        critical_flags = [f for f in flags if f.severity == "critical"]
        assert len(critical_flags) > 0
    
    def test_missing_cpf_flag(self, generator):
        flags = generator.generate(
            overall_confidence=0.8,
            coverage_score=1.0,
            validation_score=1.0,
            section_scores={},
            validation_results=[],
            extracted_data={"taxpayer_identification": {}}
        )
        
        cpf_flags = [f for f in flags if "CPF" in f.message]
        assert len(cpf_flags) > 0


class TestDeclarationConfidenceCalculator:
    """Testes para DeclarationConfidenceCalculator."""
    
    @pytest.fixture
    def calculator(self):
        return DeclarationConfidenceCalculator()
    
    def test_complete_document_high_confidence(self, calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "52998224725",
                "cpf": "529.982.247-25",
                "name": "JOAO DA SILVA",
                "exercise_year": "2024",
                "calendar_year": "2023"
            },
            "assets_declaration": {
                "items": [
                    {"current_year_asset_value": 100000, "before_year_asset_value": 80000}
                ],
                "current_year_total_value": 100000,
                "last_year_total_value": 80000
            },
            "income_from_legal_person_to_holder": {
                "items": [{"income_from_legal_person": 50000, "cpf_cnpj": "11.222.333/0001-81"}],
                "total_values": {"income_from_legal_person": {"amount": 50000, "valid": True}}
            }
        }
        
        result = calculator.calculate(
            data,
            extraction_method="digital",
            detected_sections={"taxpayer_identification", "assets_declaration", "income_from_legal_person_to_holder"}
        )
        
        assert result.overall >= 0.7
        assert result.coverage_score >= 0.8
    
    def test_incomplete_document_lower_confidence(self, calculator):
        data = {
            "taxpayer_identification": {
                "normalized_cpf": "52998224725",
                "name": "TEST"
            }
        }
        
        result = calculator.calculate(
            data,
            extraction_method="digital",
            detected_sections={"taxpayer_identification", "assets_declaration", "exempt_income"}
        )
        
        assert result.overall < 0.8
        assert result.coverage_score < 1.0
        assert len(result.review_flags) > 0
    
    def test_confidence_result_has_all_fields(self, calculator):
        result = calculator.calculate(
            {"taxpayer_identification": {"cpf": "123", "name": "Test"}},
            extraction_method="digital"
        )
        
        assert hasattr(result, "overall")
        assert hasattr(result, "coverage_score")
        assert hasattr(result, "validation_score")
        assert hasattr(result, "section_scores")
        assert hasattr(result, "review_flags")
        assert hasattr(result, "needs_review")
    
    def test_to_dict_serialization(self, calculator):
        result = calculator.calculate(
            {"taxpayer_identification": {"cpf": "529.982.247-25", "name": "Test"}},
            extraction_method="digital"
        )
        
        result_dict = result.to_dict()
        
        assert "overall" in result_dict
        assert "coverage_score" in result_dict
        assert "validation_score" in result_dict
        assert "section_scores" in result_dict
        assert "review_flags" in result_dict
        assert "needs_review" in result_dict
