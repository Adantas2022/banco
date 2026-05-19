"""Extrator de dados do recibo de entrega IRPF."""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..field_extractors import normalize_cpf
from ..table_extractor import parse_currency


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
        }


BANK_CODES = {
    "001": "Banco do Brasil",
    "033": "Santander",
    "104": "Caixa Econômica Federal",
    "237": "Bradesco",
    "341": "Itaú",
    "356": "Banco Real",
    "389": "Mercantil do Brasil",
    "399": "HSBC",
    "422": "Safra",
    "453": "Rural",
    "633": "Rendimento",
    "652": "Itaú Unibanco",
    "745": "Citibank",
    "756": "Sicoob",
}


class ReceiptExtractor(ISectionExtractor):
    """Extrai dados do recibo de entrega da declaração IRPF."""

    PATTERNS = {
        "receipt_number_formatted": r"N[ÚU]MERO\s+DO\s+RECIBO.*?é[:\s]*\n?(\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\s*-\s*\d{2})",
        "receipt_number_dotted": r"(\d{2}\.\d{2}\.\d{2}\.\d{2}\.\d{2}\s*-\s*\d{2})",
        "receipt_number_numeric": r"^(\d{10,12})$",
        "receipt_number_legacy": r"(?:RECIBO\s*(?:DE\s*ENTREGA)?|N[ºo°]\s*(?:do\s*)?Recibo)[:\s]*(\d+[.\-]?\d*)",
        "transmission_datetime": r"(?:em|recebida\s*via\s*Internet.*?em|Transmitid[oa]|Entregue|apresentada\s*em)\s*(\d{2}[/\-]\d{2}[/\-]\d{4})\s*(?:[,àa]s?)?\s*(\d{2}:\d{2}(?::\d{2})?)",
        "cpf_line": r"(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]+?)(?:\s*\(\d|\n|$)",
        "cpf": r"CPF[:\s]*(?:do\s*declarante)?[:\s]*(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})",
        "cpf_standalone": r"(?:^|\n)(\d{3}\.\d{3}\.\d{3}-\d{2})(?:\s*$|\n)",
        "name": r"(?:Nome\s*do\s*declarante|NOME|Nome|Contribuinte)[:\s\n]*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]+?)(?:\n|Telefone|CPF|Exerc|Endere)",
        "name_ocr": r"Nome\s+do\s+declarante\n([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?)(?:\n|Telefone|$)",
        "name_sr": r"Sr\(a\)\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+?),\s*inscrito",
        "exercise_year": r"EXERC[ÍI]CIO\s*(\d{4})",
        "calendar_year": r"ANO[- ]CALEND[ÁA]RIO\s*(\d{4})",
        "declaration_type": r"(?:Tipo|DECLARA[ÇC][ÃA]O)[:\s]*(.+?)(?:\n|Modelo|IDENTIFICA)",
        "total_taxable_income": r"TOTAL\s*RENDIMENTOS\s*TRIBUT[ÁA]VEIS[:\s]*R?\$?\s*([\d.,]+)",
        "tax_due": r"IMPOSTO\s*DEVIDO\s+([\d.,]+)",
        "tax_due_pdfplumber": r"[\d.,]+\s*\n([\d.,]+)\nIMPOSTO\s*DEVIDO",
        "tax_refund": r"(?:IMPOSTO\s*A\s*RESTITUIR)[:\s]*R?\$?\s*([\d.,]+)",
        "tax_to_pay": r"(?:SALDO\s*DO\s*IMPOSTO\s*A\s*PAGAR|IMPOSTO\s*A\s*PAGAR)[:\s]*R?\$?\s*([\d.,]+)",
        "refund_bank": r"(?:C[ÓO]DIGO\s*DO\s*BANCO|Banco|Institui[çc][ãa]o)[:\s]*(\d{3})",
        "refund_agency": r"(?:AG[ÊE]NCIA\s*BANC[ÁA]RIA|Ag[êe]ncia)[:\s]*(\d+[-\dX]*)",
        "refund_account": r"(?:CONTA\s*PARA\s*CR[ÉE]DITO|Conta)[:\s]*(\d+[-\dX]*)",
        "refund_account_alt": r"([\d]+-[\dX]+)\s*\n\s*CONTA\s*PARA\s*CR[ÉE]DITO",
        "refund_pix": r"(?:chave\s*PIX|PIX)[:\s]*(.+?)(?:\n|$)",
        "rectifying": r"(?:RETIFICADORA|Declara[çc][ãa]o\s*Retificadora)",
        "rectified_receipt": r"Recibo\s*(?:da\s*)?(?:Declara[çc][ãa]o\s*)?Retificad[oa][:\s]*(\d+)",
        "control_line": r"(?:^|\n)(\d{10,12})(?:\s*$|\n)",
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

        receipt_match = re.search(self.PATTERNS["receipt_number_formatted"], text, re.IGNORECASE | re.DOTALL)
        if receipt_match:
            data.receipt_number = receipt_match.group(1).strip()
        else:
            dotted_match = re.search(self.PATTERNS["receipt_number_dotted"], text)
            if dotted_match:
                data.receipt_number = dotted_match.group(1).strip()
            else:
                legacy_match = re.search(self.PATTERNS["receipt_number_legacy"], text, re.IGNORECASE)
                if legacy_match:
                    data.receipt_number = legacy_match.group(1).replace(".", "").replace("-", "")
                else:
                    for line in text.split("\n"):
                        line = line.strip()
                        numeric_match = re.match(self.PATTERNS["receipt_number_numeric"], line)
                        if numeric_match:
                            data.receipt_number = numeric_match.group(1)
                            break

        datetime_match = re.search(self.PATTERNS["transmission_datetime"], text, re.IGNORECASE)
        if datetime_match:
            data.transmission_date = datetime_match.group(1)
            data.transmission_time = datetime_match.group(2)
            data.transmission_datetime = f"{data.transmission_date} {data.transmission_time}"

        cpf_line_match = re.search(self.PATTERNS["cpf_line"], text, re.MULTILINE)
        invalid_names = {"ENDEREÇO", "ENDERECO", "TELEFONE", "NOME", "BAIRRO", "CEP", "UF", "MUNICÍPIO", "MUNICIPIO"}
        if cpf_line_match:
            data.cpf = cpf_line_match.group(1)
            data.normalized_cpf = normalize_cpf(data.cpf)
            candidate_name = cpf_line_match.group(2).strip()
            if candidate_name.upper() not in invalid_names:
                data.taxpayer_name = candidate_name

        if not data.cpf:
            cpf_match = re.search(self.PATTERNS["cpf"], text, re.IGNORECASE)
            if cpf_match:
                data.cpf = cpf_match.group(1)
                data.normalized_cpf = normalize_cpf(data.cpf)
            else:
                cpf_standalone = re.search(self.PATTERNS["cpf_standalone"], text, re.MULTILINE)
                if cpf_standalone:
                    data.cpf = cpf_standalone.group(1)
                    data.normalized_cpf = normalize_cpf(data.cpf)

        if not data.taxpayer_name:
            name_sr = re.search(self.PATTERNS["name_sr"], text, re.IGNORECASE)
            if name_sr:
                data.taxpayer_name = name_sr.group(1).strip()
            else:
                name_ocr = re.search(self.PATTERNS["name_ocr"], text, re.MULTILINE)
                if name_ocr:
                    data.taxpayer_name = name_ocr.group(1).strip()
                else:
                    name_match = re.search(self.PATTERNS["name"], text)
                    if name_match:
                        candidate = name_match.group(1).strip()
                        if candidate.upper() not in invalid_names:
                            data.taxpayer_name = candidate

        exercise_match = re.search(self.PATTERNS["exercise_year"], text, re.IGNORECASE)
        if exercise_match:
            data.exercise_year = exercise_match.group(1)

        calendar_match = re.search(self.PATTERNS["calendar_year"], text, re.IGNORECASE)
        if calendar_match:
            data.calendar_year = calendar_match.group(1)

        type_match = re.search(self.PATTERNS["declaration_type"], text, re.IGNORECASE)
        if type_match:
            data.declaration_type = type_match.group(1).strip()

        data.total_taxable_income = self._extract_monetary_value(text, "total_taxable_income")
        data.tax_due = self._extract_monetary_value_with_alt(text, "tax_due", "tax_due_pdfplumber")
        data.tax_refund = self._extract_monetary_value(text, "tax_refund")
        data.tax_to_pay = self._extract_monetary_value(text, "tax_to_pay")

        bank_match = re.search(self.PATTERNS["refund_bank"], text, re.IGNORECASE)
        if bank_match:
            data.refund_bank_code = bank_match.group(1)
            data.refund_bank_name = BANK_CODES.get(data.refund_bank_code, "")

        agency_match = re.search(self.PATTERNS["refund_agency"], text, re.IGNORECASE)
        if agency_match:
            data.refund_agency = agency_match.group(1)

        account_match = re.search(self.PATTERNS["refund_account"], text, re.IGNORECASE)
        if account_match:
            data.refund_account = account_match.group(1)
        else:
            account_alt_match = re.search(self.PATTERNS["refund_account_alt"], text, re.IGNORECASE)
            if account_alt_match:
                data.refund_account = account_alt_match.group(1)

        pix_match = re.search(self.PATTERNS["refund_pix"], text, re.IGNORECASE)
        if pix_match:
            data.refund_pix = pix_match.group(1).strip()

        data.rectifying = bool(re.search(self.PATTERNS["rectifying"], text, re.IGNORECASE))

        if data.rectifying:
            rect_match = re.search(self.PATTERNS["rectified_receipt"], text, re.IGNORECASE)
            if rect_match:
                data.rectified_receipt = rect_match.group(1)

        control_match = re.search(self.PATTERNS["control_line"], text, re.MULTILINE)
        if control_match:
            data.control_line = control_match.group(1)
        else:
            for line in reversed(text.split("\n")):
                line = line.strip()
                if re.match(r"^\d{10,12}$", line):
                    data.control_line = line
                    break

        return data.to_dict()

    def _extract_monetary_value(self, text: str, pattern_key: str) -> float:
        pattern = self.PATTERNS.get(pattern_key)
        if not pattern:
            return 0.0

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value_str = match.group(1)
            return parse_currency(value_str)
        return 0.0

    def _extract_monetary_value_with_alt(
        self, text: str, pattern_key: str, alt_pattern_key: str
    ) -> float:
        value = self._extract_monetary_value(text, pattern_key)
        if value == 0.0:
            value = self._extract_monetary_value(text, alt_pattern_key)
        return value


def is_receipt_document(text: str) -> bool:
    """Verifica se o texto representa APENAS um recibo de IRPF.
    
    IMPORTANTE: Se o documento contém "DECLARAÇÃO DE AJUSTE ANUAL",
    retorna False para que o IRPFParser processe a declaração completa.
    Isso permite que PDFs com recibo + declaração sejam processados corretamente.
    """
    text_upper = text.upper()
    
    # Se tem declaração de ajuste anual, NÃO é apenas recibo
    # Usar IRPFParser para processar a declaração completa
    if "DECLARAÇÃO DE AJUSTE ANUAL" in text_upper:
        return False
    
    # Verificar se é apenas recibo (sem declaração)
    for marker in ReceiptExtractor.RECEIPT_MARKERS:
        if marker.upper() in text_upper:
            return True
    
    return False
