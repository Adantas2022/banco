"""Validadores de campo para o sistema de confianca."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional


class IFieldValidator(ABC):
    """Interface para validadores de campo."""
    
    @abstractmethod
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        """Valida um valor e retorna (passou, lista_de_erros)."""
        pass
    
    @property
    @abstractmethod
    def field_type(self) -> str:
        """Tipo de campo que este validador manipula."""
        pass


class CpfValidator(IFieldValidator):
    """Validador de CPF com verificacao de digito."""
    
    @property
    def field_type(self) -> str:
        return "cpf"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return False, ["CPF nao informado"]
        
        cpf = str(value).replace(".", "").replace("-", "").replace(" ", "")
        
        if len(cpf) != 11:
            return False, [f"CPF deve ter 11 digitos, encontrado {len(cpf)}"]
        
        if not cpf.isdigit():
            return False, ["CPF deve conter apenas numeros"]
        
        if cpf == cpf[0] * 11:
            return False, ["CPF invalido (todos digitos iguais)"]
        
        def calc_digit(cpf_partial: str, weights: list[int]) -> int:
            total = sum(int(d) * w for d, w in zip(cpf_partial, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        first_digit = calc_digit(cpf[:9], list(range(10, 1, -1)))
        second_digit = calc_digit(cpf[:10], list(range(11, 1, -1)))
        
        if cpf[9] != str(first_digit) or cpf[10] != str(second_digit):
            return False, ["Digito verificador do CPF invalido"]
        
        return True, []


class CnpjValidator(IFieldValidator):
    """Validador de CNPJ com verificacao de digito."""
    
    @property
    def field_type(self) -> str:
        return "cnpj"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return False, ["CNPJ nao informado"]
        
        cnpj = str(value).replace(".", "").replace("-", "").replace("/", "").replace(" ", "")
        
        if len(cnpj) != 14:
            return False, [f"CNPJ deve ter 14 digitos, encontrado {len(cnpj)}"]
        
        if not cnpj.isdigit():
            return False, ["CNPJ deve conter apenas numeros"]
        
        if cnpj == cnpj[0] * 14:
            return False, ["CNPJ invalido (todos digitos iguais)"]
        
        def calc_digit(cnpj_partial: str, weights: list[int]) -> int:
            total = sum(int(d) * w for d, w in zip(cnpj_partial, weights))
            remainder = total % 11
            return 0 if remainder < 2 else 11 - remainder
        
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        
        first_digit = calc_digit(cnpj[:12], weights1)
        second_digit = calc_digit(cnpj[:13], weights2)
        
        if cnpj[12] != str(first_digit) or cnpj[13] != str(second_digit):
            return False, ["Digito verificador do CNPJ invalido"]
        
        return True, []


class CpfCnpjValidator(IFieldValidator):
    """Validador que aceita CPF ou CNPJ."""
    
    def __init__(self):
        self._cpf_validator = CpfValidator()
        self._cnpj_validator = CnpjValidator()
    
    @property
    def field_type(self) -> str:
        return "cpf_cnpj"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return False, ["CPF/CNPJ nao informado"]
        
        clean_value = str(value).replace(".", "").replace("-", "").replace("/", "").replace(" ", "")
        
        if len(clean_value) == 11:
            return self._cpf_validator.validate(value)
        elif len(clean_value) == 14:
            return self._cnpj_validator.validate(value)
        else:
            return False, [f"CPF/CNPJ deve ter 11 ou 14 digitos, encontrado {len(clean_value)}"]


class YearValidator(IFieldValidator):
    """Validador de ano (exercicio ou calendario)."""
    
    MIN_YEAR = 2015
    MAX_YEAR = 2030
    
    @property
    def field_type(self) -> str:
        return "year"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return False, ["Ano nao informado"]
        
        try:
            year = int(str(value).strip())
        except (ValueError, TypeError):
            return False, [f"Ano invalido: {value}"]
        
        if year < self.MIN_YEAR or year > self.MAX_YEAR:
            return False, [f"Ano fora do intervalo valido ({self.MIN_YEAR}-{self.MAX_YEAR}): {year}"]
        
        return True, []


class CurrencyValidator(IFieldValidator):
    """Validador de valores monetarios."""
    
    def __init__(self, allow_negative: bool = False, max_value: float = 1e12):
        self._allow_negative = allow_negative
        self._max_value = max_value
    
    @property
    def field_type(self) -> str:
        return "currency"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return True, []
        
        try:
            amount = float(value)
        except (ValueError, TypeError):
            return False, [f"Valor monetario invalido: {value}"]
        
        errors = []
        
        if not self._allow_negative and amount < 0:
            errors.append(f"Valor negativo nao permitido: {amount}")
        
        if abs(amount) > self._max_value:
            errors.append(f"Valor excede maximo permitido: {amount}")
        
        return len(errors) == 0, errors


class DateValidator(IFieldValidator):
    """Validador de datas no formato DD/MM/YYYY."""
    
    def __init__(self, min_year: int = 1900, max_year: int = 2030):
        self._min_year = min_year
        self._max_year = max_year
    
    @property
    def field_type(self) -> str:
        return "date"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None or value == "N/A":
            return True, []
        
        date_str = str(value).strip()
        
        if not re.match(r"^\d{2}/\d{2}/\d{4}$", date_str):
            return False, [f"Data deve estar no formato DD/MM/YYYY: {date_str}"]
        
        try:
            parsed = datetime.strptime(date_str, "%d/%m/%Y")
            
            if parsed.year < self._min_year or parsed.year > self._max_year:
                return False, [f"Ano da data fora do intervalo ({self._min_year}-{self._max_year}): {parsed.year}"]
            
            return True, []
        except ValueError:
            return False, [f"Data invalida: {date_str}"]


class StateValidator(IFieldValidator):
    """Validador de UF brasileira."""
    
    VALID_STATES = {
        "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
        "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
        "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"
    }
    
    @property
    def field_type(self) -> str:
        return "state"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None or value == "N/A":
            return True, []
        
        state = str(value).strip().upper()
        
        if len(state) != 2:
            return False, [f"UF deve ter 2 caracteres: {state}"]
        
        if state not in self.VALID_STATES:
            return False, [f"UF invalida: {state}"]
        
        return True, []


class NotEmptyValidator(IFieldValidator):
    """Validador que verifica se o valor nao esta vazio."""
    
    @property
    def field_type(self) -> str:
        return "not_empty"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return False, ["Valor nao pode ser vazio"]
        
        if isinstance(value, str) and not value.strip():
            return False, ["Valor nao pode ser vazio"]
        
        if isinstance(value, (list, dict)) and len(value) == 0:
            return False, ["Valor nao pode ser vazio"]
        
        return True, []


FIELD_VALIDATORS: dict[str, IFieldValidator] = {
    "taxpayer_identification.cpf": CpfValidator(),
    "taxpayer_identification.normalized_cpf": CpfValidator(),
    "taxpayer_identification.name": NotEmptyValidator(),
    "taxpayer_identification.exercise_year": YearValidator(),
    "taxpayer_identification.calendar_year": YearValidator(),
    
    "*.cpf_cnpj": CpfCnpjValidator(),
    "*.cpf": CpfValidator(),
    "*.state": StateValidator(),
    "*.uf": StateValidator(),
    "*.acquisition_date": DateValidator(),
    
    "*.before_year_asset_value": CurrencyValidator(),
    "*.current_year_asset_value": CurrencyValidator(),
    "*.last_year_total_value": CurrencyValidator(),
    "*.current_year_total_value": CurrencyValidator(),
    "*.income_from_legal_person": CurrencyValidator(),
    "*.tax_withheld_at_source": CurrencyValidator(),
}


def get_validator_for_field(field_path: str) -> IFieldValidator | None:
    if field_path in FIELD_VALIDATORS:
        return FIELD_VALIDATORS[field_path]
    
    field_name = field_path.split(".")[-1]
    wildcard_key = f"*.{field_name}"
    if wildcard_key in FIELD_VALIDATORS:
        return FIELD_VALIDATORS[wildcard_key]
    
    return None


class OcrGarbageCharsValidator(IFieldValidator):
    """Detecta caracteres invalidos comuns em erros de OCR."""
    
    GARBAGE_PATTERNS = [
        r"[^\w\s.,;:!?@#$%&*()[\]{}/\\|<>=+\-\'\"àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞŸ]",
        r"[\x00-\x1F\x7F-\x9F]",
    ]
    
    @property
    def field_type(self) -> str:
        return "ocr_garbage"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return True, []
        
        text = str(value)
        errors = []
        
        for pattern in self.GARBAGE_PATTERNS:
            matches = re.findall(pattern, text)
            if matches:
                errors.append(f"Caracteres invalidos detectados: {matches[:5]}")
        
        return len(errors) == 0, errors


class OcrRepeatedCharsValidator(IFieldValidator):
    """Detecta repeticoes anomalas de caracteres."""
    
    MAX_REPEATED = 4
    
    @property
    def field_type(self) -> str:
        return "ocr_repeated"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return True, []
        
        text = str(value)
        errors = []
        
        pattern = r"(.)\1{" + str(self.MAX_REPEATED) + r",}"
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        if matches:
            errors.append(f"Caracteres repetidos detectados: {matches[:3]}")
        
        return len(errors) == 0, errors


class OcrTruncatedValueValidator(IFieldValidator):
    """Detecta valores monetarios truncados."""
    
    TRUNCATED_PATTERNS = [
        r"\d{1,3}(?:\.\d{3})*,\d$",
        r"R\$\s*$",
        r"\d+,?$",
    ]
    
    @property
    def field_type(self) -> str:
        return "ocr_truncated"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return True, []
        
        text = str(value).strip()
        errors = []
        
        if re.match(r"^\d{1,3}(?:\.\d{3})*,\d$", text):
            errors.append(f"Valor monetario possivelmente truncado: {text}")
        
        if text.endswith(",") or text.endswith("."):
            errors.append(f"Valor termina com separador: {text}")
        
        return len(errors) == 0, errors


class OcrCpfConfusionValidator(IFieldValidator):
    """Detecta confusao de caracteres comuns em CPF via OCR."""
    
    CONFUSIONS = {
        "O": "0",
        "o": "0",
        "I": "1",
        "l": "1",
        "S": "5",
        "B": "8",
        "Z": "2",
    }
    
    @property
    def field_type(self) -> str:
        return "ocr_cpf_confusion"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return True, []
        
        text = str(value)
        errors = []
        warnings = []
        
        for char, digit in self.CONFUSIONS.items():
            if char in text:
                warnings.append(f"Possivel confusao OCR: '{char}' pode ser '{digit}'")
        
        if warnings:
            errors.extend(warnings[:2])
        
        return len(errors) == 0, errors


class OcrCurrencyConfusionValidator(IFieldValidator):
    """Detecta problemas comuns em valores monetarios extraidos via OCR."""
    
    @property
    def field_type(self) -> str:
        return "ocr_currency_confusion"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None:
            return True, []
        
        text = str(value)
        errors = []
        
        if re.search(r"\d[.,]\d[.,]\d", text):
            errors.append(f"Multiplos separadores em valor: {text}")
        
        if re.search(r"[oOIl]", text):
            errors.append(f"Possivel letra confundida com numero: {text}")
        
        if re.search(r"\d{10,}", text.replace(".", "").replace(",", "")):
            errors.append(f"Valor monetario anormalmente longo: {text}")
        
        return len(errors) == 0, errors


class OcrDateConfusionValidator(IFieldValidator):
    """Detecta problemas comuns em datas extraidas via OCR."""
    
    @property
    def field_type(self) -> str:
        return "ocr_date_confusion"
    
    def validate(self, value: Any) -> tuple[bool, list[str]]:
        if value is None or value == "N/A":
            return True, []
        
        text = str(value).strip()
        errors = []
        
        if re.search(r"[oOIl]", text):
            errors.append(f"Possivel letra confundida com numero em data: {text}")
        
        if re.search(r"\d{3}/|\d{5}", text):
            errors.append(f"Formato de data anomalo: {text}")
        
        return len(errors) == 0, errors


OCR_VALIDATORS: dict[str, IFieldValidator] = {
    "ocr_garbage": OcrGarbageCharsValidator(),
    "ocr_repeated": OcrRepeatedCharsValidator(),
    "ocr_truncated": OcrTruncatedValueValidator(),
    "ocr_cpf_confusion": OcrCpfConfusionValidator(),
    "ocr_currency_confusion": OcrCurrencyConfusionValidator(),
    "ocr_date_confusion": OcrDateConfusionValidator(),
}


def validate_ocr_field(value: Any, field_type: str = "text") -> tuple[bool, list[str]]:
    all_errors = []
    
    garbage_validator = OCR_VALIDATORS["ocr_garbage"]
    passed, errors = garbage_validator.validate(value)
    all_errors.extend(errors)
    
    repeated_validator = OCR_VALIDATORS["ocr_repeated"]
    passed, errors = repeated_validator.validate(value)
    all_errors.extend(errors)
    
    if field_type == "cpf":
        cpf_validator = OCR_VALIDATORS["ocr_cpf_confusion"]
        passed, errors = cpf_validator.validate(value)
        all_errors.extend(errors)
    elif field_type == "currency":
        currency_validator = OCR_VALIDATORS["ocr_currency_confusion"]
        passed, errors = currency_validator.validate(value)
        all_errors.extend(errors)
        
        truncated_validator = OCR_VALIDATORS["ocr_truncated"]
        passed, errors = truncated_validator.validate(value)
        all_errors.extend(errors)
    elif field_type == "date":
        date_validator = OCR_VALIDATORS["ocr_date_confusion"]
        passed, errors = date_validator.validate(value)
        all_errors.extend(errors)
    
    return len(all_errors) == 0, all_errors
