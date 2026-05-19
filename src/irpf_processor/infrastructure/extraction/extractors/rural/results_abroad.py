"""Extrator de apuração do resultado - Exterior."""

import re
from typing import Any, Optional

from ..base import ExtractionContext, ISectionExtractor
from ...table_extractor import parse_currency, generate_item_id


class RuralResultsAbroadExtractor(ISectionExtractor):
    """Extrai apuração do resultado da atividade rural - Exterior.
    
    Estrutura esperada (conforme gabarito):
    {
        "section_name": "Apuração do Resultado - Exterior",
        "subsections": {
            "previous_exercise_info": {
                "subsection_name": "INFORMAÇÃO DO EXERCÍCIO ANTERIOR",
                "items": [{"description": "...", "value": X, "id": "..."}],
                "page": N
            },
            "calculation_of_taxable_result": { ... },
            "next_exercise_info": { ... },
            "calculation_of_exempt_result": { ... }
        }
    }
    """
    
    SECTION_MARKERS = [
        "APURAÇÃO DO RESULTADO - EXTERIOR",
        "APURACAO DO RESULTADO - EXTERIOR",
        "APURAÇÃO DO RESULTADO DA ATIVIDADE RURAL - EXTERIOR",
        "APURACAO DO RESULTADO DA ATIVIDADE RURAL - EXTERIOR",
    ]
    
    SECTION_END_MARKERS = [
        "MOVIMENTAÇÃO DO REBANHO",
        "MOVIMENTACAO DO REBANHO",
        "BENS DA ATIVIDADE RURAL",
        "DÍVIDAS VINCULADAS",
        "DIVIDAS VINCULADAS",
    ]
    
    # Markers das subsections
    SUBSECTION_MARKERS = {
        "previous_exercise_info": [
            "INFORMAÇÃO DO EXERCÍCIO ANTERIOR",
            "INFORMACAO DO EXERCICIO ANTERIOR",
        ],
        "calculation_of_taxable_result": [
            "APURAÇÃO DO RESULTADO TRIBUTÁVEL",
            "APURACAO DO RESULTADO TRIBUTAVEL",
        ],
        "next_exercise_info": [
            "INFORMAÇÕES PARA O EXERCÍCIO SEGUINTE",
            "INFORMACOES PARA O EXERCICIO SEGUINTE",
        ],
        "calculation_of_exempt_result": [
            "APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL",
            "APURACAO DO RESULTADO NAO TRIBUTAVEL",
        ],
    }
    
    @property
    def section_name(self) -> str:
        return "calculation_of_rural_results_abroad"
    
    def can_extract(self, context: ExtractionContext) -> bool:
        upper_text = context.full_text.upper()
        return any(marker in upper_text for marker in self.SECTION_MARKERS)
    
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        sorted_pages = sorted(context.pages_text.items(), key=lambda x: x[0])
        
        for page_num, page_text in sorted_pages:
            upper_page = page_text.upper()
            
            # Verificar se a página tem a seção
            if any(marker in upper_page for marker in self.SECTION_MARKERS):
                subsections = self._extract_subsections(page_text, page_num)
                if subsections:
                    return {
                        "section_name": "Apuração do Resultado - Exterior",
                        "subsections": subsections
                    }
        
        return None
    
    def _extract_subsections(self, page_text: str, page_num: int) -> Optional[dict]:
        """Extrai todas as subsections da página."""
        lines = page_text.split("\n")
        subsections = {}
        
        current_subsection = None
        current_items = []
        in_main_section = False
        
        for i, line in enumerate(lines):
            upper_line = line.upper()
            
            # Detectar início da seção principal
            if any(marker in upper_line for marker in self.SECTION_MARKERS):
                in_main_section = True
                continue
            
            if not in_main_section:
                continue
            
            # Detectar fim da seção principal
            if any(marker in upper_line for marker in self.SECTION_END_MARKERS):
                # Salvar última subsection antes de sair
                if current_subsection and current_items:
                    subsections[current_subsection] = self._build_subsection(
                        current_subsection, current_items, page_num
                    )
                break
            
            # Detectar início de nova subsection
            new_subsection = self._detect_subsection(upper_line)
            if new_subsection:
                # Salvar subsection anterior se existir
                if current_subsection and current_items:
                    subsections[current_subsection] = self._build_subsection(
                        current_subsection, current_items, page_num
                    )
                current_subsection = new_subsection
                current_items = []
                continue
            
            # Se estamos em uma subsection, extrair item
            if current_subsection:
                item = self._parse_item_line(line, current_subsection)
                if item:
                    current_items.append(item)
        
        # Salvar última subsection
        if current_subsection and current_items:
            subsections[current_subsection] = self._build_subsection(
                current_subsection, current_items, page_num
            )
        
        return subsections if subsections else None
    
    def _detect_subsection(self, upper_line: str) -> Optional[str]:
        """Detecta qual subsection começa nesta linha.
        
        A linha deve COMEÇAR com o marker (não apenas conter).
        Isso evita falsos positivos como "Opção pela forma de apuração do resultado tributável"
        ser detectado como subsection "APURAÇÃO DO RESULTADO TRIBUTÁVEL".
        """
        upper_line_stripped = upper_line.strip()
        for subsection_key, markers in self.SUBSECTION_MARKERS.items():
            for marker in markers:
                if upper_line_stripped.startswith(marker):
                    return subsection_key
        return None
    
    def _build_subsection(self, subsection_key: str, items: list, page_num: int) -> dict:
        """Constrói objeto de subsection."""
        subsection_names = {
            "previous_exercise_info": "INFORMAÇÃO DO EXERCÍCIO ANTERIOR",
            "calculation_of_taxable_result": "APURAÇÃO DO RESULTADO TRIBUTÁVEL",
            "next_exercise_info": "INFORMAÇÕES PARA O EXERCÍCIO SEGUINTE",
            "calculation_of_exempt_result": "APURAÇÃO DO RESULTADO NÃO TRIBUTÁVEL",
        }
        
        return {
            "subsection_name": subsection_names.get(subsection_key, subsection_key),
            "items": items,
            "page": page_num
        }
    
    def _parse_item_line(self, line: str, subsection: str) -> Optional[dict]:
        """Extrai um item de uma linha.
        
        Formatos esperados:
        - "Descrição - R$ 1.234,56"
        - "Descrição - US$ 1.234,56"
        - "Opção pela forma de apuração do resultado tributável Pelo resultado"
        """
        line = line.strip()
        if not line:
            return None
        
        upper_line = line.upper()
        
        # Ignorar linhas de cabeçalho/título (que COMEÇAM com marker)
        upper_line_stripped = upper_line.strip()
        if any(upper_line_stripped.startswith(marker) for markers in self.SUBSECTION_MARKERS.values() for marker in markers):
            return None
        if any(upper_line_stripped.startswith(marker) for marker in self.SECTION_MARKERS):
            return None
        if "SEM INFORMAÇÕES" in upper_line or "SEM INFORMACOES" in upper_line:
            return None
        
        # Caso especial: Opção pela forma de apuração
        if "OPÇÃO PELA FORMA" in upper_line or "OPCAO PELA FORMA" in upper_line:
            return self._parse_option_line(line)
        
        # Caso especial: Resultado total com conversão (R$) - tem descrição longa
        if "RESULTADO TOTAL" in upper_line and "(R$)" in upper_line:
            return self._parse_result_total_brl(line)
        
        # Padrão: "Descrição - R$ valor" ou "Descrição - US$ valor"
        # Formato 1: Com R$ - preservar "- R$" na descrição
        match_brl = re.match(r"^(.+?)\s*(-\s*R\$)\s*([\d.,]+)\s*$", line)
        if match_brl:
            description = f"{match_brl.group(1).strip()} - R$"
            value = parse_currency(match_brl.group(3))
            return self._create_item(description, value)
        
        # Formato 2: Com US$ - preservar "- US$" na descrição
        match_usd = re.match(r"^(.+?)\s*(-\s*US\$)\s*([\d.,]+)\s*$", line)
        if match_usd:
            description = f"{match_usd.group(1).strip()} - US$"
            value = parse_currency(match_usd.group(3))
            return self._create_item(description, value)
        
        return None
    
    def _parse_option_line(self, line: str) -> dict:
        """Extrai a opção de forma de apuração.
        
        Formato: "Opção pela forma de apuração do resultado tributável Pelo resultado"
        Deve separar: description="Opção pela forma...", value="Pelo resultado"
        """
        # Padrões conhecidos de valores
        value_patterns = [
            (r"Pelo resultado", "Pelo resultado"),
            (r"Pelo limite de 20%", "Pelo limite de 20% sobre a receita bruta total"),
            (r"Pela escrituração", "Pela escrituração do Livro Caixa"),
        ]
        
        description = "Opção pela forma de apuração do resultado tributável"
        value = None
        
        for pattern, extracted_value in value_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                value = extracted_value
                break
        
        if value is None:
            # Tentar extrair o valor após "tributável"
            match = re.search(r"tributável\s+(.+)$", line, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
            else:
                value = line.strip()
        
        return self._create_item(description, value)
    
    def _parse_result_total_brl(self, line: str) -> dict:
        """Extrai resultado total em R$ com descrição completa.
        
        Formato: "Resultado total - (R$) (Resultado total - US$ multiplicado por 6,1917) 433.419,00"
        Gabarito espera: "Resultado total (R$) (Resultado total - US$ multiplicado por 6,1917)"
        """
        # Extrair todos os valores numéricos e pegar o último
        values = re.findall(r"([\d]{1,3}(?:[.,][\d]{3})*[.,][\d]{2})", line)
        
        if values:
            # Construir descrição (tudo antes do último valor)
            last_value = values[-1]
            desc_end = line.rfind(last_value)
            description = line[:desc_end].strip()
            
            # Limpar descrição - remover hífen antes de (R$) para conformar com gabarito
            # "Resultado total - (R$) ..." -> "Resultado total (R$) ..."
            description = re.sub(r"\s*-\s*\(R\$\)", " (R$)", description)
            description = description.strip()
            
            value = parse_currency(last_value)
            return self._create_item(description, value)
        
        return None
    
    def _create_item(self, description: str, value: Any) -> dict:
        """Cria um item com description, value e id."""
        # Limpar descrição
        description = description.strip()
        if description.endswith("-"):
            description = description[:-1].strip()
        
        item_id = generate_item_id(description)
        
        return {
            "description": description,
            "value": value,
            "id": item_id
        }
