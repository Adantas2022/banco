"""Gerador de flags de revisao humana."""

from typing import Any

from .models import ReviewFlag, SectionConfidence, ValidationResult


class ReviewFlagGenerator:
    """Gera flags indicando necessidade de revisao humana."""
    
    LOW_CONFIDENCE_THRESHOLD = 0.7
    CRITICAL_CONFIDENCE_THRESHOLD = 0.5
    
    def generate(
        self,
        overall_confidence: float,
        coverage_score: float,
        validation_score: float,
        section_scores: dict[str, SectionConfidence],
        validation_results: list[ValidationResult],
        extracted_data: dict[str, Any]
    ) -> list[ReviewFlag]:
        """Gera lista de flags de revisao."""
        flags: list[ReviewFlag] = []
        
        flags.extend(self._check_overall_confidence(overall_confidence))
        flags.extend(self._check_coverage(coverage_score, section_scores))
        flags.extend(self._check_validations(validation_results))
        flags.extend(self._check_sections(section_scores))
        flags.extend(self._check_critical_fields(extracted_data))
        
        flags.sort(key=lambda f: {"critical": 0, "error": 1, "warning": 2}.get(f.severity, 3))
        
        return flags
    
    def _check_overall_confidence(self, confidence: float) -> list[ReviewFlag]:
        """Verifica nivel geral de confianca."""
        flags = []
        
        if confidence < self.CRITICAL_CONFIDENCE_THRESHOLD:
            flags.append(ReviewFlag(
                severity="critical",
                message=f"Documento com confianca muito baixa ({confidence:.0%})",
                suggestion="Revisar manualmente todo o documento ou reprocessar com melhor qualidade de PDF"
            ))
        elif confidence < self.LOW_CONFIDENCE_THRESHOLD:
            flags.append(ReviewFlag(
                severity="warning",
                message=f"Documento com confianca moderada ({confidence:.0%})",
                suggestion="Verificar campos com baixa confianca"
            ))
        
        return flags
    
    def _check_coverage(
        self,
        coverage_score: float,
        section_scores: dict[str, SectionConfidence]
    ) -> list[ReviewFlag]:
        """Verifica cobertura de secoes."""
        flags = []
        
        missing_sections = [
            name for name, score in section_scores.items()
            if score.detected and not score.extracted
        ]
        
        for section_name in missing_sections:
            flags.append(ReviewFlag(
                severity="error",
                field_path=section_name,
                message=f"Secao '{self._format_section_name(section_name)}' detectada mas nao extraida",
                suggestion=f"Verificar se a secao existe no PDF e se o formato e reconhecido"
            ))
        
        if coverage_score < 0.5 and len(missing_sections) > 2:
            flags.append(ReviewFlag(
                severity="critical",
                message=f"Apenas {coverage_score:.0%} das secoes foram extraidas",
                suggestion="Verificar qualidade do PDF ou se o formato e suportado"
            ))
        
        return flags
    
    def _check_validations(self, validation_results: list[ValidationResult]) -> list[ReviewFlag]:
        """Converte resultados de validacao em flags."""
        flags = []
        
        for result in validation_results:
            if not result.passed:
                severity = self._get_validation_severity(result.validation_name)
                
                flags.append(ReviewFlag(
                    severity=severity,
                    field_path=result.affected_fields[0] if result.affected_fields else None,
                    message=result.message or f"Validacao '{result.validation_name}' falhou",
                    suggestion=self._get_validation_suggestion(result.validation_name)
                ))
        
        return flags
    
    def _check_sections(self, section_scores: dict[str, SectionConfidence]) -> list[ReviewFlag]:
        """Verifica secoes com baixa confianca."""
        flags = []
        
        for section_name, score in section_scores.items():
            if score.extracted and score.confidence < self.LOW_CONFIDENCE_THRESHOLD:
                flags.append(ReviewFlag(
                    severity="warning",
                    field_path=section_name,
                    message=f"Secao '{self._format_section_name(section_name)}' com confianca baixa ({score.confidence:.0%})",
                    suggestion=f"Verificar campos extraidos em '{self._format_section_name(section_name)}'"
                ))
        
        return flags
    
    def _check_critical_fields(self, extracted_data: dict[str, Any]) -> list[ReviewFlag]:
        """Verifica campos criticos."""
        flags = []
        
        taxpayer = extracted_data.get("taxpayer_identification", {})
        
        if not taxpayer.get("cpf") and not taxpayer.get("normalized_cpf"):
            flags.append(ReviewFlag(
                severity="critical",
                field_path="taxpayer_identification.cpf",
                message="CPF do contribuinte nao encontrado",
                suggestion="Verificar pagina inicial do documento"
            ))
        
        if not taxpayer.get("name"):
            flags.append(ReviewFlag(
                severity="critical",
                field_path="taxpayer_identification.name",
                message="Nome do contribuinte nao encontrado",
                suggestion="Verificar pagina inicial do documento"
            ))
        
        return flags
    
    def _get_validation_severity(self, validation_name: str) -> str:
        """Retorna severidade baseada no tipo de validacao."""
        critical_validations = {"cpf_valid", "cpf_present"}
        error_validations = {"sum_mismatch", "assets_sum", "debts_sum", "income_pj_sum"}
        
        if validation_name in critical_validations:
            return "critical"
        if validation_name in error_validations:
            return "error"
        return "warning"
    
    def _get_validation_suggestion(self, validation_name: str) -> str:
        """Retorna sugestao baseada no tipo de validacao."""
        suggestions = {
            "cpf_valid": "Verificar se o CPF esta correto no documento original",
            "cpf_present": "Verificar pagina inicial do documento",
            "year_consistency": "Verificar ano-exercicio e ano-calendario no cabecalho",
            "assets_sum": "Verificar se todos os bens foram extraidos corretamente",
            "debts_sum": "Verificar se todas as dividas foram extraidas",
            "income_pj_sum": "Verificar rendimentos de pessoa juridica",
            "positive_values": "Verificar valores negativos no documento",
            "income_pj_cnpjs": "Verificar CNPJs das fontes pagadoras",
        }
        return suggestions.get(validation_name, "Verificar dados no documento original")
    
    def _format_section_name(self, section_name: str) -> str:
        """Formata nome da secao para exibicao."""
        names = {
            "taxpayer_identification": "Identificacao do Contribuinte",
            "assets_declaration": "Declaracao de Bens e Direitos",
            "debts_and_encumbrances": "Dividas e Onus Reais",
            "exempt_income": "Rendimentos Isentos e Nao Tributaveis",
            "exclusive_taxation_income": "Rendimentos Sujeitos a Tributacao Exclusiva",
            "income_from_legal_person_to_holder": "Rendimentos de PJ pelo Titular",
            "income_from_legal_person_to_dependents": "Rendimentos de PJ pelos Dependentes",
            "income_from_individual_to_holder": "Rendimentos de PF pelo Titular",
            "accumulated_income_from_legal_person_to_holder": "Rendimentos PJ Acumulados",
            "exploited_rural_properties_in_brazil": "Imoveis Rurais Explorados",
            "rural_income_and_expenditure_in_brazil": "Receitas e Despesas Rurais",
            "calculation_of_rural_results_in_brazil": "Apuracao do Resultado Rural",
            "rural_activity_assets_in_brazil": "Bens da Atividade Rural",
            "rural_activity_debts_in_brazil": "Dividas da Atividade Rural",
            "livestock_movement_in_brazil": "Movimentacao do Rebanho",
        }
        return names.get(section_name, section_name.replace("_", " ").title())
