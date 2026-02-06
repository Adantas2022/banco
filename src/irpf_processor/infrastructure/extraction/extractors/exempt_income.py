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
    
    # Todas as 17 subsections conforme gabarito
    SUBSECTIONS = {
        "scholarships_and_grants_without_donor_compensation": {
            "code": "01",
            "name": "01. Bolsas de estudo e de pesquisa caracterizadas como doação, exceto médico-residente ou Pronatec, exclusivamente para proceder a estudos ou pesquisas e desde que os resultados dessas atividades não representem vantagem para o doador, nem importem contraprestação de serviços",
            "keywords": ["bolsas", "estudo", "pesquisa", "doação"],
            "has_items": True,
            "format": "standard"
        },
        "insurance_payouts_for_death_or_permanent_disability": {
            "code": "03",
            "name": "03. Capital das apólices de seguro ou pecúlio pago por morte do segurado, prêmio de seguro restituído em qualquer caso e pecúlio recebido de entidades de previdência privada em decorrência de morte ou invalidez permanente",
            "keywords": ["apólices", "seguro", "pecúlio", "morte", "invalidez"],
            "has_items": False,
            "format": "total_only"
        },
        "termination_and_work_accident_compensation_including_fgts": {
            "code": "04",
            "name": "04. Indenizações por rescisão de contrato de trabalho, inclusive a título de PDV, e por acidente de trabalho; e FGTS",
            "keywords": ["indenizações", "rescisão", "fgts", "pdv", "acidente"],
            "has_items": True,
            "format": "termination"  # Formato especial sem beneficiary, usa payer_cpf_cnpj
        },
        "capital_gains_on_asset_sale_in_the_same_month": {
            "code": "05",
            "name": "05. Ganho de capital na alienação de bem, direito ou conjunto de bens ou direitos da mesma natureza, alienados em um mesmo mês, de valor total de alienação até R$ 20.000,00, para ações alienadas no mercado de balcão, e R$ 35.000,00, nos demais casos",
            "keywords": ["ganho de capital", "alienação", "mesmo mês", "20.000"],
            "has_items": False,
            "format": "total_only"
        },
        "capital_gains_from_sale_of_only_property_within_5_years": {
            "code": "06",
            "name": "06. Ganho de capital na alienação do único imóvel por valor igual ou inferior a R$ 440.000,00 e que, nos últimos 5 anos, não tenha efetuado nenhuma outra alienação de imóvel",
            "keywords": ["único imóvel", "440.000", "5 anos"],
            "has_items": False,
            "format": "total_only"
        },
        "profits_and_dividends": {
            "code": "09",
            "name": "09. Lucros e dividendos recebidos",
            "keywords": ["lucros", "dividendos"],
            "has_items": True,
            "format": "standard"
        },
        "tax_free_retirement_income_for_seniors_age_65_and_over": {
            "code": "10",
            "name": "10. Parcela isenta de proventos de aposentadoria, reserva remunerada, reforma e pensão de declarante com 65 anos ou mais",
            "keywords": ["parcela isenta", "aposentadoria", "65 anos"],
            "has_items": True,
            "format": "retirement"  # Formato especial com Valor e 13º Salário
        },
        "pension_or_retirement_income_due_to_severe_illness_or_work_accident": {
            "code": "11",
            "name": "11. Pensão, proventos de aposentadoria ou reforma por moléstia grave ou aposentadoria ou reforma por acidente em serviço",
            "keywords": ["pensão", "moléstia grave", "acidente em serviço"],
            "has_items": True,
            "format": "illness"  # Formato especial com múltiplos campos
        },
        "income_of_small_business_partner_or_owner": {
            "code": "13",
            "name": "13. Rendimento de sócio ou titular de microempresa ou empresa de pequeno porte optante pelo Simples Nacional, exceto pro labore, aluguéis e serviços prestados",
            "keywords": ["sócio", "titular", "microempresa", "simples nacional"],
            "has_items": True,
            "format": "standard"
        },
        "asset_transfers_donations_and_inheritances": {
            "code": "14",
            "name": "14. Transferências patrimoniais - doações e heranças",
            "keywords": ["transferências patrimoniais", "doações", "heranças"],
            "has_items": True,
            "format": "standard"
        },
        "incorporation_reserves_into_capital_or_share_bonuses": {
            "code": "18",
            "name": "18. Incorporação de reservas ao capital / Bonificações em ações",
            "keywords": ["incorporação", "reservas", "capital", "bonificações"],
            "has_items": True,
            "format": "standard"
        },
        "net_gains_from_operations_in_the_spot_market": {
            "code": "20",
            "name": "20. Ganhos líquidos em operações no mercado à vista de ações negociadas em bolsas de valores nas alienações realizadas até R$ 20.000,00, em cada mês, para o conjunto de ações",
            "keywords": ["ganhos líquidos", "mercado à vista", "bolsas"],
            "has_items": True,
            "format": "simple"  # Formato sem CNPJ (apenas Beneficiário CPF Valor)
        },
        "net_gains_from_gold_sales_under_20000_per_month": {
            "code": "21",
            "name": "21. Ganhos líquidos em operações com ouro, ativo financeiro, nas alienações realizadas até R$ 20.000,00, em cada mês",
            "keywords": ["ganhos líquidos", "ouro", "ativo financeiro"],
            "has_items": True,
            "format": "simple"
        },
        "gross_income_up_to_90_from_freight_services": {
            "code": "23",
            "name": "23. Rendimento bruto, até o máximo de 90%, da prestação de serviços decorrente do transporte de carga e com trator, máquina de terraplenagem, colheitadeira e assemelhados",
            "keywords": ["rendimento bruto", "90%", "transporte", "carga"],
            "has_items": False,
            "format": "total_only"
        },
        "income_tax_refund_from_previous_years": {
            "code": "25",
            "name": "25. Restituição do imposto sobre a renda de anos-calendário anteriores",
            "keywords": ["restituição", "imposto", "anos-calendário anteriores"],
            "has_items": False,
            "format": "total_only"
        },
        "interest_on_accumulated_income_received": {
            "code": "27",
            "name": "27. Juros referentes aos Rendimentos Recebidos Acumuladamente",
            "keywords": ["juros", "rendimentos recebidos acumuladamente"],
            "has_items": False,
            "format": "total_only"
        },
        "others_99": {
            "code": "99",
            "name": "99. Outros",
            "keywords": ["outros"],
            "has_items": True,
            "format": "others"
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
        
        subsections = {}
        
        for key, config in self.SUBSECTIONS.items():
            subsection = self._extract_subsection_by_format(context, key, config)
            if subsection and (subsection.get("items") or subsection.get("total_value", 0) > 0):
                subsections[key] = subsection
        
        total_value = sum(s.get("total_value", 0) for s in subsections.values()) if subsections else 0.0
        
        # Tentar extrair total do PDF
        pdf_total = self._extract_total_from_pdf(context)
        
        return {
            "section_name": "Rendimentos Isentos e Não Tributáveis",
            "total_value": round(pdf_total if pdf_total else total_value, 2),
            "valid_total": True,
            "subsections": subsections,
            "items_count": sum(len(s.get("items", []) or []) for s in subsections.values())
        }
    
    def _extract_subsection_by_format(
        self,
        context: ExtractionContext,
        key: str,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection baseado no formato especificado."""
        fmt = config.get("format", "standard")
        
        if fmt == "total_only":
            return self._extract_total_only_subsection(context, config)
        elif fmt == "retirement":
            return self._extract_retirement_subsection(context, config)
        elif fmt == "illness":
            return self._extract_illness_subsection(context, config)
        elif fmt == "simple":
            return self._extract_simple_subsection(context, config)
        elif fmt == "others":
            return self._extract_others_subsection(context, config)
        elif fmt == "termination":
            return self._extract_termination_subsection(context, config)
        else:
            return self._extract_standard_subsection(context, config)
    
    def _extract_total_only_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection que tem apenas total (sem items).
        
        Formato no PDF: "XX. Descrição completa... VALOR"
        O valor aparece no final da linha do código.
        """
        code = config["code"]
        name = config["name"]
        total_value = 0.0
        
        # Buscar diretamente pela linha do código em todas as páginas
        # (seção pode continuar entre páginas sem repetir cabeçalho)
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        found = False
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Parar se encontrar início de outra seção principal
            if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_page:
                # Verificar se já encontramos o código nesta página antes do fim
                lines = page_text.split("\n")
                for i, line in enumerate(lines):
                    if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in line.upper():
                        # Só processar linhas antes desta
                        lines = lines[:i]
                        break
                
                for i, line in enumerate(lines):
                    if line.strip().startswith(f"{code}."):
                        value_match = re.search(r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})\s*$', line)
                        if value_match:
                            total_value = parse_currency(value_match.group(1))
                            found = True
                break
            
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                # Procurar linha que começa com o código
                if line.strip().startswith(f"{code}."):
                    found = True
                    # Extrair valor do final da linha
                    value_match = re.search(r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})\s*$', line)
                    if value_match:
                        total_value = parse_currency(value_match.group(1))
                    else:
                        # Valor pode estar em linha separada
                        for j in range(i + 1, min(i + 3, len(lines))):
                            next_line = lines[j].strip()
                            if re.match(r'^\d{2}\.', next_line):
                                break
                            if "Beneficiário" in next_line:
                                break
                            val_match = re.match(r'^([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})$', next_line)
                            if val_match:
                                total_value = parse_currency(val_match.group(1))
                                break
                    break
            
            if found:
                break
        
        if total_value <= 0:
            return None
        
        return {
            "name": name,
            "code": code,
            "total_value": round(total_value, 2),
            "valid_total": True,
            "items": None
        }
    
    def _extract_standard_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection com formato padrão.
        
        Formato: Beneficiário CPF CPF/CNPJ Nome Valor
        """
        code = config["code"]
        name = config["name"]
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_subsection = False
        section_ended = False
        
        for page_idx, (page_num, page_text) in enumerate(sorted_pages):
            if section_ended:
                break
            
            upper_page = page_text.upper()
            lines = page_text.split("\n")
            next_page_lines = []
            if page_idx + 1 < len(sorted_pages):
                next_page_lines = sorted_pages[page_idx + 1][1].split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar fim da seção principal
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    section_ended = True
                    break
                
                # Detectar início da subsection
                if line.strip().startswith(f"{code}."):
                    in_subsection = True
                    continue
                
                # Detectar fim da subsection (outro código)
                if re.match(r'^\d{2}\.', line.strip()) and not line.strip().startswith(f"{code}."):
                    in_subsection = False
                    continue
                
                # Detectar fim por TOTAL da seção
                if re.match(r'^TOTAL\s+[\d.,]+\s*$', line.strip(), re.IGNORECASE):
                    in_subsection = False
                    continue
                
                if in_subsection:
                    item = self._parse_standard_item(line, lines, i, page_num, next_page_lines)
                    if item:
                        key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
        
        total = round(sum(i.get("value", 0) for i in items), 2)
        
        # Tentar extrair total do cabeçalho da subsection
        header_total = self._extract_subsection_header_total(context, code)
        if header_total and header_total > total:
            total = header_total
        
        if not items and total <= 0:
            return None
        
        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _extract_subsection_header_total(
        self,
        context: ExtractionContext,
        code: str
    ) -> Optional[float]:
        """Extrai o total do cabeçalho da subsection."""
        for page_text in context.pages_text.values():
            lines = page_text.split("\n")
            for line in lines:
                if line.strip().startswith(f"{code}."):
                    match = re.search(r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})\s*$', line)
                    if match:
                        return parse_currency(match.group(1))
        return None
    
    def _parse_standard_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int,
        next_page_lines: list[str] = None
    ) -> Optional[dict]:
        """Parseia item no formato padrão."""
        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        
        # Pattern: Titular/Dependente CPF CPF/CNPJ Nome Valor
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
        
        # Verificar continuação do nome na próxima linha
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if self._is_name_continuation(next_line):
                payer_name = f"{payer_name} {next_line}"
        
        # Verificar continuação cross-page
        if next_page_lines and self._is_near_page_end(lines, idx):
            orphan = self._get_orphan_name_from_next_page(next_page_lines)
            if orphan:
                payer_name = f"{payer_name} {orphan}"
        
        item_id = generate_item_id(f"{payer_doc}{cpf}{value}")
        
        return {
            "beneficiary": beneficiary,
            "cpf": cpf,
            "payer_cnpj": payer_doc,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num
        }
    
    def _extract_retirement_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection 10 - aposentadoria 65+.
        
        Formato especial com Valor e 13º Salário em linha separada.
        """
        code = config["code"]
        name = config["name"]
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_subsection = False
        current_item = None
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            if section_ended:
                break
            
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                lower_line = line.lower()
                upper_line = line.upper()
                
                # Detectar fim da seção
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    if current_item:
                        items.append(current_item)
                        current_item = None
                    section_ended = True
                    break
                
                # Detectar início da subsection
                if f"{code}." in line and ("parcela isenta" in lower_line or "aposentadoria" in lower_line):
                    in_subsection = True
                    continue
                
                if in_subsection:
                    # Detectar fim
                    if re.match(r'^\d{2}\.', line.strip()) and not line.strip().startswith(f"{code}."):
                        if current_item:
                            items.append(current_item)
                            current_item = None
                        in_subsection = False
                        continue
                    
                    if re.match(r'^TOTAL\s+[\d.,]+\s*$', line.strip(), re.IGNORECASE):
                        if current_item:
                            items.append(current_item)
                            current_item = None
                        in_subsection = False
                        continue
                    
                    # Parsear item
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
                    elif current_item:
                        # Continuação do nome
                        if not "Valor:" in line and not re.match(r"^(Titular|Dependente)", line):
                            name_cont = line.strip()
                            if name_cont and re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", name_cont) and "Valor:" not in name_cont:
                                current_item["payer_name"] = f"{current_item['payer_name']} {name_cont}"
                        
                        # Linha com Valor e 13º Salário
                        if "Valor:" in line:
                            valor_match = re.search(r"Valor:\s*([\d.,]+)", line)
                            if valor_match:
                                current_item["value"] = parse_currency(valor_match.group(1))
                            
                            salario_match = re.search(r"13[º°]?\s*Sal[aá]rio:\s*([\d.,]+)", line)
                            if salario_match:
                                current_item["thirteenth_salary"] = parse_currency(salario_match.group(1))
            
            # Ao final da página, manter item pendente para próxima página
            # (não adicionar aqui, pois pode haver continuação)
        
        # Adicionar último item se existir
        if current_item:
            items.append(current_item)
        
        if not items:
            return None
        
        for item in items:
            item["id"] = generate_item_id(f"{item['payer_cnpj']}{item['cpf']}{item['value']}")
        
        total = round(sum(i["value"] + i.get("thirteenth_salary", 0) for i in items), 2)
        
        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items
        }
    
    def _extract_illness_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection 11 - moléstia grave.
        
        Formato especial:
        Beneficiário CPF Rendimento IRRF 13º Salário IRRF 13º Contrib.Prev.
        Titular CPF 20.000,00 500,00 600,00 60,00 400,00
        CPF/CNPJ da Fonte Pagadora: XX Nome da Fonte Pagadora: YY
        """
        code = config["code"]
        name = config["name"]
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_subsection = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            if section_ended:
                break
            
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                lower_line = line.lower()
                
                # Detectar fim da seção
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    section_ended = True
                    break
                
                # Detectar início
                if f"{code}." in line and ("pensão" in lower_line or "moléstia" in lower_line or "acidente em serviço" in lower_line):
                    in_subsection = True
                    continue
                
                if in_subsection:
                    # Detectar fim
                    if re.match(r'^\d{2}\.', line.strip()) and not line.strip().startswith(f"{code}."):
                        in_subsection = False
                        continue
                    
                    # Pattern: Titular/Dependente CPF Valor Valor Valor Valor Valor
                    item_match = re.match(
                        r"^(Titular|Dependente)\s+"
                        r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
                        r"([\d.,]+)\s+"
                        r"([\d.,]+)\s+"
                        r"([\d.,]+)\s+"
                        r"([\d.,]+)\s+"
                        r"([\d.,]+)\s*$",
                        line.strip()
                    )
                    
                    if item_match:
                        item = {
                            "beneficiary": item_match.group(1),
                            "cpf": item_match.group(2),
                            "income": parse_currency(item_match.group(3)),
                            "irrf": parse_currency(item_match.group(4)),
                            "thirteenth_salary": parse_currency(item_match.group(5)),
                            "irrf_on_thirteenth_salary": parse_currency(item_match.group(6)),
                            "official_social_security_contribution": parse_currency(item_match.group(7)),
                            "payer_cpf_cnpj": "",
                            "payer_name": "",
                            "page": page_num
                        }
                        
                        # Procurar CPF/CNPJ e Nome na próxima linha
                        if i + 1 < len(lines):
                            next_line = lines[i + 1]
                            payer_match = re.search(
                                r"CPF/CNPJ\s*(?:da\s*)?Fonte\s*Pagadora:\s*"
                                r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})\s*"
                                r"Nome\s*(?:da\s*)?Fonte\s*Pagadora:\s*(.+)$",
                                next_line,
                                re.IGNORECASE
                            )
                            if payer_match:
                                item["payer_cpf_cnpj"] = payer_match.group(1)
                                item["payer_name"] = payer_match.group(2).strip()
                        
                        item["id"] = generate_item_id(f"{item['payer_cpf_cnpj']}{item['cpf']}{item['income']}")
                        items.append(item)
        
        if not items:
            return None
        
        # Total = soma de income + thirteenth_salary
        total = round(sum(i["income"] + i.get("thirteenth_salary", 0) for i in items), 2)
        
        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items
        }
    
    def _extract_simple_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection 20, 21 - formato simples sem CNPJ.
        
        Formato: Beneficiário CPF Valor
        """
        code = config["code"]
        name = config["name"]
        items = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_subsection = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            if section_ended:
                break
            
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar fim da seção
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    section_ended = True
                    break
                
                # Detectar início
                if line.strip().startswith(f"{code}."):
                    in_subsection = True
                    continue
                
                if in_subsection:
                    # Detectar fim
                    if re.match(r'^\d{2}\.', line.strip()) and not line.strip().startswith(f"{code}."):
                        in_subsection = False
                        continue
                    
                    # Pattern: Titular/Dependente CPF Valor
                    item_match = re.match(
                        r"^(Titular|Dependente)\s+"
                        r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
                        r"([\d.,]+)\s*$",
                        line.strip()
                    )
                    
                    if item_match:
                        value = parse_currency(item_match.group(3))
                        item = {
                            "beneficiary": item_match.group(1),
                            "cpf": item_match.group(2),
                            "value": value,
                            "id": generate_item_id(f"{item_match.group(2)}{value}"),
                            "page": page_num
                        }
                        items.append(item)
        
        if not items:
            return None
        
        total = round(sum(i["value"] for i in items), 2)
        
        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items
        }
    
    def _extract_others_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> dict:
        """Extrai subseção 99. Outros.
        
        Formato: Beneficiário CPF CPF/CNPJ Nome Descrição Valor
        """
        code = config["code"]
        name = config["name"]
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_subsection = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            if section_ended:
                break
            
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar fim da seção
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    section_ended = True
                    break
                
                # Detectar início da subseção 99
                if re.search(r"99[.\s]+OUTROS", upper_line, re.IGNORECASE):
                    in_subsection = True
                    continue
                
                # Detectar fim
                if in_subsection:
                    if re.match(r'^TOTAL\s+[\d.,]+\s*$', line.strip(), re.IGNORECASE):
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
            "name": name,
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
        # Pattern: Titular/Dependente CPF CPF/CNPJ Nome Valor
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
            
            # Separar nome e descrição
            payer_name = remaining
            description_parts = []
            
            # Procurar descrição nas linhas seguintes
            for j in range(idx + 1, min(idx + 6, len(lines))):
                next_line = lines[j].strip()
                upper_next = next_line.upper()
                
                # Parar se encontrar TOTAL ou próximo item
                if "TOTAL" in upper_next and not re.search(r"TITULAR|DEPENDENTE", upper_next):
                    break
                if re.match(r"^(Titular|Dependente)\s+\d{3}\.", next_line):
                    break
                if re.match(r"^\d{2}\..*[A-Z]", next_line):
                    break
                if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                    break
                
                # Pular linhas vazias e cabeçalhos
                if not next_line:
                    continue
                if "Beneficiário" in next_line or "Pagadora" in next_line:
                    continue
                
                # Adicionar à descrição
                if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", next_line):
                    description_parts.append(next_line)
            
            description = " ".join(description_parts)
            
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
    
    def _extract_termination_subsection(
        self,
        context: ExtractionContext,
        config: dict
    ) -> Optional[dict]:
        """Extrai subsection 04 - indenizações/rescisão/FGTS.
        
        Formato especial: não tem 'beneficiary', usa 'payer_cpf_cnpj'.
        Formato: Beneficiário CPF CPF/CNPJ Nome Valor
        Mas output não inclui beneficiary conforme gabarito.
        """
        code = config["code"]
        name = config["name"]
        items = []
        seen_keys = set()
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        in_subsection = False
        section_ended = False
        
        for page_idx, (page_num, page_text) in enumerate(sorted_pages):
            if section_ended:
                break
            
            lines = page_text.split("\n")
            next_page_lines = []
            if page_idx + 1 < len(sorted_pages):
                next_page_lines = sorted_pages[page_idx + 1][1].split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar fim da seção principal
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    section_ended = True
                    break
                
                # Detectar início da subsection
                if line.strip().startswith(f"{code}."):
                    in_subsection = True
                    continue
                
                # Detectar fim da subsection (outro código)
                if re.match(r'^\d{2}\.', line.strip()) and not line.strip().startswith(f"{code}."):
                    in_subsection = False
                    continue
                
                # Detectar fim por TOTAL da seção
                if re.match(r'^TOTAL\s+[\d.,]+\s*$', line.strip(), re.IGNORECASE):
                    in_subsection = False
                    continue
                
                if in_subsection:
                    item = self._parse_termination_item(line, lines, i, page_num, next_page_lines)
                    if item:
                        key = f"{item.get('payer_cpf_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}"
                        if key not in seen_keys:
                            seen_keys.add(key)
                            items.append(item)
        
        total = round(sum(i.get("value", 0) for i in items), 2)
        
        # Tentar extrair total do cabeçalho da subsection
        header_total = self._extract_subsection_header_total(context, code)
        if header_total and header_total > total:
            total = header_total
        
        if not items and total <= 0:
            return None
        
        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None
        }
    
    def _parse_termination_item(
        self,
        line: str,
        lines: list[str],
        idx: int,
        page_num: int,
        next_page_lines: list[str] = None
    ) -> Optional[dict]:
        """Parseia item de indenização/rescisão (código 04).
        
        Formato: Beneficiário CPF CPF/CNPJ Nome Valor
        Output: sem beneficiary, usa payer_cpf_cnpj
        """
        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        
        # Pattern: Titular/Dependente CPF CPF/CNPJ Nome Valor
        pattern = re.match(
            rf"^(?:Titular|Dependente)\s+"
            rf"({CPF_PATTERN})\s+"
            rf"({CNPJ_PATTERN}|{CPF_PATTERN})\s+"
            rf"(.+?)\s+"
            rf"([\d.,]+)\s*$",
            line.strip()
        )
        
        if not pattern:
            return None
        
        cpf = pattern.group(1)
        payer_doc = pattern.group(2)
        payer_name = pattern.group(3).strip()
        value = parse_currency(pattern.group(4))
        
        # Verificar continuação do nome na próxima linha
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if self._is_name_continuation(next_line):
                payer_name = f"{payer_name} {next_line}"
        
        # Verificar continuação cross-page
        if next_page_lines and self._is_near_page_end(lines, idx):
            orphan = self._get_orphan_name_from_next_page(next_page_lines)
            if orphan:
                payer_name = f"{payer_name} {orphan}"
        
        item_id = generate_item_id(f"{payer_doc}{cpf}{value}")
        
        # Não inclui 'beneficiary' conforme gabarito
        return {
            "cpf": cpf,
            "payer_cpf_cnpj": payer_doc,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num
        }
    
    def _extract_total_from_pdf(self, context: ExtractionContext) -> Optional[float]:
        """Extrai o total geral da seção."""
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        # Procurar em todas as páginas, pois o total pode estar em página sem cabeçalho
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            lines = page_text.split("\n")
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                
                # Detectar fim da seção - o TOTAL vem logo antes
                if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in upper_line:
                    # O total deve estar nas linhas anteriores
                    for j in range(max(0, i - 5), i):
                        prev_line = lines[j].strip()
                        total_match = re.match(r'^TOTAL\s+([\d.,]+)\s*$', prev_line, re.IGNORECASE)
                        if total_match:
                            return parse_currency(total_match.group(1))
                    return None
                
                # Procurar "TOTAL" seguido de valor (linha de total da seção)
                # Mas só se não estiver em outra seção
                if upper_line.strip().startswith("TOTAL") and not re.search(r'TITULAR|DEPENDENTE', upper_line):
                    total_match = re.match(r'^TOTAL\s+([\d.,]+)\s*$', line.strip(), re.IGNORECASE)
                    if total_match:
                        # Verificar se após o total vem RENDIMENTOS SUJEITOS (próximas linhas)
                        for j in range(i + 1, min(i + 5, len(lines))):
                            if "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO" in lines[j].upper():
                                return parse_currency(total_match.group(1))
        
        return None
    
    def _is_name_continuation(self, line: str) -> bool:
        """Verifica se linha é continuação de nome."""
        if len(line) <= 2:
            return False
        
        if "TOTAL" in line.upper() or "Titular" in line or "Dependente" in line:
            return False
        
        if re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+$", line):
            return True
        
        return False
    
    def _is_near_page_end(self, lines: list[str], idx: int) -> bool:
        """Verifica se linha está próxima do final da página."""
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
        """Obtém nome órfão da próxima página."""
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
