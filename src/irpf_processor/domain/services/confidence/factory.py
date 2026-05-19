"""Factory for confidence calculators."""

from typing import Literal, Optional

from irpf_processor.domain.enums import DocumentCategory

from .interface import IConfidenceCalculator
from .declaration_calculator import DeclarationConfidenceCalculator
from .receipt_calculator import ReceiptConfidenceCalculator
from .ocr_calculator import OcrConfidenceCalculator


class ConfidenceCalculatorFactory:
    """Factory for creating confidence calculators based on document type."""

    _declaration_calculator: Optional[DeclarationConfidenceCalculator] = None
    _receipt_calculator: Optional[ReceiptConfidenceCalculator] = None

    @classmethod
    def get_calculator(
        cls,
        document_category: DocumentCategory,
        extraction_method: Literal["digital", "ocr", "mixed"] = "digital",
    ) -> IConfidenceCalculator:
        base_calculator = cls._get_base_calculator(document_category)

        if extraction_method in ("ocr", "mixed"):
            return OcrConfidenceCalculator(base_calculator)

        return base_calculator

    @classmethod
    def _get_base_calculator(
        cls,
        document_category: DocumentCategory,
    ) -> IConfidenceCalculator:
        if document_category == DocumentCategory.RECIBO:
            if cls._receipt_calculator is None:
                cls._receipt_calculator = ReceiptConfidenceCalculator()
            return cls._receipt_calculator

        if cls._declaration_calculator is None:
            cls._declaration_calculator = DeclarationConfidenceCalculator()
        return cls._declaration_calculator

    @classmethod
    def for_declaration(
        cls,
        use_ocr: bool = False,
    ) -> IConfidenceCalculator:
        return cls.get_calculator(
            DocumentCategory.DECLARACAO,
            extraction_method="ocr" if use_ocr else "digital",
        )

    @classmethod
    def for_receipt(
        cls,
        use_ocr: bool = False,
    ) -> IConfidenceCalculator:
        return cls.get_calculator(
            DocumentCategory.RECIBO,
            extraction_method="ocr" if use_ocr else "digital",
        )

    @classmethod
    def reset(cls) -> None:
        cls._declaration_calculator = None
        cls._receipt_calculator = None
