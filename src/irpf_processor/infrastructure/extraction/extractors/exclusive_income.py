"""Extrator de rendimentos sujeitos à tributação exclusiva/definitiva."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id


class ExclusiveIncomeExtractor(ISectionExtractor):
    """Extrai rendimentos de tributação exclusiva/definitiva."""
    
    SECTION_MARKERS = [
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA",
        "RENDIMENTOS SUJEITOS A TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA",
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA",
        "RENDIMENTOS SUJEITOS A TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA",  # Post-processor com espaços
        "TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA",
        "TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA",  # Post-processor com espaços
        "TRIBUTAÇÃO EXCLUSIVA",
        # OCR variations - sem acentos (antes do post-processor)
        "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA/DEFINITIVA",
        "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA / DEFINITIVA",  # Com espaços ao redor do /
        "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA",
        "TRIBUTACAO EXCLUSIVA/DEFINITIVA",
        "TRIBUTACAO EXCLUSIVA / DEFINITIVA",  # Com espaços ao redor do /
        "TRIBUTACAO EXCLUSIVA",
        # OCR with Ç→G
        "TRIBUTAGAO EXCLUSIVA",
    ]
    
    SECTION_END_MARKERS = [
        # Só incluir markers que vêm DEPOIS desta seção no PDF
        "PAGAMENTOS EFETUADOS",
        "DOAÇÕES EFETUADAS",
        "DOACOES EFETUADAS",
        "BENS E DIREITOS",
        "INFORMAÇÕES COMPLEMENTARES",
        "INFORMACOES COMPLEMENTARES",
    ]
    
    @property
    def section_name(self) -> str:
        return "exclusive_taxation_income"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        section_lines = self._get_section_lines(context)
        if not section_lines:
            return None
        
        section_text = "\n".join(line for _, line in section_lines)
        
        subsections = {}
        
        thirteenth = self._extract_thirteenth_salary(section_text)
        if thirteenth:
            subsections["thirteenth_salary"] = thirteenth
        
        thirteenth_dependents = self._extract_thirteenth_salary_dependents(section_text)
        if thirteenth_dependents:
            subsections["thirteen_salary_received_by_dependents"] = thirteenth_dependents

        capital_gains = self._extract_capital_gains(section_text)
        if capital_gains:
            subsections["capital_gains_from_sale_of_assets_and_or_rights"] = capital_gains

        plr = self._extract_profit_sharing(section_lines)
        if plr:
            subsections["profit_or_results_sharing"] = plr
        
        variable_income = self._extract_variable_income_gains(section_text)
        if variable_income:
            subsections["net_gains_from_variable_income_stocks_futures_and_reits"] = variable_income
        
        financial = self._extract_financial_income(section_lines, context)
        if financial and (financial.get("items") or financial.get("total_value", 0) > 0):
            subsections["income_from_financial_investments"] = financial
        
        accumulated = self._extract_accumulated_income(section_text)
        if accumulated:
            subsections["accumulated_income_received"] = accumulated
        
        accumulated_dependents = self._extract_accumulated_income_dependents(section_text)
        if accumulated_dependents:
            subsections["accumulated_income_received_by_dependents"] = accumulated_dependents
        
        interest = self._extract_interest_on_capital(section_lines)
        if interest and interest.get("items"):
            subsections["interest_on_own_capital"] = interest
        
        abroad = self._extract_financial_abroad(section_text)
        if abroad:
            subsections["financial_investments_and_profits_and_dividends_abroad"] = abroad
        
        others = self._extract_others(section_lines)
        if others and others.get("items"):
            subsections["others"] = others
        
        total_value = sum(s.get("total_value", 0) for s in subsections.values())
        
        if not subsections:
            section_total = self._extract_section_total_from_lines(section_lines)
            if section_total is not None:
                total_value = section_total
            else:
                return None
        
        return {
            "section_name": "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva",
            "total_value": round(total_value, 2),
            "valid_total": True,
            "subsections": subsections
        }
    
    def _get_section_lines(
        self, context: ExtractionContext
    ) -> list[tuple[int, str]]:
        """Retorna APENAS as linhas dentro dos limites da seção exclusive_taxation.

        Usa markers restritivos: exige "RENDIMENTOS SUJEITOS" antes de
        "TRIBUTAÇÃO EXCLUSIVA" para evitar falsos positivos em descrições.

        Suporta headers divididos em duas linhas consecutivas (Document AI).
        """
        result: list[tuple[int, str]] = []
        in_section = False
        pending_rendimentos = False

        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])

        for page_num, page_text in sorted_pages:
            for line in page_text.split("\n"):
                upper = line.upper()

                if not in_section:
                    if (
                        "RENDIMENTOS SUJEITOS" in upper
                        and ("TRIBUTAÇÃO EXCLUSIVA" in upper
                             or "TRIBUTACAO EXCLUSIVA" in upper
                             or "TRIBUTAGAO EXCLUSIVA" in upper)
                    ):
                        in_section = True
                        continue

                    if pending_rendimentos and (
                        "TRIBUTAÇÃO EXCLUSIVA" in upper
                        or "TRIBUTACAO EXCLUSIVA" in upper
                        or "TRIBUTAGAO EXCLUSIVA" in upper
                    ):
                        in_section = True
                        continue

                    pending_rendimentos = "RENDIMENTOS SUJEITOS" in upper
                    continue

                if any(m in upper for m in self.SECTION_END_MARKERS):
                    return result

                result.append((page_num, line))

        return result
    
    def _extract_section_total_from_lines(
        self, section_lines: list[tuple[int, str]]
    ) -> Optional[float]:
        """Extrai o TOTAL da seção a partir das linhas filtradas."""
        found_total_line = False
        
        for _, line in section_lines:
            stripped = line.strip()
            
            match = re.match(r"^\s*TOTAL\s+([\d.,]+)\s*$", line, re.IGNORECASE)
            if match:
                return parse_currency(match.group(1))
            
            if re.match(r"^\s*TOTAL\s*$", stripped, re.IGNORECASE):
                found_total_line = True
                continue
            
            if found_total_line:
                if not stripped:
                    continue
                value_match = re.match(r"^\s*([\d]{1,3}(?:[.\s]?\d{3})*,\d{2})\s*$", stripped)
                if value_match:
                    return parse_currency(value_match.group(1))
        
        return None
    
    def _extract_thirteenth_salary(self, section_text: str) -> Optional[dict]:
        """Extrai 01. 13º salário."""
        patterns = [
            r"01[.\s]+13[º°]?\s*(?:sal[aá]rio|SALARIO)\s+([\d.,]+)",
            r"01[.\s]+(?:DECIMO\s+TERCEIRO|13.?\s*SALARIO)[^\d]*([\d.,]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                value = parse_currency(match.group(1))
                return {
                    "name": "01. 13º salário",
                    "code": "01",
                    "total_value": value,
                    "valid_total": True,
                    "items": None
                }
        return None
    
    def _extract_thirteenth_salary_dependents(self, section_text: str) -> Optional[dict]:
        """Extrai 08. 13º salário recebido pelos dependentes."""
        patterns = [
            r"08[.\s]+13[º°]?\s*(?:sal[aá]rio|SALARIO)\s+(?:recebido\s+)?(?:pelos?\s+)?(?:dependentes?)[^\d]*([\d.,]+)",
            r"08[.\s]+(?:DECIMO\s+TERCEIRO|13.?\s*SALARIO)\s+(?:RECEBIDO\s+)?(?:PELOS?\s+)?DEPENDENTES?[^\d]*([\d.,]+)",
            r"08[.\s]+13[º°]?\s*sal[aá]rio\s+dependentes?\s+([\d.,]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                value = parse_currency(match.group(1))
                return {
                    "name": "08. 13º salário recebido pelos dependentes",
                    "code": "08",
                    "total_value": value,
                    "valid_total": True,
                    "items": None
                }
        return None
    
    def _extract_capital_gains(self, section_text: str) -> Optional[dict]:
        """Extrai 02. Ganhos de capital na alienação de bens e/ou direitos."""
        patterns = [
            r"02[.\s]+(?:Ganhos\s+de\s+)?(?:capital|CAPITAL)\s+(?:na\s+)?(?:aliena[çc][aã]o|ALIENACAO|ALIENAÇÃO)\s+(?:de\s+)?(?:bens|BENS)[^\d]*([\d.,]+)",
            r"02[.\s]+GANHOS\s+DE\s+CAPITAL[^\d]*([\d.,]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                value = parse_currency(match.group(1))
                return {
                    "name": "02. Ganhos de capital na alienação de bens e/ou direitos",
                    "code": "02",
                    "total_value": value,
                    "valid_total": True,
                    "items": None
                }
        return None

    def _extract_profit_sharing(self, section_lines: list[tuple[int, str]]) -> Optional[dict]:
        """Extrai 11. Participação nos lucros ou resultados (PLR).
        
        BUG #81758 fix: Corrigido código de 03 para 11 (código correto conforme IRPF).
        BUG #81758 fix v2: Adicionada extração de items detalhados (beneficiary, cpf, cnpj, etc.)
        """
        items = []
        seen_keys = set()
        total_value = 0.0
        in_subsection = False
        
        subsection_11_patterns = [
            r"11[.\s]+(?:PARTICIPA[CÇ][AÃ]O\s+)?(?:NOS\s+)?LUCROS",
            r"11[.\s]+PLR",
            r"11[.\s]+PARTICIPA[CÇ][AÃ]O\s+DOS\s+TRABALHADORES",
        ]
        
        lines_list = [line for _, line in section_lines]
        
        for i, (page_num, line) in enumerate(section_lines):
            upper_line = line.upper()
            
            for pattern in subsection_11_patterns:
                if re.search(pattern, upper_line, re.IGNORECASE):
                    in_subsection = True
                    total_match = re.search(r"([\d]{1,3}(?:[.\s]?\d{3})*,\d{2})\s*$", line)
                    if total_match:
                        total_value = parse_currency(total_match.group(1))
                    break
            
            if re.match(r"^(?:12|13)[.\s]+[A-Z]", line.strip()):
                in_subsection = False
                continue
            
            if re.match(r"^TOTAL\s*(?:[\d.,]+)?\s*$", line.strip(), re.IGNORECASE):
                in_subsection = False
                continue
            
            if "Beneficiário" in line and "CPF" in line and "CNPJ" in line:
                continue
            
            if in_subsection:
                item = self._parse_income_item(line, lines_list, i, page_num)
                if item:
                    continuation = self._collect_name_continuation(lines_list, i)
                    if continuation:
                        item["payer_name"] = f"{item['payer_name']} {continuation}"
                    item["payer_name"] = self._normalize_payer_name(item["payer_name"])
                    key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)

                multiline_item = self._parse_multiline_income_item(lines_list, i, page_num)
                if multiline_item:
                    multiline_item["payer_name"] = self._normalize_payer_name(multiline_item.get("payer_name", ""))
                    key = f"{multiline_item.get('payer_cnpj', '')}{multiline_item.get('cpf', '')}{multiline_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(multiline_item)

                five_line_item = self._parse_5line_income_item(lines_list, i, page_num)
                if five_line_item:
                    five_line_item["payer_name"] = self._normalize_payer_name(five_line_item.get("payer_name", ""))
                    key = f"{five_line_item.get('payer_cnpj', '')}{five_line_item.get('cpf', '')}{five_line_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(five_line_item)

                two_line_item = self._parse_2line_income_item(lines_list, i, page_num)
                if two_line_item:
                    continuation = self._collect_name_continuation(lines_list, i)
                    if continuation and two_line_item.get("payer_name"):
                        two_line_item["payer_name"] = f"{two_line_item['payer_name']} {continuation}"
                    two_line_item["payer_name"] = self._normalize_payer_name(two_line_item.get("payer_name", ""))
                    key = f"{two_line_item.get('payer_cnpj', '')}{two_line_item.get('cpf', '')}{two_line_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(two_line_item)

                loose_item = self._parse_cnpj_name_value_item(lines_list, i, page_num)
                if loose_item:
                    loose_item["payer_name"] = self._normalize_payer_name(loose_item.get("payer_name", ""))
                    key = f"{loose_item.get('payer_cnpj', '')}{loose_item.get('cpf', '')}{loose_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(loose_item)

        self._consolidate_names_by_cnpj(items)

        if total_value == 0 and items:
            total_value = round(sum(i["value"] for i in items), 2)

        if total_value == 0 and not items:
            return None

        return {
            "name": "11. Participação nos lucros ou resultados",
            "code": "11",
            "total_value": total_value,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _extract_variable_income_gains(self, section_text: str) -> Optional[dict]:
        """Extrai 05. Ganhos líquidos em renda variável."""
        patterns = [
            r"05[.\s]+Ganhos\s+l[ií]quidos\s+(?:em\s+)?renda\s+vari[aá]vel[^\d]*([\d.,]+)",
            r"05[.\s]+GANHOS\s+LIQUIDOS[^\d]*([\d.,]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                value = parse_currency(match.group(1))
                return {
                    "name": "05. Ganhos líquidos em renda variável (bolsa de valores, de mercadorias, de futuros e assemelhados e fundos de investimento imobiliário)",
                    "code": "05",
                    "total_value": value,
                    "valid_total": True,
                    "items": None
                }
        return None
    
    def _extract_financial_income(self, section_lines: list[tuple[int, str]], context: ExtractionContext) -> dict:
        """Extrai 06. Rendimentos de aplicações financeiras."""
        items = []
        seen_keys = set()
        in_subsection = False
        
        subsection_06_patterns = [
            r"06[.\s]+(?:RENDIMENTOS|REND\.?)\s*(?:DE\s*)?(?:APLIC|FINANC)",
            r"06[.\s]+APLICACOES\s+FINANCEIRAS",
            r"06[.\s]+APLICAGOES\s+FINANCEIRAS",
            r"06[.\s]+RENDIMENTOS\s+DE\s+APLICACOES\s+FINANCEIRAS",
            r"06\.?\s*Rendimentos\s+de\s+aplica",
            r"06\.?\s+REND",
            r"06\s+Rendimentos",
            r"06[.\s]+Aplica[cç][õo]es",
        ]
        
        lines_list = [line for _, line in section_lines]
        
        for i, (page_num, line) in enumerate(section_lines):
            upper_line = line.upper()
            
            if any(re.search(p, upper_line, re.IGNORECASE) for p in subsection_06_patterns):
                in_subsection = True
                continue
            
            if re.match(r"^(?:07|08|09|10|11|12|13)[.\s]+[A-Z]", line.strip()):
                in_subsection = False
                continue
            
            if re.match(r"^TOTAL\s*(?:[\d.,]+)?\s*$", line.strip(), re.IGNORECASE):
                in_subsection = False
                continue
            
            if in_subsection:
                item = self._parse_income_item(line, lines_list, i, page_num)
                if item:
                    continuation = self._collect_name_continuation(lines_list, i)
                    if continuation:
                        item["payer_name"] = f"{item['payer_name']} {continuation}"
                    item["payer_name"] = self._normalize_payer_name(item["payer_name"])
                    key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)

                multiline_item = self._parse_multiline_income_item(lines_list, i, page_num)
                if multiline_item:
                    multiline_item["payer_name"] = self._normalize_payer_name(multiline_item.get("payer_name", ""))
                    key = f"{multiline_item.get('payer_cnpj', '')}{multiline_item.get('cpf', '')}{multiline_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(multiline_item)

                five_line_item = self._parse_5line_income_item(lines_list, i, page_num)
                if five_line_item:
                    five_line_item["payer_name"] = self._normalize_payer_name(five_line_item.get("payer_name", ""))
                    key = f"{five_line_item.get('payer_cnpj', '')}{five_line_item.get('cpf', '')}{five_line_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(five_line_item)

                two_line_item = self._parse_2line_income_item(lines_list, i, page_num)
                if two_line_item:
                    continuation = self._collect_name_continuation(lines_list, i)
                    if continuation and two_line_item.get("payer_name"):
                        two_line_item["payer_name"] = f"{two_line_item['payer_name']} {continuation}"
                    two_line_item["payer_name"] = self._normalize_payer_name(two_line_item.get("payer_name", ""))
                    key = f"{two_line_item.get('payer_cnpj', '')}{two_line_item.get('cpf', '')}{two_line_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(two_line_item)

        self._consolidate_names_by_cnpj(items)
        total = round(sum(i["value"] for i in items), 2)

        if not items and total == 0:
            extracted_total = self._extract_section_06_total(section_lines, context)
            if extracted_total > 0:
                total = extracted_total

        return {
            "name": "06. Rendimentos de aplicações financeiras",
            "code": "06",
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _extract_section_06_total(self, section_lines: list[tuple[int, str]], context: ExtractionContext) -> float:
        """Extrai total da seção 06 diretamente do OCR quando itens estão separados.
        
        O OCR pode separar tabela em duas partes:
        - Beneficiários e CNPJs no início
        - Valores no final da página, após "(Valores em Reais)" e "Pagina X de Y"
        """
        section_text = "\n".join(line for _, line in section_lines)
        upper_section = section_text.upper()
        
        has_section_06 = bool(re.search(r"06[.\s]+.*(?:APLICAC|FINANC)", upper_section))
        if not has_section_06:
            return 0.0
        
        lines_list = [line for _, line in section_lines]
        
        for line in lines_list:
            match = re.match(r"^\s*TOTAL\s+([\d.,\s]+)\s*$", line, re.IGNORECASE)
            if match:
                value = parse_currency(match.group(1))
                if value < 500000:
                    return value
        
        for i, line in enumerate(lines_list):
            if re.search(r"Pagina\s+\d+\s*de\s*\d+", line, re.IGNORECASE):
                for j in range(i + 1, min(i + 10, len(lines_list))):
                    value_match = re.match(r"^\s*([\d]{1,3}(?:[\s.]?\d{3})*\s*,\s*\d{2})\s*$", lines_list[j])
                    if value_match:
                        value = parse_currency(value_match.group(1))
                        if value > 100 and value < 500000:
                            return value
        return 0.0
    
    def _extract_accumulated_income(self, section_text: str) -> Optional[dict]:
        """Extrai 07. Rendimentos recebidos acumuladamente."""
        match = re.search(
            r"07[.\s]+Rendimentos\s+recebidos\s+acumuladamente[^\d]+([\d.,]+)",
            section_text,
            re.IGNORECASE
        )
        if match:
            value = parse_currency(match.group(1))
            return {
                "name": "07. Rendimentos recebidos acumuladamente",
                "code": "07",
                "total_value": value,
                "valid_total": True,
                "items": None
            }
        return None
    
    def _extract_accumulated_income_dependents(self, section_text: str) -> Optional[dict]:
        """Extrai 09. Rendimentos recebidos acumuladamente pelos dependentes.
        
        BUG #81758 fix: Corrigido código de 08 para 09 (código correto conforme IRPF).
        """
        patterns = [
            r"09[.\s]+Rendimentos\s+recebidos\s+acumuladamente\s+(?:pelos?\s+)?dependentes?[^\d]*([\d.,]+)",
            r"09[.\s]+RENDIMENTOS\s+RECEBIDOS\s+ACUMULADAMENTE\s+(?:PELOS?\s+)?DEPENDENTES?[^\d]*([\d.,]+)",
            r"09[.\s]+(?:rend\.?\s+)?(?:rec\.?\s+)?acumulad(?:os|amente)\s+(?:pelos?\s+)?dep(?:endentes?)?[^\d]*([\d.,]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, section_text, re.IGNORECASE)
            if match:
                value = parse_currency(match.group(1))
                return {
                    "name": "09. Rendimentos recebidos acumuladamente pelos dependentes",
                    "code": "09",
                    "total_value": value,
                    "valid_total": True,
                    "items": None
                }
        return None
    
    def _extract_interest_on_capital(self, section_lines: list[tuple[int, str]]) -> dict:
        """Extrai 10. Juros sobre capital próprio."""
        items = []
        seen_keys = set()
        in_subsection = False
        
        lines_list = [line for _, line in section_lines]
        
        for i, (page_num, line) in enumerate(section_lines):
            upper_line = line.upper()
            
            if re.search(r"10[.\s]+JUROS\s+SOBRE\s+CAPITAL\s+PR[OÓ]PRIO", upper_line, re.IGNORECASE):
                in_subsection = True
                continue
            
            if re.match(r"^(?:11|12|13)[.\s]+", line.strip()):
                in_subsection = False
                continue
            
            if "TOTAL" in upper_line and not re.search(r"TITULAR|DEPENDENTE", upper_line):
                if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                    in_subsection = False
                    continue
            
            if in_subsection and any(m in upper_line for m in self.SECTION_END_MARKERS):
                in_subsection = False
                break
            
            if in_subsection:
                item = self._parse_income_item(line, lines_list, i, page_num)
                if item:
                    continuation = self._collect_name_continuation(lines_list, i)
                    if continuation:
                        item["payer_name"] = f"{item['payer_name']} {continuation}"
                    item["payer_name"] = self._normalize_payer_name(item["payer_name"])
                    key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)

                multiline_item = self._parse_multiline_income_item(lines_list, i, page_num)
                if multiline_item:
                    multiline_item["payer_name"] = self._normalize_payer_name(multiline_item.get("payer_name", ""))
                    key = f"{multiline_item.get('payer_cnpj', '')}{multiline_item.get('cpf', '')}{multiline_item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(multiline_item)

        self._consolidate_names_by_cnpj(items)
        total = round(sum(i["value"] for i in items), 2)

        return {
            "name": "10. Juros sobre capital próprio",
            "code": "10",
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _extract_financial_abroad(self, section_text: str) -> Optional[dict]:
        """Extrai 12. Aplicações Financeiras e Lucros e Dividendos no Exterior."""
        title_pattern = re.compile(
            r"12[.\s]+Aplica[çcg][õo]es\s+Financeiras",
            re.IGNORECASE,
        )
        inline_value_pattern = re.compile(
            r"(\d{1,3}(?:[.,]\d{3})*[.,]\d{2})\s*$"
        )
        standalone_value_pattern = re.compile(
            r"^\s*(\d{1,3}(?:[.,\s]?\d{3})*[.,]\d{2})\s*$"
        )
        next_subsection_pattern = re.compile(r"^(?:13)[.\s]+[A-Z]", re.IGNORECASE)

        lines = section_text.split('\n')
        found_title = False
        lookahead = 0

        for line in lines:
            stripped = line.strip()

            if not found_title:
                if title_pattern.search(line):
                    match = inline_value_pattern.search(line)
                    if match:
                        value = parse_currency(match.group(1))
                        if value > 0:
                            return {
                                "name": "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
                                "code": "12",
                                "total_value": value,
                                "valid_total": True,
                                "items": None,
                            }
                    found_title = True
                    lookahead = 0
                continue

            if not stripped:
                lookahead += 1
                if lookahead > 5:
                    return None
                continue

            lookahead += 1

            if next_subsection_pattern.match(stripped):
                return None
            if re.match(r"^\s*TOTAL", stripped, re.IGNORECASE):
                return None
            if any(m in stripped.upper() for m in self.SECTION_END_MARKERS):
                return None
            if lookahead > 5:
                return None

            match = standalone_value_pattern.match(line)
            if match:
                value = parse_currency(match.group(1))
                if value > 0:
                    return {
                        "name": "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
                        "code": "12",
                        "total_value": value,
                        "valid_total": True,
                        "items": None,
                    }

        return None
    
    def _extract_others(self, section_lines: list[tuple[int, str]]) -> dict:
        """Extrai subsection Outros (code 12 or 13 depending on fiscal year)."""
        items = []
        seen_keys = set()
        in_subsection = False
        detected_code = "13"

        lines_list = [line for _, line in section_lines]

        for i, (page_num, line) in enumerate(section_lines):
            upper_line = line.upper()

            m = re.search(r"(12|13)[.\s]+OUTROS", upper_line, re.IGNORECASE)
            if m:
                detected_code = m.group(1)
                in_subsection = True
                continue
            
            if "TOTAL" in upper_line and not re.search(r"TITULAR|DEPENDENTE", upper_line):
                if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                    in_subsection = False
                    continue
            
            if in_subsection and any(m in upper_line for m in self.SECTION_END_MARKERS):
                in_subsection = False
                break
            
            if in_subsection:
                item = self._parse_others_item(line, lines_list, i, page_num)
                if item:
                    key = f"{item.get('payer_cpf_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}_{i}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": f"{detected_code}. Outros",
            "code": detected_code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    _CONTINUATION_STOP_RE = re.compile(
        r"^(?:Titular|Dependente)\s+"
        r"|^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        r"|^\d{3}\.\d{3}\.\d{3}-\d{2}"
        r"|^\d{2}[.\s]+[A-Z]"
        r"|^TOTAL\s"
        r"|^\s*[\d]{1,3}(?:[.,\s]?\d{3})*[.,]\d{2}\s*$"
        r"|^Controle\s*:",  # Bug #16887: rodapé do PDF digital
        re.IGNORECASE,
    )

    _PAGE_HEADER_RE = re.compile(
        r"^P[aá]gina\s+\d+"
        r"|^NOME\s*:"
        r"|^CPF\s*:"
        r"|^DECLARA"
        r"|^EXERC[IÍ]CIO"
        r"|^Benefici[aá]rio\s+CPF"
        r"|^\(Valores\s+em\s+Reais\)"
        r"|^IMPOSTO\s+SOBRE\s+A\s+RENDA"
        r"|^ANO\s*-?\s*CALEND"
        r"|^Controle\s*:"
        r"|^Data\s*/?\s*Hora\s+d[ae]\s+Entrega"
        r"|^Data\s+d[ae]\s+Entrega"
        r"|^Hora\s+d[ae]\s+Entrega",
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_payer_name(name: str) -> str:
        # Bug #16887: limpar rodapé/metadata do PDF digital concatenado ao nome
        name = re.sub(r"\s*Controle\s*:\s*\d+.*$", "", name)
        name = re.sub(r"\s*Data\s*/?\s*Hora\s+d[ae]\s+Entrega.*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*P[aá]gina\s+\d+\s+de\s*\d+.*$", "", name, flags=re.IGNORECASE)
        # Normalizações padrão
        name = re.sub(r"\bS\s*/\s*A\b", "S/A", name)
        name = re.sub(r"\(\s+", "(", name)
        name = re.sub(r"\s+\)", ")", name)
        name = re.sub(r"\s+,", ",", name)
        return name.strip()

    def _collect_name_continuation(
        self, lines: list[str], matched_idx: int, max_lookahead: int = 8
    ) -> str:
        parts: list[str] = []
        skipped_headers = 0
        for offset in range(1, max_lookahead + 1):
            nxt_idx = matched_idx + offset
            if nxt_idx >= len(lines):
                break
            nxt = lines[nxt_idx].strip()
            if not nxt:
                if skipped_headers:
                    continue
                break
            if self._PAGE_HEADER_RE.search(nxt):
                skipped_headers += 1
                continue
            if self._CONTINUATION_STOP_RE.search(nxt):
                break
            if any(m in nxt.upper() for m in self.SECTION_END_MARKERS):
                break
            if not re.search(r"[A-Za-zÀ-ÿ]", nxt):
                if skipped_headers:
                    continue
                break
            parts.append(nxt)
            if skipped_headers:
                break
        return " ".join(parts)

    @staticmethod
    def _consolidate_names_by_cnpj(items: list[dict]) -> list[dict]:
        from collections import Counter, defaultdict
        cnpj_names: dict[str, set[str]] = defaultdict(set)
        cnpj_name_freq: Counter = Counter()
        first_seen: dict[tuple[str, str], int] = {}
        for pos, item in enumerate(items):
            cnpj = item.get("payer_cnpj", "")
            name = item.get("payer_name", "")
            if cnpj and name:
                cnpj_names[cnpj].add(name)
                cnpj_name_freq[(cnpj, name)] += 1
                if (cnpj, name) not in first_seen:
                    first_seen[(cnpj, name)] = pos

        upgrades: dict[tuple[str, str], str] = {}
        for cnpj, names in cnpj_names.items():
            sorted_names = sorted(names, key=len, reverse=True)
            for i, shorter in enumerate(sorted_names):
                for longer in sorted_names[:i]:
                    if longer.startswith(shorter):
                        upgrades[(cnpj, shorter)] = longer
                        break

            remaining = [n for n in sorted_names if (cnpj, n) not in upgrades]
            for i, name_a in enumerate(remaining):
                if (cnpj, name_a) in upgrades:
                    continue
                for name_b in remaining[:i]:
                    if (cnpj, name_b) in upgrades:
                        continue
                    if len(name_a) != len(name_b) or len(name_a) < 10:
                        continue
                    char_diffs = sum(a != b for a, b in zip(name_a, name_b))
                    if char_diffs == 1:
                        freq_a = cnpj_name_freq[(cnpj, name_a)]
                        freq_b = cnpj_name_freq[(cnpj, name_b)]
                        pos_a = first_seen.get((cnpj, name_a), 0)
                        pos_b = first_seen.get((cnpj, name_b), 0)
                        if freq_b > freq_a or (freq_b == freq_a and pos_b < pos_a):
                            upgrades[(cnpj, name_a)] = name_b
                        else:
                            upgrades[(cnpj, name_b)] = name_a
                        break

        for item in items:
            key = (item.get("payer_cnpj", ""), item.get("payer_name", ""))
            if key in upgrades:
                item["payer_name"] = upgrades[key]

        return items

    def _parse_income_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item de rendimento com formato inline."""
        # Formato 1: Titular/Dependente CPF CNPJ Nome Valor
        pattern1 = re.match(
            r"^(Titular|Dependente)\s+"
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"(.+?)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern1:
            beneficiary = pattern1.group(1)
            cpf = pattern1.group(2)
            cnpj = pattern1.group(3)
            payer_name = pattern1.group(4).strip()
            value = parse_currency(pattern1.group(5))
            
            item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{idx}")
            
            return {
                "beneficiary": beneficiary,
                "cpf": cpf,
                "payer_cnpj": cnpj,
                "payer_name": payer_name,
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        # Formato 2: CNPJ NOME	Beneficiário VALOR	CPF
        # Ex: "40.498.539/0001-37 ITAU OPTIMUS RF LP FIC	Titular 38.204,65	169.407.738-19"
        pattern2 = re.match(
            r"^(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"  # CNPJ
            r"(.+?)\s+"                                # Nome
            r"(Titular|Dependente)\s+"                 # Beneficiário
            r"([\d.,]+)\s+"                            # Valor
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s*$",        # CPF
            line.strip()
        )
        
        if pattern2:
            cnpj = pattern2.group(1)
            payer_name = pattern2.group(2).strip()
            beneficiary = pattern2.group(3)
            value = parse_currency(pattern2.group(4))
            cpf = pattern2.group(5)
            
            item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{idx}")
            
            return {
                "beneficiary": beneficiary,
                "cpf": cpf,
                "payer_cnpj": cnpj,
                "payer_name": payer_name,
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        # Formato 3: Column-aligned com múltiplos espaços (PDFs escaneados)
        # Ex: "Titular             097.427.418-67         22.791.329/0001-50        CAIXA E-SIMPLES FI RENDA FIXA LP                 0,50"
        # Formato: Beneficiário   CPF   CNPJ   Nome   Valor
        pattern3 = re.match(
            r"^\s*(Titular|Dependente)\s{2,}"          # Beneficiário + 2+ espaços
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s{2,}"       # CPF + 2+ espaços
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s{2,}" # CNPJ + 2+ espaços
            r"(.+?)\s{2,}"                              # Nome + 2+ espaços
            r"([\d.,]+)\s*$",                           # Valor
            line
        )
        
        if pattern3:
            beneficiary = pattern3.group(1)
            cpf = pattern3.group(2)
            cnpj = pattern3.group(3)
            payer_name = pattern3.group(4).strip()
            value = parse_currency(pattern3.group(5))
            
            item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{idx}")
            
            return {
                "beneficiary": beneficiary,
                "cpf": cpf,
                "payer_cnpj": cnpj,
                "payer_name": payer_name,
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        # Formato 4: Flexível com tabs ou espaços (OCR variável)
        # Permite separadores flexíveis (\s+ em vez de exatamente 2+)
        pattern4 = re.match(
            r"^\s*(Titular|Dependente)\s+"              # Beneficiário + espaços
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"           # CPF + espaços
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"     # CNPJ + espaços
            r"(.+?)\s+"                                  # Nome + espaços
            r"([\d]{1,3}(?:[.\s]?\d{3})*,\d{2})\s*$",   # Valor brasileiro
            line.strip(),
            re.IGNORECASE
        )
        
        if pattern4:
            beneficiary = pattern4.group(1)
            cpf = pattern4.group(2)
            cnpj = pattern4.group(3)
            payer_name = pattern4.group(4).strip()
            value = parse_currency(pattern4.group(5))
            
            item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{idx}")
            
            return {
                "beneficiary": beneficiary,
                "cpf": cpf,
                "payer_cnpj": cnpj,
                "payer_name": payer_name,
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        return None
    
    def _parse_multiline_income_item(
        self,
        lines: list[str],
        start_idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item de rendimento com formato multiline (CNPJ em linha separada)."""
        cnpj_pattern = r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$"
        current_line = lines[start_idx].strip()
        
        if not re.match(cnpj_pattern, current_line):
            return None
        
        cnpj = current_line
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
            elif re.match(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$", next_line):
                cpf = next_line
            elif re.match(r"^[\d.,]+$", next_line) and "," in next_line:
                parsed_value = parse_currency(next_line)
                if parsed_value > 0:
                    value = parsed_value
            elif re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", next_line):
                if not re.match(cnpj_pattern, next_line):
                    if not re.match(r"^\d{2}[.\s]", next_line) and "TOTAL" not in next_line.upper():
                        if payer_name is None:
                            payer_name = next_line
            
            # Parar se encontrarmos outro CNPJ ou código de seção
            if re.match(cnpj_pattern, next_line) and next_line != cnpj:
                break
            if re.match(r"^\d{2}[.\s]+[A-Z]", next_line):
                break
        
        if cnpj and value is not None and value > 0:
            item_id = generate_item_id(f"{cnpj}{cpf or ''}{value}{page_num}_{start_idx}")
            return {
                "beneficiary": beneficiary or "Titular",
                "cpf": cpf or "",
                "payer_cnpj": cnpj,
                "payer_name": payer_name or "",
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        return None
    
    def _parse_2line_income_item(
        self,
        lines: list[str],
        start_idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item com formato de 2 linhas.
        
        Formato:
        Linha 1: CNPJ NOME DA FONTE
        Linha 2: Beneficiário Valor	CPF
        
        Exemplo:
        07.667.259/0001-30 BRADESCO FIC DE FI REFERENCIADO DI ONIX
        Titular 1.529,69	779.701.955-04
        """
        if start_idx + 1 >= len(lines):
            return None
        
        line1 = lines[start_idx].strip()
        line2 = lines[start_idx + 1].strip()
        
        # Linha 1: CNPJ + Nome (CNPJ no início seguido de espaço e nome)
        match1 = re.match(
            r"^(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+(.+)$",
            line1
        )
        if not match1:
            return None
        
        cnpj = match1.group(1)
        payer_name = match1.group(2).strip()
        
        # Linha 2: Beneficiário Valor CPF (separados por espaços ou tabs)
        # Formatos possíveis:
        # "Titular 1.529,69	779.701.955-04"
        # "Dependente 24.232,72	783.468.005-68"
        match2 = re.match(
            r"^(Titular|Dependente)\s+([\d.,]+)\s+(\d{3}\.\d{3}\.\d{3}-\d{2})\s*$",
            line2
        )
        if not match2:
            return None
        
        beneficiary = match2.group(1)
        value = parse_currency(match2.group(2))
        cpf = match2.group(3)
        
        if value > 0:
            item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{start_idx}")
            return {
                "beneficiary": beneficiary,
                "cpf": cpf,
                "payer_cnpj": cnpj,
                "payer_name": payer_name,
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        return None

    def _parse_cnpj_name_value_item(
        self,
        lines: list[str],
        start_idx: int,
        page_num: int,
    ) -> Optional[dict]:
        line = lines[start_idx].strip()
        match = re.match(
            r"^(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+(.+?)\s+([\d]{1,3}(?:[.\s]?\d{3})*,\d{2})\s*$",
            line,
        )
        if not match:
            return None

        cnpj = match.group(1)
        payer_name = match.group(2).strip()
        value = parse_currency(match.group(3))
        if value <= 0:
            return None

        beneficiary = "Titular"
        cpf = ""
        for offset in range(1, 5):
            if start_idx + offset >= len(lines):
                break
            nxt = lines[start_idx + offset].strip()
            m = re.match(r"^(Titular|Dependente)\s+(\d{3}\.\d{3}\.\d{3}-\d{2})\s*$", nxt)
            if m:
                beneficiary = m.group(1)
                cpf = m.group(2)
                break

        item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{start_idx}")
        return {
            "beneficiary": beneficiary,
            "cpf": cpf,
            "payer_cnpj": cnpj,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num,
        }
    
    def _parse_5line_income_item(
        self,
        lines: list[str],
        start_idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item com formato de 5 linhas (PDFs escaneados específicos).
        
        Formato:
        Linha 1: Titular ou Dependente
        Linha 2: 123.456.789-00  (CPF)
        Linha 3: 12.345.678/0001-90  (CNPJ)
        Linha 4: NOME DA FONTE PAGADORA
        Linha 5: 1.234,56  (Valor)
        """
        if start_idx >= len(lines):
            return None
        
        # Linha 1: Beneficiário
        beneficiary_line = lines[start_idx].strip()
        if beneficiary_line not in ("Titular", "Dependente"):
            return None
        
        # Verificar se as próximas 4 linhas existem
        if start_idx + 4 >= len(lines):
            return None
        
        cpf = None
        cnpj = None
        payer_name = None
        value = None
        
        cpf_pattern = r"^\d{3}\.\d{3}\.\d{3}-\d{2}$"
        cnpj_pattern = r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$"
        
        # Buscar nas próximas 4-6 linhas (permite linhas vazias)
        fields_found = 0
        for offset in range(1, 7):
            if start_idx + offset >= len(lines):
                break
            
            line = lines[start_idx + offset].strip()
            
            # Pular linhas vazias
            if not line:
                continue
            
            # Parar se encontrar outro Beneficiário (próximo item)
            if line in ("Titular", "Dependente"):
                break
            
            # Parar se encontrar TOTAL ou outro código de seção
            if "TOTAL" in line.upper() or re.match(r"^\d{2}[.\s]+[A-Z]", line):
                break
            
            # Identificar tipo de campo
            if re.match(cpf_pattern, line) and not cpf:
                cpf = line
                fields_found += 1
            elif re.match(cnpj_pattern, line) and not cnpj:
                cnpj = line
                fields_found += 1
            elif re.match(r"^[\d.,\s]+$", line) and "," in line and not value:
                parsed = parse_currency(line)
                if parsed > 0:
                    value = parsed
                    fields_found += 1
            elif line and not payer_name and not re.match(r"^\d", line):
                # Nome não começa com dígito e não é CPF/CNPJ
                payer_name = line
                fields_found += 1
            
            # Se encontrou todos os campos, parar
            if fields_found >= 4:
                break
        
        # Validar item completo (CPF, CNPJ e valor são obrigatórios)
        if cpf and cnpj and value is not None and value > 0:
            item_id = generate_item_id(f"{cnpj}{cpf}{value}{page_num}_{start_idx}")
            return {
                "beneficiary": beneficiary_line,
                "cpf": cpf,
                "payer_cnpj": cnpj,
                "payer_name": payer_name or "",
                "value": value,
                "id": item_id,
                "page": page_num
            }
        
        return None
    
    def _parse_others_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item de 'Outros' com descrição.
        
        BUG fix: Separar corretamente nome do pagador e descrição quando estão
        na mesma linha ou em múltiplas linhas.
        
        Exemplo problemático:
        Linha: "Titular 171.955.328-95 51.572.102/0001-12 FINACNEIRA XYZ OUTROS 11.000,00"
        Linhas seguintes: "RENDIMENTOS", "SUJEITOS A", "TRIBUTACAO", "EXCLUSIVA"
        
        Resultado esperado:
        - payer_name: "FINACNEIRA XYZ"
        - description: "OUTROS RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA"
        """
        # Formato: Titular/Dependente CPF CPF/CNPJ Nome Descrição Valor
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
            # Palavras-chave que indicam início de descrição
            description_keywords = [
                "OUTROS", "RENDIMENTOS", "GANHOS", "JUROS", "DIVIDENDOS",
                "LUCROS", "PRÊMIOS", "PREMIOS", "INDENIZAÇÃO", "INDENIZACAO",
                "COMPENSAÇÃO", "COMPENSACAO", "AUXÍLIO", "AUXILIO",
            ]
            
            payer_name = remaining
            description_parts = []
            
            # Verificar se alguma palavra-chave de descrição está no remaining
            words = remaining.split()
            split_idx = -1
            
            for i, word in enumerate(words):
                if word.upper() in description_keywords:
                    split_idx = i
                    break
            
            if split_idx > 0:
                # Nome é tudo antes da palavra-chave de descrição
                payer_name = " ".join(words[:split_idx])
                # Descrição começa com a palavra-chave
                description_parts.append(" ".join(words[split_idx:]))
            elif split_idx == 0:
                # Toda a linha remaining é descrição (nome pode estar vazio ou em outro formato)
                # Neste caso, tentamos manter o nome original e não adicionar descrição da linha
                pass
            
            # Concatenar linhas seguintes à descrição
            for j in range(idx + 1, min(idx + 8, len(lines))):
                next_line = lines[j].strip()
                upper_next = next_line.upper()
                
                # Parar se encontrar novo item, TOTAL, ou seção
                if re.match(r"^(Titular|Dependente)\s+\d{3}\.\d{3}", next_line):
                    break
                if "TOTAL" in upper_next and re.match(r"^TOTAL\s", upper_next):
                    break
                if re.match(r"^\d{2}[.\s]+[A-Z]", next_line):
                    break
                if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                    break
                
                # Pular linhas vazias
                if not next_line:
                    continue
                
                # Pular linhas que são valores monetários sozinhos
                if re.match(r"^[\d.,]+$", next_line):
                    continue
                
                # Pular linhas de cabeçalho
                if any(kw in upper_next for kw in ["BENEFICIÁRIO", "PAGADORA", "CPF/CNPJ"]):
                    continue
                
                # Adicionar à descrição se parece texto de descrição
                if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]*$", next_line):
                    description_parts.append(next_line)
            
            # Juntar descrição
            description = " ".join(description_parts)
            
            item_id = generate_item_id(f"{payer_cpf_cnpj}{cpf}{value}{page_num}_{idx}")
            
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
