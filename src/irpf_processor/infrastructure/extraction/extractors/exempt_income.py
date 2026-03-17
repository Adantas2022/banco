"""Extrator de rendimentos isentos e não tributáveis."""

import re
from typing import Any

from ..table_extractor import generate_item_id, parse_currency
from .base import ExtractionContext, ISectionExtractor


class ExemptIncomeExtractor(ISectionExtractor):
    """Extrai rendimentos isentos e não tributáveis."""

    SECTION_MARKERS = ["RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS", "RENDIMENTOS ISENTOS"]

    SECTION_END_MARKERS = [
        "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO",
        "RENDIMENTOS TRIBUTÁVEIS",
        "PAGAMENTOS EFETUADOS",
        "DOAÇÕES EFETUADAS",
        "BENS E DIREITOS",
    ]

    # Todas as 17 subsections conforme gabarito
    SUBSECTIONS = {
        "scholarships_and_grants_without_donor_compensation": {
            "code": "01",
            "name": "01. Bolsas de estudo e de pesquisa caracterizadas como doação, exceto médico-residente ou Pronatec, exclusivamente para proceder a estudos ou pesquisas e desde que os resultados dessas atividades não representem vantagem para o doador, nem importem contraprestação de serviços",
            "keywords": ["bolsas", "estudo", "pesquisa", "doação"],
            "has_items": True,
            "format": "standard",
        },
        "insurance_payouts_for_death_or_permanent_disability": {
            "code": "03",
            "name": "03. Capital das apólices de seguro ou pecúlio pago por morte do segurado, prêmio de seguro restituído em qualquer caso e pecúlio recebido de entidades de previdência privada em decorrência de morte ou invalidez permanente",
            "keywords": ["apólices", "seguro", "pecúlio", "morte", "invalidez"],
            "has_items": False,
            "format": "total_only",
        },
        "termination_and_work_accident_compensation_including_fgts": {
            "code": "04",
            "name": "04. Indenizações por rescisão de contrato de trabalho, inclusive a título de PDV, e por acidente de trabalho; e FGTS",
            "keywords": ["indenizações", "rescisão", "fgts", "pdv", "acidente"],
            "has_items": True,
            "format": "termination",  # Formato especial sem beneficiary, usa payer_cpf_cnpj
        },
        "capital_gains_on_asset_sale_in_the_same_month": {
            "code": "05",
            "name": "05. Ganho de capital na alienação de bem, direito ou conjunto de bens ou direitos da mesma natureza, alienados em um mesmo mês, de valor total de alienação até R$ 20.000,00, para ações alienadas no mercado de balcão, e R$ 35.000,00, nos demais casos",
            "keywords": ["ganho de capital", "alienação", "mesmo mês", "20.000"],
            "has_items": False,
            "format": "total_only",
        },
        "capital_gains_from_sale_of_only_property_within_5_years": {
            "code": "06",
            "name": "06. Ganho de capital na alienação do único imóvel por valor igual ou inferior a R$ 440.000,00 e que, nos últimos 5 anos, não tenha efetuado nenhuma outra alienação de imóvel",
            "keywords": ["único imóvel", "440.000", "5 anos"],
            "has_items": False,
            "format": "total_only",
        },
        "profits_and_dividends": {
            "code": "09",
            "name": "09. Lucros e dividendos recebidos",
            "keywords": ["lucros", "dividendos"],
            "has_items": True,
            "format": "standard",
        },
        "tax_free_retirement_income_for_seniors_age_65_and_over": {
            "code": "10",
            "name": "10. Parcela isenta de proventos de aposentadoria, reserva remunerada, reforma e pensão de declarante com 65 anos ou mais",
            "keywords": ["parcela isenta", "aposentadoria", "65 anos"],
            "has_items": True,
            "format": "retirement",  # Formato especial com Valor e 13º Salário
        },
        "pension_or_retirement_income_due_to_severe_illness_or_work_accident": {
            "code": "11",
            "name": "11. Pensão, proventos de aposentadoria ou reforma por moléstia grave ou aposentadoria ou reforma por acidente em serviço",
            "keywords": ["pensão", "moléstia grave", "acidente em serviço"],
            "has_items": True,
            "format": "illness",
        },
        "savings_accounts_mortgage_lci_lca_cra_cri": {
            "code": "12",
            "name": "12. Rendimentos de cadernetas de poupança, letras hipotecárias, letras de crédito do agronegócio e imobiliário (LCA e LCI) e certificados de recebíveis do agronegócio e imobiliários (CRA e CRI)",
            "keywords": [
                "cadernetas",
                "poupança",
                "letras hipotecárias",
                "LCA",
                "LCI",
                "CRA",
                "CRI",
            ],
            "has_items": True,
            "format": "standard",
        },
        "income_of_small_business_partner_or_owner": {
            "code": "13",
            "name": "13. Rendimento de sócio ou titular de microempresa ou empresa de pequeno porte optante pelo Simples Nacional, exceto pro labore, aluguéis e serviços prestados",
            "keywords": ["sócio", "titular", "microempresa", "simples nacional"],
            "has_items": True,
            "format": "standard",
        },
        "asset_transfers_donations_and_inheritances": {
            "code": "14",
            "name": "14. Transferências patrimoniais - doações e heranças",
            "keywords": ["transferências patrimoniais", "doações", "heranças"],
            "has_items": True,
            "format": "standard",
        },
        "exempt_portion_from_rural_activity": {
            "code": "15",
            "name": "15. Parcela não tributável correspondente à atividade rural",
            "keywords": ["parcela não tributável", "atividade rural", "rural"],
            "has_items": False,
            "format": "total_only",
        },
        "incorporation_reserves_into_capital_or_share_bonuses": {
            "code": "18",
            "name": "18. Incorporação de reservas ao capital / Bonificações em ações",
            "keywords": ["incorporação", "reservas", "capital", "bonificações"],
            "has_items": True,
            "format": "standard",
        },
        "net_gains_from_operations_in_the_spot_market": {
            "code": "20",
            "name": "20. Ganhos líquidos em operações no mercado à vista de ações negociadas em bolsas de valores nas alienações realizadas até R$ 20.000,00, em cada mês, para o conjunto de ações",
            "keywords": ["ganhos líquidos", "mercado à vista", "bolsas"],
            "has_items": True,
            "format": "simple",  # Formato sem CNPJ (apenas Beneficiário CPF Valor)
        },
        "net_gains_from_gold_sales_under_20000_per_month": {
            "code": "21",
            "name": "21. Ganhos líquidos em operações com ouro, ativo financeiro, nas alienações realizadas até R$ 20.000,00, em cada mês",
            "keywords": ["ganhos líquidos", "ouro", "ativo financeiro"],
            "has_items": True,
            "format": "simple",
        },
        "recovery_of_losses_in_variable_income": {
            "code": "22",
            "name": "22. Recuperação de Prejuízos em Renda Variável (bolsa de valores, de mercadorias, de futuros e assemelhados e fundos de investimento imobiliário)",
            "keywords": [
                "recuperação de prejuízos",
                "renda variável",
                "bolsa de valores",
                "fundos de investimento imobiliário",
            ],
            "has_items": False,
            "format": "total_only",
        },
        "gross_income_up_to_90_from_freight_services": {
            "code": "23",
            "name": "23. Rendimento bruto, até o máximo de 90%, da prestação de serviços decorrente do transporte de carga e com trator, máquina de terraplenagem, colheitadeira e assemelhados",
            "keywords": ["rendimento bruto", "90%", "transporte", "carga"],
            "has_items": False,
            "format": "total_only",
        },
        "income_tax_refund_from_previous_years": {
            "code": "25",
            "name": "25. Restituição do imposto sobre a renda de anos-calendário anteriores",
            "keywords": ["restituição", "imposto", "anos-calendário anteriores"],
            "has_items": False,
            "format": "total_only",
        },
        "interest_on_accumulated_income_received": {
            "code": "27",
            "name": "27. Juros referentes aos Rendimentos Recebidos Acumuladamente",
            "keywords": ["juros", "rendimentos recebidos acumuladamente"],
            "has_items": False,
            "format": "total_only",
        },
        "others_99": {
            "code": "99",
            "name": "99. Outros",
            "keywords": ["outros"],
            "has_items": True,
            "format": "others",
        },
    }

    @property
    def section_name(self) -> str:
        return "exempt_income"

    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)

    def extract(self, context: ExtractionContext) -> dict[str, Any] | None:
        if not self.can_extract(context):
            return None

        section_lines = self._get_section_lines(context)
        if not section_lines:
            return None

        subsections = {}

        for key, config in self.SUBSECTIONS.items():
            subsection = self._extract_subsection_by_format(section_lines, config, context)
            if subsection and (subsection.get("items") or subsection.get("total_value", 0) > 0):
                subsections[key] = subsection

        total_value = (
            sum(s.get("total_value", 0) for s in subsections.values()) if subsections else 0.0
        )

        pdf_total = self._extract_total_from_section(section_lines)

        return {
            "section_name": "Rendimentos Isentos e Não Tributáveis",
            "total_value": round(pdf_total if pdf_total else total_value, 2),
            "valid_total": True,
            "subsections": subsections,
            "items_count": sum(len(s.get("items", []) or []) for s in subsections.values()),
        }

    @staticmethod
    def _is_section_header(upper_line: str, markers: list[str]) -> bool:
        stripped = upper_line.strip()
        for marker in markers:
            if marker not in stripped:
                continue
            pos = stripped.find(marker)
            prefix = stripped[:pos].rstrip()
            if not prefix or re.match(r"^[\d\s.\-–—:]*$", prefix):
                return True
        return False

    def _get_section_lines(self, context: ExtractionContext) -> list[tuple[int, str]]:
        """Retorna APENAS as linhas dentro dos limites da seção exempt_income.

        Returns:
            Lista de (page_num, line_text) estritamente dentro de
            'RENDIMENTOS ISENTOS' até o próximo end marker.
        """
        result: list[tuple[int, str]] = []
        in_section = False

        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])

        for page_num, page_text in sorted_pages:
            for line in page_text.split("\n"):
                upper = line.upper()

                if not in_section:
                    if self._is_section_header(upper, self.SECTION_MARKERS):
                        in_section = True
                    continue

                if self._is_section_header(upper, self.SECTION_END_MARKERS):
                    return result

                result.append((page_num, line))

        return result

    def _extract_subsection_by_format(
        self, section_lines: list[tuple[int, str]], config: dict, context: ExtractionContext
    ) -> dict | None:
        fmt = config.get("format", "standard")

        if fmt == "total_only":
            return self._extract_total_only_subsection(section_lines, config)
        elif fmt == "retirement":
            return self._extract_retirement_subsection(section_lines, config)
        elif fmt == "illness":
            return self._extract_illness_subsection(section_lines, config)
        elif fmt == "simple":
            return self._extract_simple_subsection(section_lines, config)
        elif fmt == "others":
            return self._extract_others_subsection(section_lines, config, context)
        elif fmt == "termination":
            return self._extract_termination_subsection(section_lines, config)
        else:
            return self._extract_standard_subsection(section_lines, config)

    def _extract_total_only_subsection(
        self, section_lines: list[tuple[int, str]], config: dict
    ) -> dict | None:
        """Extrai subsection que tem apenas total (sem items)."""
        code = config["code"]
        name = config["name"]
        total_value = 0.0

        for idx, (_page_num, line) in enumerate(section_lines):
            if line.strip().startswith(f"{code}."):
                value_match = re.search(r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})\s*$", line)
                if value_match:
                    total_value = parse_currency(value_match.group(1))
                else:
                    for j in range(idx + 1, min(idx + 3, len(section_lines))):
                        next_line = section_lines[j][1].strip()
                        if re.match(r"^\d{2}\.", next_line):
                            break
                        if "Beneficiário" in next_line:
                            break
                        val_match = re.match(r"^([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})$", next_line)
                        if val_match:
                            total_value = parse_currency(val_match.group(1))
                            break
                break

        if total_value <= 0:
            return None

        return {
            "name": name,
            "code": code,
            "total_value": round(total_value, 2),
            "valid_total": True,
            "items": None,
        }

    def _extract_standard_subsection(
        self, section_lines: list[tuple[int, str]], config: dict
    ) -> dict | None:
        """Extrai subsection com formato padrão.

        Formato: Beneficiário CPF CPF/CNPJ Nome Valor
        """
        code = config["code"]
        name = config["name"]
        items = []
        seen_keys = set()

        in_subsection = False

        for idx, (page_num, line) in enumerate(section_lines):
            if line.strip().startswith(f"{code}."):
                in_subsection = True
                continue

            if re.match(r"^\d{2}\.", line.strip()) and not line.strip().startswith(f"{code}."):
                in_subsection = False
                continue

            if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                in_subsection = False
                continue

            if in_subsection:
                item = self._parse_standard_item_from_lines(line, section_lines, idx, page_num)
                if item:
                    key = f"{item.get('payer_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)

        total = round(sum(i.get("value", 0) for i in items), 2)

        header_total = self._extract_subsection_header_total(section_lines, code)
        if header_total and header_total > total:
            total = header_total

        if not items and total <= 0:
            return None

        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None,
        }

    def _extract_subsection_header_total(
        self, section_lines: list[tuple[int, str]], code: str
    ) -> float | None:
        """Extrai o total do cabeçalho da subsection."""
        for _, line in section_lines:
            if line.strip().startswith(f"{code}."):
                match = re.search(r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})\s*$", line)
                if match:
                    return parse_currency(match.group(1))
        return None

    def _parse_standard_item_from_lines(
        self, line: str, section_lines: list[tuple[int, str]], idx: int, page_num: int
    ) -> dict | None:
        """Parseia item no formato padrão usando section_lines."""
        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"

        pattern = re.match(
            rf"^(Titular|Dependente)\s+"
            rf"({CPF_PATTERN})\s+"
            rf"({CNPJ_PATTERN}|{CPF_PATTERN})\s+"
            rf"(.+?)\s+"
            rf"([\d.,]+)\s*$",
            line.strip(),
        )

        if not pattern:
            return None

        beneficiary = pattern.group(1)
        cpf = pattern.group(2)
        payer_doc = pattern.group(3)
        payer_name = pattern.group(4).strip()
        value = parse_currency(pattern.group(5))

        if idx + 1 < len(section_lines):
            next_line = section_lines[idx + 1][1].strip()
            if self._is_name_continuation(next_line):
                payer_name = f"{payer_name} {next_line}"

        item_id = generate_item_id(f"{payer_doc}{cpf}{value}")

        return {
            "beneficiary": beneficiary,
            "cpf": cpf,
            "payer_cnpj": payer_doc,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num,
        }

    def _extract_retirement_subsection(
        self, section_lines: list[tuple[int, str]], config: dict
    ) -> dict | None:
        """Extrai subsection 10 - aposentadoria 65+."""
        code = config["code"]
        name = config["name"]
        items = []

        in_subsection = False
        current_item = None

        for _idx, (page_num, line) in enumerate(section_lines):
            lower_line = line.lower()

            if f"{code}." in line and (
                "parcela isenta" in lower_line or "aposentadoria" in lower_line
            ):
                in_subsection = True
                continue

            if in_subsection:
                if re.match(r"^\d{2}\.", line.strip()) and not line.strip().startswith(f"{code}."):
                    if current_item:
                        items.append(current_item)
                        current_item = None
                    in_subsection = False
                    continue

                if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
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
                    line.strip(),
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
                        "page": page_num,
                    }
                elif current_item:
                    if "Valor:" not in line and not re.match(r"^(Titular|Dependente)", line):
                        name_cont = line.strip()
                        if (
                            name_cont
                            and re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", name_cont)
                            and "Valor:" not in name_cont
                        ):
                            current_item["payer_name"] = f"{current_item['payer_name']} {name_cont}"

                    if "Valor:" in line:
                        valor_match = re.search(r"Valor:\s*([\d.,]+)", line)
                        if valor_match:
                            current_item["value"] = parse_currency(valor_match.group(1))

                        salario_match = re.search(r"13[º°]?\s*Sal[aá]rio:\s*([\d.,]+)", line)
                        if salario_match:
                            current_item["thirteenth_salary"] = parse_currency(
                                salario_match.group(1)
                            )

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
            "items": items,
        }

    def _extract_illness_subsection(
        self, section_lines: list[tuple[int, str]], config: dict
    ) -> dict | None:
        """Extrai subsection 11 - moléstia grave."""
        code = config["code"]
        name = config["name"]
        items = []

        in_subsection = False

        for idx, (page_num, line) in enumerate(section_lines):
            lower_line = line.lower()

            if f"{code}." in line and (
                "pensão" in lower_line
                or "moléstia" in lower_line
                or "acidente em serviço" in lower_line
            ):
                in_subsection = True
                continue

            if in_subsection:
                if re.match(r"^\d{2}\.", line.strip()) and not line.strip().startswith(f"{code}."):
                    in_subsection = False
                    continue

                item_match = re.match(
                    r"^(Titular|Dependente)\s+"
                    r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
                    r"([\d.,]+)\s+"
                    r"([\d.,]+)\s+"
                    r"([\d.,]+)\s+"
                    r"([\d.,]+)\s+"
                    r"([\d.,]+)\s*$",
                    line.strip(),
                )

                if item_match:
                    item = {
                        "beneficiary": item_match.group(1),
                        "cpf": item_match.group(2),
                        "income": parse_currency(item_match.group(3)),
                        "irrf": parse_currency(item_match.group(4)),
                        "thirteenth_salary": parse_currency(item_match.group(5)),
                        "irrf_on_thirteenth_salary": parse_currency(item_match.group(6)),
                        "official_social_security_contribution": parse_currency(
                            item_match.group(7)
                        ),
                        "payer_cpf_cnpj": "",
                        "payer_name": "",
                        "page": page_num,
                    }

                    if idx + 1 < len(section_lines):
                        next_line = section_lines[idx + 1][1]
                        payer_match = re.search(
                            r"CPF/CNPJ\s*(?:da\s*)?Fonte\s*Pagadora:\s*"
                            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})\s*"
                            r"Nome\s*(?:da\s*)?Fonte\s*Pagadora:\s*(.+)$",
                            next_line,
                            re.IGNORECASE,
                        )
                        if payer_match:
                            item["payer_cpf_cnpj"] = payer_match.group(1)
                            item["payer_name"] = payer_match.group(2).strip()

                    item["id"] = generate_item_id(
                        f"{item['payer_cpf_cnpj']}{item['cpf']}{item['income']}"
                    )
                    items.append(item)

        if not items:
            return None

        total = round(sum(i["income"] + i.get("thirteenth_salary", 0) for i in items), 2)

        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items,
        }

    def _extract_simple_subsection(
        self, section_lines: list[tuple[int, str]], config: dict
    ) -> dict | None:
        """Extrai subsection 20, 21 - formato simples sem CNPJ."""
        code = config["code"]
        name = config["name"]
        items = []

        in_subsection = False

        for _idx, (page_num, line) in enumerate(section_lines):
            if line.strip().startswith(f"{code}."):
                in_subsection = True
                continue

            if in_subsection:
                if re.match(r"^\d{2}\.", line.strip()) and not line.strip().startswith(f"{code}."):
                    in_subsection = False
                    continue

                item_match = re.match(
                    r"^(Titular|Dependente)\s+"
                    r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
                    r"([\d.,]+)\s*$",
                    line.strip(),
                )

                if item_match:
                    value = parse_currency(item_match.group(3))
                    item = {
                        "beneficiary": item_match.group(1),
                        "cpf": item_match.group(2),
                        "value": value,
                        "id": generate_item_id(f"{item_match.group(2)}{value}"),
                        "page": page_num,
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
            "items": items,
        }

    def _extract_others_subsection(
        self, section_lines: list[tuple[int, str]], config: dict, context: ExtractionContext
    ) -> dict:
        """Extrai subseção 99. Outros."""
        code = config["code"]
        name = config["name"]
        items: list[dict] = []
        seen_keys: set[str] = set()

        others_page = None
        in_subsection = False

        for _idx, (page_num, line) in enumerate(section_lines):
            upper_line = line.upper()

            if re.search(r"99[.\s]+OUTROS", upper_line, re.IGNORECASE):
                in_subsection = True
                others_page = page_num
                continue

            if in_subsection and re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                in_subsection = False
                continue

            if in_subsection:
                item = self._parse_others_item_basic(line, page_num)
                if item:
                    key = f"{item.get('payer_cpf_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)
                elif items and self._is_others_continuation(line):
                    self._merge_others_continuation(items[-1], line)

        if items and context.pdf_path and others_page:
            items = self._refine_others_with_word_positions(context.pdf_path, others_page, items)

        total = round(sum(i["value"] for i in items), 2)

        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None,
        }

    @staticmethod
    def _is_others_continuation(line: str) -> bool:
        stripped = line.strip()
        if len(stripped) < 3:
            return False
        if re.match(r"^(Titular|Dependente)\s", stripped):
            return False
        if re.match(r"^(Benefici|CPF|CNPJ|Pagadora|Nome da)", stripped, re.IGNORECASE):
            return False
        if re.match(r"^TOTAL\s", stripped, re.IGNORECASE):
            return False
        return bool(re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]{2,}$", stripped))

    @staticmethod
    def _merge_others_continuation(item: dict, line: str) -> None:
        parts = re.split(r"\s{3,}", line.strip())
        if len(parts) >= 2:
            name_part = parts[0].strip()
            desc_part = " ".join(parts[1:]).strip()
            if item["payer_name"]:
                item["payer_name"] = f"{item['payer_name']} {name_part}"
            else:
                item["payer_name"] = name_part
            if desc_part:
                if item["description"]:
                    item["description"] = f"{item['description']} {desc_part}"
                else:
                    item["description"] = desc_part
        else:
            text = line.strip()
            if item["payer_name"]:
                item["payer_name"] = f"{item['payer_name']} {text}"
            else:
                item["payer_name"] = text

    @staticmethod
    def _split_name_description(text: str) -> tuple[str, str]:
        parts = re.split(r"\s{3,}", text.strip())
        if len(parts) >= 2:
            return parts[0].strip(), " ".join(parts[1:]).strip()
        return text.strip(), ""

    def _parse_others_item_basic(self, line: str, page_num: int) -> dict | None:
        """Parseia item de 'Outros' - extrai campos estruturados (CPF, CNPJ, valor)."""
        pattern = re.match(
            r"^(Titular|Dependente)\s+"
            r"(\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{3}\.\d{3}\.\d{3}-\d{2})\s+"
            r"(.+?)\s+"
            r"([\d.,]+)\s*$",
            line.strip(),
        )

        if not pattern:
            return None

        payer_name, description = self._split_name_description(pattern.group(4))

        return {
            "beneficiary": pattern.group(1),
            "cpf": pattern.group(2),
            "payer_cpf_cnpj": pattern.group(3),
            "payer_name": payer_name,
            "description": description,
            "value": parse_currency(pattern.group(5)),
            "id": generate_item_id(
                f"{pattern.group(3)}{pattern.group(2)}{parse_currency(pattern.group(5))}"
            ),
            "page": page_num,
        }

    def _refine_others_with_word_positions(
        self, pdf_path: str, page_num: int, items: list[dict]
    ) -> list[dict]:
        """Usa posições de palavras do pdfplumber para separar nome e descrição."""
        try:
            import pdfplumber

            with pdfplumber.open(pdf_path) as pdf:
                page = pdf.pages[page_num - 1]
                words = page.extract_words()

            section_start = next((w for w in words if w["text"] == "99."), None)
            if not section_start:
                return items
            section_top = section_start["top"]

            total_word = next(
                (w for w in words if w["text"].upper() == "TOTAL" and w["top"] > section_top + 20),
                None,
            )
            section_bottom = total_word["top"] if total_word else section_top + 200

            section_words = [w for w in words if section_top <= w["top"] <= section_bottom]

            desc_header = next((w for w in section_words if w["text"] == "Descrição"), None)
            if not desc_header:
                return items

            desc_x = desc_header["x0"]
            name_header = next(
                (w for w in section_words if w["text"] == "Nome" and w["x0"] < desc_x), None
            )
            name_x = name_header["x0"] if name_header else desc_x - 100
            col_boundary = (desc_x + name_x) / 2 + (desc_x - name_x) * 0.3

            for item in items:
                cnpj_str = item["payer_cpf_cnpj"].replace(".", "").replace("/", "").replace("-", "")

                anchor_word = next(
                    (
                        w
                        for w in section_words
                        if cnpj_str in w["text"].replace(".", "").replace("/", "").replace("-", "")
                    ),
                    None,
                )
                if not anchor_word:
                    continue

                item_top = anchor_word["top"]

                next_item_top = None
                for other in items:
                    if other is item:
                        continue
                    other_cnpj = (
                        other["payer_cpf_cnpj"].replace(".", "").replace("/", "").replace("-", "")
                    )
                    other_w = next(
                        (
                            w
                            for w in section_words
                            if other_cnpj
                            in w["text"].replace(".", "").replace("/", "").replace("-", "")
                        ),
                        None,
                    )
                    if (
                        other_w
                        and other_w["top"] > item_top
                        and (next_item_top is None or other_w["top"] < next_item_top)
                    ):
                        next_item_top = other_w["top"]

                end_top = min(next_item_top or section_bottom, section_bottom)

                left_x = anchor_word["x1"] + 5

                text_words = [
                    w
                    for w in section_words
                    if w["top"] >= item_top - 2
                    and w["top"] < end_top
                    and w["x0"] >= left_x
                    and not re.match(r"^[\d.,]+$", w["text"])
                    and w["text"] not in ("Titular", "Dependente")
                    and not re.match(r"^\d{3}\.\d{3}\.\d{3}", w["text"])
                    and not re.match(r"^\d{2}\.\d{3}\.\d{3}/", w["text"])
                ]

                name_words = sorted(
                    [w for w in text_words if w["x0"] < col_boundary],
                    key=lambda w: (w["top"], w["x0"]),
                )
                desc_words = sorted(
                    [w for w in text_words if w["x0"] >= col_boundary],
                    key=lambda w: (w["top"], w["x0"]),
                )

                if name_words:
                    item["payer_name"] = " ".join(w["text"] for w in name_words)
                if desc_words:
                    item["description"] = " ".join(w["text"] for w in desc_words)

        except Exception:
            pass

        return items

    def _extract_termination_subsection(
        self, section_lines: list[tuple[int, str]], config: dict
    ) -> dict | None:
        """Extrai subsection 04 - indenizações/rescisão/FGTS."""
        code = config["code"]
        name = config["name"]
        items = []
        seen_keys = set()

        in_subsection = False

        for idx, (page_num, line) in enumerate(section_lines):
            if line.strip().startswith(f"{code}."):
                in_subsection = True
                continue

            if re.match(r"^\d{2}\.", line.strip()) and not line.strip().startswith(f"{code}."):
                in_subsection = False
                continue

            if re.match(r"^TOTAL\s+[\d.,]+\s*$", line.strip(), re.IGNORECASE):
                in_subsection = False
                continue

            if in_subsection:
                item = self._parse_termination_item_from_lines(line, section_lines, idx, page_num)
                if item:
                    key = f"{item.get('payer_cpf_cnpj', '')}{item.get('cpf', '')}{item.get('value', 0)}{page_num}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        items.append(item)

        total = round(sum(i.get("value", 0) for i in items), 2)

        header_total = self._extract_subsection_header_total(section_lines, code)
        if header_total and header_total > total:
            total = header_total

        if not items and total <= 0:
            return None

        return {
            "name": name,
            "code": code,
            "total_value": total,
            "valid_total": True,
            "items": items if items else None,
        }

    def _parse_termination_item_from_lines(
        self, line: str, section_lines: list[tuple[int, str]], idx: int, page_num: int
    ) -> dict | None:
        """Parseia item de indenização/rescisão (código 04)."""
        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"

        pattern = re.match(
            rf"^(?:Titular|Dependente)\s+"
            rf"({CPF_PATTERN})\s+"
            rf"({CNPJ_PATTERN}|{CPF_PATTERN})\s+"
            rf"(.+?)\s+"
            rf"([\d.,]+)\s*$",
            line.strip(),
        )

        if not pattern:
            return None

        cpf = pattern.group(1)
        payer_doc = pattern.group(2)
        payer_name = pattern.group(3).strip()
        value = parse_currency(pattern.group(4))

        if idx + 1 < len(section_lines):
            next_line = section_lines[idx + 1][1].strip()
            if self._is_name_continuation(next_line):
                payer_name = f"{payer_name} {next_line}"

        item_id = generate_item_id(f"{payer_doc}{cpf}{value}")

        return {
            "cpf": cpf,
            "payer_cpf_cnpj": payer_doc,
            "payer_name": payer_name,
            "value": value,
            "id": item_id,
            "page": page_num,
        }

    def _extract_total_from_section(self, section_lines: list[tuple[int, str]]) -> float | None:
        """Extrai o total geral da seção a partir das linhas filtradas.

        O TOTAL costuma ser a última linha relevante da seção.
        """
        for _, line in reversed(section_lines):
            stripped = line.strip()
            total_match = re.match(r"^TOTAL\s+([\d.,]+)\s*$", stripped, re.IGNORECASE)
            if total_match:
                return parse_currency(total_match.group(1))
            if stripped and not stripped.startswith("Página"):
                break
        return None

    def _is_name_continuation(self, line: str) -> bool:
        """Verifica se linha é continuação de nome."""
        if len(line) <= 2:
            return False

        if "TOTAL" in line.upper() or "Titular" in line or "Dependente" in line:
            return False

        return bool(re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇ\s]+$", line))
