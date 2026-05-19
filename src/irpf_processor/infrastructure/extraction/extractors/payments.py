"""Extrator de pagamentos efetuados."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class PaymentsExtractor(ISectionExtractor):
    """Extrai pagamentos efetuados (saude, educacao, pensao, etc)."""
    
    SECTION_MARKER = "PAGAMENTOS EFETUADOS"
    SECTION_END_MARKERS = [
        "DOAÇÕES EFETUADAS",
        "DOAÇÕES A PARTIDOS",
        "RENDIMENTOS ISENTOS",
        "RENDIMENTOS TRIBUTÁVEIS",
        "BENS E DIREITOS",
        "DÍVIDAS E ÔNUS"
    ]
    
    PAYMENT_CODES = {
        "01": "Instrução no Brasil",
        "02": "Instrução no Exterior",
        "03": "Hospitais, clínicas e laboratórios de radiologia no Brasil",
        "04": "Hospitais, clínicas e laboratórios de radiologia no Exterior",
        "05": "Médicos no Brasil",
        "06": "Médicos no Exterior",
        "07": "Dentistas no Brasil",
        "08": "Dentistas no Exterior",
        "09": "Psicólogos no Brasil",
        "10": "Psicólogos no Exterior",
        "11": "Fisioterapeutas no Brasil",
        "12": "Fisioterapeutas no Exterior",
        "13": "Fonoaudiólogos no Brasil",
        "14": "Fonoaudiólogos no Exterior",
        "15": "Terapeutas ocupacionais no Brasil",
        "16": "Terapeutas ocupacionais no Exterior",
        "17": "Advogados no Brasil",
        "18": "Advogados no Exterior",
        "19": "Engenheiros no Brasil",
        "20": "Engenheiros no Exterior",
        "21": "Corretores no Brasil",
        "22": "Corretores no Exterior",
        "23": "Outros profissionais no Brasil",
        "24": "Outros profissionais no Exterior",
        "25": "Pensão alimentícia judicial",
        "26": "Pensão alimentícia - separação/divórcio",
        "27": "Pensão alimentícia - acordo homologado",
        "28": "Pensão alimentícia - escritura pública",
        "29": "Planos de saúde no Brasil - CNPJ",
        "30": "Planos de saúde no Brasil - titular",
        "36": "Previdência complementar",
        "37": "Fapi",
        "38": "Funpresp",
        "40": "Doações em espécie",
        "99": "Outros"
    }
    
    @property
    def section_name(self) -> str:
        return "payments_made"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            if self.SECTION_MARKER in upper_text:
                in_section = True
            
            if in_section and not section_ended:
                page_items, found_end = self._extract_from_page_with_end_detection(page_text, page_num)
                items.extend(page_items)
                
                if found_end:
                    section_ended = True
        
        if not items:
            return None

        total_value = round(sum(i.get("value", 0) for i in items), 2)

        return {
            "section_name": "Pagamentos Efetuados",
            "items": items,
            "total_value": total_value,
            "pages_with_problems": []
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items, _ = self._extract_from_page_with_end_detection(page_text, page_num)
        return items
    
    def _extract_from_page_with_end_detection(self, page_text: str, page_num: int) -> tuple[list[dict], bool]:
        items = []
        lines = page_text.split("\n")
        found_end = False
        
        in_section = False
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            if "PAGAMENTOS EFETUADOS" in upper_line:
                in_section = True
                i += 1
                continue
            
            if not in_section:
                i += 1
                continue
            
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                found_end = True
                break
            
            if "CÓDIGO" in upper_line or "TOTAL" in upper_line or "SEM INFORMAÇÕES" in upper_line:
                i += 1
                continue
            
            if upper_line.startswith("CÓD.") or upper_line.startswith("COD."):
                i += 1
                continue
            
            if "BENEFICIÁRIO" in upper_line or "DEDUTÍVEL" in upper_line:
                i += 1
                continue
            
            if upper_line.startswith("TITULAR") or upper_line.startswith("PÁGINA"):
                i += 1
                continue
            
            item = self._try_parse_payment(line, lines, i, page_num)
            if item:
                items.append(item)
                i = item.pop("_next_index", i + 1)
                continue
            
            i += 1
        
        return items, found_end
    
    def _try_parse_payment(
        self, 
        line: str, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        pattern_with_two_values = re.match(
            r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
            line
        )
        
        if pattern_with_two_values:
            return self._parse_payment_line_with_deductible(pattern_with_two_values, lines, idx, page_num)
        
        pattern_with_value = re.match(
            r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s*$",
            line
        )
        
        if pattern_with_value:
            return self._parse_payment_line(pattern_with_value, lines, idx, page_num)
        
        pattern_code_only = re.match(r"^(\d{2})\s+(.+)$", line)
        if pattern_code_only:
            code = pattern_code_only.group(1)
            if code in self.PAYMENT_CODES or code.isdigit():
                return self._parse_payment_multiline(pattern_code_only, lines, idx, page_num)
        
        return None
    
    def _parse_payment_line_with_deductible(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        code = match.group(1)
        desc_and_beneficiary = match.group(2).strip()
        value = parse_currency(match.group(3))
        non_deductible = parse_currency(match.group(4))
        
        beneficiary_cpf_cnpj = ""
        beneficiary_name = ""
        description = desc_and_beneficiary
        
        cpf_match = re.search(r"(\d{3}\.\d{3}\.\d{3}-\d{2})", desc_and_beneficiary)
        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", desc_and_beneficiary)
        
        if cnpj_match:
            beneficiary_cpf_cnpj = cnpj_match.group(1)
            parts = desc_and_beneficiary.split(beneficiary_cpf_cnpj)
            if len(parts) >= 2:
                beneficiary_name = parts[0].strip()
                description = code
        elif cpf_match:
            beneficiary_cpf_cnpj = cpf_match.group(1)
            parts = desc_and_beneficiary.split(beneficiary_cpf_cnpj)
            if len(parts) >= 2:
                beneficiary_name = parts[0].strip()
                description = code
        
        extra_desc_parts = []
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next:
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            is_new_item = re.match(r"^(\d{2})\s+", next_line)
            if is_new_item:
                break
            
            if upper_next.startswith("DESCRIÇÃO:") or upper_next.startswith("DESCRICAO:"):
                j += 1
                continue
            
            if next_line and not next_line.upper().startswith("CÓDIGO"):
                if not re.match(r"^[\d.,]+\s+[\d.,]+\s*$", next_line):
                    extra_desc_parts.append(next_line)
            
            j += 1
        
        full_desc = self.PAYMENT_CODES.get(code, code)
        if extra_desc_parts:
            full_desc = f"{full_desc} - {' '.join(extra_desc_parts)}"
        
        item_id = generate_item_id(f"{code}{beneficiary_cpf_cnpj}{beneficiary_name}")
        
        return {
            "payment_code": code,
            "payment_description": full_desc,
            "beneficiary_cpf_cnpj": beneficiary_cpf_cnpj,
            "beneficiary_name": beneficiary_name,
            "value": value,
            "non_deductible_value": non_deductible,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _parse_payment_line(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        code = match.group(1)
        desc_and_beneficiary = match.group(2).strip()
        value = parse_currency(match.group(3))
        
        beneficiary_cpf_cnpj = ""
        beneficiary_name = ""
        description = desc_and_beneficiary
        
        cpf_match = re.search(r"(\d{3}\.\d{3}\.\d{3}-\d{2})", desc_and_beneficiary)
        cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", desc_and_beneficiary)
        
        if cnpj_match:
            beneficiary_cpf_cnpj = cnpj_match.group(1)
            parts = desc_and_beneficiary.split(beneficiary_cpf_cnpj)
            if len(parts) >= 2:
                description = parts[0].strip()
                beneficiary_name = parts[1].strip()
        elif cpf_match:
            beneficiary_cpf_cnpj = cpf_match.group(1)
            parts = desc_and_beneficiary.split(beneficiary_cpf_cnpj)
            if len(parts) >= 2:
                description = parts[0].strip()
                beneficiary_name = parts[1].strip()
        
        desc_parts = [description]
        name_parts = [beneficiary_name] if beneficiary_name else []
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next:
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            is_new_item = re.match(r"^(\d{2})\s+", next_line)
            if is_new_item:
                break
            
            if re.match(r"^[\d.,]+\s*$", next_line):
                break
            
            if next_line and not next_line.upper().startswith("CÓDIGO"):
                if beneficiary_cpf_cnpj and not beneficiary_name:
                    name_parts.append(next_line)
                elif not re.match(r"^\d+$", next_line):
                    desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        if name_parts:
            beneficiary_name = " ".join(name_parts)
            beneficiary_name = re.sub(r"\s+", " ", beneficiary_name).strip()
        
        item_id = generate_item_id(f"{code}{beneficiary_cpf_cnpj}{full_desc}")
        
        return {
            "payment_code": code,
            "payment_description": full_desc,
            "beneficiary_cpf_cnpj": beneficiary_cpf_cnpj,
            "beneficiary_name": beneficiary_name,
            "value": value,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _parse_payment_multiline(
        self,
        match: re.Match,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        code = match.group(1)
        first_part = match.group(2).strip()
        
        desc_parts = [first_part]
        beneficiary_cpf_cnpj = ""
        beneficiary_name = ""
        value = 0.0
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next:
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            is_new_item = re.match(r"^(\d{2})\s+", next_line)
            if is_new_item and j > idx + 1:
                break
            
            cpf_match = re.search(r"(\d{3}\.\d{3}\.\d{3}-\d{2})", next_line)
            cnpj_match = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", next_line)
            
            if cnpj_match and not beneficiary_cpf_cnpj:
                beneficiary_cpf_cnpj = cnpj_match.group(1)
            elif cpf_match and not beneficiary_cpf_cnpj:
                beneficiary_cpf_cnpj = cpf_match.group(1)
            
            value_match = re.search(r"([\d.,]+)\s*$", next_line)
            if value_match and not re.match(r"^\d{2}\.\d{3}\.\d{3}", next_line):
                potential_value = parse_currency(value_match.group(1))
                if potential_value > 0:
                    value = potential_value
            
            if not next_line.upper().startswith("CÓDIGO"):
                if not re.match(r"^[\d.,]+\s*$", next_line):
                    desc_parts.append(next_line)
            
            j += 1
        
        if value == 0:
            return None
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        full_desc = re.sub(r"\s*[\d.,]+\s*$", "", full_desc).strip()
        
        item_id = generate_item_id(f"{code}{beneficiary_cpf_cnpj}{full_desc}")
        
        return {
            "payment_code": code,
            "payment_description": full_desc,
            "beneficiary_cpf_cnpj": beneficiary_cpf_cnpj,
            "beneficiary_name": beneficiary_name,
            "value": value,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
