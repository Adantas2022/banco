"""Extrator de imoveis rurais explorados."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id

# Pattern de área: aceita BR (800,0 / 1.200,0) e US (800.0 / 1200.5)
_AREA_PATTERN = r"\d[\d.]*[.,]\d+"
_AREA_CIB_TAIL_RE = re.compile(rf"({_AREA_PATTERN})\s+([\d.-]+)$")
_AREA_ONLY_RE = re.compile(rf"^{_AREA_PATTERN}$")


class RuralPropertiesExtractor(ISectionExtractor):
    """Extrai dados de imoveis rurais explorados."""

    # Marcadores incluindo variações OCR comuns (ex: "Ç" pode virar "G" no OCR)
    # BUG #81760 fix: Adicionar marcadores com sufixo "- BRASIL" (formato Gilberto Rech)
    SECTION_MARKERS = [
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - BRASIL",
        "DADOS E IDENTIFICACAO DO IMOVEL EXPLORADO - BRASIL",
        "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO",
        "DADOS E IDENTIFICACAO DO IMOVEL EXPLORADO",
        "DADOS E IDENTIFICAGAO DO IMOVEL EXPLORADO",  # OCR: Ç -> G
        "PROPRIEDADES RURAIS EXPLORADAS",
        "IMÓVEIS RURAIS EXPLORADOS",
        "IMOVEIS RURAIS EXPLORADOS",
    ]
    # IMPORTANTE: Apenas marcadores de seções que vêm DEPOIS de "Dados do Imóvel Explorado"
    # A ordem no IRPF é: Imóvel Explorado > Movimentação Rebanho > Bens Atividade Rural > Receitas/Despesas
    SECTION_END_MARKERS = [
        "RECEITAS DA ATIVIDADE RURAL",
        "DESPESAS DA ATIVIDADE RURAL",
        "RESULTADO DA ATIVIDADE RURAL",
        "RECEITAS E DESPESAS",
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "MOVIMENTAGAO DO REBANHO",  # OCR: Ç -> G
        "BENS DA ATIVIDADE RURAL",
        "APURAÇÃO DO RESULTADO",
        "APURACAO DO RESULTADO",
        "APURAGAO DO RESULTADO",  # OCR: Ç -> G
    ]

    @property
    def section_name(self) -> str:
        return "exploited_rural_properties_in_brazil"

    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)

    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        if not self.can_extract(context):
            return None

        items = []
        seen_ids = set()

        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])

        in_section = False
        section_ended = False
        last_item_for_participants: dict | None = (
            None  # Item que pode receber participantes da próxima página
        )

        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()

            # Entrar na seção
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                in_section = True

            if not in_section:
                continue

            if section_ended:
                break

            # BUG FIX #82637: Verificar se há participantes no início da página
            # que pertencem ao último item da página anterior (quebra de página)
            if last_item_for_participants:
                additional_participants = self._extract_participants_from_page_start(page_text)
                if additional_participants:
                    existing = last_item_for_participants.get("participants")
                    if existing and existing.get("items"):
                        existing["items"].extend(additional_participants)
                    else:
                        last_item_for_participants["participants"] = {
                            "items": additional_participants
                        }
                last_item_for_participants = None

            # Extrair itens da página
            page_items = self._extract_from_page(page_text, page_num, seen_ids)
            items.extend(page_items)

            # Verificar se o último item pode ter participantes na próxima página
            if page_items:
                last_item_for_participants = page_items[-1]

            # Verificar se terminou APÓS extrair
            if self._is_definitive_section_end(page_text):
                section_ended = True

        if not items:
            return {
                "section_name": "Dados e Identificação do Imóvel Explorado - Brasil",
                "items": None,
                "total_properties": 0,
                "total_area": 0.0,
            }

        total_area = sum(item.get("area", 0) for item in items)

        return {
            "section_name": "Dados e Identificação do Imóvel Explorado - Brasil",
            "items": items,
            "total_properties": len(items),
            "total_area": round(total_area, 2),
        }

    def _is_definitive_section_end(self, page_text: str) -> bool:
        """Verifica se a página marca o fim definitivo da seção."""
        lines = page_text.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip().upper()
            if not stripped:
                continue

            for marker in self.SECTION_END_MARKERS:
                if stripped == marker or stripped.startswith(marker):
                    # Confirmar que é nova seção
                    next_lines = " ".join(lines[i + 1 : i + 5]).upper()
                    if "CÓDIGO" in next_lines or "DISCRIMINAÇÃO" in next_lines:
                        return True
                    if re.search(r"^\d{2}\s+", next_lines):
                        return True

        return False

    def _extract_from_page(self, page_text: str, page_num: int, seen_ids: set) -> list[dict]:
        items = []
        lines = page_text.split("\n")

        in_section = False
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            upper_line = line.upper()

            # Detectar início da seção - verificar variações OCR
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_section = True
                i += 1
                continue

            # Skip cabeçalhos - incluindo variações OCR sem acentos
            # BUG #81760 fix: Só considerar header se a linha COMEÇA com keyword
            # Não ignorar linhas que contêm keywords no meio (ex: "IMOVEL COM AREA DE...")
            header_keywords = [
                "CÓDIGO",
                "CODIGO",
                "ATIVIDADE",
                "PARTICIPAÇÃO",
                "PARTICIPACAO",
                "CONDIÇÃO",
                "CONDICAO",
                "NOME E",
                "(HA)",
                "EXPLORAÇÃO",
                "EXPLORACAO",
                "NIRF",
            ]
            # Verificar se linha É um cabeçalho (começa com keyword ou é linha de header)
            is_header = False
            stripped_upper = upper_line.strip()
            for h in header_keywords:
                if stripped_upper.startswith(h) or stripped_upper == h:
                    is_header = True
                    break
            # Linha com "ÁREA" e "CIB" juntos é header
            if "ÁREA" in upper_line and "CIB" in upper_line:
                is_header = True
            if "AREA" in upper_line and "CIB" in upper_line:
                is_header = True

            if is_header:
                in_section = True
                i += 1
                continue

            if "PARTICIPANTE" in upper_line:
                i += 1
                continue

            # Skip linhas "Estrangeiro: Nao" e similares
            if upper_line.startswith("ESTRANGE"):
                i += 1
                continue

            # Detectar fim da seção
            if in_section and any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                break

            if not in_section:
                i += 1
                continue

            # Normalizar linha para OCR
            normalized_line = re.sub(r"(\d)\s+,", r"\1,", line)

            # Tentar parsear item inline
            item = self._try_parse_inline_property(normalized_line, lines, i, page_num)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                items.append(item)
                skip_lines = self._count_property_lines(lines, i)
                i += max(1, skip_lines)
                continue

            # Tentar parsear item multiline (código em linha separada)
            if re.match(r"^\d{1,2}$", normalized_line):
                item = self._try_parse_multiline_property(lines, i, page_num)
                if item and item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    items.append(item)
                    skip_lines = self._count_multiline_property_lines(lines, i)
                    i += max(1, skip_lines)
                    continue

            i += 1

        return items

    def _try_parse_inline_property(
        self, line: str, lines: list[str], idx: int, page_num: int
    ) -> Optional[dict]:
        """Tenta parsear propriedade em formato inline.

        BUG #81760 fix: Melhorar captura de nomes/localizações multilinhas.
        O nome da propriedade pode se estender por múltiplas linhas antes de
        área e CIB aparecerem.
        """
        # Normalizar linha para OCR (espaços antes da vírgula)
        line = re.sub(r"(\d)\s+,", r"\1,", line.strip())
        line = self._normalize_ocr_code_line(line)

        # Formato: codigo participacao condicao nome area cib
        # Ex: "10 15,00 3 FAZENDA LAMBARI, CAMPOS DE JULIO/MT. 1.200,0 4.695.449-0"
        pattern = re.match(
            r"^(\d{1,2})\s+"  # código: 10, 11
            r"([\d.,]+)\s+"  # participação: 15,00 ou 100,00
            r"(\d)\s+"  # condição: 1, 3, 4
            r"(.+?)\s+"  # nome e localização
            rf"({_AREA_PATTERN})\s+"  # área: 1.200,0 / 800.0
            r"([\d.-]+)$",  # CIB: 4.695.449-0
            line,
        )

        if pattern:
            return self._parse_from_match(pattern, lines, idx, page_num)

        # Formato parcial - nome/area/cib pode estar em linhas seguintes
        partial_pattern = re.match(
            r"^(\d{1,2})\s+"
            r"([\d.,]+)\s+"
            r"(\d)\s+"
            r"(.+)$",
            line,
        )

        if partial_pattern:
            code = int(partial_pattern.group(1))
            participation = parse_currency(partial_pattern.group(2))
            exploration = int(partial_pattern.group(3))
            remaining = partial_pattern.group(4).strip()

            area_cib_match = _AREA_CIB_TAIL_RE.search(remaining)

            if area_cib_match:
                name_location = remaining[: area_cib_match.start()].strip()
                area = parse_currency(self._normalize_area_value(area_cib_match.group(1)))
                cib = area_cib_match.group(2)

                # Verificar se próxima linha é continuação do nome
                # Ex: "MAQUINAS DE CULTURA DE SOLO, MATO" + "GROSSO"
                if idx + 1 < len(lines):
                    next_line = lines[idx + 1].strip()
                    if (
                        next_line
                        and not re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", next_line)
                        and not re.match(r"^\d{1,2}$", next_line)
                        and not re.match(r"^[\d.,]+\s", next_line)
                        and "PARTICIPANTE" not in next_line.upper()
                        and not any(
                            marker in next_line.upper() for marker in self.SECTION_END_MARKERS
                        )
                        and re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", next_line)
                        and len(next_line) < 40
                    ):
                        name_location = f"{name_location} {next_line}"
            else:
                # BUG #81760 fix: Buscar agressivamente nas linhas seguintes
                # Nomes de propriedades rurais frequentemente são muito longos e
                # se estendem por 2-4 linhas antes de área/CIB aparecerem
                name_parts = [remaining]
                area = 0.0
                cib = ""
                found_area_cib = False

                # Aumentar range de busca para capturar nomes longos (até 12 linhas)
                for j in range(idx + 1, min(idx + 12, len(lines))):
                    next_line = re.sub(r"(\d)\s+,", r"\1,", lines[j].strip())
                    upper_next = next_line.upper()

                    # Parar em participantes (mas já devemos ter área/CIB)
                    if "PARTICIPANTE" in upper_next:
                        break

                    # Parar em novo item (formato código participação condição)
                    norm_next = self._normalize_ocr_code_line(next_line)
                    if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", norm_next):
                        break
                    # Parar se encontrar apenas código (início de novo item multiline)
                    if re.match(r"^\d{1,2}$", next_line):
                        break

                    # Parar em fim de seção
                    if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                        break

                    # Skip cabeçalhos repetidos
                    header_keywords = [
                        "CÓDIGO",
                        "CODIGO",
                        "ATIVIDADE",
                        "PARTICIPAÇÃO",
                        "ÁREA",
                        "AREA",
                        "CIB",
                        "(HA)",
                        "EXPLORAÇÃO",
                    ]
                    if any(h in upper_next for h in header_keywords):
                        continue

                    # Tentar extrair area e cib da linha atual
                    # Pattern 1: "nome parcial 1.200,0 4.695.449-0"
                    area_cib_end = _AREA_CIB_TAIL_RE.search(next_line)
                    if area_cib_end:
                        name_part = next_line[: area_cib_end.start()].strip()
                        if name_part:
                            name_parts.append(name_part)
                        area = parse_currency(self._normalize_area_value(area_cib_end.group(1)))
                        cib = area_cib_end.group(2)
                        found_area_cib = True
                        break

                    if _AREA_ONLY_RE.match(next_line):
                        area = parse_currency(self._normalize_area_value(next_line))
                        if j + 1 < len(lines):
                            cib_line = lines[j + 1].strip()
                            if re.match(r"^[\d.-]+$", cib_line) and "-" in cib_line:
                                cib = cib_line
                        found_area_cib = True
                        break

                    # Pattern 3: CIB sozinho (sem área - improvável mas possível)
                    if re.match(r"^[\d.-]+$", next_line) and "-" in next_line:
                        cib = next_line
                        break

                    # Se linha não vazia e não é numérica pura, é parte do nome
                    if next_line and not re.match(r"^[\d.,\s-]+$", next_line):
                        name_parts.append(next_line)

                name_location = " ".join(name_parts)

            # CIB é opcional - alguns imóveis não têm
            name_location = self._normalize_name(name_location)
            participants = self._extract_participants(lines, idx)
            item_id = generate_item_id(f"{code}{name_location}{cib or area}")

            return {
                "code": code,
                "participation": participation,
                "exploration_condition": exploration,
                "name_and_location": name_location,
                "area": area,
                "cib": cib,
                "participants": {"items": participants} if participants else None,
                "id": item_id,
                "page": page_num,
            }

        return None

    def _parse_from_match(self, match: re.Match, lines: list[str], idx: int, page_num: int) -> dict:
        code = int(match.group(1))
        participation = parse_currency(match.group(2))
        exploration = int(match.group(3))
        name_location = match.group(4).strip()
        area = parse_currency(self._normalize_area_value(match.group(5)))
        cib = match.group(6)

        # Verificar se próxima linha é continuação do nome
        # Ex: "MAQUINAS DE CULTURA DE SOLO, MATO" + "GROSSO"
        if idx + 1 < len(lines):
            next_line = lines[idx + 1].strip()
            if (
                next_line
                and not re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", next_line)
                and not re.match(r"^\d{1,2}$", next_line)
                and not re.match(r"^[\d.,]+\s", next_line)
                and "PARTICIPANTE" not in next_line.upper()
                and not any(marker in next_line.upper() for marker in self.SECTION_END_MARKERS)
                and re.match(r"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]", next_line)
                and len(next_line) < 40
            ):
                name_location = f"{name_location} {next_line}"

        name_location = self._normalize_name(name_location)
        participants = self._extract_participants(lines, idx)
        item_id = generate_item_id(f"{code}{name_location}{cib}")

        return {
            "code": code,
            "participation": participation,
            "exploration_condition": exploration,
            "name_and_location": name_location,
            "area": area,
            "cib": cib,
            "participants": {"items": participants} if participants else None,
            "id": item_id,
            "page": page_num,
        }

    def _try_parse_multiline_property(
        self, lines: list[str], idx: int, page_num: int
    ) -> Optional[dict]:
        """Tenta parsear propriedade em formato multiline.

        BUG #81760 fix: Melhorar captura de nomes multilinhas no formato
        onde código, participação, condição vêm em linhas separadas.
        """
        line = lines[idx].strip()

        if not re.match(r"^\d{1,2}$", line):
            return None

        code = int(line)
        j = idx + 1

        if j >= len(lines):
            return None

        participation = parse_currency(lines[j].strip())
        if participation == 0.0 and lines[j].strip() != "0,00":
            return None
        j += 1

        if j >= len(lines):
            return None

        # Condição de exploração
        exploration_str = lines[j].strip()
        if not re.match(r"^\d$", exploration_str):
            return None
        exploration = int(exploration_str)
        j += 1

        # Nome, área e CIB - BUG #81760 fix: buscar mais agressivamente
        name_parts = []
        area = 0.0
        cib = ""

        # Aumentar limite para capturar nomes longos
        max_lines = min(j + 15, len(lines))

        while j < max_lines:
            next_line = lines[j].strip()
            upper_next = next_line.upper()

            if "PARTICIPANTE" in upper_next:
                break

            # Novo item começando
            if re.match(r"^\d{1,2}$", next_line):
                break

            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break

            # Skip cabeçalhos repetidos
            header_keywords = [
                "CÓDIGO",
                "CODIGO",
                "ATIVIDADE",
                "PARTICIPAÇÃO",
                "ÁREA",
                "AREA",
                "CIB",
                "(HA)",
                "EXPLORAÇÃO",
            ]
            if any(h in upper_next for h in header_keywords):
                j += 1
                continue

            # Linha com área e CIB juntos: "nome 1.200,0 4.695.449-0"
            area_cib_match = _AREA_CIB_TAIL_RE.search(next_line)
            if area_cib_match:
                name_part = next_line[: area_cib_match.start()].strip()
                if name_part:
                    name_parts.append(name_part)
                area = parse_currency(self._normalize_area_value(area_cib_match.group(1)))
                cib = area_cib_match.group(2)
                j += 1
                break

            if _AREA_ONLY_RE.match(next_line):
                area = parse_currency(self._normalize_area_value(next_line))
                j += 1
                if j < len(lines):
                    cib_line = lines[j].strip()
                    if re.match(r"^[\d.-]+$", cib_line) and "-" in cib_line:
                        cib = cib_line
                        j += 1
                break

            # CIB sozinho
            if re.match(r"^[\d.-]+$", next_line) and "-" in next_line:
                cib = next_line
                j += 1
                break

            # Nome - se não é numérico puro e não é cabeçalho
            if next_line and not re.match(r"^[\d.,\s-]+$", next_line):
                name_parts.append(next_line)
            j += 1

        # CIB é opcional - alguns imóveis não têm
        name_location = self._normalize_name(" ".join(name_parts))
        participants = self._extract_participants(lines, j - 1)
        item_id = generate_item_id(f"{code}{name_location}{cib or area}")

        return {
            "code": code,
            "participation": participation,
            "exploration_condition": exploration,
            "name_and_location": name_location,
            "area": area,
            "cib": cib,
            "participants": {"items": participants} if participants else None,
            "id": item_id,
            "page": page_num,
        }

    @staticmethod
    def _normalize_area_value(area_str: str) -> str:
        """Normalize OCR artifacts where comma becomes period in area values.

        Pattern: "1.200.0" (OCR misread of "1.200,0") → "1.200,0"
        Matches: digits.3digits.1digit — replace last '.' with ','
        """
        if re.match(r"^\d+\.\d{3}\.\d$", area_str):
            return area_str[::-1].replace(".", ",", 1)[::-1]
        return area_str

    @staticmethod
    def _normalize_ocr_code_line(line: str) -> str:
        """Normaliza artefatos OCR onde código e participação se fundem.

        Caso 1 (dedup exato): '10 10  100,00  1  ...' → '10  100,00  1  ...'
        Caso 2 (phantom): '10 110  100,00  1  ...' → '10  100,00  1  ...'
          O OCR insere um número espúrio entre código e participação.
          Detecta: code(1-2d) + phantom(int sem vírgula) + participation(com vírgula) + condição(1d)
        """
        # Caso 1: dedup exato (ex: '10 10' → '10')
        m = re.match(r'^(\d{1,2})\s+\1(?=\s)', line)
        if m:
            return line[:m.start(1) + len(m.group(1))] + line[m.end():]

        # Caso 2: phantom number entre code e participation
        # Pattern: code + espaço + phantom_int + espaço + real_participation(com vírgula) + espaço + condição
        m2 = re.match(
            r'^(\d{1,2})\s+(\d{2,4})\s+([\d.,]+,\d{2})\s+(\d)\s+',
            line,
        )
        if m2:
            phantom = m2.group(2)
            real_part = m2.group(3)
            # Se phantom não tem vírgula (é inteiro puro) e real_part tem vírgula → phantom é artefato
            if ',' not in phantom and ',' in real_part:
                return line[:m2.start(2)] + line[m2.end(2):]

        return line

    def _normalize_name(self, name: str) -> str:
        name = re.sub(r"\s+", " ", name)
        return name.strip()

    def _count_property_lines(self, lines: list[str], start_idx: int) -> int:
        count = 1
        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"

        for j in range(start_idx + 1, min(start_idx + 20, len(lines))):
            line = lines[j].strip()
            upper_line = line.upper()

            normalized = self._normalize_ocr_code_line(line)
            if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", normalized):
                break
            if re.match(r"^\d{1,2}$", line):
                break
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                break

            if "PARTICIPANTE" in upper_line:
                count += 1
                continue
            if re.match(rf"^[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ].+\(\s*({CPF_PATTERN}|{CNPJ_PATTERN})\s*\)", line):
                count += 1
                continue
            count += 1
        return count

    def _count_multiline_property_lines(self, lines: list[str], start_idx: int) -> int:
        count = 1
        for j in range(start_idx + 1, min(start_idx + 15, len(lines))):
            line = lines[j].strip()
            upper_line = line.upper()

            if re.match(r"^\d{1,2}$", line):
                break
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                break
            count += 1
        return count

    def _extract_participants(self, lines: list[str], start_idx: int) -> list[dict]:
        participants = []

        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        CPF_OR_CNPJ = f"({CPF_PATTERN}|{CNPJ_PATTERN})"

        for j in range(start_idx + 1, min(start_idx + 20, len(lines))):
            next_line = lines[j].strip()
            upper_next = next_line.upper()

            if "PARTICIPANTE" in upper_next:
                continue

            normalized_next = self._normalize_ocr_code_line(next_line)
            if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", normalized_next):
                break
            if re.match(r"^\d{1,2}$", next_line):
                break

            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break

            part_match = re.match(rf"^(.+?)\s*\(\s*{CPF_OR_CNPJ}\s*\)", next_line)

            if part_match:
                doc_number = part_match.group(2)
                is_cnpj = "/" in doc_number

                participant = {
                    "participant_name": f"{part_match.group(1).strip()} ({doc_number})",
                    "foreigner": "Estrangeiro: Sim" in next_line or "Estrangeiro:Sim" in next_line,
                    "id": generate_item_id(doc_number),
                }

                if is_cnpj:
                    participant["cnpj"] = doc_number
                else:
                    participant["cpf"] = doc_number

                participants.append(participant)

        return participants

    def _extract_participants_from_page_start(self, page_text: str) -> list[dict]:
        """Extrai participantes do início da página (quebra de página).

        BUG FIX #82637: Quando há quebra de página, os participantes de um imóvel
        podem estar no início da próxima página. Este método extrai esses participantes
        até encontrar um novo item ou o fim da seção.
        """
        participants = []
        lines = page_text.split("\n")

        CPF_PATTERN = r"\d{3}\.\d{3}\.\d{3}-\d{2}"
        CNPJ_PATTERN = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
        CPF_OR_CNPJ = f"({CPF_PATTERN}|{CNPJ_PATTERN})"

        for _i, line in enumerate(lines):
            next_line = line.strip()
            upper_next = next_line.upper()

            # Skip linhas vazias no início
            if not next_line:
                continue

            # Skip cabeçalhos
            if "PARTICIPANTE" in upper_next:
                continue

            # Skip header da seção se presente
            if any(marker in upper_next for marker in self.SECTION_MARKERS):
                continue

            # Parar se encontrar novo item (código participação condição)
            normalized_next = self._normalize_ocr_code_line(next_line)
            if re.match(r"^\d{1,2}\s+[\d.,]+\s+\d\s+", normalized_next):
                break
            # Parar se encontrar apenas código (início de novo item multiline)
            if re.match(r"^\d{1,2}$", next_line):
                break

            # Parar em fim de seção
            if any(marker in upper_next for marker in self.SECTION_END_MARKERS):
                break

            # Skip cabeçalhos de tabela (não parar, apenas pular)
            header_keywords = [
                "CÓDIGO",
                "CODIGO",
                "ATIVIDADE",
                "PARTICIPAÇÃO",
                "ÁREA",
                "AREA",
                "CIB",
                "(HA)",
                "EXPLORAÇÃO",
                "NOME E LOCALIZAÇÃO",
                "CONDIÇÃO",
                "CONDICAO",
            ]
            if any(h in upper_next for h in header_keywords):
                continue

            # Skip linhas de cabeçalho do documento (NOME:, CPF:, DECLARAÇÃO, etc)
            if upper_next.startswith("NOME:") or upper_next.startswith("CPF:"):
                continue
            if "DECLARAÇÃO DE AJUSTE" in upper_next or "EXERCÍCIO" in upper_next:
                continue
            if "IMPOSTO SOBRE A RENDA" in upper_next:
                continue

            # Tentar extrair participante
            part_match = re.match(rf"^(.+?)\s*\(\s*{CPF_OR_CNPJ}\s*\)", next_line)

            if part_match:
                doc_number = part_match.group(2)
                is_cnpj = "/" in doc_number

                participant = {
                    "participant_name": f"{part_match.group(1).strip()} ({doc_number})",
                    "foreigner": "Estrangeiro: Sim" in next_line or "Estrangeiro:Sim" in next_line,
                    "id": generate_item_id(doc_number),
                }

                if is_cnpj:
                    participant["cnpj"] = doc_number
                else:
                    participant["cpf"] = doc_number

                participants.append(participant)
            else:
                # Se linha não é participante nem item, pode ser continuação de dados
                # mas se já extraímos participantes, paramos
                if participants:
                    break

        return participants
