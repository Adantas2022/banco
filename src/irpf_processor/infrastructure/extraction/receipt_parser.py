"""Parser para recibos de entrega IRPF."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

from irpf_processor.shared.logging import get_logger
from irpf_processor.domain.services import ConfidenceCalculatorFactory, ConfidenceResult

from .extractors import ExtractionContext, ReceiptExtractor
from .version_detector import VersionDetector, DocumentProfile

logger = get_logger(__name__)


@dataclass
class IRPFReceiptResult:
    """Resultado da extração de um recibo de entrega IRPF."""

    receipt_number: str = ""
    transmission_datetime: str = ""
    transmission_date: str = ""
    transmission_time: str = ""
    cpf: str = ""
    normalized_cpf: str = ""
    taxpayer_name: str = ""
    exercise_year: str = ""
    calendar_year: str = ""
    declaration_type: str = ""
    total_taxable_income: float = 0.0
    tax_due: float = 0.0
    tax_refund: float = 0.0
    tax_to_pay: float = 0.0
    refund_bank_code: str = ""
    refund_bank_name: str = ""
    refund_agency: str = ""
    refund_account: str = ""
    refund_pix: str = ""
    rectifying: bool = False
    rectified_receipt: str = ""
    control_line: str = ""
    total_pages: int = 0
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "receipt_number": self.receipt_number,
            "transmission_datetime": self.transmission_datetime,
            "transmission_date": self.transmission_date,
            "transmission_time": self.transmission_time,
            "cpf": self.cpf,
            "normalized_cpf": self.normalized_cpf,
            "taxpayer_name": self.taxpayer_name,
            "exercise_year": self.exercise_year,
            "calendar_year": self.calendar_year,
            "declaration_type": self.declaration_type,
            "total_taxable_income": self.total_taxable_income,
            "tax_due": self.tax_due,
            "tax_refund": self.tax_refund,
            "tax_to_pay": self.tax_to_pay,
            "refund_bank_code": self.refund_bank_code,
            "refund_bank_name": self.refund_bank_name,
            "refund_agency": self.refund_agency,
            "refund_account": self.refund_account,
            "refund_pix": self.refund_pix,
            "rectifying": self.rectifying,
            "rectified_receipt": self.rectified_receipt,
            "control_line": self.control_line,
            "total_pages": self.total_pages,
        }


class ReceiptParser:
    """Parser específico para recibos de entrega IRPF."""

    def __init__(self):
        self._extractor = ReceiptExtractor()
        self._pdfplumber = None
        self._last_profile: Optional[DocumentProfile] = None
        self._last_context: Optional[ExtractionContext] = None

    @property
    def last_extraction_context(self) -> Optional[ExtractionContext]:
        """Retorna o ExtractionContext do último documento processado.
        
        Permite acesso aos textos (full_text, pages_text) usados na
        aplicação de REGEX durante a extração.
        """
        return self._last_context

    def _ensure_pdfplumber(self):
        if self._pdfplumber is None:
            import pdfplumber
            self._pdfplumber = pdfplumber

    def parse(self, pdf_source: Union[str, Path, bytes]) -> IRPFReceiptResult:
        """Parseia recibo de entrega IRPF."""
        context = self._create_context(pdf_source)
        self._last_context = context
        result = IRPFReceiptResult(total_pages=context.total_pages)

        data = self._extractor.extract(context)
        if data:
            self._assign_to_result(data, result)

        result.warnings = context.warnings
        result.confidence = self._calculate_confidence(result)

        return result

    def parse_from_text(
        self, 
        text: str, 
        total_pages: int = 1,
        ocr_confidence: float | None = None,
    ) -> IRPFReceiptResult:
        context = ExtractionContext(
            full_text=text,
            pages_text={1: text},
            total_pages=total_pages
        )
        self._last_context = context
        result = IRPFReceiptResult(total_pages=total_pages)

        data = self._extractor.extract(context)
        if data:
            self._assign_to_result(data, result)

        result.warnings = context.warnings
        result.confidence = self._calculate_confidence(
            result, 
            extraction_method="ocr",
            ocr_confidence=ocr_confidence,
        )

        return result

    def _create_context(self, pdf_source: Union[str, Path, bytes]) -> ExtractionContext:
        self._ensure_pdfplumber()

        if isinstance(pdf_source, bytes):
            import io
            pdf_file = io.BytesIO(pdf_source)
        else:
            pdf_file = pdf_source

        full_text = ""
        pages_text: dict[int, str] = {}
        total_pages = 0

        with self._pdfplumber.open(pdf_file) as pdf:
            total_pages = len(pdf.pages)
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text() or ""
                pages_text[page_num] = page_text
                full_text += page_text + "\n"

        return ExtractionContext(
            full_text=full_text,
            pages_text=pages_text,
            total_pages=total_pages
        )

    def _assign_to_result(self, data: dict[str, Any], result: IRPFReceiptResult) -> None:
        for key, value in data.items():
            if hasattr(result, key):
                setattr(result, key, value)

    def _calculate_confidence(
        self,
        result: IRPFReceiptResult,
        extraction_method: str = "digital",
        ocr_confidence: float | None = None,
    ) -> float:
        calculator = ConfidenceCalculatorFactory.for_receipt(
            use_ocr=(extraction_method == "ocr")
        )
        
        confidence_result = calculator.calculate(
            extracted_data=result.to_dict(),
            extraction_method=extraction_method,
            ocr_confidence=ocr_confidence,
        )
        
        self._last_confidence_result = confidence_result
        return confidence_result.overall
    
    def get_confidence_details(self) -> ConfidenceResult | None:
        return getattr(self, "_last_confidence_result", None)
