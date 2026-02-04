"""Extrator de rendimentos isentos e não tributáveis."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class ExemptIncomeExtractor(ISectionExtractor):
    """Extrai rendimentos isentos e não tributáveis."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS",
        "RENDIMENTOS ISENTOS"
    ]
    
    SECTION_END_MARKERS = [
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "RENDIMENTOS TRIBUTÁVEIS",
        "PAGAMENTOS EFETUADOS",
        "DOAÇÕES EFETUADAS",
        "BENS E DIREITOS"
    ]
    
    SUBSECTIONS = {
        "insurance_payouts_for_death_or_permanent_disability": {
            "code": "03",
            "name": "Indenizações por rescisão de contrato de trabalho, inclusive a título de PDV, e por acidente de trabalho; e FGTS",
            "keywords": ["indenizações", "rescisão", "acidente", "fgts"]
        },
        "profits_and_dividends": {
            "code": "09",
            "name": "Lucros e dividendos recebidos",
            "keywords": ["lucros", "dividendos"]
        },
        "tax_free_retirement_income_for_seniors_age_65_and_over": {
            "code": "10",
            "name": "Parcela isenta de proventos de aposentadoria, reserva remunerada, reforma e pensão de declarante com 65 anos ou mais",
            "keywords": ["parcela isenta", "aposentadoria", "65 anos"]
        },
        "savings_accounts_mortgage_lci_lca_cra_cri": {
            "code": "12",
            "name": "Rendimentos de cadernetas de poupança, letras hipotecárias, letras de crédito do agronegócio e imobiliário (LCA e LCI) e certificados de recebíveis do agronegócio e imobiliários (CRA e CRI)",
            "keywords": ["poupança", "cadernetas", "lci", "lca", "letras"]
        },
        "asset_transfers_donations_and_inheritances": {
            "code": "14",
            "name": "Transferências patrimoniais - doações e heranças",
            "keywords": ["transferências patrimoniais", "doações", "heranças", "doação", "herança"]
        },
        "exempt_portion_from_rural_activity": {
            "code": "15",
            "name": "Parcela não tributável correspondente à atividade rural",
            "keywords": ["parcela não tributável", "atividade rural", "rural"]
        },
        "capital_reserves_incorporation": {
            "code": "18",
            "name": "Incorporação de reservas ao capital",
            "keywords": ["incorporação", "reservas", "capital"]
        },
        "income_tax_refund_from_previous_years": {
            "code": "25",
            "name": "Restituição do imposto sobre a renda de anos-calendário anteriores",
            "keywords": ["restituição", "imposto", "anos-calendário anteriores", "anos anteriores"]
        },
        "others_99": {
            "code": "99",
            "name": "Outros",
            "keywords": ["outros"]
        }
    }
    
    @property
    def section_name(self) -> str:
        return "exempt_income"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        if not self.can_extract(context):
            return None
        
        total_from_pdf = self._extract_total_from_pdf(context)
        
        subsections = {}
        
        for key, config in self.SUBSECTIONS.items():
            if key == "tax_free_retirement_income_for_seniors_age_65_and_over":
                subsection = self._extract_retirement_subsection(context, config)
            elif key == "others_99":
                subsection = self._extract_others_subsection(context, config)
            else:
                subsection = self._extract_subsection(
                    context,
                    config["code"],
                    config["name"],
                    config["keywords"]
                )
            if subsection and (subsection.get("items") or subsection.get("total_value", 0) > 0):
                subsections[key] = subsection
        
        total_value = sum(s.get("total_value", 0) for s in subsections.values()) if subsections else 0.0
        
        if total_from_pdf is not None:
            total_value = total_from_pdf
        
        return {
            "section_name": "Rendimentos Isentos e Não Tributáveis",
            "total_value": round(total_value, 2),
            "valid_total": True,
            "subsections": subsections,
            "items_count": sum(len(s.get("items", []) or []) for s in subsections.values())
        }
    
    def _extract_total_from_pdf(self, context: ExtractionContext) -> Optional[float]:
        for page_text in context.pages_text.values():
            upper_text = page_text.upper()
            if any(marker in upper_text for marker in self.SECTION_MARKERS):
                lines = page_text.split("\n")
                for i, line in enumerate(lines):
                    if any(marker in line.upper() for marker in self.SECTION_MARKERS):
                        for j in range(i, min(i + 5, len(lines))):
                            total_match = re.match(r"^TOTAL\s+([\d.,]+)\s*$", lines[j].strip(), re.IGNORECASE)
                            if total_match:
                                return parse_currency(total_match.group(1))
        return None
    
    def _extract_retirement_subsection(self, context: ExtractionContext, config: dict) -> Optional[dict]:
        code = config["code"]
        name = config["name"]
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        for page_num, page_text in sorted_pages:
            if f"{code}." not in page_text:
                continue
            
            lines = page_text.split("\n")
            in_subsection = False
            current_item = None
            
            for i, line in enumerate(lines):
                lower_line = line.lower()
                
                if f"{code}." in line and ("parcela isenta" in lower_line or "aposentadoria" in lower_line):
                    in_subsection = True
                    continue
                
                if in_subsection:
                    if re.match(r"^\d{2}\.", line) or "TOTAL" in line.upper():
                        if current_item:
                            items.append(current_item)
                            current_item = None
                        in_subsection = False
                        continue
                    
                    item_match = re.match(
                        r"^(Titular|Dependente)\s+"
                        r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
                        r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
                        r"(.+)$",
                        line.strip()
                    )
                    
                    if item_match:
                        if current_item:
                            items.append(current_item)
                        
                        current_item = {
                            "beneficiary": item_match.group(1),
                            "cpf": item_match.group(2),
                            "payer_cnpj": item_match.group(3),
                            "payer_name": item_match.group(4).strip(),
                            "value": 0.0,
                            "thirteenth_salary": 0.0,
                            "page": page_num
                        }
                    elif current_item and "Valor:" not in line and not re.match(r"^(Titular|Dependente)", line):
                        name_continuation = line.strip()
                        if name_continuation and re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", name_continuation) and "Valor:" not in name_continuation:
                            current_item["payer_name"] = f"{current_item['payer_name']} {name_continuation}"
                    
                    if current_item and "Valor:" in line:
                        valor_match = re.search(r"Valor:\s*([\d.,]+)", line)
                        if valor_match:
                            current_item["value"] = parse_currency(valor_match.group(1))
                        
                        salario_match = re.search(r"13[º°]?\s*Salário:\s*([\d.,]+)", line)
                        if salario_match:
                            current_item["thirteenth_salary"] = parse_currency(salario_match.group(1))
            
            # Adicionar último item se existir
            if current_item:
                items.append(current_item)
        
        if not items:
            return None
        
        for item in items:
            item["id"] = generate_item_id(f"{item['payer_cnpj']}{item['cpf']}{item['value']}")
        
        total = round(sum(i["value"] + i.get("thirteenth_salary", 0) for i in items), 2)
        
        return {
            "name": f"{code}. {name}",
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items
        }
    
    def _extract_others_subsection(self, context: ExtractionContext, config: dict) -> dict:
        """Extrai subseção 99. Outros."""
        code = config["code"]
        name = config["name"]
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_section = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Verificar se estamos na seção de rendimentos isentos
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                in_section = True
            
            if not in_section:
                continue
            
            lines = page_text.split("\n")
            in_subsection = False
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar início da subseção 99
                if re.search(r"99[.\s]+OUTROS", upper_line, re.IGNORECASE):
                    in_subsection = True
                    continue
                
                # Detectar fim da subseção
                if in_subsection:
                    if re.match(r"^\d{2}\.", line) and not line.startswith("99"):
                        in_subsection = False
                        continue
                    if "TOTAL" in upper_line and not re.search(r"TITULAR|DEPENDENTE", upper_line):
                        in_subsection = False
                        continue
                    if any(end in upper_line for end in self.SECTION_END_MARKERS):
                        in_subsection = False
                        continue
                
                if in_subsection:
                    item = self._parse_others_item(line, lines, i, page_num)
                    if item:
                        key = f"{item.get('payer_cpf_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": f"{code}. {name}",
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _parse_others_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item de 'Outros' com descrição."""
        # Formato: Titular/Dependente CPF CPF/CNPJ Nome Descrição Valor
        # ou formato multiline
        
        # Tentar formato inline
        pattern = re.match(
            r"^(Titular|Dependente)\s+"
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(.+?)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern:
            beneficiary = pattern.group(1)
            cpf = pattern.group(2)
            payer_cpf_cnpj = pattern.group(3)
            remaining = pattern.group(4).strip()
            value = parse_currency(pattern.group(5))
            
            # Separar nome do pagador da descrição
            payer_name = remaining
            description = ""
            
            # Procurar descrição nas linhas seguintes
            for j in range(idx + 1, min(idx + 4, len(lines))):
                next_line = lines[j].strip()
                if next_line and not re.match(r"^(Titular|Dependente|[\d.,]+|\d{2}\.)", next_line):
                    if "TOTAL" not in next_line.upper():
                        description = next_line
                        break
            
            item_id = generate_item_id(f"{payer_cpf_cnpj}{cpf}{value}")
            
            return {
                "beneficiary": beneficiary,
                "cpf": cpf,
                "payer_cpf_cnpj": payer_cpf_cnpj,
                "payer_name": payer_name,
                "description": description,
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        return None
    
    def _extract_subsection(
        self,
        context: ExtractionContext,
        code: str,
        name: str,
        keywords: list[str]
    ) -> dict:
        items = []
        seen_keys = set()
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_main_section = False
        in_subsection = False  # Manter estado entre páginas
        section_ended = False
        
        for page_idx, (page_num, page_text) in enumerate(sorted_pages):
            if section_ended:
                break
            
            lines = page_text.split("\n")
            
            next_page_lines = []
            if page_idx + 1 < len(sorted_pages):
                next_page_lines = sorted_pages[page_idx + 1][1].split("\n")
            
            for i, line in enumerate(lines):
                lower_line = line.lower()
                upper_line = line.upper()
                
                # Detectar início da seção principal
                if any(marker in upper_line for marker in self.SECTION_MARKERS):
                    in_main_section = True
                    continue
                
                if not in_main_section:
                    continue
                
                # Detectar fim da seção principal (RENDIMENTOS SUJEITOS À TRIBUTAÇÃO... como título de seção)
                # Só considerar como fim se for início de nova seção (não parte de título de outra seção)
                if "RENDIMENTOS SUJEITOS" in upper_line and "TRIBUTAÇÃO EXCLUSIVA" in upper_line:
                    section_ended = True
                    break
                
                # Detectar início da subseção
                if f"{code}." in line and any(k in lower_line for k in keywords):
                    in_subsection = True
                    continue
                
                # Detectar fim da subseção (outro código de seção como 99., 12., etc.)
                if re.match(r"^\d{2}\.", line) and not line.startswith(f"{code}."):
                    in_subsection = False
                    continue
                
                # Detectar fim por TOTAL (mas não linha de item)
                if "TOTAL" in upper_line and not re.search(r"TITULAR|DEPENDENTE", upper_line):
                    # Verificar se é TOTAL da seção principal ou apenas subtotal
                    if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                        in_subsection = False
                        continue
                
                if in_subsection:
                    # Parsear item
                    item = self._parse_item(line, lines, i, page_num, next_page_lines)
                    if item:
                        key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
                    
                    # Tentar multiline
                    multiline_item = self._parse_multiline_item(lines, i, page_num)
                    if multiline_item:
                        key = f"{multiline_item.get('payer_cnpj', '')}{multiline_item.get('cpf', '')}{multiline_item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(multiline_item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": f"{code}. {name}",
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _parse_multiline_item(
        self,
        lines: list[str],
        start_idx: int,
        page_num: int
    ) -> Optional[dict]:
        cnpj_pattern = r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$"
        cpf_pattern = r"^\d{3}\.\d{3}\.\d{3}-\d{2}$"
        current_line = lines[start_idx].strip()
        
        is_cnpj = re.match(cnpj_pattern, current_line)
        is_cpf_payer = re.match(cpf_pattern, current_line)
        
        if not is_cnpj and not is_cpf_payer:
            return None
        
        payer_doc = current_line
        payer_name = None
        beneficiary = None
        value = None
        cpf = None
        
        for offset in range(1, 8):
            if start_idx + offset >= len(lines):
                break
            
            next_line = lines[start_idx + offset].strip()
            
            if not next_line:
                continue
            
            if next_line in ("Titular", "Dependente"):
                beneficiary = next_line
            elif re.match(cpf_pattern, next_line) and next_line != payer_doc:
                cpf = next_line
            elif re.match(r"^[\d.,]+$", next_line) and "," in next_line:
                parsed_value = parse_currency(next_line)
                if parsed_value > 0:
                    value = parsed_value
            elif re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", next_line) and not re.match(cnpj_pattern, next_line) and not re.match(cpf_pattern, next_line):
                if not re.match(r"^\d{2}\.", next_line) and "TOTAL" not in next_line.upper():
                    if payer_name is None:
                        payer_name = next_line
            
            if (re.match(cnpj_pattern, next_line) or re.match(cpf_pattern, next_line)) and next_line != payer_doc and next_line != cpf:
                break
            if re.match(r"^\d{2}[.\s]+[A-Z]", next_line):
                break
        
        if payer_doc and value is not None and value > 0:
            item_id = generate_item_id(f"{payer_doc}{cpf or ''}{value}")
            return {
                "beneficiary": beneficiary or "Titular",
                "cpf": cpf or "",
                "payer_cnpj": payer_doc,
                "payer_name": payer_name or "",
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        return None
    
    def _parse_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int,
        next_page_lines: list[str] = None
    ) -> Optional[dict]:
        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        
        pattern = re.match(
            rf"^(Titular|Dependente)\s+"
            rf"({CPF_PATTERN})\s+"
            rf"({CNPJ_PATTERN}|{CPF_PATTERN})\s+"
            rf"(.+?)\s+"
            rf"([\d.,]+)\s*$",
            line.strip()
        )
        
        if not pattern:
            return None
        
        beneficiary = pattern.group(1)
        cpf = pattern.group(2)
        payer_doc = pattern.group(3)
        payer_name = pattern.group(4).strip()
        value = parse_currency(pattern.group(5))
        
        is_cnpj = "/" in payer_doc
        cnpj = payer_doc if is_cnpj else ""
        payer_cpf = payer_doc if not is_cnpj else ""
        
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if self._is_name_continuation(next_line):
                payer_name = f"{payer_name} {next_line}"
            elif self._is_last_item_line(idx, lines) and next_page_lines:
                orphan_name = self._get_orphan_name_from_next_page(next_page_lines)
                if orphan_name:
                    payer_name = f"{payer_name} {orphan_name}"
        
        item_id = generate_item_id(f"{payer_doc}{cpf}{value}")
        
        result = {
            "beneficiary": beneficiary,
            "cpf": cpf,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num
        }
        
        if is_cnpj:
            result["payer_cnpj"] = cnpj
        else:
            result["payer_cnpj"] = payer_cpf
        
        return result
    
    def _is_name_continuation(self, line: str) -> bool:
        if len(line) <= 2:
            return False
        
        if "TOTAL" in line.upper() or "Titular" in line or "Dependente" in line:
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
