from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from irpf_processor.shared.logging import get_logger

from .interfaces import IPostProcessor

logger = get_logger(__name__)


@dataclass
class PostProcessingResult:
    text: str
    corrections_made: dict[str, int] = field(default_factory=dict)
    total_corrections: int = 0
    confidence_adjustment: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "corrections_made": self.corrections_made,
            "total_corrections": self.total_corrections,
            "confidence_adjustment": self.confidence_adjustment,
        }


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
    
    CONFIDENCE_ADJUSTMENTS = {
        "accent_fix": 0.02,
        "ocr_char_fix": 0.01,
        "cpf_format": 0.02,
        "cnpj_format": 0.02,
        "currency_fix": 0.01,
        "artifact_removal": 0.005,
        "line_break_fix": 0.005,
    }

    def __init__(self, lang: str = "pt-BR"):
        self._lang = lang
        self._corrections: dict[str, int] = {}

    def process(
        self,
        text: Optional[str],
        preserve_column_gaps: bool = False,
    ) -> str:
        if not text:
            return ""

        self._corrections = {}

        text = self.normalize_whitespace(text, preserve_column_gaps=preserve_column_gaps)
        text = self.normalize_ocr_slashes(text)
        text = self.fix_accents(text)
        text = self.fix_ocr_errors(text)
        text = self.format_cpf(text)
        text = self.format_cnpj(text)
        text = self.normalize_us_currency(text)
        text = self.fix_currency(text)
        text = self.remove_artifacts(text)
        text = self.fix_line_breaks(text)

        return text.strip()
    
    def process_with_metrics(
        self,
        text: Optional[str],
        preserve_column_gaps: bool = False,
    ) -> PostProcessingResult:
        if not text:
            return PostProcessingResult(text="")

        self._corrections = {}

        text = self.normalize_whitespace(text, preserve_column_gaps=preserve_column_gaps)
        text = self.normalize_ocr_slashes(text)
        text = self.fix_accents(text)
        text = self.fix_ocr_errors(text)
        text = self.format_cpf(text)
        text = self.format_cnpj(text)
        text = self.normalize_us_currency(text)
        text = self.fix_currency(text)
        text = self.remove_artifacts(text)
        text = self.fix_line_breaks(text)
        
        total_corrections = sum(self._corrections.values())
        confidence_adjustment = self._calculate_confidence_adjustment()
        
        logger.info(
            "OCR post-processing completed",
            total_corrections=total_corrections,
            corrections=self._corrections,
            confidence_adjustment=confidence_adjustment,
        )
        
        return PostProcessingResult(
            text=text.strip(),
            corrections_made=self._corrections.copy(),
            total_corrections=total_corrections,
            confidence_adjustment=confidence_adjustment,
        )
    
    def _calculate_confidence_adjustment(self) -> float:
        total_adjustment = 0.0
        
        for correction_type, count in self._corrections.items():
            adjustment_per_correction = self.CONFIDENCE_ADJUSTMENTS.get(correction_type, 0.0)
            adjustment = min(count * adjustment_per_correction, 0.05)
            total_adjustment += adjustment
        
        return min(total_adjustment, 0.15)
    
    def _record_correction(self, correction_type: str, count: int = 1) -> None:
        if correction_type not in self._corrections:
            self._corrections[correction_type] = 0
        self._corrections[correction_type] += count
    
    def get_last_corrections(self) -> dict[str, int]:
        return self._corrections.copy()

    def fix_ocr_errors(self, text: str) -> str:
        correction_count = 0
        
        cpf_pattern = r"CPF[:\s]*(\d[\dOoBbIl\|\s\.\-]{10,17})"
        matches = re.finditer(cpf_pattern, text, re.IGNORECASE)

        for match in matches:
            original = match.group(1)
            fixed = self._fix_digits(original)
            if original != fixed:
                correction_count += 1
                text = text.replace(original, fixed)

        cnpj_pattern = r"CNPJ[:\s]*(\d[\dOoBbIl\|\s\.\-\/]{14,20})"
        matches = re.finditer(cnpj_pattern, text, re.IGNORECASE)

        for match in matches:
            original = match.group(1)
            fixed = self._fix_digits(original)
            if original != fixed:
                correction_count += 1
                text = text.replace(original, fixed)

        if correction_count > 0:
            self._record_correction("ocr_char_fix", correction_count)

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
        correction_count = 0
        
        for wrong, correct in self.ACCENT_CORRECTIONS.items():
            matches = len(re.findall(rf"\b{wrong}\b", text, flags=re.IGNORECASE))
            if matches > 0:
                correction_count += matches
                text = re.sub(rf"\b{wrong}\b", correct, text, flags=re.IGNORECASE)

        if correction_count > 0:
            self._record_correction("accent_fix", correction_count)

        return text

    def normalize_whitespace(
        self,
        text: str,
        preserve_column_gaps: bool = False,
    ) -> str:
        if preserve_column_gaps:
            text = re.sub(r"\t", " ", text)
            text = re.sub(r" +\n", "\n", text)
            text = re.sub(r"\n +", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
        else:
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r" +\n", "\n", text)
            text = re.sub(r"\n +", "\n", text)
            text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    def normalize_ocr_slashes(self, text: str) -> str:
        original_text = text

        text = re.sub(r"(\d)\s*/\s*(\d)", r"\1/\2", text)

        if text != original_text:
            corrections = len(re.findall(r"(\d)\s*/\s*(\d)", original_text))
            self._record_correction("ocr_slash_normalize", corrections)

        return text

    def normalize_us_currency(self, text: str) -> str:
        """Normaliza valores monetários em formato US/misto para formato BR.

        O Document AI ocasionalmente troca separadores de milhar/decimal,
        produzindo formatos como:
          - ``150,000.00``  (US puro:  vírgula=milhar, ponto=decimal)
          - ``150,000,00``  (misto: vírgula=milhar E vírgula=decimal)

        Ambos são convertidos para o formato BR: ``150.000,00``.
        """
        original_text = text

        def _us_to_br(m: re.Match) -> str:
            integer = m.group(1) + m.group(2).replace(",", ".")
            return f"{integer},{m.group(3)}"

        text = re.sub(
            r"(\d{1,3})((?:,\d{3})+)\.(\d{2})(?!\d)",
            _us_to_br,
            text,
        )

        def _mixed_to_br(m: re.Match) -> str:
            integer = m.group(1) + m.group(2).replace(",", ".")
            return f"{integer},{m.group(3)}"

        text = re.sub(
            r"(\d{1,3})((?:,\d{3})+),(\d{2})(?!\d)",
            _mixed_to_br,
            text,
        )

        if text != original_text:
            corrections = sum(
                1 for a, b in zip(original_text, text) if a != b
            ) // 2 or 1
            self._record_correction("currency_format_normalize", corrections)

        return text

    def fix_currency(self, text: str) -> str:
        pattern = r"R\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2}))"
        matches = list(re.finditer(pattern, text))
        correction_count = 0

        for match in matches:
            original = match.group(0)
            value = match.group(1)
            fixed_value = value.replace(",", "X").replace(".", ",").replace("X", ".")
            fixed = f"R$ {fixed_value}"
            if original != fixed:
                correction_count += 1
                text = text.replace(original, fixed)

        if correction_count > 0:
            self._record_correction("currency_fix", correction_count)

        return text

    def format_cpf(self, text: str) -> str:
        context_pattern = r"CPF[:\s]*(\d{11})(?!\d)"
        matches = len(re.findall(context_pattern, text, flags=re.IGNORECASE))

        def format_match(match):
            cpf = match.group(1)
            return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"

        text = re.sub(context_pattern, lambda m: f"CPF: {format_match(m)}", text, flags=re.IGNORECASE)
        
        if matches > 0:
            self._record_correction("cpf_format", matches)

        return text

    def format_cnpj(self, text: str) -> str:
        context_pattern = r"CNPJ[:\s]*(\d{14})(?!\d)"
        matches = len(re.findall(context_pattern, text, flags=re.IGNORECASE))

        def format_match(match):
            cnpj = match.group(1)
            return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"

        text = re.sub(context_pattern, lambda m: f"CNPJ: {format_match(m)}", text, flags=re.IGNORECASE)
        
        if matches > 0:
            self._record_correction("cnpj_format", matches)

        return text

    def remove_artifacts(self, text: str) -> str:
        original_text = text
        
        text = re.sub(r"[|]{2,}", "", text)
        text = re.sub(r"[-]{3,}", "", text)
        text = re.sub(r"[_]{3,}", "", text)
        text = re.sub(r"[=]{3,}", "", text)
        text = re.sub(r"[.]{4,}", "...", text)
        
        if text != original_text:
            self._record_correction("artifact_removal", 1)

        return text

    def fix_line_breaks(self, text: str) -> str:
        original_text = text
        
        text = re.sub(r"(\w)-\n([a-zA-ZÀ-ÿ])", r"\1\2", text)

        name_pattern = r"(NOME[:\s]+\w+)\n(\w+)"
        text = re.sub(name_pattern, r"\1 \2", text)
        
        if text != original_text:
            self._record_correction("line_break_fix", 1)

        return text
