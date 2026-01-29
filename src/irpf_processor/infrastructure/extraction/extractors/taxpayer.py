"""Extrator de identificação do contribuinte."""

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..field_extractors import normalize_cpf


@dataclass
class TaxpayerData:
    """Dados de identificação do contribuinte."""
    
    cpf: str = ""
    normalized_cpf: str = ""
    name: str = ""
    exercise_year: str = ""
    calendar_year: str = ""
    occupation_nature: str = ""
    main_occupation: str = ""
    contact_and_address: dict = field(default_factory=dict)
    type_ir: str = ""
    
    def to_dict(self) -> dict:
        return {
            "cpf": self.cpf,
            "normalized_cpf": self.normalized_cpf,
            "name": self.name,
            "exercise_year": self.exercise_year,
            "calendar_year": self.calendar_year,
            "occupation_nature": self.occupation_nature,
            "main_occupation": self.main_occupation,
            "contact_and_address": self.contact_and_address,
            "type_ir": self.type_ir
        }


class TaxpayerExtractor(ISectionExtractor):
    """Extrai dados de identificação do contribuinte."""
    
    PATTERNS = {
        "cpf": r"CPF[:\s]*(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})",
        "name": r"(?:NOME|Nome)[:\s]*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]+?)(?:\n|CPF)",
        "exercise_year": r"EXERC[ÍI]CIO\s*(\d{4})",
        "calendar_year": r"ANO[- ]CALEND[ÁA]RIO\s*(\d{4})",
        # Patterns melhorados para OCR - capturam valor na mesma linha OU na linha seguinte
        "occupation_nature": r"Natureza da Ocupa[çc][ãa]o[:\s]*\n?\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+)",
        "main_occupation": r"Ocupa[çc][ãa]o Principal[:\s]*\n?\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+)",
        "type_ir": r"Tipo de declara[çc][ãa]o[:\s]*\n?\s*(Declara[çc][ãa]o\s+de\s+Ajuste\s+Anual[^N\n]*)",
        "street": r"Endere[çc]o[:\s]*(.+?)(?:\s+N[úu]mero|$)",
        "number": r"N[úu]mero[:\s]*(\d+)",
        "complement": r"Complemento[:\s]*(.+?)(?:\s+Bairro|$)",
        "neighborhood": r"Bairro(?:/Distrito)?[:\s]*(.+?)(?:\s+Munic|$)",
        "city": r"Munic[íi]pio[:\s]*(.+?)(?:\s+UF|$)",
        "uf": r"UF[:\s]*([A-Z]{2})",
        "zip_code": r"CEP[:\s]*(\d{5}[-\s]?\d{3})",
        "phone": r"(?:DDD/)?Telefone[:\s]*([\d\s()-]+?)(?:\n|$)",
        "email": r"E-mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        "cell_phone": r"(?:DDD/)?Celular[:\s]*(\(?\d{2}\)?\s*\d{4,5}[-\s]?\d{4})",
    }
    
    @property
    def section_name(self) -> str:
        return "taxpayer_identification"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return bool(re.search(self.PATTERNS["cpf"], context.full_text, re.IGNORECASE))
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        data = TaxpayerData()
        text = context.full_text
        
        cpf_match = re.search(self.PATTERNS["cpf"], text, re.IGNORECASE)
        if cpf_match:
            data.cpf = cpf_match.group(1)
            data.normalized_cpf = normalize_cpf(data.cpf)
        
        name_match = re.search(self.PATTERNS["name"], text)
        if name_match:
            data.name = name_match.group(1).strip()
        
        exercise_match = re.search(self.PATTERNS["exercise_year"], text, re.IGNORECASE)
        if exercise_match:
            data.exercise_year = exercise_match.group(1)
        
        calendar_match = re.search(self.PATTERNS["calendar_year"], text, re.IGNORECASE)
        if calendar_match:
            data.calendar_year = calendar_match.group(1)
        
        # Extração melhorada para OCR - trata labels e valores em linhas separadas
        data.occupation_nature = self._extract_occupation_nature(text)
        data.main_occupation = self._extract_main_occupation(text)
        data.type_ir = self._extract_type_ir(text)
        
        data.contact_and_address = self._extract_address(text)
        
        return data.to_dict()
    
    def _extract_occupation_nature(self, text: str) -> str:
        """Extrai natureza da ocupação lidando com formato OCR."""
        # Primeiro tenta formato: "Natureza da Ocupação:\n12 - PROPRIETARIO..."
        pattern1 = re.search(
            r"Natureza da Ocupa[çc][ãa]o[:\s]*\n?\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,.-]+?)(?:\n|Ocupa|$)",
            text, re.IGNORECASE | re.MULTILINE
        )
        if pattern1:
            return pattern1.group(1).strip()
        
        # Formato alternativo onde valor está na linha seguinte
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Natureza da Ocupa[çc][ãa]o", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Natureza da Ocupa[çc][ãa]o[:\s]*(\d+\s*[-–].+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Valor na próxima linha
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.match(r"^\d+\s*[-–]", next_line):
                        return next_line.strip()
        return ""
    
    def _extract_main_occupation(self, text: str) -> str:
        """Extrai ocupação principal lidando com formato OCR."""
        # Primeiro tenta formato: "Ocupação Principal:\n610 - PRODUTOR..."
        pattern1 = re.search(
            r"Ocupa[çc][ãa]o Principal[:\s]*\n?\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,.-]+?)(?:\n|Tipo|$)",
            text, re.IGNORECASE | re.MULTILINE
        )
        if pattern1:
            return pattern1.group(1).strip()
        
        # Formato alternativo onde valor está na linha seguinte
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Ocupa[çc][ãa]o Principal", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Ocupa[çc][ãa]o Principal[:\s]*(\d+\s*[-–].+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Valor na próxima linha
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.match(r"^\d+\s*[-–]", next_line):
                        return next_line.strip()
        return ""
    
    def _extract_type_ir(self, text: str) -> str:
        """Extrai tipo de declaração lidando com formato OCR."""
        # Tenta formato: "Tipo de declaração:\nDeclaração de Ajuste Anual Original"
        pattern1 = re.search(
            r"Tipo de declara[çc][ãa]o[:\s]*\n?\s*(Declara[çc][ãa]o\s+de\s+Ajuste\s+Anual[^\n]*)",
            text, re.IGNORECASE | re.MULTILINE
        )
        if pattern1:
            return pattern1.group(1).strip().upper()
        
        # Formato alternativo onde valor está na linha seguinte
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Tipo de declara[çc][ãa]o", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Tipo de declara[çc][ãa]o[:\s]*(Declara[çc][ãa]o.+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip().upper()
                # Valor na próxima linha
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.search(r"Declara[çc][ãa]o", next_line, re.IGNORECASE):
                        return next_line.strip().upper()
        return ""
    
    def _extract_address(self, text: str) -> dict:
        address = {
            "street_address": "",
            "number": "",
            "complement": "",
            "neighborhood": "",
            "city": "",
            "uf": "",
            "zip_code": "",
            "phone": "",
            "email": "",
            "cell_phone": ""
        }
        
        field_mapping = {
            "street": "street_address",
            "number": "number",
            "complement": "complement",
            "neighborhood": "neighborhood",
            "city": "city",
            "uf": "uf",
            "zip_code": "zip_code",
            "phone": "phone",
            "email": "email",
            "cell_phone": "cell_phone"
        }
        
        for pattern_key, address_key in field_mapping.items():
            pattern = self.PATTERNS.get(pattern_key)
            if pattern:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    address[address_key] = match.group(1).strip()
        
        return address
