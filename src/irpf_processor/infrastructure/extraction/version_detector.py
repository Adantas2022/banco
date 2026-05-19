"""Detector de versão do documento IRPF.

Responsável por identificar dinamicamente:
- Ano de exercício
- Ano-calendário  
- Tipo de declaração
- Categoria do documento (Declaração ou Recibo)
- Seções presentes no documento
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from irpf_processor.domain.enums import DocumentCategory
from .extractors.base import ExtractionContext


@dataclass
class DocumentProfile:
    """Perfil do documento IRPF detectado."""
    
    exercise_year: str = ""
    calendar_year: str = ""
    declaration_type: str = ""
    document_category: DocumentCategory = DocumentCategory.UNKNOWN
    taxpayer_name: str = ""
    taxpayer_cpf: str = ""
    total_pages: int = 0
    
    detected_sections: list[str] = field(default_factory=list)
    
    confidence: float = 0.0
    
    def has_section(self, section_name: str) -> bool:
        return section_name in self.detected_sections
    
    def is_receipt(self) -> bool:
        return self.document_category == DocumentCategory.RECIBO
    
    def is_declaration(self) -> bool:
        return self.document_category == DocumentCategory.DECLARACAO
    
    def to_dict(self) -> dict:
        return {
            "exercise_year": self.exercise_year,
            "calendar_year": self.calendar_year,
            "declaration_type": self.declaration_type,
            "document_category": self.document_category.value,
            "taxpayer_name": self.taxpayer_name,
            "taxpayer_cpf": self.taxpayer_cpf,
            "total_pages": self.total_pages,
            "detected_sections": self.detected_sections,
            "confidence": self.confidence
        }


class VersionDetector:
    """Detecta versão e estrutura do documento IRPF."""
    
    RECEIPT_MARKERS = [
        "RECIBO DE ENTREGA",
        "RECIBO DA DECLARAÇÃO",
        "RECIBO DECLARAÇÃO",
        "COMPROVANTE DE ENTREGA",
        "DECLARAÇÃO TRANSMITIDA",
        "TRANSMISSÃO DA DECLARAÇÃO",
        "Nº do Recibo",
        "Número do Recibo",
    ]
    
    SECTION_MARKERS = {
        "taxpayer_identification": [
            "DECLARAÇÃO DE AJUSTE ANUAL",
            "CPF:",
            "NOME:"
        ],
        "assets_declaration": [
            "DECLARAÇÃO DE BENS E DIREITOS",
            "DECLARACAO DE BENS E DIREITOS",  # OCR sem acentos
            "DECLARAGAO DE BENS E DIREITOS",  # OCR: Ç → G
            "BENS E DIREITOS"
        ],
        "income_from_legal_person_to_holder": [
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELO TITULAR",
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELO TITULAR",
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA JURIDICA PELO TITULAR",  # OCR sem acentos
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOAS JURIDICAS PELO TITULAR"
        ],
        "income_from_legal_person_to_dependents": [
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELOS DEPENDENTES",
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES",
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOAS JURIDICAS PELOS DEPENDENTES",  # OCR sem acentos
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA JURIDICA PELOS DEPENDENTES"
        ],
        "exempt_income": [
            "RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS",
            "RENDIMENTOS ISENTOS E NAO TRIBUTAVEIS"  # OCR sem acentos
        ],
        "exclusive_taxation_income": [
            "RENDIMENTOS SUJEITOS À TRIBUTAÇÃO EXCLUSIVA",
            "RENDIMENTOS SUJEITOS A TRIBUTAÇÃO EXCLUSIVA",
            "RENDIMENTOS SUJEITOS A TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA",  # Post-processor com espaços
            "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA",  # OCR sem acentos
            "RENDIMENTOS SUJEITOS A TRIBUTACAO EXCLUSIVA / DEFINITIVA",  # OCR com espaços
            "TRIBUTAÇÃO EXCLUSIVA / DEFINITIVA",  # Post-processor
            "TRIBUTAÇÃO EXCLUSIVA/DEFINITIVA",
            "TRIBUTAÇÃO EXCLUSIVA",
            "TRIBUTACAO EXCLUSIVA/DEFINITIVA",  # OCR sem acentos
            "TRIBUTACAO EXCLUSIVA / DEFINITIVA",  # OCR com espaços
            "TRIBUTAGAO EXCLUSIVA",  # OCR: Ç → G
        ],
        "debts_and_encumbrances": [
            "DÍVIDAS E ÔNUS REAIS",
            "DIVIDAS E ONUS REAIS"  # OCR sem acentos
        ],
        "exploited_rural_properties_in_brazil": [
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO",
            "DADOS E IDENTIFICACAO DO IMOVEL EXPLORADO",  # OCR sem acentos
            "DADOS E IDENTIFICAGAO DO IMOVEL EXPLORADO"   # OCR: Ç -> G
        ],
        "rural_income_and_expenditure_in_brazil": [
            "RECEITAS E DESPESAS - BRASIL"
        ],
        "calculation_of_rural_results_in_brazil": [
            "APURAÇÃO DO RESULTADO - BRASIL",
            "APURACAO DO RESULTADO - BRASIL",  # OCR sem acentos
            "APURAGAO DO RESULTADO - BRASIL"   # OCR: Ç -> G
        ],
        "rural_activity_assets_in_brazil": [
            "BENS DA ATIVIDADE RURAL - BRASIL"
        ],
        "rural_activity_debts_in_brazil": [
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL",
            "DIVIDAS VINCULADAS A ATIVIDADE RURAL"  # OCR sem acentos
        ],
        "livestock_movement_in_brazil": [
            "MOVIMENTAÇÃO DO REBANHO",
            "MOVIMENTACAO DO REBANHO",  # OCR sem acentos
            "MOVIMENTAGAO DO REBANHO"   # OCR: Ç -> G
        ],
        "income_from_individual_to_holder": [
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA",
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA FISICA"  # OCR sem acentos
        ],
        "donations_made": [
            "DOAÇÕES EFETUADAS",
            "DOACOES EFETUADAS"  # OCR sem acentos
        ],
        "payments_made": [
            "PAGAMENTOS EFETUADOS"
        ],
        "dependents": [
            "RELAÇÃO DE DEPENDENTES",
            "RELACAO DE DEPENDENTES"  # OCR sem acentos
        ],
        # Seções ABROAD (Exterior) - Adicionadas para BUGs 81770, 81781, 81783, 81784
        "calculation_of_rural_results_abroad": [
            "APURAÇÃO DO RESULTADO - EXTERIOR",
            "APURACAO DO RESULTADO - EXTERIOR",
            "APURAGAO DO RESULTADO - EXTERIOR",  # OCR: Ç -> G
        ],
        "livestock_movement_abroad": [
            "MOVIMENTAÇÃO DO REBANHO - EXTERIOR",
            "MOVIMENTACAO DO REBANHO - EXTERIOR",
            "MOVIMENTAGAO DO REBANHO - EXTERIOR",  # OCR: Ç -> G
        ],
        "rural_activity_assets_abroad": [
            "BENS DA ATIVIDADE RURAL - EXTERIOR",
        ],
        "rural_activity_debts_abroad": [
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL - EXTERIOR",
            "DIVIDAS VINCULADAS A ATIVIDADE RURAL - EXTERIOR",
            "DÍVIDAS VINCULADAS À ATIVIDADE RURAL – EXTERIOR",  # En-dash
            "DIVIDAS VINCULADAS A ATIVIDADE RURAL – EXTERIOR",  # En-dash
            "DÍVIDAS VINCULADAS - EXTERIOR",
            "DIVIDAS VINCULADAS - EXTERIOR",
        ],
        "rural_income_and_expenditure_abroad": [
            "RECEITAS E DESPESAS - EXTERIOR",
            "DEMONSTRATIVO DE ATIVIDADE RURAL - EXTERIOR",
        ],
        "exploited_rural_properties_abroad": [
            "DADOS E IDENTIFICAÇÃO DO IMÓVEL EXPLORADO - EXTERIOR",
            "DADOS E IDENTIFICACAO DO IMOVEL EXPLORADO - EXTERIOR",
            "IMÓVEL EXPLORADO - EXTERIOR",
        ],
        # Seções de DEPENDENTES - Adicionadas para BUGs 81767, 81773, 81775
        "income_from_individual_to_dependents": [
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA E DO EXTERIOR PELOS DEPENDENTES",
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA FISICA E DO EXTERIOR PELOS DEPENDENTES",
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA PELOS DEPENDENTES",
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA FISICA PELOS DEPENDENTES",
        ],
        "accumulated_income_from_legal_person_to_dependents": [
            "RECEBIDOS ACUMULADAMENTE PELOS DEPENDENTES",  # Marker parcial (título quebrado em 2 linhas)
            "ACUMULADAMENTE PELOS DEPENDENTES",
        ],
        "income_from_legal_person_to_dependents_with_suspended_requirements": [
            "PELOS DEPENDENTES (IMPOSTO COM",  # Marker parcial (título quebrado em 2 linhas)
            "RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA JURÍDICA PELOS DEPENDENTES (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
            "RENDIMENTOS TRIBUTAVEIS RECEBIDOS DE PESSOA JURIDICA PELOS DEPENDENTES (IMPOSTO COM EXIGIBILIDADE SUSPENSA)",
        ],
        # Seções adicionais de rendimentos
        "accumulated_income_from_legal_person_to_holder": [
            "RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE PELO TITULAR",
            "RENDIMENTOS TRIBUTAVEIS DE PESSOA JURIDICA RECEBIDOS ACUMULADAMENTE PELO TITULAR",
            "RECEBIDOS ACUMULADAMENTE PELO TITULAR",
        ],
        "income_from_legal_person_to_holder_with_suspended_requirements": [
            "IMPOSTO COM EXIGIBILIDADE SUSPENSA",
            "EXIGIBILIDADE SUSPENSA",
        ],
    }
    
    VERSION_PATTERNS = {
        "exercise_year": r"EXERC[ÍI]CIO\s*(\d{4})",
        "calendar_year": r"ANO[- ]CALEND[ÁA]RIO\s*(\d{4})",
        "cpf": r"CPF[:\s]*(\d{3}[.\s]?\d{3}[.\s]?\d{3}[-\s]?\d{2})",
        "name": r"(?:NOME|Nome)[:\s]*([A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][A-ZÁÀÂÃÉÊÍÓÔÕÚÇa-záàâãéêíóôõúç\s]+?)(?:\n|CPF)",
        "declaration_type": r"Tipo de declara[çc][ãa]o[:\s]*(.+?)(?:\n|$)"
    }
    
    def detect(self, context: ExtractionContext) -> DocumentProfile:
        """Detecta o perfil do documento."""
        profile = DocumentProfile(total_pages=context.total_pages)
        
        self._detect_category(context.full_text, profile)
        self._detect_version(context.full_text, profile)
        self._detect_taxpayer(context.full_text, profile)
        self._detect_sections(context.full_text, profile)
        self._calculate_confidence(profile)
        
        return profile
    
    def _detect_category(self, text: str, profile: DocumentProfile) -> None:
        """Detecta se é declaração ou recibo."""
        text_upper = text.upper()
        
        for marker in self.RECEIPT_MARKERS:
            if marker.upper() in text_upper:
                if "DECLARAÇÃO DE AJUSTE ANUAL" in text_upper:
                    receipt_pos = text_upper.find(marker.upper())
                    decl_pos = text_upper.find("DECLARAÇÃO DE AJUSTE ANUAL")
                    if receipt_pos < decl_pos:
                        profile.document_category = DocumentCategory.RECIBO
                        return
                else:
                    profile.document_category = DocumentCategory.RECIBO
                    return
        
        if "DECLARAÇÃO DE AJUSTE ANUAL" in text_upper:
            profile.document_category = DocumentCategory.DECLARACAO
        elif "IRPF" in text_upper and profile.document_category == DocumentCategory.UNKNOWN:
            profile.document_category = DocumentCategory.DECLARACAO
    
    def _detect_version(self, text: str, profile: DocumentProfile) -> None:
        exercise_match = re.search(
            self.VERSION_PATTERNS["exercise_year"], 
            text, 
            re.IGNORECASE
        )
        if exercise_match:
            profile.exercise_year = exercise_match.group(1)
        
        calendar_match = re.search(
            self.VERSION_PATTERNS["calendar_year"], 
            text, 
            re.IGNORECASE
        )
        if calendar_match:
            profile.calendar_year = calendar_match.group(1)
        
        type_match = re.search(
            self.VERSION_PATTERNS["declaration_type"],
            text,
            re.IGNORECASE
        )
        if type_match:
            profile.declaration_type = type_match.group(1).strip().upper()
    
    def _detect_taxpayer(self, text: str, profile: DocumentProfile) -> None:
        cpf_match = re.search(self.VERSION_PATTERNS["cpf"], text, re.IGNORECASE)
        if cpf_match:
            profile.taxpayer_cpf = cpf_match.group(1)
        
        name_match = re.search(self.VERSION_PATTERNS["name"], text)
        if name_match:
            profile.taxpayer_name = name_match.group(1).strip()
    
    def _detect_sections(self, text: str, profile: DocumentProfile) -> None:
        text_upper = text.upper()
        
        for section_name, markers in self.SECTION_MARKERS.items():
            for marker in markers:
                marker_upper = marker.upper()
                if marker_upper in text_upper:
                    if self._section_has_data(text_upper, marker_upper):
                        if section_name not in profile.detected_sections:
                            profile.detected_sections.append(section_name)
                    break
    
    def _section_has_data(self, text_upper: str, marker_upper: str) -> bool:
        """Verifica se a seção tem dados (não está marcada como 'Sem Informações').
        
        A verificação é feita em duas etapas:
        1. Verificar se "Sem Informações" aparece IMEDIATAMENTE após o marker (dentro de 100 chars)
        2. Se aparecer depois de 100 chars, verificar se há outra seção antes (indicando que
           o "Sem Informações" pertence a outra seção, não a esta)
        
        BUG FIX: A janela anterior era muito grande e encontrava "Sem Informações" de seções
        adjacentes, causando falsos negativos.
        """
        idx = text_upper.find(marker_upper)
        if idx == -1:
            return False
        
        no_data_markers = [
            "SEM INFORMAÇÕES",
            "SEM INFORMACOES",
            "SEM DADOS",
            "NAO HA DADOS",
            "NÃO HÁ DADOS",
        ]
        
        # Janela imediata (100 chars) - se "Sem Informações" aqui, seção está vazia
        immediate_context = text_upper[idx + len(marker_upper):idx + len(marker_upper) + 100]
        for no_data in no_data_markers:
            if no_data in immediate_context:
                return False
        
        # Janela estendida (300 chars) - verificar se há outra seção antes do "Sem Informações"
        extended_context = text_upper[idx + len(marker_upper):idx + len(marker_upper) + 400]
        
        # Markers que indicam início de outra seção
        other_section_markers = [
            "DEMONSTRATIVO",
            "APURAÇÃO",
            "APURACAO",
            "RECEITAS E DESPESAS",
            "MOVIMENTAÇÃO",
            "MOVIMENTACAO",
            "BENS DA ATIVIDADE",
            "DÍVIDAS VINCULADAS",
            "DIVIDAS VINCULADAS",
            "RENDIMENTOS",
            "PAGAMENTOS",
            "DOAÇÕES",
            "DOACOES",
        ]
        
        for no_data in no_data_markers:
            no_data_pos = extended_context.find(no_data)
            if no_data_pos != -1:
                # Verificar se há outra seção ANTES do "Sem Informações"
                context_before_no_data = extended_context[:no_data_pos]
                for other_marker in other_section_markers:
                    if other_marker in context_before_no_data:
                        # "Sem Informações" pertence a outra seção, não a esta
                        return True
                # "Sem Informações" provavelmente pertence a esta seção
                return False
        
        return True
    
    def _calculate_confidence(self, profile: DocumentProfile) -> None:
        score = 0.0
        total = 0.0
        
        if profile.exercise_year:
            score += 1.0
        total += 1.0
        
        if profile.calendar_year:
            score += 1.0
        total += 1.0
        
        if profile.taxpayer_cpf:
            score += 1.0
        total += 1.0
        
        if profile.taxpayer_name:
            score += 1.0
        total += 1.0
        
        if profile.detected_sections:
            score += min(len(profile.detected_sections) / 5, 1.0)
        total += 1.0
        
        profile.confidence = score / total if total > 0 else 0.0
    
    def get_recommended_extractors(
        self, 
        profile: DocumentProfile
    ) -> list[str]:
        """Retorna lista de extratores recomendados para o documento."""
        return profile.detected_sections
