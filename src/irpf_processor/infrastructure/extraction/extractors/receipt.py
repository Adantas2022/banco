"""Extrator de dados do recibo de entrega IRPF."""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..field_extractors import normalize_cpf


@dataclass
class ReceiptData:
    """Dados do recibo de entrega IRPF."""

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
    tax_due: float = 0.0
    tax_refund: float = 0.0
    refund_bank_code: str = ""
    refund_bank_name: str = ""
    refund_agency: str = ""
    refund_account: str = ""
    refund_pix: str = ""
    rectifying: bool = False
    rectified_receipt: str = ""
    control_line: str = ""

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
            "tax_due": self.tax_due,
            "tax_refund": self.tax_refund,
            "refund_bank_code": self.refund_bank_code,
            "refund_bank_name": self.refund_bank_name,
            "refund_agency": self.refund_agency,
            "refund_account": self.refund_account,
            "refund_pix": self.refund_pix,
            "rectifying": self.rectifying,
            "rectified_receipt": self.rectified_receipt,
            "control_line": self.control_line,
        }


class ReceiptExtractor(ISectionExtractor):
    """Extrai dados do recibo de entrega da declaração IRPF."""

    PATTERNS = {
        "receipt_number": r"(?:RECIBO\s*(?:DE\s*ENTREGA)?|N[ºo°]\s*(?:do\s*)?Recibo)[:\s]*(\d+[.\-]?\d*)",
        "transmission_datetime": r"(?:em|recebida\s*via\s*Internet.*?em|Transmitid[oa]|Entregue)\s*(\d{2}[/\-]\d{2}[/\-]\d{4})\s*(?:[àa]s?)?\s*(\d{2}:\d{2}(?::\d{2})?)",
        "cpf_line": r"(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]+?)(?:\s*\(\d|\n|$)",
        "cpf": r"CPF[:\s]*(?:do\s*declarante)?[:\s]*(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})",
        "name": r"(?:Nome\s*do\s*declarante|NOME|Nome|Contribuinte)[:\s\n]*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]+?)(?:\n|Telefone|CPF|Exerc|Endere)",
        "exercise_year": r"EXERC[ÍI]CIO\s*(\d{4})",
        "calendar_year": r"ANO[- ]CALEND[ÁA]RIO\s*(\d{4})",
        "declaration_type": r"(?:Tipo|DECLARA[ÇC][ÃA]O)[:\s]*(.+?)(?:\n|Modelo|IDENTIFICA)",
        "tax_due": r"(?:IMPOSTO\s*A\s*PAGAR|SALDO\s*DO\s*IMPOSTO\s*A\s*PAGAR)[:\s]*R?\$?\s*([\d.,]+)",
        "tax_refund": r"(?:IMPOSTO\s*A\s*RESTITUIR)[:\s]*R?\$?\s*([\d.,]+)",
        "refund_bank": r"(?:C[ÓO]DIGO\s*DO\s*BANCO|Banco|Institui[çc][ãa]o)[:\s]*(\d{3})",
        "refund_agency": r"(?:AG[ÊE]NCIA\s*BANC[ÁA]RIA|Ag[êe]ncia)[:\s]*(\d+[-\dX]*)",
        "refund_account": r"(?:CONTA\s*PARA\s*CR[ÉE]DITO|Conta)[:\s]*(\d+[-\dX]*)",
        "refund_pix": r"(?:chave\s*PIX|PIX)[:\s]*(.+?)(?:\n|$)",
        "rectifying": r"(?:RETIFICADORA|Declara[çc][ãa]o\s*Retificadora)",
        "rectified_receipt": r"Recibo\s*(?:da\s*)?(?:Declara[çc][ãa]o\s*)?Retificad[oa][:\s]*(\d+)",
        "control_line": r"(\d{10,})\s*$",
    }

    RECEIPT_MARKERS = [
        "RECIBO DE ENTREGA",
        "RECIBO DA DECLARAÇÃO",
        "RECIBO DECLARAÇÃO",
        "COMPROVANTE DE ENTREGA",
        "DECLARAÇÃO TRANSMITIDA",
        "TRANSMISSÃO DA DECLARAÇÃO",
        "Nº do Recibo",
        "Número do Recibo",
    ]

    @property
    def section_name(self) -> str:
        return "receipt"

    def can_extract(self, context: ExtractionContext) -> bool:
        text_upper = context.full_text.upper()
        for marker in self.RECEIPT_MARKERS:
            if marker.upper() in text_upper:
                return True
        return False

    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        data = ReceiptData()
        text = context.full_text

        receipt_match = re.search(self.PATTERNS["receipt_number"], text, re.IGNORECASE)
        if receipt_match:
            data.receipt_number = receipt_match.group(1).replace(".", "").replace("-", "")

        datetime_match = re.search(self.PATTERNS["transmission_datetime"], text, re.IGNORECASE)
        if datetime_match:
            data.transmission_date = datetime_match.group(1)
            data.transmission_time = datetime_match.group(2)
            data.transmission_datetime = f"{data.transmission_date} {data.transmission_time}"

        cpf_line_match = re.search(self.PATTERNS["cpf_line"], text, re.MULTILINE)
        if cpf_line_match:
            data.cpf = cpf_line_match.group(1)
            data.normalized_cpf = normalize_cpf(data.cpf)
            data.taxpayer_name = cpf_line_match.group(2).strip()
        else:
            cpf_match = re.search(self.PATTERNS["cpf"], text, re.IGNORECASE)
            if cpf_match:
                data.cpf = cpf_match.group(1)
                data.normalized_cpf = normalize_cpf(data.cpf)

            name_match = re.search(self.PATTERNS["name"], text)
            if name_match:
                data.taxpayer_name = name_match.group(1).strip()

        exercise_match = re.search(self.PATTERNS["exercise_year"], text, re.IGNORECASE)
        if exercise_match:
            data.exercise_year = exercise_match.group(1)

        calendar_match = re.search(self.PATTERNS["calendar_year"], text, re.IGNORECASE)
        if calendar_match:
            data.calendar_year = calendar_match.group(1)

        type_match = re.search(self.PATTERNS["declaration_type"], text, re.IGNORECASE)
        if type_match:
            data.declaration_type = type_match.group(1).strip()

        data.tax_due = self._extract_monetary_value(text, "tax_due")
        data.tax_refund = self._extract_monetary_value(text, "tax_refund")

        bank_match = re.search(self.PATTERNS["refund_bank"], text, re.IGNORECASE)
        if bank_match:
            data.refund_bank_code = bank_match.group(1)

        agency_match = re.search(self.PATTERNS["refund_agency"], text, re.IGNORECASE)
        if agency_match:
            data.refund_agency = agency_match.group(1)

        account_match = re.search(self.PATTERNS["refund_account"], text, re.IGNORECASE)
        if account_match:
            data.refund_account = account_match.group(1)

        pix_match = re.search(self.PATTERNS["refund_pix"], text, re.IGNORECASE)
        if pix_match:
            data.refund_pix = pix_match.group(1).strip()

        data.rectifying = bool(re.search(self.PATTERNS["rectifying"], text, re.IGNORECASE))

        if data.rectifying:
            rect_match = re.search(self.PATTERNS["rectified_receipt"], text, re.IGNORECASE)
            if rect_match:
                data.rectified_receipt = rect_match.group(1)

        control_match = re.search(self.PATTERNS["control_line"], text, re.IGNORECASE)
        if control_match:
            data.control_line = control_match.group(1)

        return data.to_dict()

    def _extract_monetary_value(self, text: str, pattern_key: str) -> float:
        pattern = self.PATTERNS.get(pattern_key)
        if not pattern:
            return 0.0

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value_str = match.group(1)
            value_str = value_str.replace(".", "").replace(",", ".")
            try:
                return float(value_str)
            except ValueError:
                return 0.0
        return 0.0


def is_receipt_document(text: str) -> bool:
    """Verifica se o texto representa um recibo de IRPF."""
    text_upper = text.upper()
    for marker in ReceiptExtractor.RECEIPT_MARKERS:
        if marker.upper() in text_upper:
            if "DECLARAÇÃO DE AJUSTE ANUAL" not in text_upper:
                return True
            receipt_pos = text_upper.find(marker.upper())
            decl_pos = text_upper.find("DECLARAÇÃO DE AJUSTE ANUAL")
            if receipt_pos < decl_pos or decl_pos == -1:
                return True
    return False
