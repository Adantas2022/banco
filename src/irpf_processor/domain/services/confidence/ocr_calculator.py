"""OCR confidence calculator - decorator for base calculators."""

from __future__ import annotations

from typing import Any, Literal

from .interface import IConfidenceCalculator, ConfidenceResult
from .models import ReviewFlag


class OcrConfidenceCalculator(IConfidenceCalculator):
    """Decorator that applies OCR penalties to base calculator."""

    DEFAULT_OCR_PENALTY = 0.10
    DEFAULT_MIXED_PENALTY = 0.05
    MIN_OCR_QUALITY_THRESHOLD = 0.3
    MODERATE_OCR_QUALITY_THRESHOLD = 0.7
    CRITICAL_OCR_QUALITY_THRESHOLD = 0.5

    def __init__(
        self,
        base_calculator: IConfidenceCalculator,
        ocr_penalty: float = DEFAULT_OCR_PENALTY,
        mixed_penalty: float = DEFAULT_MIXED_PENALTY,
    ):
        self._base_calculator = base_calculator
        self._ocr_penalty = ocr_penalty
        self._mixed_penalty = mixed_penalty

    @property
    def document_type(self) -> str:
        return f"{self._base_calculator.document_type}_OCR"

    def calculate(
        self,
        extracted_data: dict[str, Any],
        extraction_method: Literal["digital", "ocr", "mixed"] = "ocr",
        **kwargs: Any,
    ) -> ConfidenceResult:
        base_result = self._base_calculator.calculate(
            extracted_data,
            extraction_method="digital",
            **kwargs,
        )

        penalties = dict(base_result.penalties)
        overall = base_result.overall

        if extraction_method == "ocr":
            penalties["ocr_extraction"] = self._ocr_penalty
            overall = overall * (1 - self._ocr_penalty)
        elif extraction_method == "mixed":
            penalties["mixed_extraction"] = self._mixed_penalty
            overall = overall * (1 - self._mixed_penalty)

        ocr_confidence = kwargs.get("ocr_confidence")
        if ocr_confidence is not None:
            if ocr_confidence < self.MIN_OCR_QUALITY_THRESHOLD:
                penalties["ocr_quality_very_low"] = 0.2
                overall = overall * 0.8

            if ocr_confidence < overall:
                cap_penalty = overall - ocr_confidence
                penalties["ocr_quality_cap"] = cap_penalty
                overall = ocr_confidence

        overall = max(0.0, min(1.0, overall))

        ocr_review_flags = self._generate_ocr_flags(
            extraction_method=extraction_method,
            ocr_confidence=ocr_confidence,
        )
        
        all_review_flags = list(base_result.review_flags) + ocr_review_flags
        
        needs_review = base_result.needs_review
        if ocr_confidence is not None and ocr_confidence < self.MODERATE_OCR_QUALITY_THRESHOLD:
            needs_review = True
        if extraction_method == "ocr":
            needs_review = True

        return ConfidenceResult(
            overall=overall,
            extraction_method=extraction_method,
            field_scores=base_result.field_scores,
            penalties=penalties,
            bonuses=base_result.bonuses,
            details={
                **base_result.details,
                "base_confidence": base_result.overall,
                "ocr_confidence": ocr_confidence,
                "ocr_penalty_applied": self._ocr_penalty if extraction_method == "ocr" else self._mixed_penalty,
            },
            coverage_score=base_result.coverage_score,
            validation_score=base_result.validation_score,
            section_scores=base_result.section_scores,
            review_flags=all_review_flags,
            validation_results=base_result.validation_results,
            needs_review=needs_review,
        )

    def _generate_ocr_flags(
        self,
        extraction_method: Literal["digital", "ocr", "mixed"],
        ocr_confidence: float | None,
    ) -> list[ReviewFlag]:
        flags: list[ReviewFlag] = []
        
        if extraction_method == "ocr":
            flags.append(ReviewFlag(
                severity="warning",
                message="Documento processado via OCR",
                suggestion="Validar CPF, CNPJ e valores monetarios manualmente",
            ))
        elif extraction_method == "mixed":
            flags.append(ReviewFlag(
                severity="warning",
                message="Documento parcialmente escaneado",
                suggestion="Verificar secoes extraidas via OCR",
            ))
        
        if ocr_confidence is not None:
            if ocr_confidence < self.CRITICAL_OCR_QUALITY_THRESHOLD:
                flags.append(ReviewFlag(
                    severity="critical",
                    message=f"Qualidade OCR muito baixa ({ocr_confidence:.0%})",
                    suggestion="Recomenda-se reprocessar com documento de melhor qualidade",
                ))
            elif ocr_confidence < self.MODERATE_OCR_QUALITY_THRESHOLD:
                flags.append(ReviewFlag(
                    severity="warning",
                    message=f"Qualidade OCR moderada ({ocr_confidence:.0%})",
                    suggestion="Verificar campos numericos e datas manualmente",
                ))
        
        return flags

    def get_required_fields(self) -> list[str]:
        return self._base_calculator.get_required_fields()

    def get_optional_fields(self) -> list[str]:
        return self._base_calculator.get_optional_fields()
