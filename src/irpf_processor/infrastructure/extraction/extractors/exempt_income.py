"""Extrator de rendimentos isentos e não tributáveis."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class ExemptIncomeExtractor(ISectionExtractor):
    """Extrai rendimentos isentos e não tributáveis."""
    
    SECTION_MARKER = "RENDIMENTOS ISENTOS"
    
    SUBSECTIONS = {
        "profits_and_dividends": {
            "code": "09",
            "name": "Lucros e dividendos recebidos",
            "keywords": ["lucros", "dividendos"]
        },
        "savings_accounts_mortgage_lci_lca_cra_cri": {
            "code": "12",
            "name": "Rendimentos de cadernetas de poupança, letras hipotecárias, letras de crédito do agronegócio e imobiliário (LCA e LCI) e certificados de recebíveis do agronegócio e imobiliários (CRA e CRI)",
            "keywords": ["poupança", "cadernetas", "lci", "lca"]
        }
    }
    
    @property
    def section_name(self) -> str:
        return "exempt_income"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        subsections = {}
        
        for key, config in self.SUBSECTIONS.items():
            subsection = self._extract_subsection(
                context,
                config["code"],
                config["name"],
                config["keywords"]
            )
            if subsection["items"]:
                subsections[key] = subsection
        
        if not subsections:
            return None
        
        total_value = sum(s["total_value"] for s in subsections.values())
        
        return {
            "section_name": "Rendimentos Isentos e Não Tributáveis",
            "total_value": round(total_value, 2),
            "valid_total": True,
            "subsections": subsections
        }
    
    def _extract_subsection(
        self,
        context: ExtractionContext,
        code: str,
        name: str,
        keywords: list[str]
    ) -> dict:
        items = []
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        for page_idx, (page_num, page_text) in enumerate(sorted_pages):
            lines = page_text.split("\n")
            in_subsection = False
            
            next_page_lines = []
            if page_idx + 1 < len(sorted_pages):
                next_page_lines = sorted_pages[page_idx + 1][1].split("\n")
            
            for i, line in enumerate(lines):
                lower_line = line.lower()
                
                if f"{code}." in line and any(k in lower_line for k in keywords):
                    in_subsection = True
                    continue
                
                if in_subsection:
                    if re.match(r"^\d{2}\.", line) or "TOTAL" in line.upper():
                        in_subsection = False
                        continue
                    
                    item = self._parse_item(line, lines, i, page_num, next_page_lines)
                    if item:
                        items.append(item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": f"{code}. {name}",
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items
        }
    
    def _parse_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int,
        next_page_lines: list[str] = None
    ) -> Optional[dict]:
        pattern = re.match(
            r"^(Titular|Dependente)\s+"
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"(.+?)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if not pattern:
            return None
        
        beneficiary = pattern.group(1)
        cpf = pattern.group(2)
        cnpj = pattern.group(3)
        payer_name = pattern.group(4).strip()
        value = parse_currency(pattern.group(5))
        
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if self._is_name_continuation(next_line):
                payer_name = f"{payer_name} {next_line}"
            elif self._is_last_item_line(idx, lines) and next_page_lines:
                orphan_name = self._get_orphan_name_from_next_page(next_page_lines)
                if orphan_name:
                    payer_name = f"{payer_name} {orphan_name}"
        
        item_id = generate_item_id(f"{cnpj}{cpf}{value}")
        
        return {
            "beneficiary": beneficiary,
            "cpf": cpf,
            "payer_cnpj": cnpj,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num
        }
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        
        if "TOTAL" in line.upper() or "Titular" in line:
            return False
        
        if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+$", line):
            return True
        
        return False
    
    def _is_last_item_line(self, idx: int, lines: list[str]) -> bool:
        for i in range(idx + 1, len(lines)):
            line = lines[i].strip()
            if not line or "Página" in line:
                continue
            if re.match(r"^(Titular|Dependente)\s+\d{3}\.", line):
                return False
            if "TOTAL" in line.upper():
                return False
        return True
    
    def _get_orphan_name_from_next_page(self, next_page_lines: list[str]) -> Optional[str]:
        skip_keywords = [
            "NOME:", "CPF:", "DECLARAÇÃO", "RENDIMENTOS", "Página",
            "PAGAMENTOS", "DOAÇÕES", "BENS E DIREITOS", "TOTAL", "IMPOSTO"
        ]
        
        for line in next_page_lines[:10]:
            line = line.strip()
            if not line or len(line) <= 2:
                continue
            
            if any(skip in line for skip in skip_keywords):
                continue
            
            if re.match(r"^(Titular|Dependente)\s+\d{3}\.", line):
                return None
            
            if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+$", line):
                return line
        
        return None
