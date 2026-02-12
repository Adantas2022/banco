"""Extrator de dívidas da atividade rural."""

import re
from typing import Any

from ...table_extractor import generate_item_id, parse_currency, sum_currency_values
from ...validation_utils import create_validated_total
from ..base import ExtractionContext, ISectionExtractor


class RuralDebtsExtractor(ISectionExtractor):
    """Extrai dívidas vinculadas à atividade rural."""

    SECTION_MARKER = "DÍVIDAS VINCULADAS À ATIVIDADE RURAL"

    @property
    def section_name(self) -> str:
        return "rural_activity_debts_in_brazil"

    def can_extract(self, context: ExtractionContext) -> bool:
        return self.SECTION_MARKER in context.full_text.upper()

    def extract(self, context: ExtractionContext) -> dict[str, Any] | None:
        items = []
        pdf_totals = []  # Totais extraídos do PDF

        for page_num, page_text in context.pages_text.items():
            upper_text = page_text.upper()

            if self.SECTION_MARKER not in upper_text:
                continue

            # Garantir que é BRASIL e não EXTERIOR
            if "EXTERIOR" in upper_text and "BRASIL" not in upper_text:
                continue

            # Se a página tem ambos (BRASIL e EXTERIOR), só extrair a parte BRASIL
            page_items = self._extract_from_page(page_text, page_num)
            items.extend(page_items)

            # Extrair total do PDF APENAS após o marcador da seção
            if not pdf_totals:
                page_totals = self._extract_section_total(page_text)
                if page_totals:
                    pdf_totals = page_totals

        if not items:
            return None

        # Somar valores extraídos
        sum_before = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        sum_last = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        sum_paid = sum_currency_values([i["paid_value_in_last_year"] for i in items], as_int=False)

        # Totais do PDF (se disponíveis)
        pdf_before = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_last = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_paid = pdf_totals[2] if len(pdf_totals) > 2 else None

        totals = {
            "year_before_last_value": create_validated_total(sum_before, pdf_before),
            "last_year_value": create_validated_total(sum_last, pdf_last),
            "paid_value_in_last_year": create_validated_total(sum_paid, pdf_paid),
        }

        return {
            "section_name": "Dívidas Vinculadas à Atividade Rural - Brasil",
            "items": items,
            "total_values": totals,
        }

    def _extract_section_total(self, page_text: str) -> list[float]:
        """Extrai o TOTAL específico da seção de Dívidas Rurais - BRASIL.

        Busca a linha TOTAL apenas APÓS encontrar o marcador da seção BRASIL,
        evitando pegar totais de seções anteriores (BENS) ou EXTERIOR.

        Suporta dois formatos:
        1. Inline: TOTAL 100,000.00 120,000.00 20,000.00
        2. OCR multiline: valores em linhas separadas antes de TOTAL

        No formato OCR, os totais aparecem nas linhas anteriores a "TOTAL":
        - valor_pago_total
        - valor_31_12_anterior_total
        - valor_31_12_atual_total
        - TOTAL

        Retorna: [valor_31_12_anterior, valor_31_12_atual, valor_pago]
        """
        lines = page_text.split("\n")
        in_section = False
        num_pattern = r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})"

        # Coletar valores após entrar na seção, antes de TOTAL
        section_values = []

        for i, line in enumerate(lines):
            upper_line = line.upper()

            # Entrar na seção BRASIL (não EXTERIOR)
            if (
                self.SECTION_MARKER in upper_line
                and "BRASIL" in upper_line
                and "EXTERIOR" not in upper_line
            ):
                in_section = True
                section_values = []  # Reset ao entrar na seção
                continue

            # Sair se encontrar EXTERIOR
            if in_section and "EXTERIOR" in upper_line and self.SECTION_MARKER in upper_line:
                break

            if not in_section:
                continue

            # Encontrar linha de TOTAL dentro da seção
            if upper_line.strip() == "TOTAL":
                # Tentar formato inline primeiro
                matches = re.findall(num_pattern, line)
                if matches and len(matches) >= 2:
                    return [self._parse_currency(m) for m in matches]

                # Se não há valores na linha TOTAL, pegar os últimos valores coletados
                # No formato OCR multiline, as últimas 3 linhas antes de TOTAL são:
                # valor_pago, valor_31_12_2024, valor_31_12_2023 (ordem invertida)
                # Precisamos retornar: [valor_31_12_2023, valor_31_12_2024, valor_pago]
                if len(section_values) >= 3:
                    paid = section_values[-3]  # 20,000.00
                    current = section_values[-2]  # 120,000.00 (31/12/2024)
                    before = section_values[-1]  # 100,000.00 (31/12/2023)
                    return [before, current, paid]
                elif len(section_values) >= 2:
                    return section_values[-2:]

                return []

            # Coletar valores monetários dentro da seção
            stripped = line.strip()
            if re.match(r"^[\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2}$", stripped):
                section_values.append(self._parse_currency(stripped))

        return []

    def _parse_currency(self, value_str: str) -> float:
        return parse_currency(value_str)

    def _extract_from_page(self, page_text: str, page_num: int) -> list[dict]:
        items = []
        lines = page_text.split("\n")

        in_section = False
        passed_header = False  # Indica se já passamos pelo cabeçalho da seção
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()

            # Detectar início da seção BRASIL (marker completo com "BRASIL")
            if (
                self.SECTION_MARKER in upper_line
                and "BRASIL" in upper_line
                and "EXTERIOR" not in upper_line
            ):
                in_section = True
                passed_header = False
                i += 1
                continue

            # Parar se encontrar seção EXTERIOR
            if in_section and "EXTERIOR" in upper_line and self.SECTION_MARKER in upper_line:
                break

            # Parar no TOTAL da seção
            if in_section and upper_line.startswith("TOTAL"):
                break

            if not in_section:
                i += 1
                continue

            # Pular cabeçalhos da tabela
            if not passed_header:
                if "VALOR PAGO" in upper_line:
                    passed_header = True
                i += 1
                continue

            # Tentar formato inline: ITEM DESC VAL1 VAL2 VAL3
            pattern = re.match(r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", line)

            if pattern and "ITEM" not in upper_line and "TOTAL" not in upper_line:
                item = self._parse_debt(pattern, lines, i, page_num)
                if item:
                    items.append(item)
                    i = item.pop("_next_index", i + 1)
                    continue

            # Tentar formato OCR multiline onde descrição, valores e item estão em linhas separadas
            multiline_item = self._try_parse_multiline_format(lines, i, page_num)
            if multiline_item:
                items.append(multiline_item)
                i = multiline_item.pop("_next_index", i + 1)
                continue

            i += 1

        return items

    def _try_parse_multiline_format(
        self, lines: list[str], start_idx: int, page_num: int
    ) -> dict | None:
        """Parse formato OCR onde dados estão em linhas separadas.

        Formato esperado (após cabeçalho):
        - Linha com descrição (texto)
        - Linha com valor 31/12/ano_anterior (número)
        - Linha com valor 31/12/ano_atual (número)
        - Linha com número do item (número inteiro pequeno)
        - Linha com valor pago no ano (número)

        Exemplo:
        54: 'DÍVIDAS VINCULADAS À ATIVIDADE RURAL'  <- descrição do item
        55: '100,000.00'                            <- valor 31/12/2023
        56: '120,000.00'                            <- valor 31/12/2024
        57: '1'                                     <- número do item
        58: '20,000.00'                             <- valor pago
        """
        if start_idx + 3 >= len(lines):
            return None

        line = lines[start_idx].strip()
        upper_line = line.upper()

        # A descrição deve ser texto (não apenas números)
        if not line or re.match(r"^[\d.,]+$", line):
            return None

        # Pular linhas de cabeçalho que não são descrições válidas
        if self._is_header_line(line):
            return None

        # Verificar se parece uma descrição válida
        if not self._is_valid_description(line):
            return None

        # Coletar as próximas linhas para verificar padrão
        next_lines = []
        j = start_idx + 1
        while j < len(lines) and len(next_lines) < 6:
            next_line = lines[j].strip()
            upper_next = next_line.upper()

            if "TOTAL" in upper_next:
                break

            if next_line:
                next_lines.append((j, next_line))
            j += 1

        if len(next_lines) < 3:
            return None

        # Tentar identificar padrão: val1, val2, item_num, val3
        values = []
        item_num = None
        last_idx = start_idx

        for idx, next_line in next_lines:
            # É um número de item (inteiro pequeno, geralmente 1-99)?
            if re.match(r"^(\d{1,2})$", next_line) and item_num is None:
                item_num = int(next_line)
                last_idx = idx
                continue

            # É um valor monetário?
            if re.match(r"^[\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2}$", next_line):
                values.append(parse_currency(next_line))
                last_idx = idx
                continue

            # Se encontrou texto que não é valor/item, parar
            if not re.match(r"^[\d.,]+$", next_line):
                break

        # Precisamos de pelo menos: val1, val2, item_num
        if item_num is None or len(values) < 2:
            return None

        # Determinar quais valores são quais baseado na posição
        # Formato típico: descrição -> val1 -> val2 -> item -> val_pago
        if len(values) >= 3:
            year_before = values[0]
            year_current = values[1]
            paid_value = values[2]
        elif len(values) == 2:
            # Apenas 2 valores - assumir que valor pago é 0
            year_before = values[0]
            year_current = values[1]
            paid_value = 0.0
        else:
            return None

        item_id = generate_item_id(f"{item_num}{line[:30]}")

        return {
            "item": item_num,
            "description": line,
            "year_before_last_value": year_before,
            "last_year_value": year_current,
            "paid_value_in_last_year": paid_value,
            "id": item_id,
            "page": page_num,
            "_next_index": last_idx + 1,
        }

    def _is_header_line(self, line: str) -> bool:
        """Verifica se a linha é um cabeçalho de tabela."""
        upper = line.upper()
        header_patterns = [
            "ITEM",
            "DISCRIMINAÇÃO",
            "SITUAÇÃO EM",
            "VALOR PAGO",
            "(VALORES EM REAIS)",
            "CÓDIGO",
            "TOTAL",
            "PÁGINA",
            "31/12/",
        ]
        return any(p in upper for p in header_patterns)

    def _is_valid_description(self, line: str) -> bool:
        """Verifica se a linha parece uma descrição válida de dívida."""
        # Deve ter pelo menos 3 caracteres
        if len(line) < 3:
            return False

        # Não deve ser apenas números
        if re.match(r"^[\d.,\s]+$", line):
            return False

        # Deve conter letras
        if not re.search(r"[A-Za-záàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ]", line):
            return False

        return True

    def _parse_debt(self, match: re.Match, lines: list[str], idx: int, page_num: int) -> dict:
        item_num = int(match.group(1))
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        paid_val = parse_currency(match.group(5))

        prefix_parts = self._get_prefix_lines(lines, idx)
        desc_parts = prefix_parts + [desc_start]
        j = idx + 1

        while j < len(lines):
            next_line = lines[j].strip()

            if re.match(r"^\d+\s+", next_line) or "TOTAL" in next_line.upper():
                break

            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+", next_line):
                desc_parts.append(next_line)

            j += 1

        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()

        item_id = generate_item_id(f"{item_num}{full_desc[:30]}")

        return {
            "item": item_num,
            "description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "paid_value_in_last_year": paid_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j,
        }

    def _get_prefix_lines(self, lines: list[str], idx: int) -> list[str]:
        prefix_parts = []
        k = idx - 1
        while k >= 0:
            prev_line = lines[k].strip()

            if not prev_line:
                break

            if re.match(r"^(\d+)\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", prev_line):
                break

            if re.match(r"^[\d.,]+\s+[\d.,]+\s*$", prev_line):
                break

            if "TOTAL" in prev_line.upper() or "ITEM" in prev_line.upper():
                break

            if re.match(r"^Página\s+\d+\s+de", prev_line, re.IGNORECASE):
                break

            if "DÍVIDAS VINCULADAS" in prev_line.upper():
                break

            if self._is_description_fragment(prev_line):
                prefix_parts.insert(0, prev_line)
                k -= 1
            else:
                break

        return prefix_parts

    def _is_description_fragment(self, line: str) -> bool:
        if re.match(r"^\d+$", line):
            return False

        if re.match(r"^[\d.,]+$", line):
            return False

        if len(line) < 3:
            return False

        # Ignorar datas de cabeçalho (ex: "31/12/2023 31/12/2024")
        if re.match(r"^\d{2}/\d{2}/\d{4}", line):
            return False

        # Ignorar cabeçalhos de coluna
        if "SITUAÇÃO EM" in line.upper() or "VALOR PAGO" in line.upper():
            return False

        return True
