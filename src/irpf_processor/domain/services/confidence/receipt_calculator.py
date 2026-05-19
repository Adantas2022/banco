"""Confidence calculator for IRPF receipts."""

from typing import Any, Literal

from .interface import IConfidenceCalculator, ConfidenceResult


class ReceiptConfidenceCalculator(IConfidenceCalculator):
    """Calculates confidence for IRPF receipt documents."""

    FIELD_WEIGHTS = {
        "normalized_cpf": 1.0,
        "taxpayer_name": 1.0,
        "exercise_year": 0.9,
        "calendar_year": 0.8,
        "transmission_datetime": 0.8,
        "receipt_number": 0.7,
        "tax_refund": 0.6,
        "tax_due": 0.6,
        "refund_bank_code": 0.5,
        "refund_pix": 0.5,
        "control_line": 0.4,
    }

    REQUIRED_FIELDS = [
        "normalized_cpf",
        "taxpayer_name",
        "exercise_year",
    ]

    OPTIONAL_FIELDS = [
        "calendar_year",
        "transmission_datetime",
        "receipt_number",
        "tax_refund",
        "tax_due",
        "refund_bank_code",
        "refund_pix",
        "control_line",
    ]

    @property
    def document_type(self) -> str:
        return "RECIBO"

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

        for field_name, weight in self.FIELD_WEIGHTS.items():
            value = extracted_data.get(field_name)
            has_value = self._has_meaningful_value(value, field_name)

            if has_value:
                field_scores[field_name] = 1.0
                weighted_sum += weight
            else:
                field_scores[field_name] = 0.0

            if field_name in self.REQUIRED_FIELDS:
                weight_total += weight
            elif has_value:
                weight_total += weight

        if weight_total == 0:
            overall = 0.0
        else:
            overall = weighted_sum / weight_total

        if extraction_method == "ocr":
            ocr_penalty = kwargs.get("ocr_penalty", 0.15)
            penalties["ocr_extraction"] = ocr_penalty
            overall = overall * (1 - ocr_penalty)
        elif extraction_method == "mixed":
            mixed_penalty = kwargs.get("mixed_penalty", 0.08)
            penalties["mixed_extraction"] = mixed_penalty
            overall = overall * (1 - mixed_penalty)

        ocr_confidence = kwargs.get("ocr_confidence")
        if ocr_confidence is not None and ocr_confidence < overall:
            overall = min(overall, ocr_confidence)
            penalties["ocr_quality_cap"] = overall - ocr_confidence

        if extracted_data.get("transmission_datetime"):
            bonuses["has_datetime"] = 0.02
            overall = min(1.0, overall + 0.02)

        has_refund_info = (
            extracted_data.get("refund_bank_code") or 
            extracted_data.get("refund_pix")
        )
        if has_refund_info and extracted_data.get("tax_refund", 0) > 0:
            bonuses["complete_refund_info"] = 0.03
            overall = min(1.0, overall + 0.03)

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

    def _has_meaningful_value(self, value: Any, field_name: str) -> bool:
        if value is None:
            return False

        if field_name in ("tax_refund", "tax_due"):
            return isinstance(value, (int, float)) and value > 0

        if isinstance(value, str):
            return len(value.strip()) > 0

        if isinstance(value, (list, dict)):
            return len(value) > 0

        if isinstance(value, bool):
            return True

        if isinstance(value, (int, float)):
            return True

        return bool(value)
