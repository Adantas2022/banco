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
        "calendar_year": r"ANO\s*[-–]\s*CALEND[ÁAáa]RIO[:\s]*(\d{4})",
        # Patterns melhorados para OCR - capturam valor na mesma linha OU na linha seguinte
        "occupation_nature": r"Natureza da Ocupa[çc][ãa]o[:\s]*\n?\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+)",
        "main_occupation": r"Ocupa[çc][ãa]o Principal[:\s]*\n?\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s]+)",
        "type_ir": r"Tipo de declara[çc][ãa]o[:\s]*\n?\s*(Declara[çc][ãa]o\s+de\s+Ajuste\s+Anual[^N\n]*)",
        "street": r"Endere[çc]o[:\s]*(.+?)(?:\s+N[úu]mero|$)",
        "number": r"N[úu]mero[:\s]*(\d+|S/?N)",
        "complement": r"Complemento[:\s]*(.+?)(?:\s+Munic[íi]pio|\n|$)",
        "neighborhood": r"(?:^|\n)\s*Bairro(?:\s*/\s*Distrito)?[:\s]*(.+?)(?:\s+Munic|$)",
        "city": r"Munic[íi]pio[:\s]*(.+?)(?:\s+UF|$)",
        "uf": r"UF[:\s]*([A-Z]{2})",
        "zip_code": r"CEP[:\s]*(\d{5}[-\s]?\d{3})",
        "phone": r"(?:DDD\s*/\s*)?Telefone[:\s]*([\d\s()-]+?)(?:\n|$)",
        "email": r"E-mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        "cell_phone": r"(?:DDD\s*/\s*)?Celular[:\s]*(\(?\d{2}\)?\s*\d{4,5}[-\s]?\d{4})",
    }
    
    @property
    def section_name(self) -> str:
        return "taxpayer_identification"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return bool(re.search(self.PATTERNS["cpf"], context.full_text, re.IGNORECASE))
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        data = TaxpayerData()
        text = context.full_text
        taxpayer_section = self._extract_taxpayer_section(text)
        
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
        data.occupation_nature = self._extract_occupation_nature(taxpayer_section)
        data.main_occupation = self._extract_main_occupation(taxpayer_section)
        data.type_ir = self._extract_type_ir(taxpayer_section) or self._extract_type_ir(text)
        
        data.contact_and_address = self._extract_address(taxpayer_section)
        
        return data.to_dict()

    def _extract_taxpayer_section(self, text: str) -> str:
        match = re.search(
            r"IDENTIFICA[ÇC][ÃA]O\s+DO\s+CONTRIBUINTE(.*?)(?:\nDEPENDENTES|\nALIMENTANDOS|\nRENDIMENTOS\s+TRIBUT[ÁA]VEIS)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1)
        return text
    
    def _extract_occupation_nature(self, text: str) -> str:
        """Extrai natureza da ocupação lidando com formato OCR."""
        # Normalizar texto para facilitar busca
        # OCR pode gerar: "Natureza da Ocupagao", "Natureza da Ocupacao", etc.
        
        # Pattern mais flexível para OCR - captura código e descrição
        patterns = [
            # Formato: "Natureza da Ocupação: 12 - PROPRIETARIO..."
            r"Natureza\s+da\s+Ocupa[çcg][ãa]o[:\s]*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,./()-]+?)(?:\n|Ocupa[çcg][ãa]o\s+Principal|$)",
            # Formato com quebra de linha
            r"Natureza\s+da\s+Ocupa[çcg][ãa]o[:\s]*\n\s*(\d+\s*[-–]\s*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-Za-zÀ-ÿ\s,./()-]+?)(?:\n|$)",
            # Formato OCR sem acentos
            r"Natureza\s+da\s+Ocupacao[:\s]*(\d+\s*[-–]\s*[A-Z][A-Za-z\s,./()-]+?)(?:\n|Ocupacao\s+Principal|$)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                result = match.group(1).strip()
                # Limpar trailing "Ocup" que pode ter sido capturado
                result = re.sub(r'\s*Ocup.*$', '', result, flags=re.IGNORECASE)
                return result
        
        # Formato alternativo: buscar linha por linha
        # IMPORTANTE: O OCR pode colocar os 3 labels em linhas consecutivas
        # e depois os valores em linhas separadas:
        #   Natureza da Ocupac¢ao:
        #   Ocupagao Principal:
        #   Tipo de declaracao:
        #   
        #   12 - PROPRIETARIO...       <- valor de Natureza
        #   610 - PRODUTOR...          <- valor de Ocupação Principal
        #   Declaragao de Ajuste...    <- valor de Tipo
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Natureza\s+da\s+Ocupa", line, re.IGNORECASE):
                # Valor na mesma linha após o label
                match = re.search(r"Natureza\s+da\s+Ocupa[çcg]?[ãa]?o?[:\s]*(\d+\s*[-–].+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Buscar nas próximas 10 linhas por valor no formato "XX - DESCRIÇÃO"
                # onde XX é código de 1-2 dígitos (natureza da ocupação: 01-99)
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j].strip()
                    # Código de natureza é 1-2 dígitos (diferente de ocupação principal que é 3+)
                    match = re.match(r"^(\d{1,2}\s*[-–]\s*[A-Z][A-Za-zÀ-ÿ\s,./()ÁÀÂÃÉÊÍÓÔÕÚÇ-]+)", next_line, re.IGNORECASE)
                    if match:
                        result = match.group(1).strip()
                        # Continuar na próxima linha se for continuação da descrição
                        if j + 1 < len(lines):
                            next_next = lines[j + 1].strip()
                            # Não é continuação se começa com código novo ou label
                            if next_next and not re.match(r"^\d{1,3}\s*[-–]", next_next):
                                if not re.match(r"^(Tipo|Endere|CEP|Munic|Declar|Ocupa|ANO)", next_next, re.IGNORECASE):
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
        # O OCR pode separar labels dos valores - buscar nas próximas linhas
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Ocupa[çcg]?[ãa]?o?\s+Principal", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Ocupa[çcg]?[ãa]?o?\s+Principal[:\s]*(\d+\s*[-–].+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
                # Buscar nas próximas 10 linhas por valor no formato "XXX - DESCRIÇÃO"
                # onde XXX é código de 3+ dígitos (ocupação principal: 100-999)
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j].strip()
                    # Código de ocupação principal é 3 dígitos (diferente de natureza que é 1-2)
                    match = re.match(r"^(\d{3}\s*[-–]\s*[A-Z][A-Za-zÀ-ÿ\s,./()ÁÀÂÃÉÊÍÓÔÕÚÇ-]+)", next_line, re.IGNORECASE)
                    if match:
                        result = match.group(1).strip()
                        # Continuar na próxima linha se for continuação
                        if j + 1 < len(lines):
                            next_next = lines[j + 1].strip()
                            if next_next and not re.match(r"^\d+\s*[-–]", next_next) and not re.search(r"Tipo", next_next, re.IGNORECASE):
                                if not re.match(r"^(Endere|CEP|Munic|Declara|ANO)", next_next, re.IGNORECASE):
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
        # O OCR pode separar labels dos valores - buscar nas próximas linhas
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r"Tipo\s+de\s+[Dd]eclar", line, re.IGNORECASE):
                # Valor na mesma linha
                match = re.search(r"Tipo\s+de\s+[Dd]eclar[^\n:]*[:\s]+(Declar.+)", line, re.IGNORECASE)
                if match:
                    return match.group(1).strip().upper().replace("DECLARAGAO", "DECLARACAO")
                
                # Buscar nas próximas 10 linhas por valor "Declaração de Ajuste Anual"
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j].strip()
                    # Buscar "Declaração de Ajuste Anual" com variações OCR
                    match = re.match(r"^(Declar[aç]?[gç]?[ãa]o\s+de\s+Ajuste\s+Anual[^\n]*)", next_line, re.IGNORECASE)
                    if match:
                        result = match.group(1).strip().upper()
                        result = result.replace("DECLARAGAO", "DECLARACAO")
                        result = result.replace("DECLARAÇAO", "DECLARACAO")
                        result = result.replace("DECLARAÇÃO", "DECLARACAO")
                        return result
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
