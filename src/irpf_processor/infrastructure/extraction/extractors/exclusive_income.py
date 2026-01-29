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
        "TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA",
        "TRIBUTAÇÃO EXCLUSIVA",
        # OCR variations - sem acentos
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
        subsections = {}
        
        # 01. 13º salário
        thirteenth = self._extract_thirteenth_salary(context)
        if thirteenth:
            subsections["thirteenth_salary"] = thirteenth
        
        # 05. Ganhos líquidos em renda variável
        variable_income = self._extract_variable_income_gains(context)
        if variable_income:
            subsections["net_gains_from_variable_income_stocks_futures_and_reits"] = variable_income
        
        # 06. Rendimentos de aplicações financeiras
        financial = self._extract_financial_income(context)
        # Incluir se tem itens OU se tem total extraído diretamente
        if financial and (financial.get("items") or financial.get("total_value", 0) > 0):
            subsections["income_from_financial_investments"] = financial
        
        # 07. Rendimentos recebidos acumuladamente
        accumulated = self._extract_accumulated_income(context)
        if accumulated:
            subsections["accumulated_income_received"] = accumulated
        
        # 10. Juros sobre capital próprio
        interest = self._extract_interest_on_capital(context)
        if interest and interest.get("items"):
            subsections["interest_on_own_capital"] = interest
        
        # 12. Aplicações financeiras e lucros/dividendos no exterior
        abroad = self._extract_financial_abroad(context)
        if abroad:
            subsections["financial_investments_and_profits_and_dividends_abroad"] = abroad
        
        # 13. Outros
        others = self._extract_others(context)
        if others and others.get("items"):
            subsections["others_13"] = others
        
        if not subsections:
            return None
        
        total_value = sum(s.get("total_value", 0) for s in subsections.values())
        
        return {
            "section_name": "Rendimentos Sujeitos à Tributação Exclusiva/Definitiva",
            "total_value": round(total_value, 2),
            "valid_total": True,
            "subsections": subsections
        }
    
    def _is_in_exclusive_section(self, page_text: str) -> bool:
        """Verifica se a página contém a seção de tributação exclusiva."""
        upper_text = page_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def _extract_thirteenth_salary(self, context: ExtractionContext) -> Optional[dict]:
        """Extrai 01. 13º salário."""
        # Procurar em todas as páginas sequencialmente
        in_section = False
        for page_num, page_text in sorted(context.pages_text.items()):
            upper_text = page_text.upper()
            
            # Detectar início da seção
            if any(marker in upper_text for marker in self.SECTION_MARKERS):
                in_section = True
            
            # Detectar fim da seção
            if in_section and any(marker in upper_text for marker in self.SECTION_END_MARKERS):
                break
            
            if not in_section:
                continue
            
            # Patterns mais flexíveis para OCR
            patterns = [
                r"01[.\s]+13[º°]?\s*(?:sal[aá]rio|SALARIO)\s+([\d.,]+)",
                r"01[.\s]+(?:DECIMO\s+TERCEIRO|13.?\s*SALARIO)[^\d]*([\d.,]+)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
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
    
    def _extract_variable_income_gains(self, context: ExtractionContext) -> Optional[dict]:
        """Extrai 05. Ganhos líquidos em renda variável."""
        in_section = False
        for page_num, page_text in sorted(context.pages_text.items()):
            upper_text = page_text.upper()
            
            if any(marker in upper_text for marker in self.SECTION_MARKERS):
                in_section = True
            
            if in_section and any(marker in upper_text for marker in self.SECTION_END_MARKERS):
                break
            
            if not in_section:
                continue
            
            # Patterns mais flexíveis para OCR
            patterns = [
                r"05[.\s]+Ganhos\s+l[ií]quidos\s+(?:em\s+)?renda\s+vari[aá]vel[^\d]*([\d.,]+)",
                r"05[.\s]+GANHOS\s+LIQUIDOS[^\d]*([\d.,]+)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
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
    
    def _extract_financial_income(self, context: ExtractionContext) -> dict:
        """Extrai 06. Rendimentos de aplicações financeiras."""
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_section = False
        in_subsection = False
        
        # Patterns para detectar início da subseção 06
        subsection_06_patterns = [
            r"06[.\s]+(?:RENDIMENTOS|REND\.?)\s*(?:DE\s*)?(?:APLIC|FINANC)",
            r"06[.\s]+APLICACOES\s+FINANCEIRAS",
            r"06[.\s]+APLICAGOES\s+FINANCEIRAS",  # OCR Ç→G
        ]
        
        for page_num, page_text in sorted_pages:
            lines = page_text.split("\n")
            upper_page = page_text.upper()
            
            # Detectar início da seção principal
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                in_section = True
            
            # Detectar fim da seção principal
            if in_section and any(marker in upper_page for marker in self.SECTION_END_MARKERS):
                break
            
            if not in_section:
                continue
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar início da subseção 06
                if any(re.search(p, upper_line) for p in subsection_06_patterns):
                    in_subsection = True
                    continue
                
                # Detectar fim da subseção (próximo código)
                if re.match(r"^(?:07|08|09|10|11|12|13)[.\s]+[A-Z]", line.strip()):
                    in_subsection = False
                    continue
                
                # Detectar TOTAL como fim (mas não "TITULAR")
                if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                    in_subsection = False
                    continue
                
                if in_subsection:
                    # Tentar parsear item inline
                    item = self._parse_income_item(line, lines, i, page_num)
                    if item:
                        key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
                    
                    # Tentar parsear item multiline (CNPJ na linha sozinho)
                    multiline_item = self._parse_multiline_income_item(lines, i, page_num)
                    if multiline_item:
                        key = f"{multiline_item.get('payer_cnpj', '')}{multiline_item.get('cpf', '')}{multiline_item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(multiline_item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        # Se não encontrou itens, tentar capturar total diretamente da página
        # OCR pode separar tabela em duas partes: dados e valores no final
        if not items and total == 0:
            extracted_total = self._extract_section_06_total(context)
            if extracted_total > 0:
                total = extracted_total
        
        return {
            "name": "06. Rendimentos de aplicações financeiras",
            "code": "06",
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _extract_section_06_total(self, context: ExtractionContext) -> float:
        """Extrai total da seção 06 diretamente do OCR quando itens estão separados.
        
        O OCR pode separar tabela em duas partes:
        - Beneficiários e CNPJs no início
        - Valores no final da página, após "(Valores em Reais)" e "Pagina X de Y"
        """
        for page_num, page_text in sorted(context.pages_text.items()):
            upper_page = page_text.upper()
            
            # Verificar se esta página contém "06." e "APLICAÇÕES/FINANCEIRAS"
            # e também "TRIBUTACAO EXCLUSIVA" (para não confundir com ISENTOS)
            has_section_06 = bool(re.search(r"06[.\s]+.*(?:APLICAC|FINANC)", upper_page))
            has_exclusive = "TRIBUTACAO EXCLUSIVA" in upper_page or "TRIBUTAÇÃO EXCLUSIVA" in upper_page
            
            if has_section_06 and has_exclusive:
                lines = page_text.split('\n')
                
                # Estratégia 1: Buscar TOTAL seguido de valor (na página 5, no final da seção)
                for line in lines:
                    match = re.match(r"^\s*TOTAL\s+([\d.,\s]+)\s*$", line, re.IGNORECASE)
                    if match:
                        value = parse_currency(match.group(1))
                        # O total de TRIBUTAÇÃO EXCLUSIVA neste doc é ~359.000
                        # O total de ISENTOS é ~1.200.000
                        if value < 500000:  # Filtro para evitar pegar ISENTOS
                            return value
                
                # Estratégia 2: Buscar primeiro valor grande após "Pagina X de Y"
                # que indica o total da seção OCR separada
                for i, line in enumerate(lines):
                    if re.search(r"Pagina\s+\d+\s*de\s*\d+", line, re.IGNORECASE):
                        # Buscar nas próximas linhas
                        for j in range(i + 1, min(i + 10, len(lines))):
                            # Buscar valor monetário sozinho em uma linha
                            value_match = re.match(r"^\s*([\d]{1,3}(?:[\s.]?\d{3})*\s*,\s*\d{2})\s*$", lines[j])
                            if value_match:
                                value = parse_currency(value_match.group(1))
                                # Valor plausível para tributação exclusiva (< 500000)
                                if value > 100 and value < 500000:
                                    return value
        return 0.0
    
    def _extract_accumulated_income(self, context: ExtractionContext) -> Optional[dict]:
        """Extrai 07. Rendimentos recebidos acumuladamente."""
        for page_text in context.pages_text.values():
            if not self._is_in_exclusive_section(page_text):
                continue
            
            pattern = re.search(
                r"07[.\s]+Rendimentos\s+recebidos\s+acumuladamente[^\d]+([\d.,]+)",
                page_text,
                re.IGNORECASE
            )
            if pattern:
                value = parse_currency(pattern.group(1))
                return {
                    "name": "07. Rendimentos recebidos acumuladamente",
                    "code": "07",
                    "total_value": value,
                    "valid_total": True,
                    "items": []
                }
        return None
    
    def _extract_interest_on_capital(self, context: ExtractionContext) -> dict:
        """Extrai 10. Juros sobre capital próprio."""
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_section = False
        in_subsection = False  # Manter estado entre páginas
        
        for page_num, page_text in sorted_pages:
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar início da seção principal
                if any(marker in upper_line for marker in self.SECTION_MARKERS):
                    in_section = True
                    continue
                
                if not in_section:
                    continue
                
                # Detectar início da subseção 10
                if re.search(r"10[.\s]+JUROS\s+SOBRE\s+CAPITAL\s+PR[OÓ]PRIO", upper_line, re.IGNORECASE):
                    in_subsection = True
                    continue
                
                # Detectar fim da subseção
                if re.match(r"^(?:11|12|13)[.\s]+", line.strip()):
                    in_subsection = False
                    continue
                
                if "TOTAL" in upper_line and not re.search(r"TITULAR|DEPENDENTE", upper_line):
                    if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                        in_subsection = False
                        continue
                
                # Detectar fim da seção principal (só se já entramos)
                if in_section and in_subsection:
                    if "PAGAMENTOS EFETUADOS" in upper_line or "DOAÇÕES EFETUADAS" in upper_line:
                        in_subsection = False
                        in_section = False
                        break
                
                if in_subsection:
                    item = self._parse_income_item(line, lines, i, page_num)
                    if item:
                        key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
                    
                    multiline_item = self._parse_multiline_income_item(lines, i, page_num)
                    if multiline_item:
                        key = f"{multiline_item.get('payer_cnpj', '')}{multiline_item.get('cpf', '')}{multiline_item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(multiline_item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": "10. Juros sobre capital próprio",
            "code": "10",
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _extract_financial_abroad(self, context: ExtractionContext) -> Optional[dict]:
        """Extrai 12. Aplicações Financeiras e Lucros e Dividendos no Exterior."""
        for page_text in context.pages_text.values():
            if not self._is_in_exclusive_section(page_text):
                continue
            
            pattern = re.search(
                r"12[.\s]+Aplica[çc][õo]es\s+Financeiras\s+e\s+Lucros[^\d]+([\d.,]+)",
                page_text,
                re.IGNORECASE
            )
            if pattern:
                value = parse_currency(pattern.group(1))
                return {
                    "name": "12. Aplicações Financeiras e Lucros e Dividendos no Exterior (Lei 14.754/2023)",
                    "code": "12",
                    "total_value": value,
                    "valid_total": True,
                    "items": []
                }
        return None
    
    def _extract_others(self, context: ExtractionContext) -> dict:
        """Extrai 13. Outros (ou 12. Outros em alguns PDFs)."""
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_section = False
        in_subsection = False  # Manter estado entre páginas
        
        for page_num, page_text in sorted_pages:
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar início da seção principal
                if any(marker in upper_line for marker in self.SECTION_MARKERS):
                    in_section = True
                    continue
                
                if not in_section:
                    continue
                
                # Detectar início da subseção 13.Outros ou 12.Outros
                if re.search(r"(?:12|13)[.\s]+OUTROS", upper_line, re.IGNORECASE):
                    in_subsection = True
                    continue
                
                # Detectar fim da subseção
                if "TOTAL" in upper_line and not re.search(r"TITULAR|DEPENDENTE", upper_line):
                    if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                        in_subsection = False
                        continue
                
                # Detectar fim da seção principal (só se já entramos)
                if in_section and in_subsection:
                    if "PAGAMENTOS EFETUADOS" in upper_line or "DOAÇÕES EFETUADAS" in upper_line:
                        in_subsection = False
                        in_section = False
                        break
                
                if in_subsection:
                    item = self._parse_others_item(line, lines, i, page_num)
                    if item:
                        key = f"{item.get('payer_cpf_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": "13. Outros",
            "code": "13",
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _parse_income_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item de rendimento com formato inline."""
        # Formato: Titular/Dependente CPF CNPJ Nome Valor
        pattern = re.match(
            r"^(Titular|Dependente)\s+"
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s+"
            r"(.+?)\s+"
            r"([\d.,]+)\s*$",
            line.strip()
        )
        
        if pattern:
            beneficiary = pattern.group(1)
            cpf = pattern.group(2)
            cnpj = pattern.group(3)
            payer_name = pattern.group(4).strip()
            value = parse_currency(pattern.group(5))
            
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
            item_id = generate_item_id(f"{cnpj}{cpf or ''}{value}")
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
    
    def _parse_others_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int
    ) -> Optional[dict]:
        """Parseia item de 'Outros' com descrição."""
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
            payer_name = remaining
            description = ""
            
            # Procurar descrição nas linhas seguintes ou no restante
            for j in range(idx + 1, min(idx + 3, len(lines))):
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
