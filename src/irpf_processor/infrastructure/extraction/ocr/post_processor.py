from __future__ import annotations

import re
from typing import Optional

from irpf_processor.shared.logging import get_logger

from .interfaces import IPostProcessor

logger = get_logger(__name__)


class PostProcessor(IPostProcessor):

    COMMON_OCR_ERRORS = {
        "0": ["O", "o", "Q"],
        "1": ["l", "I", "i", "|"],
        "2": ["Z", "z"],
        "5": ["S", "s"],
        "6": ["G", "b"],
        "8": ["B"],
        "9": ["g", "q"],
    }

    ACCENT_CORRECTIONS = {
        "DECLARACAO": "DECLARAÇÃO",
        "CONTRIBUICAO": "CONTRIBUIÇÃO",
        "CONTRIBUINTE": "CONTRIBUINTE",
        "IDENTIFICACAO": "IDENTIFICAÇÃO",
        "EXERCICIO": "EXERCÍCIO",
        "CALENDARIO": "CALENDÁRIO",
        "RENDIMENTO": "RENDIMENTO",
        "TRIBUTAVEL": "TRIBUTÁVEL",
        "TRIBUTAVEIS": "TRIBUTÁVEIS",
        "ISENTO": "ISENTO",
        "ISENTOS": "ISENTOS",
        "EXCLUSIVA": "EXCLUSIVA",
        "TRIBUTACAO": "TRIBUTAÇÃO",
        "ATIVIDADE": "ATIVIDADE",
        "OCUPACAO": "OCUPAÇÃO",
        "NATUREZA": "NATUREZA",
        "CODIGO": "CÓDIGO",
        "SITUACAO": "SITUAÇÃO",
        "DESCRICAO": "DESCRIÇÃO",
        "AQUISICAO": "AQUISIÇÃO",
        "ANTERIOR": "ANTERIOR",
        "ANO-CALENDARIO": "ANO-CALENDÁRIO",
    }

    def __init__(self, lang: str = "pt-BR"):
        self._lang = lang

    def process(self, text: Optional[str]) -> str:
        if not text:
            return ""

        text = self.normalize_whitespace(text)
        text = self.fix_accents(text)
        text = self.fix_ocr_errors(text)
        text = self.format_cpf(text)
        text = self.format_cnpj(text)
        text = self.fix_currency(text)
        text = self.remove_artifacts(text)
        text = self.fix_line_breaks(text)

        return text.strip()

    def fix_ocr_errors(self, text: str) -> str:
        cpf_pattern = r"CPF[:\s]*(\d[\dOoBbIl\|\s\.\-]{10,17})"
        matches = re.finditer(cpf_pattern, text, re.IGNORECASE)

        for match in matches:
            original = match.group(1)
            fixed = self._fix_digits(original)
            text = text.replace(original, fixed)

        cnpj_pattern = r"CNPJ[:\s]*(\d[\dOoBbIl\|\s\.\-\/]{14,20})"
        matches = re.finditer(cnpj_pattern, text, re.IGNORECASE)

        for match in matches:
            original = match.group(1)
            fixed = self._fix_digits(original)
            text = text.replace(original, fixed)

        return text

    def _fix_digits(self, text: str) -> str:
        result = text

        result = result.replace("O", "0").replace("o", "0")
        result = result.replace("l", "1").replace("I", "1").replace("|", "1")
        result = result.replace("B", "8")
        result = result.replace("S", "5").replace("s", "5")
        result = result.replace("Z", "2").replace("z", "2")
        result = result.replace("G", "6")
        result = result.replace("g", "9").replace("q", "9")

        return result

    def fix_accents(self, text: str) -> str:
        for wrong, correct in self.ACCENT_CORRECTIONS.items():
            text = re.sub(rf"\b{wrong}\b", correct, text, flags=re.IGNORECASE)

        return text

    def normalize_whitespace(self, text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" +\n", "\n", text)
        text = re.sub(r"\n +", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def fix_currency(self, text: str) -> str:
        pattern = r"R\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2}))"
        matches = re.finditer(pattern, text)

        for match in matches:
            original = match.group(0)
            value = match.group(1)
            fixed_value = value.replace(",", "X").replace(".", ",").replace("X", ".")
            fixed = f"R$ {fixed_value}"
            text = text.replace(original, fixed)

        return text

    def format_cpf(self, text: str) -> str:
        pattern = r"(\d{11})(?!\d)"

        def format_match(match):
            cpf = match.group(1)
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

        context_pattern = r"CPF[:\s]*(\d{11})(?!\d)"
        text = re.sub(context_pattern, lambda m: f"CPF: {format_match(m)}", text, flags=re.IGNORECASE)

        return text

    def format_cnpj(self, text: str) -> str:
        pattern = r"(\d{14})(?!\d)"

        def format_match(match):
            cnpj = match.group(1)
            return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

        context_pattern = r"CNPJ[:\s]*(\d{14})(?!\d)"
        text = re.sub(context_pattern, lambda m: f"CNPJ: {format_match(m)}", text, flags=re.IGNORECASE)

        return text

    def remove_artifacts(self, text: str) -> str:
        text = re.sub(r"[|]{2,}", "", text)
        text = re.sub(r"[-]{3,}", "", text)
        text = re.sub(r"[_]{3,}", "", text)
        text = re.sub(r"[=]{3,}", "", text)
        text = re.sub(r"[.]{4,}", "...", text)

        return text

    def fix_line_breaks(self, text: str) -> str:
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

        name_pattern = r"(NOME[:\s]+\w+)\n(\w+)"
        text = re.sub(name_pattern, r"\1 \2", text)

        return text
