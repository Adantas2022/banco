"""Confidence calculator for IRPF declarations."""

from typing import Any, Literal

from .interface import IConfidenceCalculator, ConfidenceResult


class DeclarationConfidenceCalculator(IConfidenceCalculator):
    """Calculates confidence for IRPF declaration documents."""

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
    ]

    @property
    def document_type(self) -> str:
        return "DECLARACAO"

    def calculate(
        self,
        extracted_data: dict[str, Any],
        extraction_method: Literal["digital", "ocr", "mixed"] = "digital",
        **kwargs: Any,
    ) -> ConfidenceResult:
        field_scores: dict[str, float] = {}
        penalties: dict[str, float] = {}
        bonuses: dict[str, float] = {}
        weighted_sum = 0.0
        weight_total = 0.0

        for field_path, weight in self.FIELD_WEIGHTS.items():
            value = self._get_nested_value(extracted_data, field_path)
            has_value = self._has_meaningful_value(value)

            if has_value:
                field_scores[field_path] = 1.0
                weighted_sum += weight
            else:
                field_scores[field_path] = 0.0

            if field_path in self.REQUIRED_FIELDS:
                weight_total += weight
            elif has_value:
                weight_total += weight

        if weight_total == 0:
            overall = 0.0
        else:
            overall = weighted_sum / weight_total

        if extraction_method == "ocr":
            ocr_penalty = kwargs.get("ocr_penalty", 0.10)
            penalties["ocr_extraction"] = ocr_penalty
            overall = overall * (1 - ocr_penalty)
        elif extraction_method == "mixed":
            mixed_penalty = kwargs.get("mixed_penalty", 0.05)
            penalties["mixed_extraction"] = mixed_penalty
            overall = overall * (1 - mixed_penalty)

        ocr_confidence = kwargs.get("ocr_confidence")
        if ocr_confidence is not None and ocr_confidence < overall:
            overall = min(overall, ocr_confidence)
            penalties["ocr_quality_cap"] = overall - ocr_confidence

        taxpayer = extracted_data.get("taxpayer_identification", {})
        if taxpayer.get("contact_and_address", {}).get("email"):
            bonuses["has_email"] = 0.02
            overall = min(1.0, overall + 0.02)

        return ConfidenceResult(
            overall=overall,
            extraction_method=extraction_method,
            field_scores=field_scores,
            penalties=penalties,
            bonuses=bonuses,
            details={
                "weighted_sum": weighted_sum,
                "weight_total": weight_total,
                "fields_found": sum(1 for s in field_scores.values() if s > 0),
                "fields_total": len(field_scores),
            },
        )

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
            return len(value.strip()) > 0
        if isinstance(value, (list, dict)):
            return len(value) > 0
        if isinstance(value, (int, float)):
            return True
        return bool(value)
