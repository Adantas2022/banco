"""Extrator de declaração de bens e direitos."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class AssetsExtractor(ISectionExtractor):
    """Extrai declaração de bens e direitos."""
    
    SECTION_MARKER = "DECLARAÇÃO DE BENS E DIREITOS"
    
    @property
    def section_name(self) -> str:
        return "assets_declaration"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        
        for page_num, page_text in context.pages_text.items():
            if self.SECTION_MARKER not in page_text.upper():
                continue
            
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)
        
        if not items:
            return None
        
        last_year_total = round(sum(i["before_year_asset_value"] for i in items), 2)
        current_year_total = round(sum(i["current_year_asset_value"] for i in items), 2)
        
        return {
            "section_name": "Declaração de Bens e Direitos",
            "items": items,
            "last_year_total_value": last_year_total,
            "current_year_total_value": current_year_total,
            "pages_with_problems": []
        }
    
    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            asset_match = re.match(
                r"^(\d{2})\s+(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line
            )
            
            if asset_match:
                item = self._parse_asset_block(
                    lines, i, asset_match, page_num
                )
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue
            
            i += 1
        
        return items
    
    def _parse_asset_block(
        self, 
        lines: list[str], 
        start_idx: int,
        match: re.Match,
        page_num: int
    ) -> Optional[dict]:
        group_code = match.group(1)
        asset_code = match.group(2)
        description_start = match.group(3)
        before_value = parse_currency(match.group(4))
        current_value = parse_currency(match.group(5))
        
        description_parts = [description_start]
        country_code = "105"
        country_name = "BRASIL"
        raw_lines = []
        
        j = start_idx + 1
        while j < len(lines):
            next_line = lines[j].strip()
            
            if re.match(r"^\d{2}\s+\d{2}\s+", next_line):
                break
            
            country_match = re.match(r"^(\d+)\s*[-–]\s*(.+)$", next_line)
            if country_match:
                country_code = country_match.group(1)
                country_name = country_match.group(2).strip()
                j += 1
                continue
            
            if "Página" in next_line and "de" in next_line:
                break
            
            if next_line.upper().startswith("TOTAL") or next_line.upper().startswith("TOTAL DE BENS"):
                break
            
            raw_lines.append(next_line)
            
            if self._is_description_continuation(next_line):
                description_parts.append(next_line)
            
            j += 1
        
        full_description = " ".join(description_parts)
        full_description = re.sub(r"\s+", " ", full_description).strip()
        
        additional_info = self._build_additional_info(
            group_code, raw_lines, full_description
        )
        
        item_id = generate_item_id(f"{group_code}{asset_code}{full_description[:50]}")
        
        return {
            "id": item_id,
            "asset_group_code": group_code,
            "asset_code": asset_code,
            "asset_description": full_description,
            "before_year_asset_value": before_value,
            "current_year_asset_value": current_value,
            "country_code": country_code,
            "country_name": country_name,
            "additional_info": additional_info,
            "country_valid": True,
            "page": page_num,
            "_next_index": j
        }
    
    def _build_additional_info(
        self, 
        group_code: str, 
        raw_lines: list[str],
        description: str
    ) -> dict:
        raw_text = " ".join(raw_lines)
        
        if group_code == "01":
            return self._extract_real_estate_info(raw_lines, raw_text, description)
        elif group_code == "02":
            return self._extract_vehicle_info(raw_lines, raw_text)
        elif group_code in ("03", "04", "05"):
            return self._extract_participation_info(raw_lines, raw_text)
        elif group_code == "06":
            return self._extract_deposit_info(raw_lines, raw_text)
        elif group_code == "07":
            return self._extract_fund_info(raw_lines, raw_text)
        elif group_code == "08":
            return self._extract_crypto_info(raw_lines, raw_text)
        else:
            return self._extract_generic_info(raw_lines, raw_text)
    
    def _extract_real_estate_info(
        self, 
        lines: list[str], 
        raw_text: str,
        description: str
    ) -> dict:
        info = {
            "municipal_registration": "N/A",
            "street_address": "N/A",
            "complement": "N/A",
            "city": "N/A",
            "area": "N/A",
            "registered_at_registy_office": False,
            "matriculation": "N/A",
            "number": "N/A",
            "neighborhood": "N/A",
            "state": "N/A",
            "acquisition_date": "N/A",
            "registry_office_name": "N/A",
            "zipcode": "N/A",
            "cei_cno": "N/A"
        }
        
        for line in lines:
            if "Inscrição Municipal" in line:
                m = re.search(r"Inscrição Municipal[^:]*[:\s]+([\d.-]+)", line)
                if m:
                    info["municipal_registration"] = m.group(1).strip() or "N/A"
            
            if "Logradouro" in line:
                m = re.search(r"Logradouro[:\s]*(.+?)(?:\s+Nº[:\s]|$)", line)
                if m:
                    info["street_address"] = m.group(1).strip() or "N/A"
            
            if "Nº" in line:
                m = re.search(r"Nº[:\s]*(\S+)", line)
                if m:
                    info["number"] = m.group(1).strip() or "N/A"
            
            if "Comp" in line and ":" in line:
                m = re.search(r"Comp[^:]*[:\s]*(.+?)(?:\s+Bairro[:\s]|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val:
                        info["complement"] = val
            
            if "Bairro" in line:
                m = re.search(r"Bairro[:\s]*(.+?)(?:\s+UF[:\s]|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val:
                        info["neighborhood"] = val
            
            if "Município" in line:
                m = re.search(r"Município[:\s]*(.+?)(?:\s+UF[:\s]|$)", line)
                if m:
                    val = m.group(1).strip()
                    if val:
                        info["city"] = val
            
            if "UF" in line:
                m = re.search(r"UF[:\s]*([A-Z]{2})", line)
                if m:
                    info["state"] = m.group(1)
            
            if "CEP" in line:
                m = re.search(r"CEP[:\s]*([\d-]+)", line)
                if m:
                    info["zipcode"] = m.group(1).strip()
            
            if "Área" in line:
                m = re.search(r"Área[^:]*[:\s]*([\d.,]+\s*m²?)", line)
                if m:
                    info["area"] = m.group(1).strip()
            
            if "Data de Aquisição" in line:
                m = re.search(r"Data de Aquisição[:\s]*(\d{2}/\d{2}/\d{4})", line)
                if m:
                    info["acquisition_date"] = m.group(1)
            
            if "Registrado" in line and "Cartório" in line:
                info["registered_at_registy_office"] = "Sim" in line
            
            if "Nome Cartório" in line:
                m = re.search(r"Nome Cartório[:\s]*(.+?)(?:\s+Matrícula|$)", line)
                if m:
                    info["registry_office_name"] = m.group(1).strip() or "N/A"
            
            if "Matrícula" in line:
                m = re.search(r"Matrícula[:\s]*([\d.]+)", line)
                if m:
                    info["matriculation"] = m.group(1)
            
            if "CEI" in line or "CNO" in line:
                m = re.search(r"(?:CEI/?CNO|CEI|CNO)[:\s]*([\d./-]+)", line)
                if m:
                    info["cei_cno"] = m.group(1).strip()
        
        city_desc = re.search(r"(?:RIBEIR[AÃ]O\s+PRETO|[A-Z][A-Za-zÀ-ÿ\s]+)\s*/\s*([A-Z]{2})", description)
        if city_desc:
            if info["state"] == "N/A":
                info["state"] = city_desc.group(1)
            city_match = re.search(r"([A-Z][A-Za-zÀ-ÿ\s]+)\s*/\s*[A-Z]{2}", description)
            if city_match and info["city"] == "N/A":
                info["city"] = city_match.group(1).strip()
        
        number_desc = re.search(r"NR\.?\s*(\d+)", description)
        if number_desc and info["number"] == "N/A":
            info["number"] = number_desc.group(1)
        
        street_desc = re.search(r"(?:SITO\s+A\s+)?(?:RUA|AV\.?|AVENIDA)\s+([A-Z][A-Za-zÀ-ÿ\s]+?)(?:\s+NR|,|\s+\d)", description, re.IGNORECASE)
        if street_desc and info["street_address"] == "N/A":
            info["street_address"] = street_desc.group(1).strip()
        
        mat_desc = re.search(r"MATR[IÍ]CULA\s*(\d+)", description, re.IGNORECASE)
        if mat_desc and info["matriculation"] == "N/A":
            info["matriculation"] = mat_desc.group(1)
            info["registered_at_registy_office"] = True
        
        cri_desc = re.search(r"(\d+[ºOo]?\s*C[RI]{2}[IO]?\s+DE\s+\w+(?:\s+\w+)?)", description, re.IGNORECASE)
        if cri_desc and info["registry_office_name"] == "N/A":
            info["registry_office_name"] = cri_desc.group(1).upper()
            info["registered_at_registy_office"] = True
        
        area_desc = re.search(r"(\d+[,.]?\d*)\s*m[²2]", description, re.IGNORECASE)
        if area_desc and info["area"] == "N/A":
            info["area"] = f"{area_desc.group(1)} m²"
        
        cei_desc = re.search(r"(?:CEI|CNO)[:\s]*([\d./-]+)", description, re.IGNORECASE)
        if cei_desc and info["cei_cno"] == "N/A":
            info["cei_cno"] = cei_desc.group(1).strip()
        
        return info
    
    def _extract_vehicle_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        for line in lines:
            if "RENAVAM" in line.upper():
                m = re.search(r"RENAVAM[:\s]*(\d+)", line, re.IGNORECASE)
                if m:
                    info["renavam"] = m.group(1)
            
            elif "Registro de Embarcação" in line:
                m = re.search(r"Registro de Embarcação[:\s]*(.+)", line)
                if m:
                    info["vessel_registration"] = m.group(1).strip()
        
        return info
    
    def _extract_participation_info(self, lines: list[str], raw_text: str) -> dict:
        info = {
            "beneficiary": None,
            "cpf": None
        }
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj:
            info["cnpj"] = cnpj.group(1)
        else:
            cnpj_raw = re.search(r"CNPJ[:\s]*(\d{11,14})", raw_text)
            if cnpj_raw:
                info["cnpj"] = cnpj_raw.group(1)
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.\d{3}\.\d{3}-\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        traded_match = re.search(r"Negociad[oa]s em Bolsa[:\s]*(Sim|Não)", raw_text)
        if traded_match:
            info["traded_on_stock_market"] = traded_match.group(1) == "Sim"
        
        trading_code_match = re.search(r"Código de Negociação[:\s]*([A-Z0-9]+)", raw_text)
        if trading_code_match:
            info["trading_code"] = trading_code_match.group(1)
        
        trading_code_desc = re.search(r"(?:TICKER|CÓDIGO)[:\s]*([A-Z]{4}\d+)", raw_text, re.IGNORECASE)
        if trading_code_desc and "trading_code" not in info:
            info["trading_code"] = trading_code_desc.group(1)
        
        bank = re.search(r"Banco[:\s]*(\d+)", raw_text)
        if bank:
            info["bank"] = bank.group(1)
        
        agency = re.search(r"Ag[êe]ncia[:\s]*(\d+[-\d]*)", raw_text)
        if agency:
            info["agency"] = agency.group(1)
        
        account = re.search(r"Conta[:\s]*([\d-]+)", raw_text)
        if account:
            info["account"] = account.group(1)
        
        return info
    
    def _extract_deposit_info(self, lines: list[str], raw_text: str) -> dict:
        info = {
            "beneficiary": "N/A",
            "cpf": "N/A"
        }
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj:
            info["cnpj"] = cnpj.group(1)
        
        bank = re.search(r"Banco[:\s]*(\d+)", raw_text)
        if bank:
            info["bank"] = bank.group(1)
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.\d{3}\.\d{3}-\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        agency = re.search(r"Ag[êe]ncia[:\s]*(\d+[-\d]*)", raw_text)
        if agency:
            info["agency"] = agency.group(1)
        
        account = re.search(r"Conta[:\s]*([\d-]+)", raw_text)
        if account:
            info["account"] = account.group(1)
        
        if "Conta Pagamento" in raw_text:
            info["is_payment_account"] = "Sim" in raw_text.split("Conta Pagamento")[1][:20]
        else:
            info["is_payment_account"] = False
        
        return info
    
    def _extract_fund_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.\d{3}\.\d{3}-\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        cnpj_fund = re.search(r"CNPJ do Fundo[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj_fund:
            info["cnpj"] = cnpj_fund.group(1)
        else:
            cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
            if cnpj:
                info["cnpj"] = cnpj.group(1)
            else:
                cnpj_raw = re.search(r"CNPJ[:\s]*(\d{14})", raw_text)
                if cnpj_raw:
                    info["cnpj"] = cnpj_raw.group(1)
        
        custodian_cnpj = re.search(r"CNPJ (?:do )?Custodiante[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if custodian_cnpj:
            info["custodian_cnpj"] = custodian_cnpj.group(1)
        
        if "Autocustodiante" in raw_text:
            info["self_custodian"] = "Sim" in raw_text.split("Autocustodiante")[1][:20]
        elif "Próprio Custodiante" in raw_text:
            info["self_custodian"] = "Sim" in raw_text.split("Próprio Custodiante")[1][:20]
        
        if "Negociados em Bolsa" in raw_text:
            info["traded_on_stock_market"] = "Sim" in raw_text
        
        trading_code = re.search(r"Código de Negociação[:\s]*([A-Z0-9]+)", raw_text)
        if trading_code:
            info["trading_code"] = trading_code.group(1)
        
        profit_loss = re.search(r"Lucro ou Prejuízo[:\s]*([\d.,]+)", raw_text)
        tax_abroad = re.search(r"Imposto Pago no Exterior[:\s]*([\d.,]+)", raw_text)
        
        if profit_loss or tax_abroad:
            info["financial_application"] = {
                "items": {
                    "profit_or_loss": parse_currency(profit_loss.group(1)) if profit_loss else 0.0,
                    "tax_paid_abroad": parse_currency(tax_abroad.group(1)) if tax_abroad else 0.0
                }
            }
        
        value_received = re.search(r"Valor Recebido[:\s]*([\d.,]+)", raw_text)
        irrf_abroad = re.search(r"Imposto Pago Exterior/IRRF Brasil[:\s]*([\d.,]+)", raw_text)
        
        if value_received or irrf_abroad:
            info["profits_and_dividends"] = {
                "items": {
                    "value_received": parse_currency(value_received.group(1)) if value_received else 0.0,
                    "tax_paid_abroad_irrf": parse_currency(irrf_abroad.group(1)) if irrf_abroad else 0.0
                }
            }
        
        return info
    
    def _extract_crypto_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        beneficiary = self._find_beneficiary(lines)
        if beneficiary:
            info["beneficiary"] = beneficiary
        
        cnpj = re.search(r"(?<!Custodiante[:\s])CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        info["cnpj"] = cnpj.group(1) if cnpj else "N/A"
        
        custodian = re.search(r"CNPJ Custodiante[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if custodian:
            info["custodian_cnpj"] = custodian.group(1)
        
        if "Autocustodiante" in raw_text:
            info["self_custodian"] = "Sim" in raw_text.split("Autocustodiante")[1][:10]
        
        cpf = re.search(r"CPF[:\s]*(\d{3}\.\d{3}\.\d{3}-\d{2})", raw_text)
        if cpf:
            info["cpf"] = cpf.group(1)
        
        return info
    
    def _extract_generic_info(self, lines: list[str], raw_text: str) -> dict:
        info = {}
        
        cnpj = re.search(r"CNPJ[:\s]*(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})", raw_text)
        if cnpj:
            info["cnpj"] = cnpj.group(1)
        
        return info
    
    def _find_beneficiary(self, lines: list[str]) -> Optional[str]:
        for line in lines:
            if "Bem" in line and "Titular" in line:
                return "Titular"
            if "Bem" in line and "Dependente" in line:
                return "Dependente"
        return None
    
    def _is_description_continuation(self, line: str) -> bool:
        skip_prefixes = (
            "Bem", "Inscrição", "Logradouro", "Comp", "Município",
            "Área", "Registrado", "Nome Cartório", "Nº", "RENAVAM",
            "Registro de Embarcação", "Matrícula", "Banco", "Agência",
            "Conta", "Negociados", "Código de Neg", "Autocustodiante",
            "CNPJ", "CPF", "Lucro ou", "Valor Recebido", "Imposto",
            "CEI", "CNO", "CEI/CNO", "Aplicação Financeira", "UF",
            "Bairro", "Data de Aquisição", "CNPJ do Fundo", "CNPJ Custodiante"
        )
        
        if not line or len(line) <= 3:
            return False
        
        if re.match(r"^\d{2}\s+\d{2}\s+", line):
            return False
        
        if re.match(r"^\d+$", line):
            return False
        
        if any(line.startswith(p) for p in skip_prefixes):
            return False
        
        if re.match(r"^CEI/?CNO[:\s]", line, re.IGNORECASE):
            return False
        
        return True
