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
        # Normalizar texto para facilitar busca
        # OCR pode gerar: "Natureza da Ocupagao", "Natureza da Ocupacao", etc.
        
        # Pattern mais flexível para OCR - captura código e descrição
        patterns = [
            # Formato: "Natureza da Ocupação: 12 - PROPRIETARIO..."
            r"Natureza\s+da\s+Ocupa[çcg][ãa]o[:\s]*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,./()-]+?)(?:\n|Ocupa[çcg]|$)",
            # Formato com quebra de linha
            r"Natureza\s+da\s+Ocupa[çcg][ãa]o[:\s]*\n\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,./()-]+?)(?:\n|$)",
            # Formato OCR sem acentos
            r"Natureza\s+da\s+Ocupacao[:\s]*(\d+\s*[-–]\s*[A-Z][A-Za-z\s,./()-]+?)(?:\n|Ocup|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1).strip()
                # Limpar trailing "Ocup" que pode ter sido capturado
                result = re.sub(r'\s*Ocup.*$', '', result, flags=re.IGNORECASE)
                return result
        
        # Formato alternativo: buscar linha por linha
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Natureza\s+da\s+Ocupa", line, re.IGNORECASE):
                # Valor na mesma linha após o label
                match = re.search(r"Natureza\s+da\s+Ocupa[çcg]?[ãa]?o?[:\s]*(\d+\s*[-–].+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Valor na próxima linha (OCR comum)
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.match(r"^\d+\s*[-–]", next_line):
                        # Pode continuar na linha seguinte
                        result = next_line
                        if i + 2 < len(lines):
                            next_next = lines[i + 2].strip()
                            # Se a próxima linha parece continuação (sem número inicial)
                            if next_next and not re.match(r"^\d+\s*[-–]", next_next) and not re.search(r"Ocupa[çcg]", next_next, re.IGNORECASE):
                                if not re.match(r"^(Tipo|Endere|CEP|Munic)", next_next, re.IGNORECASE):
                                    result += " " + next_next
                        return result
        return ""
    
    def _extract_main_occupation(self, text: str) -> str:
        """Extrai ocupação principal lidando com formato OCR."""
        # Patterns mais flexíveis para OCR
        patterns = [
            # Formato: "Ocupação Principal: 610 - PRODUTOR..."
            r"Ocupa[çcg][ãa]o\s+Principal[:\s]*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,./()-]+?)(?:\n|Tipo|$)",
            # Formato com quebra de linha
            r"Ocupa[çcg][ãa]o\s+Principal[:\s]*\n\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,./()-]+?)(?:\n|$)",
            # Formato OCR sem acentos
            r"Ocupacao\s+Principal[:\s]*(\d+\s*[-–]\s*[A-Z][A-Za-z\s,./()-]+?)(?:\n|Tipo|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1).strip()
                # Limpar trailing "Tipo" que pode ter sido capturado
                result = re.sub(r'\s*Tipo.*$', '', result, flags=re.IGNORECASE)
                return result
        
        # Formato alternativo: buscar linha por linha
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Ocupa[çcg]?[ãa]?o?\s+Principal", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Ocupa[çcg]?[ãa]?o?\s+Principal[:\s]*(\d+\s*[-–].+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Valor na próxima linha
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.match(r"^\d+\s*[-–]", next_line):
                        # Pode continuar na linha seguinte
                        result = next_line
                        if i + 2 < len(lines):
                            next_next = lines[i + 2].strip()
                            if next_next and not re.match(r"^\d+\s*[-–]", next_next) and not re.search(r"Tipo", next_next, re.IGNORECASE):
                                if not re.match(r"^(Endere|CEP|Munic|Declara)", next_next, re.IGNORECASE):
                                    result += " " + next_next
                        return result
        return ""
    
    def _extract_type_ir(self, text: str) -> str:
        """Extrai tipo de declaração lidando com formato OCR."""
        # Patterns mais flexíveis para OCR
        patterns = [
            # Formato: "Tipo de declaração: Declaração de Ajuste Anual Original"
            r"Tipo\s+de\s+[Dd]eclara[çcg][ãa]o[:\s]*(Declara[çcg][ãa]o\s+de\s+Ajuste\s+Anual[^\n]*)",
            # Formato com quebra de linha
            r"Tipo\s+de\s+[Dd]eclara[çcg][ãa]o[:\s]*\n\s*(Declara[çcg][ãa]o\s+de\s+Ajuste\s+Anual[^\n]*)",
            # OCR pode gerar: "Declaragao"
            r"Tipo\s+de\s+[Dd]eclaracao[:\s]*(Declaracao\s+de\s+Ajuste\s+Anual[^\n]*)",
            # Formato mais flexível
            r"Tipo\s+de\s+[Dd]eclar[^\n:]*[:\s]+(Declar[^\n]+Ajuste\s+Anual[^\n]*)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1).strip().upper()
                # Normalizar: "DECLARAGAO" -> "DECLARACAO"
                result = result.replace("DECLARAGAO", "DECLARACAO")
                result = result.replace("DECLARAÇAO", "DECLARACAO")
                result = result.replace("DECLARAÇÃO", "DECLARACAO")
                return result
        
        # Buscar linha por linha
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Tipo\s+de\s+[Dd]eclar", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Tipo\s+de\s+[Dd]eclar[^\n:]*[:\s]+(Declar.+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip().upper().replace("DECLARAGAO", "DECLARACAO")
                # Valor na próxima linha
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.search(r"Declar", next_line, re.IGNORECASE):
                        result = next_line.strip().upper()
                        # Pode continuar na linha seguinte
                        if i + 2 < len(lines) and "ORIGINAL" not in result and "RETIFICADORA" not in result:
                            next_next = lines[i + 2].strip()
                            if "ORIGINAL" in next_next.upper() or "RETIFICADORA" in next_next.upper():
                                result += " " + next_next.upper()
                        return result.replace("DECLARAGAO", "DECLARACAO")
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
            "cell_phone": "cell_phone"
        }
        
        for pattern_key, address_key in field_mapping.items():
            pattern = self.PATTERNS.get(pattern_key)
            if pattern:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    address[address_key] = match.group(1).strip()
        
        # Extração melhorada de email para OCR
        address["email"] = self._extract_email(text)
        
        return address
    
    def _extract_email(self, text: str) -> str:
        """Extrai email com tratamento especial para OCR."""
        # Patterns de email
        email_patterns = [
            # Formato: "E-mail: email@domain.com"
            r"E-?mail[:\s]+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            # Formato com quebra de linha
            r"E-?mail[:\s]*\n\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
            # Email em qualquer lugar (fallback - busca padrão de email)
            r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:COM|BR|NET|ORG|GOV)(?:\.[A-Z]{2})?)",
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                email = match.group(1).strip().upper()
                # Validar que parece um email válido
                if "@" in email and "." in email.split("@")[1]:
                    return email
        
        # Busca linha por linha para casos de OCR fragmentado
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"E-?mail", line, re.IGNORECASE):
                # Tentar extrair email da mesma linha
                email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", line)
                if email_match:
                    return email_match.group(1).strip().upper()
                # Tentar da próxima linha
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    email_match = re.search(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", next_line)
                    if email_match:
                        return email_match.group(1).strip().upper()
        
        return ""
