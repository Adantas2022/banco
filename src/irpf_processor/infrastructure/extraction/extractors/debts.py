"""Extrator de dívidas e ônus reais."""

import re
from typing import Any, Optional

from .base import ExtractionContext, ISectionExtractor
from ..table_extractor import parse_currency, generate_item_id, sum_currency_values
from ..validation_utils import create_validated_total


class DebtsExtractor(ISectionExtractor):
    """Extrai dívidas e ônus reais."""
    
    # Marcadores de seção - incluindo variações OCR
    SECTION_MARKERS = [
        "DÍVIDAS E ÔNUS REAIS",
        "DIVIDAS E ONUS REAIS",
        "DÍVIDAS E ONUS REAIS",
        "DIVIDAS E ÔNUS REAIS",
    ]
    SECTION_MARKER = "DÍVIDAS E ÔNUS REAIS"  # Mantido para compatibilidade
    # IMPORTANTE: Apenas marcadores de seções que vêm DEPOIS de dívidas na declaração IRPF
    # A ordem no IRPF é: Identificação > Rendimentos > Pagamentos > Bens > DÍVIDAS > Doações > Atividade Rural
    SECTION_END_MARKERS = [
        # Seções que vêm DEPOIS de dívidas
        "DOAÇÕES A PARTIDOS",
        "DOACOES A PARTIDOS",
        "DOAÇÕES EFETUADAS",
        "DOACOES EFETUADAS",
        "ESPÓLIO",
        "ESPOLIO",
        # Seções de atividade rural que indicam fim
        "DÍVIDAS VINCULADAS À ATIVIDADE RURAL",
        "DIVIDAS VINCULADAS A ATIVIDADE RURAL",
        "BENS DA ATIVIDADE RURAL",
        "PROPRIEDADES RURAIS EXPLORADAS",
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL",
        "DADOS E IDENTIFICACAO DO IMOVEL",
        "DEMONSTRATIVO DE ATIVIDADE RURAL",
    ]
    VALID_DEBT_CODES = {"11", "12", "13", "14", "15", "16", "17", "18", "19"}
    
    @property
    def section_name(self) -> str:
        return "debts_and_encumbrances"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        section_pages: list[tuple[int, str]] = []
        
        empty_pages: list[tuple[int, str]] = []
        
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            has_debts_marker = any(marker in upper_text for marker in self.SECTION_MARKERS)
            
            if has_debts_marker:
                in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            section_pages.append((page_num, page_text))
            
            items_before = len(items)
            page_items = self._extract_from_page(page_text, page_num, seen_ids, already_in_section=in_section)
            items.extend(page_items)
            
            if len(items) == items_before:
                empty_pages.append((page_num, page_text))
            
            if not pdf_totals:
                page_totals = self._extract_debts_total(page_text)
                if page_totals:
                    pdf_totals = page_totals
            
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
        if not items and section_pages:
            items = self._extract_ocr_fallback(section_pages)
        elif empty_pages:
            fallback_items = self._extract_ocr_fallback(
                empty_pages, assume_in_section=True
            )
            if fallback_items:
                for fi in fallback_items:
                    if fi["id"] not in seen_ids:
                        seen_ids.add(fi["id"])
                        items.append(fi)
        
        if not items:
            return None
        
        # Somar valores extraídos
        year_before_last_total = sum_currency_values([i["year_before_last_value"] for i in items], as_int=False)
        last_year_total = sum_currency_values([i["last_year_value"] for i in items], as_int=False)
        paid_total = sum_currency_values([i.get("current_year_value", 0) for i in items], as_int=False)
        
        # Totais do PDF (se disponíveis)
        pdf_before = pdf_totals[0] if len(pdf_totals) > 0 else None
        pdf_last = pdf_totals[1] if len(pdf_totals) > 1 else None
        pdf_paid = pdf_totals[2] if len(pdf_totals) > 2 else None
        
        return {
            "section_name": "Dívidas e Ônus Reais",
            "items": items,
            "amount_of_codes_equal_to_amount_of_values": True,
            "year_before_last_total_value": year_before_last_total,
            "last_year_total_value": last_year_total,
            "current_year_total_value": paid_total,
            "total_values": {
                "year_before_last_value": create_validated_total(year_before_last_total, pdf_before),
                "last_year_value": create_validated_total(last_year_total, pdf_last),
                "current_year_value": create_validated_total(paid_total, pdf_paid)
            },
            "pages_with_problems": []
        }
    
    def _is_definitive_section_end(self, page_text: str) -> bool:
        """Verifica se esta página marca o fim definitivo da seção."""
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue
            
            # Verificar marcadores de fim de seção
            for marker in self.SECTION_END_MARKERS:
                if stripped == marker or stripped.startswith(marker + " "):
                    # Confirmar que é uma nova seção (tem código ou cabeçalho)
                    next_lines = " ".join(lines[i+1:i+5]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
                        return True
                    if re.search(r"^\d{2}\s+", next_lines):
                        return True
            
            # Se encontrar outra seção principal
            if stripped.startswith("PROPRIEDADES RURAIS EXPLORADAS"):
                return True
            if stripped == "BENS DA ATIVIDADE RURAL - BRASIL":
                return True
        
        return False
    
    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set, already_in_section: bool = False) -> list[dict]:
        items = []
        lines = page_text.split("\n")
        
        # Se já estamos na seção (página de continuação), começar como True
        in_section = already_in_section
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()
            
            # Detectar início da seção (para primeira página) - verificar todos os marcadores
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                if "ATIVIDADE RURAL" not in upper_line:
                    in_section = True
                    i += 1
                    continue
            
            # Detectar fim da seção nesta página
            if in_section and self._is_section_end_line(upper_line):
                break
            
            # Skip linhas de cabeçalho (também entra na seção)
            if "CÓDIGO" in upper_line or "CODIGO" in upper_line or "DISCRIMINAÇÃO" in upper_line or "DISCRIMINACAO" in upper_line:
                in_section = True
                i += 1
                continue
            
            if "TOTAL" in upper_line and not re.match(r"^\d{2}\s+", line):
                i += 1
                continue
            
            # SOMENTE extrair se já estiver dentro da seção
            # NÃO forçar entrada na seção apenas por encontrar padrão de código
            if not in_section:
                i += 1
                continue
            
            # Normalizar linha para lidar com OCR (espaços antes da vírgula)
            normalized_line = self._normalize_ocr_numbers(line)
            
            # Tentar detectar item de dívida - formato padrão
            debt_match = re.match(
                r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                normalized_line
            )
            
            if debt_match:
                code = debt_match.group(1)
                if self._is_valid_debt_code(code):
                    item = self._parse_debt(debt_match, lines, i, page_num)
                    if item and item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        items.append(item)
                        i = item.pop("_next_index", i + 1)
                        continue
            
            # Tentar formato alternativo OCR - código + descrição + valores em linhas separadas
            if re.match(r"^(\d{2})\s+(.+)", normalized_line):
                item = self._try_parse_multiline_debt(lines, i, page_num, seen_ids)
                if item:
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        items.append(item)
                        i = item.pop("_next_index", i + 1)
                        continue
            
            i += 1
        
        return items
    
    def _normalize_ocr_numbers(self, line: str) -> str:
        """Normaliza números OCR removendo espaços antes da vírgula decimal."""
        # Remove espaços antes da vírgula: "7.795.431 ,86" -> "7.795.431,86"
        return re.sub(r'(\d)\s+,', r'\1,', line)
    
    def _try_parse_multiline_debt(
        self, 
        lines: list[str], 
        idx: int, 
        page_num: int,
        seen_ids: set
    ) -> Optional[dict]:
        """Tenta parsear dívida em formato multiline (OCR)."""
        line = self._normalize_ocr_numbers(lines[idx].strip())
        
        # Verificar se começa com código válido
        code_match = re.match(r"^(\d{2})\s+(.+)", line)
        if not code_match:
            return None
        
        code = code_match.group(1)
        if not self._is_valid_debt_code(code):
            return None
        
        desc_start = code_match.group(2).strip()
        
        # Coletar descrição e valores nas próximas linhas
        desc_parts = [desc_start]
        values = []
        j = idx + 1
        
        while j < len(lines):
            next_line = self._normalize_ocr_numbers(lines[j].strip())
            upper_next = next_line.upper()
            
            # Parar em TOTAL
            if "TOTAL" in upper_next and not re.match(r"^\d{2}\s+", next_line):
                break
            
            # Parar em marcadores de fim
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            # Parar se encontrar novo item
            if re.match(r"^(\d{2})\s+.+\s+[\d.,]+\s+[\d.,]+\s+[\d.,]+\s*$", next_line):
                break
            if re.match(r"^(\d{2})\s+[A-Z]", next_line) and self._is_valid_debt_code(re.match(r"^(\d{2})", next_line).group(1)):
                break
            
            # Extrair valores se a linha contiver 3 números
            values_match = re.findall(r'([\d.]+,\d{2})', next_line)
            if len(values_match) >= 3:
                values = values_match[:3]
                j += 1
                break
            
            # Adicionar como continuação da descrição
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+\s+[\d.,]+$", next_line):
                if not upper_next.startswith("CÓDIGO") and not upper_next.startswith("CODIGO"):
                    if not upper_next.startswith("DISCRIMINAÇÃO") and not upper_next.startswith("DISCRIMINACAO"):
                        desc_parts.append(next_line)
            
            j += 1
        
        # Se não encontrou 3 valores, não é um item válido
        if len(values) < 3:
            return None
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s*Pagina\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        normalized_desc = re.sub(r"(\S)\(", r"\1 (", full_desc)
        normalized_desc = re.sub(r"\(\s+", "(", normalized_desc)
        v1 = parse_currency(values[0])
        v2 = parse_currency(values[1])
        v3 = parse_currency(values[2])
        item_id = generate_item_id(f"{normalized_desc}_{v1}_{v2}_{v3}")
        
        return {
            "debt_code": code,
            "debt_description": full_desc,
            "year_before_last_value": v1,
            "last_year_value": v2,
            "current_year_value": v3,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    def _is_section_end_line(self, upper_line: str) -> bool:
        """Verifica se a linha indica fim da seção."""
        for marker in self.SECTION_END_MARKERS:
            if marker.upper() in upper_line:
                return True
        
        # Outras seções que indicam fim
        if upper_line.startswith("PROPRIEDADES RURAIS"):
            return True
        if "ATIVIDADE RURAL" in upper_line:
            return True
        
        return False
    
    def _is_valid_debt_code(self, code: str) -> bool:
        return code in self.VALID_DEBT_CODES
    
    def _parse_debt(
        self, 
        match: re.Match, 
        lines: list[str], 
        idx: int,
        page_num: int
    ) -> dict:
        code = match.group(1)
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        paid_val = parse_currency(match.group(5))
        
        desc_parts = [desc_start]
        j = idx + 1
        
        while j < len(lines):
            next_line = lines[j].strip()
            upper_next = next_line.upper()
            
            # Parar em TOTAL
            if "TOTAL" in upper_next and not re.match(r"^\d{2}\s+", next_line):
                break
            
            # Parar em marcadores de fim
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            # Parar se encontrar novo item
            is_new_item = re.match(r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", next_line)
            if is_new_item:
                break
            
            # Adicionar como continuação da descrição
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+\s+[\d.,]+$", next_line):
                if not next_line.upper().startswith("CÓDIGO"):
                    if not next_line.upper().startswith("DISCRIMINAÇÃO"):
                        desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        normalized_desc = re.sub(r"(\S)\(", r"\1 (", full_desc)
        normalized_desc = re.sub(r"\(\s+", "(", normalized_desc)
        item_id = generate_item_id(f"{normalized_desc}_{before_val}_{current_val}_{paid_val}_{page_num}")
        
        return {
            "debt_code": code,
            "debt_description": full_desc,
            "year_before_last_value": before_val,
            "last_year_value": current_val,
            "current_year_value": paid_val,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }
    
    @staticmethod
    def _prev_line_ends_with_currency_prefix(current_block: list[str],
                                              raw_blocks: list) -> bool:
        """Verifica se a linha anterior termina com 'R$' (indicando valor embutido na descrição).
        
        Quando o OCR quebra "R$ 367.000,00" em duas linhas, a segunda linha
        ("367.000,00") parece um valor de coluna mas na verdade faz parte da descrição.
        """
        prev_line = None
        if current_block:
            prev_line = current_block[-1].strip()
        elif raw_blocks:
            prev_line = raw_blocks[-1][0][-1].strip()
        
        if prev_line and re.search(r'R\$\s*[-]?\s*$', prev_line, re.IGNORECASE):
            return True
        return False

    def _extract_ocr_fallback(
        self,
        section_pages: list[tuple[int, str]],
        assume_in_section: bool = False,
    ) -> list[dict]:
        CURRENCY_RE = r"(\d[\d.]*,\d{2})"
        # SKIP_RE: pula linhas de cabeçalho.
        # CPF: agora exige formato completo para não pular referências a CPF dentro de descrições.
        SKIP_RE = re.compile(
            r"^(NOME:|DECLARAÇÃO DE AJUSTE|DECLARACAO DE AJUSTE|IMPOSTO SOBRE|"
            r"EXERC[IÍ]CIO\s+\d|\(Valores em|CÓDIGO|CODIGO|"
            r"DISCRIMINA[CÇ][AÃ]O|SITUA[CÇ][AÃ]O|VALOR PAGO|"
            r"AN[O0]-CALEND[AÁ]RIO|\d{2}/\d{2}/\d{4}\s+EM\s+\d{4})",
            re.IGNORECASE,
        )
        # CPF de cabeçalho: linha curta com apenas CPF (ex: "CPF: 004.044.951-33")
        CPF_HEADER_RE = re.compile(
            r"^CPF:\s*\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2}\s*$",
            re.IGNORECASE,
        )
        
        raw_blocks: list[tuple[list[str], int]] = []
        value_lines_info: list[int] = []
        flat_values: list[str] = []
        
        in_section = assume_in_section
        past_header = assume_in_section
        collecting_values = False
        current_block: list[str] = []
        current_page = 0
        
        for page_num, page_text in section_pages:
            for raw_line in page_text.split("\n"):
                s = raw_line.strip()
                upper = s.upper()
                
                if any(m in upper for m in self.SECTION_MARKERS):
                    if "ATIVIDADE RURAL" not in upper and "VINCULADA" not in upper:
                        in_section = True
                        continue
                
                if not in_section:
                    continue
                
                if any(m in upper for m in self.SECTION_END_MARKERS):
                    in_section = False
                    break
                if "ATIVIDADE RURAL" in upper:
                    in_section = False
                    break
                
                if not past_header and ("CÓDIGO" in upper or "CODIGO" in upper
                                        or "DISCRIMINA" in upper):
                    past_header = True
                    continue
                
                if not past_header:
                    continue
                
                if upper.startswith("TOTAL"):
                    if current_block and not collecting_values:
                        raw_blocks.append((current_block, current_page))
                        current_block = []
                    if collecting_values:
                        collecting_values = False
                    continue
                
                if re.match(r"^P[aá]gina\s+\d+\s+de\s+\d+", s, re.IGNORECASE):
                    continue
                
                if SKIP_RE.match(s):
                    continue
                
                # Pular apenas CPF de cabeçalho (linha curta com CPF isolado)
                if CPF_HEADER_RE.match(s):
                    continue
                
                if not s:
                    if current_block and not collecting_values:
                        raw_blocks.append((current_block, current_page))
                        current_block = []
                    continue
                
                normalized = self._normalize_ocr_numbers(s)
                is_value_only = re.match(
                    rf"^{CURRENCY_RE}(?:\s+{CURRENCY_RE})*\s*$", normalized
                )
                
                if is_value_only:
                    # BUG FIX #82488: Verificar se este valor é embutido na descrição
                    # Ex: "R$ 367.000,00" quebrado pelo OCR em duas linhas:
                    #   "...E 30/09/2024 - R$"
                    #   "367.000,00"
                    # Neste caso, "367.000,00" faz parte da descrição, não é valor de coluna.
                    if not collecting_values and self._prev_line_ends_with_currency_prefix(
                        current_block, raw_blocks
                    ):
                        # Valor embutido na descrição - incorporar ao bloco atual
                        if current_block:
                            current_block.append(s)
                        elif raw_blocks:
                            raw_blocks[-1][0].append(s)
                        continue
                    
                    if current_block and not collecting_values:
                        raw_blocks.append((current_block, current_page))
                        current_block = []
                    collecting_values = True
                    vals = re.findall(CURRENCY_RE, normalized)
                    value_lines_info.append(len(vals))
                    flat_values.extend(vals)
                    continue
                
                if collecting_values:
                    continue
                
                if not current_block:
                    current_page = page_num
                current_block.append(s)
            
            if not in_section and past_header:
                break
        
        if current_block and not collecting_values:
            raw_blocks.append((current_block, current_page))
        
        if not raw_blocks or not flat_values:
            return []
        
        NEW_ITEM_KEYWORDS = [
            "SALDO", "BANCO", "CDC", "EMPRESTIMO", "EMPRÉSTIMO",
            "FINANCIAMENTO", "FINACIAMENTO", "CHEQUE", "CONSÓRCIO",
            "CONSORCIO", "CREDITO", "CRÉDITO",
        ]
        
        desc_items: list[tuple[str, int]] = []
        for block_lines, page in raw_blocks:
            first_line = block_lines[0]
            upper_first = first_line.upper()
            
            is_new_item = bool(
                re.match(r"^\d{2}\s+[A-Z]", first_line)
                and self._is_valid_debt_code(first_line[:2])
            )
            if not is_new_item:
                is_new_item = bool(
                    re.match(r"^\d+%", first_line)
                )
            if not is_new_item:
                first_word = upper_first.split()[0] if upper_first.split() else ""
                is_new_item = any(
                    first_word.startswith(kw) for kw in NEW_ITEM_KEYWORDS
                )
            
            block_text = " ".join(block_lines)
            
            if not is_new_item and desc_items:
                prev_desc, prev_page = desc_items[-1]
                desc_items[-1] = (prev_desc + " " + block_text, prev_page)
            else:
                desc_items.append((block_text, page))
        
        n_items = len(desc_items)
        n_vals = len(flat_values)
        
        if n_vals < n_items * 3:
            return []
        
        is_triplet = (value_lines_info
                      and all(v == 3 for v in value_lines_info))
        
        items = []
        
        if is_triplet:
            n_triplets = n_vals // 3
            limit = min(n_items, n_triplets)
            for i, (desc, page) in enumerate(desc_items[:limit]):
                base = i * 3
                v1 = flat_values[base]
                v2 = flat_values[base + 1]
                v3 = flat_values[base + 2]
                code = self._infer_debt_code(desc)
                clean_desc = self._clean_description(desc, code)
                pv1, pv2, pv3 = parse_currency(v1), parse_currency(v2), parse_currency(v3)
                item_id = generate_item_id(f"{clean_desc}_{pv1}_{pv2}_{pv3}")
                items.append({
                    "debt_code": code,
                    "debt_description": clean_desc,
                    "year_before_last_value": pv1,
                    "last_year_value": pv2,
                    "current_year_value": pv3,
                    "id": item_id,
                    "page": page,
                })
        else:
            for i, (desc, page) in enumerate(desc_items):
                v1 = flat_values[i]
                v2 = flat_values[n_items + i] if n_items + i < n_vals else "0,00"
                v3 = flat_values[2 * n_items + i] if 2 * n_items + i < n_vals else "0,00"
                code = self._infer_debt_code(desc)
                clean_desc = self._clean_description(desc, code)
                pv1, pv2, pv3 = parse_currency(v1), parse_currency(v2), parse_currency(v3)
                item_id = generate_item_id(f"{clean_desc}_{pv1}_{pv2}_{pv3}")
                items.append({
                    "debt_code": code,
                    "debt_description": clean_desc,
                    "year_before_last_value": pv1,
                    "last_year_value": pv2,
                    "current_year_value": pv3,
                    "id": item_id,
                    "page": page,
                })
        
        return items

    BANK_KEYWORDS = [
        "BANCO", "BRADESCO", "ITAU", "ITAÚ", "SICREDI", "SICOB",
        "CAIXA ECONOMICA", "CAIXA ECONÔMICA", "UNIBANCO", "SANTANDER",
        "NUBANK", "INTER ", "BB ", "CEF ", "BANRISUL", "BANCOOB",
        "COOPERATIVA DE CREDITO", "COOPERATIVA DE CRÉDITO",
    ]

    def _infer_debt_code(self, description: str) -> str:
        upper = description.upper()
        if re.match(r"^\d{2}\s+", description):
            code = description[:2]
            if code in self.VALID_DEBT_CODES:
                return code
        
        is_bank = any(b in upper for b in self.BANK_KEYWORDS)
        
        if is_bank:
            return "11"
        
        if "SALDO NEGATIVO" in upper or "SALDO DEVEDOR" in upper:
            return "11"
        if "CDC" in upper:
            return "11"
        if "CHEQUE ESPECIAL" in upper:
            return "11"
        
        if "CNPJ" in upper or "EMPRESA" in upper:
            return "13"
        
        if "CONSÓRCIO" in upper or "CONSORCIO" in upper:
            return "12"
        
        if "CPF" in upper:
            return "14"
        
        if "EMPRESTIMO" in upper or "EMPRÉSTIMO" in upper:
            return "14"
        if "FINANCIAMENTO" in upper or "FINACIAMENTO" in upper:
            return "14"
        if "CREDITO" in upper or "CRÉDITO" in upper:
            return "11"
        return "14"

    def _clean_description(self, desc: str, code: str) -> str:
        cleaned = re.sub(r"^\d{2}\s+", "", desc)
        cleaned = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _extract_debts_total(self, page_text: str) -> list[float]:
        page_text_normalized = self._normalize_ocr_numbers(page_text)
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        lines = page_text_normalized.split("\n")
        in_debts_section = False
        
        for line in lines:
            upper_line = line.upper().strip()
            
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_debts_section = True
                continue
            
            if in_debts_section and upper_line.startswith("TOTAL"):
                if "DEDUÇÃO" in upper_line or "DEDUCAO" in upper_line:
                    continue
                
                matches = re.findall(num_pattern, line)
                if len(matches) >= 2:
                    return [parse_currency(m) for m in matches]
        
        return []
