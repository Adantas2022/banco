"""Calculador de confianca profissional para declaracoes IRPF."""

from typing import Any, Literal

from .interface import IConfidenceCalculator, ConfidenceResult
from .models import SectionConfidence, ReviewFlag, ValidationResult
from .section_calculator import SectionCoverageCalculator
from .cross_validator import CrossValidationCalculator
from .review_flags import ReviewFlagGenerator
from .validators import get_validator_for_field


class DeclarationConfidenceCalculator(IConfidenceCalculator):
    """Calculador de confianca composto para declaracoes IRPF."""
    
    WEIGHT_FIELD_SCORE = 0.25
    WEIGHT_COVERAGE_SCORE = 0.35
    WEIGHT_VALIDATION_SCORE = 0.30
    WEIGHT_METHOD_FACTOR = 0.10
    
    METHOD_FACTORS = {
        "digital": 1.0,
        "mixed": 0.95,
        "ocr": 0.90,
    }
    
    FIELD_WEIGHTS = {
        "taxpayer_identification.normalized_cpf": 1.0,
        "taxpayer_identification.name": 1.0,
        "taxpayer_identification.exercise_year": 0.8,
        "taxpayer_identification.calendar_year": 0.8,
        "assets_declaration": 0.9,
        "income_from_legal_person_to_holder": 0.9,
        "exempt_income": 0.7,
        "exclusive_taxation_income": 0.7,
        "debts_and_encumbrances": 0.6,
        "payments_made": 0.8,
        "donations_made": 0.5,
    }
    
    REQUIRED_FIELDS = [
        "taxpayer_identification.normalized_cpf",
        "taxpayer_identification.name",
    ]
    
    OPTIONAL_FIELDS = [
        "taxpayer_identification.exercise_year",
        "taxpayer_identification.calendar_year",
        "assets_declaration",
        "income_from_legal_person_to_holder",
        "exempt_income",
        "exclusive_taxation_income",
        "debts_and_encumbrances",
        "payments_made",
        "donations_made",
    ]
    
    def __init__(self):
        self._section_calculator = SectionCoverageCalculator()
        self._cross_validator = CrossValidationCalculator()
        self._flag_generator = ReviewFlagGenerator()
    
    @property
    def document_type(self) -> str:
        return "DECLARACAO"
    
    def calculate(
        self,
        extracted_data: dict[str, Any],
        extraction_method: Literal["digital", "ocr", "mixed"] = "digital",
        **kwargs: Any,
    ) -> ConfidenceResult:
        detected_sections = kwargs.get("detected_sections", set())
        ocr_confidence = kwargs.get("ocr_confidence")
        
        field_score, field_scores = self._calculate_field_confidence(extracted_data)
        
        coverage_score, section_scores = self._section_calculator.calculate(
            detected_sections, extracted_data
        )
        
        validation_score, validation_results = self._cross_validator.calculate(extracted_data)
        
        method_factor = self.METHOD_FACTORS.get(extraction_method, 1.0)
        
        overall = (
            self.WEIGHT_FIELD_SCORE * field_score +
            self.WEIGHT_COVERAGE_SCORE * coverage_score +
            self.WEIGHT_VALIDATION_SCORE * validation_score +
            self.WEIGHT_METHOD_FACTOR * method_factor
        )
        
        penalties: dict[str, float] = {}
        bonuses: dict[str, float] = {}
        
        if extraction_method == "ocr":
            penalties["ocr_extraction"] = 0.10
        elif extraction_method == "mixed":
            penalties["mixed_extraction"] = 0.05
        
        if ocr_confidence is not None and ocr_confidence < overall:
            overall = min(overall, ocr_confidence)
            penalties["ocr_quality_cap"] = overall - ocr_confidence
        
        taxpayer = extracted_data.get("taxpayer_identification", {})
        if taxpayer.get("contact_and_address", {}).get("email"):
            bonuses["has_email"] = 0.02
            overall = min(1.0, overall + 0.02)
        
        review_flags = self._flag_generator.generate(
            overall_confidence=overall,
            coverage_score=coverage_score,
            validation_score=validation_score,
            section_scores=section_scores,
            validation_results=validation_results,
            extracted_data=extracted_data
        )
        
        needs_review = any(f.severity in ("error", "critical") for f in review_flags)
        
        return ConfidenceResult(
            overall=overall,
            extraction_method=extraction_method,
            coverage_score=coverage_score,
            validation_score=validation_score,
            field_scores=field_scores,
            section_scores=section_scores,
            validation_results=validation_results,
            review_flags=review_flags,
            needs_review=needs_review,
            penalties=penalties,
            bonuses=bonuses,
            details={
                "field_score": field_score,
                "coverage_score": coverage_score,
                "validation_score": validation_score,
                "method_factor": method_factor,
                "fields_found": sum(1 for s in field_scores.values() if s > 0),
                "fields_total": len(field_scores),
                "sections_detected": len([s for s in section_scores.values() if s.detected]),
                "sections_extracted": len([s for s in section_scores.values() if s.extracted]),
                "validations_passed": len([v for v in validation_results if v.passed]),
                "validations_total": len(validation_results),
                "review_flags_count": len(review_flags),
                "critical_flags": len([f for f in review_flags if f.severity == "critical"]),
            },
        )
    
    def _calculate_field_confidence(
        self,
        extracted_data: dict[str, Any]
    ) -> tuple[float, dict[str, float]]:
        """Calcula confianca baseada em campos individuais."""
        field_scores: dict[str, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0
        
        for field_path, weight in self.FIELD_WEIGHTS.items():
            value = self._get_nested_value(extracted_data, field_path)
            has_value = self._has_meaningful_value(value)
            
            score = 0.0
            if has_value:
                score = 1.0
                
                validator = get_validator_for_field(field_path)
                if validator:
                    passed, _ = validator.validate(value)
                    if not passed:
                        score = 0.5
            
            field_scores[field_path] = score
            
            weight_total += weight
            weighted_sum += score * weight
        
        overall = weighted_sum / weight_total if weight_total > 0 else 0.0
        
        return overall, field_scores
    
    def get_required_fields(self) -> list[str]:
        return self.REQUIRED_FIELDS.copy()
    
    def get_optional_fields(self) -> list[str]:
        return self.OPTIONAL_FIELDS.copy()
    
    def _get_nested_value(self, data: dict, path: str) -> Any:
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def _has_meaningful_value(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return len(value.strip()) > 0 and value != "N/A"
        if isinstance(value, (list, dict)):
            return len(value) > 0
        if isinstance(value, (int, float)):
            return True
        return bool(value)
