"""Validador cruzado para consistencia de dados extraidos."""

from typing import Any

from .models import ValidationResult
from .validators import CpfValidator, CnpjValidator


VALIDATION_PENALTIES = {
    "sum_mismatch": 0.15,
    "invalid_cpf": 0.25,
    "invalid_cnpj": 0.10,
    "year_inconsistency": 0.10,
    "negative_value": 0.05,
    "missing_required": 0.20,
}


class CrossValidationCalculator:
    """Calcula validacoes cruzadas entre campos e secoes."""
    
    def __init__(self):
        self._cpf_validator = CpfValidator()
        self._cnpj_validator = CnpjValidator()
    
    def calculate(
        self,
        extracted_data: dict[str, Any]
    ) -> tuple[float, list[ValidationResult]]:
        """Executa todas as validacoes e retorna (score, resultados)."""
        results: list[ValidationResult] = []
        
        results.append(self._validate_cpf(extracted_data))
        results.append(self._validate_year_consistency(extracted_data))
        results.append(self._validate_assets_sum(extracted_data))
        results.append(self._validate_debts_sum(extracted_data))
        results.append(self._validate_income_pj_sum(extracted_data))
        results.append(self._validate_positive_values(extracted_data))
        results.extend(self._validate_item_cnpjs(extracted_data))
        
        total_penalty = sum(r.penalty for r in results if not r.passed)
        score = max(0.0, 1.0 - total_penalty)
        
        return score, results
    
    def _validate_cpf(self, data: dict) -> ValidationResult:
        """Valida CPF do contribuinte."""
        taxpayer = data.get("taxpayer_identification", {})
        cpf = taxpayer.get("cpf") or taxpayer.get("normalized_cpf")
        
        if not cpf:
            return ValidationResult(
                validation_name="cpf_present",
                passed=False,
                penalty=VALIDATION_PENALTIES["missing_required"],
                message="CPF do contribuinte nao encontrado",
                affected_fields=["taxpayer_identification.cpf"]
            )
        
        passed, errors = self._cpf_validator.validate(cpf)
        
        return ValidationResult(
            validation_name="cpf_valid",
            passed=passed,
            penalty=0.0 if passed else VALIDATION_PENALTIES["invalid_cpf"],
            message=errors[0] if errors else None,
            affected_fields=["taxpayer_identification.cpf"] if not passed else []
        )
    
    def _validate_year_consistency(self, data: dict) -> ValidationResult:
        """Valida consistencia entre ano exercicio e calendario."""
        taxpayer = data.get("taxpayer_identification", {})
        
        exercise_year = taxpayer.get("exercise_year")
        calendar_year = taxpayer.get("calendar_year")
        
        if not exercise_year or not calendar_year:
            return ValidationResult(
                validation_name="year_consistency",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        try:
            ex_year = int(str(exercise_year))
            cal_year = int(str(calendar_year))
            
            if ex_year != cal_year + 1:
                return ValidationResult(
                    validation_name="year_consistency",
                    passed=False,
                    penalty=VALIDATION_PENALTIES["year_inconsistency"],
                    message=f"Ano exercicio ({ex_year}) deve ser calendario ({cal_year}) + 1",
                    affected_fields=["taxpayer_identification.exercise_year", "taxpayer_identification.calendar_year"]
                )
            
            return ValidationResult(
                validation_name="year_consistency",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        except (ValueError, TypeError):
            return ValidationResult(
                validation_name="year_consistency",
                passed=False,
                penalty=VALIDATION_PENALTIES["year_inconsistency"],
                message="Anos invalidos para comparacao",
                affected_fields=["taxpayer_identification.exercise_year", "taxpayer_identification.calendar_year"]
            )
    
    def _validate_assets_sum(self, data: dict) -> ValidationResult:
        """Valida se soma dos bens confere com total."""
        assets = data.get("assets_declaration")
        if not assets or not isinstance(assets, dict):
            return ValidationResult(
                validation_name="assets_sum",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        items = assets.get("items", [])
        declared_total = assets.get("current_year_total_value", 0)
        
        if not items:
            return ValidationResult(
                validation_name="assets_sum",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        calculated_sum = sum(
            item.get("current_year_asset_value", 0) or 0
            for item in items
            if isinstance(item, dict)
        )
        
        tolerance = max(1.0, abs(declared_total) * 0.01)
        
        if abs(calculated_sum - declared_total) > tolerance:
            return ValidationResult(
                validation_name="assets_sum",
                passed=False,
                penalty=VALIDATION_PENALTIES["sum_mismatch"],
                message=f"Soma dos bens (R$ {calculated_sum:,.2f}) difere do total declarado (R$ {declared_total:,.2f})",
                affected_fields=["assets_declaration.current_year_total_value"]
            )
        
        return ValidationResult(
            validation_name="assets_sum",
            passed=True,
            penalty=0.0,
            message=None,
            affected_fields=[]
        )
    
    def _validate_debts_sum(self, data: dict) -> ValidationResult:
        """Valida se soma das dividas confere com total."""
        debts = data.get("debts_and_encumbrances")
        if not debts or not isinstance(debts, dict):
            return ValidationResult(
                validation_name="debts_sum",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        items = debts.get("items", [])
        declared_total = debts.get("current_year_total_value", 0)
        
        if not items or not declared_total:
            return ValidationResult(
                validation_name="debts_sum",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        calculated_sum = sum(
            item.get("current_year_value", 0) or 0
            for item in items
            if isinstance(item, dict)
        )
        
        tolerance = max(1.0, abs(declared_total) * 0.01)
        
        if abs(calculated_sum - declared_total) > tolerance:
            return ValidationResult(
                validation_name="debts_sum",
                passed=False,
                penalty=VALIDATION_PENALTIES["sum_mismatch"],
                message=f"Soma das dividas (R$ {calculated_sum:,.2f}) difere do total (R$ {declared_total:,.2f})",
                affected_fields=["debts_and_encumbrances.current_year_total_value"]
            )
        
        return ValidationResult(
            validation_name="debts_sum",
            passed=True,
            penalty=0.0,
            message=None,
            affected_fields=[]
        )
    
    def _validate_income_pj_sum(self, data: dict) -> ValidationResult:
        """Valida soma dos rendimentos de PJ."""
        income = data.get("income_from_legal_person_to_holder")
        if not income or not isinstance(income, dict):
            return ValidationResult(
                validation_name="income_pj_sum",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        items = income.get("items", [])
        total_values = income.get("total_values", {})
        
        if not items or not total_values:
            return ValidationResult(
                validation_name="income_pj_sum",
                passed=True,
                penalty=0.0,
                message=None,
                affected_fields=[]
            )
        
        declared_income_total = total_values.get("income_from_legal_person", {})
        if isinstance(declared_income_total, dict):
            declared_amount = declared_income_total.get("amount", 0)
        else:
            declared_amount = declared_income_total or 0
        
        calculated_sum = sum(
            item.get("income_from_legal_person", 0) or 0
            for item in items
            if isinstance(item, dict)
        )
        
        tolerance = max(1.0, abs(declared_amount) * 0.01)
        
        if abs(calculated_sum - declared_amount) > tolerance:
            return ValidationResult(
                validation_name="income_pj_sum",
                passed=False,
                penalty=VALIDATION_PENALTIES["sum_mismatch"],
                message=f"Soma dos rendimentos PJ (R$ {calculated_sum:,.2f}) difere do total (R$ {declared_amount:,.2f})",
                affected_fields=["income_from_legal_person_to_holder.total_values"]
            )
        
        return ValidationResult(
            validation_name="income_pj_sum",
            passed=True,
            penalty=0.0,
            message=None,
            affected_fields=[]
        )
    
    def _validate_positive_values(self, data: dict) -> ValidationResult:
        """Valida se valores monetarios sao positivos."""
        negative_fields = []
        
        assets = data.get("assets_declaration", {})
        if isinstance(assets, dict):
            for i, item in enumerate(assets.get("items", [])):
                if isinstance(item, dict):
                    for key in ["before_year_asset_value", "current_year_asset_value"]:
                        value = item.get(key)
                        if value is not None and value < 0:
                            negative_fields.append(f"assets_declaration.items[{i}].{key}")
        
        if negative_fields:
            return ValidationResult(
                validation_name="positive_values",
                passed=False,
                penalty=VALIDATION_PENALTIES["negative_value"] * len(negative_fields),
                message=f"Encontrados {len(negative_fields)} valores negativos",
                affected_fields=negative_fields
            )
        
        return ValidationResult(
            validation_name="positive_values",
            passed=True,
            penalty=0.0,
            message=None,
            affected_fields=[]
        )
    
    def _validate_item_cnpjs(self, data: dict) -> list[ValidationResult]:
        """Valida CNPJs em items de rendimentos."""
        results = []
        
        income = data.get("income_from_legal_person_to_holder", {})
        if isinstance(income, dict):
            items = income.get("items", [])
            invalid_count = 0
            invalid_fields = []
            
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    cnpj = item.get("cpf_cnpj")
                    if cnpj:
                        passed, _ = self._cnpj_validator.validate(cnpj)
                        if not passed:
                            invalid_count += 1
                            invalid_fields.append(f"income_from_legal_person_to_holder.items[{i}].cpf_cnpj")
            
            if invalid_count > 0:
                results.append(ValidationResult(
                    validation_name="income_pj_cnpjs",
                    passed=False,
                    penalty=min(VALIDATION_PENALTIES["invalid_cnpj"] * invalid_count, 0.20),
                    message=f"Encontrados {invalid_count} CNPJs invalidos em rendimentos PJ",
                    affected_fields=invalid_fields
                ))
            else:
                results.append(ValidationResult(
                    validation_name="income_pj_cnpjs",
                    passed=True,
                    penalty=0.0,
                    message=None,
                    affected_fields=[]
                ))
        
        return results if results else [ValidationResult(
            validation_name="income_pj_cnpjs",
            passed=True,
            penalty=0.0,
            message=None,
            affected_fields=[]
        )]
