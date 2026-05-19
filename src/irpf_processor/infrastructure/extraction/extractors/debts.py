"""Extrator de dívidas e ônus reais."""

import json
import os
import re
from typing import Any, Optional

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

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

    LLM_PROMPT = """
================================================================
SECAO - DIVIDAS E ONUS REAIS
================================================================
REGRA: liste TODAS as dividas e onus reais da declaracao. Cada linha da
tabela = um objeto separado. Nao omita nenhum item.

{
    "items": [
        {
            "debt_code": "string (codigo da divida, 2 digitos: '11','12','13','14','15','16','17','18','19')",
            "debt_description": "string - copie o texto EXATO da coluna discriminacao (nome do credor + descricao)",
            "year_before_last_value": numero (saldo do ano anterior; converta '1.234,56' para 1234.56),
            "last_year_value": numero (saldo do exercicio anterior),
            "current_year_value": numero (saldo atual / valor pago/quitado no ano-base),
            "page": numero (pagina onde o item aparece no rodape 'Pagina X de Y' -> page=X)
        }
    ],
    "year_before_last_total_value": numero (linha TOTAL ano-2),
    "last_year_total_value": numero (linha TOTAL ano-1),
    "current_year_total_value": numero (linha TOTAL atual)
}

REGRAS IMPORTANTES:
- Extraia APENAS itens da secao "DIVIDAS E ONUS REAIS"
- NAO inclua itens da secao "DIVIDAS VINCULADAS A ATIVIDADE RURAL"
- O campo "debt_code" deve ser STRING de 2 digitos (apenas valores 11-19)
- Valores monetarios devem ser NUMEROS (ex: 87624.85, nao "87.624,85")
- Se a discriminacao de um item ocupa multiplas linhas, junte em uma unica string
- Se um item nao tem valor para alguma coluna, retorne 0
"""

    @property
    def section_name(self) -> str:
        return "debts_and_encumbrances"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        items = []
        seen_ids = set()
        pdf_totals = []  # Totais do PDF
        
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        in_section = False
        section_ended = False
        
        for page_num, page_text in sorted_pages:
            upper_text = page_text.upper()
            
            # Verificar se a página contém o marcador de dívidas
            has_debts_marker = any(marker in upper_text for marker in self.SECTION_MARKERS)
            
            # CORREÇÃO: Não pular página inteira se ela também contém nossa seção
            # Isso acontece quando todo o texto OCR está em uma única página
            if has_debts_marker:
                in_section = True
            
            if not in_section:
                continue
            
            if section_ended:
                break
            
            # Extrair itens da página ANTES de verificar fim
            # (a página pode ter itens E o marcador de fim depois deles)
            # already_in_section=True apenas se a seção começou em OUTRA página
            # Se esta página contém o marcador, deixar _extract_from_page descobrir naturalmente
            page_items = self._extract_from_page(page_text, page_num, seen_ids, already_in_section=(in_section and not has_debts_marker))
            items.extend(page_items)
            
            if not pdf_totals:
                page_totals = self._extract_debts_total(page_text)
                if page_totals:
                    pdf_totals = page_totals
            
            # Verificar se a seção terminou APÓS extrair
            if self._is_definitive_section_end(page_text):
                section_ended = True
        
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
        
        # Coletar items sem valor (split-column do Tesseract)
        headeronly_items: list[dict] = []
        # Coletar linhas de valor órfãs
        orphan_value_lines: list[list[str]] = []
        
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
            if not in_section:
                i += 1
                continue
            
            # Normalizar linha para lidar com OCR (espaços antes da vírgula)
            normalized_line = self._normalize_ocr_numbers(line)
            
            # Fix código duplicado: "14 14 EMPRESTIMO..." -> "14 EMPRESTIMO..."
            normalized_line = re.sub(r"^(\d{2})\s+\1\s+", r"\1 ", normalized_line)
            
            # Tentar detectar item de dívida - formato padrão
            debt_match = re.match(
                r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                normalized_line
            )
            
            if debt_match:
                code = debt_match.group(1)
                if self._is_valid_debt_code(code):
                    item = self._parse_debt(debt_match, lines, i, page_num, seen_ids)
                    if item:
                        next_i = item.pop("_next_index", i + 1)
                        if item["id"] not in seen_ids:
                            seen_ids.add(item["id"])
                            items.append(item)
                        i = next_i
                        continue
            
            # Tentar formato alternativo OCR - código + descrição + valores em linhas separadas
            if re.match(r"^(\d{2})\s+(.+)", normalized_line):
                item = self._try_parse_multiline_debt(lines, i, page_num, seen_ids)
                if item:
                    next_i = item.pop("_next_index", i + 1)
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        items.append(item)
                    i = next_i
                    continue
                
                # Se não achou valores, guardar como header-only
                # (Tesseract split-column: descrição e valores em blocos separados)
                code_m = re.match(r"^(\d{2})\s+(.+)", normalized_line)
                if code_m and self._is_valid_debt_code(code_m.group(1)):
                    desc_start = code_m.group(2).strip()
                    desc_parts = [desc_start]
                    j = i + 1
                    while j < len(lines):
                        nl = lines[j].strip()
                        upper_nl = nl.upper()
                        if not nl:
                            j += 1
                            continue
                        # Parar se encontrar novo item, TOTAL, fim de seção, ou linha de valores
                        # Normalizar código duplicado OCR (ex: "14 14" -> "14")
                        normalized_nl = re.sub(r"^(\d{2})\s+\1\s+", r"\1 ", nl)
                        if re.match(r"^\d{2}\s+[A-Z]", normalized_nl):
                            break
                        if "TOTAL" in upper_nl:
                            break
                        if any(m in upper_nl for m in self.SECTION_END_MARKERS):
                            break
                        if re.match(r"^[\d.,]+\s+[\d.,]+\s+[\d.,]+\s*$", self._normalize_ocr_numbers(nl)):
                            break
                        desc_parts.append(nl)
                        j += 1
                    
                    full_desc = " ".join(desc_parts)
                    full_desc = re.sub(r"\s*P[aá]gina\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
                    full_desc = re.sub(r"\s+", " ", full_desc).strip()
                    
                    headeronly_items.append({
                        "code": code_m.group(1),
                        "desc": full_desc,
                        "page": page_num,
                    })
                    i = j
                    continue
            
            # Detectar linhas órfãs de valores (3 valores numéricos soltos)
            val_line = self._normalize_ocr_numbers(line)
            val_match = re.match(r"^([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", val_line)
            if val_match and in_section:
                orphan_value_lines.append([val_match.group(1), val_match.group(2), val_match.group(3)])
                i += 1
                continue
            
            # Detectar valores individuais órfãos (Tesseract extremo: 1 valor por linha)
            single_val = re.match(r"^(\d{1,3}(?:\.\d{3})*,\d{2})\s*$", val_line)
            if single_val and in_section:
                orphan_value_lines.append(single_val.group(1))
                i += 1
                continue
            
            # Coletar descrições sem código (Tesseract cortou o código)
            # Se estamos na seção e a linha parece descrição (começa com maiúscula)
            # e NÃO é um marcador/cabeçalho
            if in_section and line and not line[0].isdigit():
                stripped_upper = line.strip().upper()
                skip_patterns = [
                    "CÓDIGO", "CODIGO", "DISCRIMINAÇÃO", "DISCRIMINACAO",
                    "SITUAÇÃO", "SITUACAO", "EXERCÍCIO", "EXERCICIO",
                    "IMPOSTO", "VALORES", "DECLARAÇÃO", "DECLARACAO",
                    "NOME:", "CPF:", "PÁGINA", "PAGINA",
                ]
                if not any(p in stripped_upper for p in skip_patterns):
                    # Pode ser descrição sem código — apenas guardar para
                    # futuro matching se não casar com nenhum header
                    pass
            
            i += 1
        
        # ------------------------------------------------------------------
        # Pós-processo: reassociar items header-only com valores órfãos
        # (padrão Tesseract: descrições num bloco, valores em outro)
        # ------------------------------------------------------------------
        if headeronly_items and orphan_value_lines:
            # Agrupar valores individuais em tripletos se necessário
            grouped_values = self._group_orphan_values(orphan_value_lines)
            reassembled = self._reassemble_split_columns(
                headeronly_items, grouped_values, seen_ids
            )
            items.extend(reassembled)
        
        return items
    
    @staticmethod
    def _group_orphan_values(
        raw_values: list,
    ) -> list[list[str]]:
        """Agrupa valores órfãos em tripletos.
        
        Se os valores já são listas de 3, retorna como está.
        Se são strings individuais, agrupa de 3 em 3 na ordem.
        """
        # Separar já-agrupados de individuais
        grouped = []
        singles = []
        for v in raw_values:
            if isinstance(v, list):
                grouped.append(v)
            else:
                singles.append(v)
        
        # Se só temos agrupados, retornar
        if not singles:
            return grouped
        
        # Se só temos individuais, agrupar de 3 em 3
        if not grouped:
            result = []
            for i in range(0, len(singles) - 2, 3):
                result.append([singles[i], singles[i+1], singles[i+2]])
            return result
        
        # Mistura: retornar os agrupados + agrupar restantes
        for i in range(0, len(singles) - 2, 3):
            grouped.append([singles[i], singles[i+1], singles[i+2]])
        return grouped
    
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
            # Normalizar código duplicado OCR (ex: "14 14" -> "14")
            next_line_dedup = re.sub(r"^(\d{2})\s+\1\s+", r"\1 ", next_line)
            if re.match(r"^(\d{2})\s+[A-Z]", next_line_dedup) and self._is_valid_debt_code(re.match(r"^(\d{2})", next_line_dedup).group(1)):
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
        v0 = parse_currency(values[0])
        v1 = parse_currency(values[1])
        v2 = parse_currency(values[2])
        id_content = f"{normalized_desc}|{v0}|{v1}|{v2}|{page_num}"
        item_id = generate_item_id(id_content)
        item_id = self._resolve_duplicate_id(item_id, seen_ids)
        
        return {
            "debt_code": code,
            "debt_description": full_desc,
            "year_before_last_value": v0,
            "last_year_value": v1,
            "current_year_value": v2,
            "id": item_id,
            "page": page_num,
            "_next_index": j
        }

    def _reassemble_split_columns(
        self,
        headers: list[dict],
        value_lines: list[list[str]],
        seen_ids: set,
    ) -> list[dict]:
        """Reassocia items sem valor com linhas de valor órfãs.

        Tesseract frequentemente separa o layout 2-colunas do PDF em
        dois blocos verticais:
          Bloco 1 (esquerda): códigos + descrições
          Bloco 2 (direita): 3 colunas de valores

        Esta função emparelha cada header com sua respectiva linha de
        valores, na ordem em que aparecem.
        """
        items = []
        paired = min(len(headers), len(value_lines))

        if paired == 0:
            return items

        logger.info(
            "Reassembling split-column items",
            headers=len(headers),
            value_lines=len(value_lines),
            paired=paired,
        )

        for idx in range(paired):
            h = headers[idx]
            vals = value_lines[idx]
            v0 = parse_currency(vals[0])
            v1 = parse_currency(vals[1])
            v2 = parse_currency(vals[2])

            normalized_desc = re.sub(r"(\S)\(", r"\1 (", h["desc"])
            normalized_desc = re.sub(r"\(\s+", "(", normalized_desc)
            id_content = f"{normalized_desc}|{v0}|{v1}|{v2}|{h['page']}"
            item_id = generate_item_id(id_content)
            item_id = self._resolve_duplicate_id(item_id, seen_ids)
            seen_ids.add(item_id)

            items.append({
                "debt_code": h["code"],
                "debt_description": h["desc"],
                "year_before_last_value": v0,
                "last_year_value": v1,
                "current_year_value": v2,
                "id": item_id,
                "page": h["page"],
            })

        return items
    
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
    
    def _line_starts_new_debt_item(self, line: str) -> bool:
        """Detecta se a linha inicia um novo item de dívida."""
        normalized = self._normalize_ocr_numbers(line)
        if re.match(r"^(\d{2})\s+(.+?)\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)\s*$", normalized):
            code = normalized[:2]
            if self._is_valid_debt_code(code):
                return True
        code_match = re.match(r"^(\d{2})\s+[A-Z]", normalized)
        if code_match and self._is_valid_debt_code(code_match.group(1)):
            return True
        return False

    def _is_valid_debt_code(self, code: str) -> bool:
        return code in self.VALID_DEBT_CODES

    @staticmethod
    def _resolve_duplicate_id(item_id: str, seen_ids: set) -> str:
        """Resolve ID collisions for legitimate duplicate entries.

        When two distinct debt entries produce the same hash (same description,
        values, and page), append a counter suffix to make the ID unique
        while remaining deterministic.

        Bug #16728: Multiple loans to the same entity with identical amounts
        are legitimate and must all be extracted.
        """
        if item_id not in seen_ids:
            return item_id
        counter = 1
        while True:
            new_id = generate_item_id(f"{item_id}|dup_{counter}")
            if new_id not in seen_ids:
                return new_id
            counter += 1
    
    def _parse_debt(
        self, 
        match: re.Match, 
        lines: list[str], 
        idx: int,
        page_num: int,
        seen_ids: set | None = None
    ) -> dict:
        code = match.group(1)
        desc_start = match.group(2).strip()
        before_val = parse_currency(match.group(3))
        current_val = parse_currency(match.group(4))
        paid_val = parse_currency(match.group(5))
        
        desc_parts = [desc_start]
        j = idx + 1
        
        while j < len(lines):
            next_line = self._normalize_ocr_numbers(lines[j].strip())
            upper_next = next_line.upper()
            
            if "TOTAL" in upper_next and not re.match(r"^\d{2}\s+", next_line):
                break
            
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break
            
            if self._line_starts_new_debt_item(next_line):
                break
            
            if next_line and not re.match(r"^[\d.,]+\s+[\d.,]+\s+[\d.,]+$", next_line):
                if not upper_next.startswith("CÓDIGO") and not upper_next.startswith("CODIGO"):
                    if not upper_next.startswith("DISCRIMINAÇÃO") and not upper_next.startswith("DISCRIMINACAO"):
                        desc_parts.append(next_line)
            
            j += 1
        
        full_desc = " ".join(desc_parts)
        full_desc = re.sub(r"\s*Página\s+\d+\s+de\s*\d+\s*$", "", full_desc, flags=re.IGNORECASE)
        full_desc = re.sub(r"\s+", " ", full_desc).strip()
        
        normalized_desc = re.sub(r"(\S)\(", r"\1 (", full_desc)
        normalized_desc = re.sub(r"\(\s+", "(", normalized_desc)
        id_content = f"{normalized_desc}|{before_val}|{current_val}|{paid_val}|{page_num}"
        item_id = generate_item_id(id_content)
        if seen_ids is not None:
            item_id = self._resolve_duplicate_id(item_id, seen_ids)
        
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
    
    def _extract_debts_total(self, page_text: str) -> list[float]:
        # Normalizar números OCR
        page_text_normalized = self._normalize_ocr_numbers(page_text)
        num_pattern = r'([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})'
        lines = page_text_normalized.split("\n")
        in_debts_section = False
        
        for line in lines:
            upper_line = line.upper().strip()
            
            # Verificar todos os marcadores
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

    # ------------------------------------------------------------------
    # LLM extraction (#19158) — mirrors the rural_properties.py pattern
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_currency(value: Any) -> float:
        """Parse LLM currency output (string BR/US or number)."""
        if value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip()
        if not s:
            return 0.0
        try:
            return float(parse_currency(s))
        except Exception:
            try:
                return float(s.replace(",", "."))
            except Exception:
                return 0.0

    def _normalize_llm_item(self, item: dict) -> Optional[dict]:
        """Normalize an LLM-emitted debt item to the regex extractor's shape."""
        if not isinstance(item, dict):
            return None

        raw_code = item.get("debt_code", "")
        debt_code = str(raw_code).strip().zfill(2) if raw_code != "" else ""
        if debt_code not in self.VALID_DEBT_CODES:
            return None

        description = re.sub(r"\s+", " ", str(item.get("debt_description", "") or "").strip())
        if not description:
            return None

        v0 = self._parse_llm_currency(item.get("year_before_last_value", 0))
        v1 = self._parse_llm_currency(item.get("last_year_value", 0))
        v2 = self._parse_llm_currency(item.get("current_year_value", 0))

        page = item.get("page", 0)
        if isinstance(page, str):
            page = int(page) if page.isdigit() else 0

        item_id = generate_item_id(f"{description}|{v0}|{v1}|{v2}|{page}")

        return {
            "debt_code": debt_code,
            "debt_description": description,
            "year_before_last_value": v0,
            "last_year_value": v1,
            "current_year_value": v2,
            "id": item_id,
            "page": page,
        }

    async def extract_with_llm(
        self,
        context: ExtractionContext,
        custom_prompt: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Extract debts_and_encumbrances section using LLM.

        Mirrors RuralPropertiesExtractor.extract_with_llm():
        1. Calls get_llm_extraction_data() from the base class.
        2. Saves raw chunks under ``tmp/<doc_id>/chunks/debts_and_encumbrances/``.
        3. Normalizes each item via ``_normalize_llm_item`` and dedups by id.
        4. Returns the same dict shape as ``extract()`` with ``extraction_method='llm'``.
        """
        try:
            extraction_result = await self.get_llm_extraction_data(context, custom_prompt)

            if not extraction_result or not isinstance(extraction_result, list):
                logger.warning(
                    "llm_extraction_no_data",
                    section_name=self.section_name,
                    reason="no_chunks_returned",
                    document_id=context.document_id,
                )
                context.add_warning(
                    "LLM extraction returned no chunks for debts_and_encumbrances"
                )
                return None

            debug_base = os.path.join(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                ),
                "tmp",
                context.document_id or "unknown",
            )
            debug_chunks_dir = os.path.join(debug_base, "chunks", "debts_and_encumbrances")
            debug_result_dir = os.path.join(debug_base, "result", "debts_and_encumbrances")
            os.makedirs(debug_chunks_dir, exist_ok=True)
            os.makedirs(debug_result_dir, exist_ok=True)

            for idx, chunk in enumerate(extraction_result):
                chunk_path = os.path.join(debug_chunks_dir, f"chunk_{idx}.json")
                try:
                    with open(chunk_path, "w", encoding="utf-8") as f:
                        f.write(json.dumps(chunk, indent=2, ensure_ascii=False))
                except Exception:
                    pass

            logger.info(
                "llm_debts_extraction_start",
                section_name=self.section_name,
                document_id=context.document_id,
                chunk_count=len(extraction_result),
            )

            items: list[dict] = []
            seen_ids: set[str] = set()
            pdf_before = pdf_last = pdf_paid = 0.0

            for chunk_idx, chunk in enumerate(extraction_result):
                if not isinstance(chunk, dict):
                    continue

                if chunk.get("year_before_last_total_value") is not None and pdf_before == 0.0:
                    pdf_before = self._parse_llm_currency(chunk["year_before_last_total_value"])
                if chunk.get("last_year_total_value") is not None and pdf_last == 0.0:
                    pdf_last = self._parse_llm_currency(chunk["last_year_total_value"])
                if chunk.get("current_year_total_value") is not None and pdf_paid == 0.0:
                    pdf_paid = self._parse_llm_currency(chunk["current_year_total_value"])

                raw_items = chunk.get("items") or []
                if not isinstance(raw_items, list):
                    continue

                for raw in raw_items:
                    normalized = self._normalize_llm_item(raw)
                    if not normalized:
                        continue
                    if normalized["id"] in seen_ids:
                        continue
                    seen_ids.add(normalized["id"])
                    items.append(normalized)

                logger.info(
                    "llm_debts_chunk_processed",
                    chunk_index=chunk_idx,
                    chunk_item_count=len(raw_items),
                )

            if not items:
                logger.warning(
                    "llm_debts_extraction_empty_result",
                    document_id=context.document_id,
                )
                context.add_warning(
                    "LLM extraction returned no items for debts_and_encumbrances"
                )
                return None

            year_before_last_total = sum_currency_values(
                [i["year_before_last_value"] for i in items], as_int=False
            )
            last_year_total = sum_currency_values(
                [i["last_year_value"] for i in items], as_int=False
            )
            paid_total = sum_currency_values(
                [i.get("current_year_value", 0) for i in items], as_int=False
            )

            result = {
                "section_name": "Dívidas e Ônus Reais",
                "items": items,
                "amount_of_codes_equal_to_amount_of_values": True,
                "year_before_last_total_value": year_before_last_total,
                "last_year_total_value": last_year_total,
                "current_year_total_value": paid_total,
                "total_values": {
                    "year_before_last_value": create_validated_total(
                        year_before_last_total, pdf_before or None
                    ),
                    "last_year_value": create_validated_total(
                        last_year_total, pdf_last or None
                    ),
                    "current_year_value": create_validated_total(
                        paid_total, pdf_paid or None
                    ),
                },
                "pages_with_problems": [],
                "extraction_method": "llm",
            }

            try:
                with open(
                    os.path.join(debug_result_dir, "merged_result.json"),
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(json.dumps(result, indent=2, ensure_ascii=False, default=str))
            except Exception:
                pass

            logger.info(
                "llm_debts_extraction_complete",
                document_id=context.document_id,
                items_count=len(items),
            )

            return result

        except Exception as exc:
            logger.exception(
                "llm_debts_extraction_failed",
                document_id=context.document_id,
                error_type=type(exc).__name__,
            )
            context.add_warning(
                f"LLM extraction failed for debts_and_encumbrances: {type(exc).__name__}: {exc}"
            )
            return None
