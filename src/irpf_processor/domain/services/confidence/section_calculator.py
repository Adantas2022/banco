"""Calculador de cobertura de secoes."""

from typing import Any

from .models import SectionConfidence


class SectionCoverageCalculator:
    """Calcula a cobertura entre secoes detectadas e extraidas."""
    
    REQUIRED_SECTIONS = {
        "taxpayer_identification",
    }
    
    EXPECTED_SECTIONS = {
        "taxpayer_identification",
        "assets_declaration",
        "debts_and_encumbrances",
        "exempt_income",
        "exclusive_taxation_income",
        "income_from_legal_person_to_holder",
        "payments_made",
        "donations_made",
    }
    
    def calculate(
        self,
        detected_sections: set[str],
        extracted_data: dict[str, Any]
    ) -> tuple[float, dict[str, SectionConfidence]]:
        """Calcula cobertura e retorna (score, section_results)."""
        section_results: dict[str, SectionConfidence] = {}
        
        if not isinstance(detected_sections, set):
            detected_sections = set(detected_sections) if detected_sections else set()
        
        all_sections = detected_sections | self.REQUIRED_SECTIONS
        
        extracted_count = 0
        detected_count = 0
        
        for section_name in all_sections:
            detected = section_name in detected_sections or section_name in self.REQUIRED_SECTIONS
            section_data = extracted_data.get(section_name)
            
            extracted = self._has_meaningful_data(section_data)
            field_count, fields_valid = self._count_fields(section_data)
            
            confidence = 0.0
            if detected and extracted:
                if field_count > 0:
                    confidence = fields_valid / field_count
                else:
                    confidence = 1.0
            
            section_results[section_name] = SectionConfidence(
                section_name=section_name,
                detected=detected,
                extracted=extracted,
                field_count=field_count,
                fields_valid=fields_valid,
                confidence=confidence
            )
            
            if detected:
                detected_count += 1
                if extracted:
                    extracted_count += 1
        
        coverage_score = extracted_count / detected_count if detected_count > 0 else 0.0
        
        return coverage_score, section_results
    
    def _has_meaningful_data(self, data: Any) -> bool:
        """Verifica se a secao tem dados significativos."""
        if data is None:
            return False
        
        if isinstance(data, dict):
            if not data:
                return False
            
            if "items" in data:
                items = data.get("items", [])
                return isinstance(items, list) and len(items) > 0
            
            meaningful_keys = [k for k in data.keys() if not k.startswith("_")]
            if not meaningful_keys:
                return False
            
            for key in meaningful_keys:
                if key in ("section_name", "pages_with_problems"):
                    continue
                value = data[key]
                if value is not None and value != "" and value != "N/A":
                    if isinstance(value, (list, dict)):
                        if len(value) > 0:
                            return True
                    else:
                        return True
            
            return False
        
        if isinstance(data, list):
            return len(data) > 0
        
        return data is not None and data != "" and data != "N/A"
    
    def _count_fields(self, data: Any) -> tuple[int, int]:
        """Conta campos totais e validos em uma secao."""
        if data is None:
            return 0, 0
        
        if not isinstance(data, dict):
            return 1, 1 if data is not None else 0
        
        total = 0
        valid = 0
        
        for key, value in data.items():
            if key.startswith("_") or key == "section_name":
                continue
            
            if key == "items" and isinstance(value, list):
                for item in value:
                    item_total, item_valid = self._count_item_fields(item)
                    total += item_total
                    valid += item_valid
            elif key == "total_values" and isinstance(value, dict):
                for total_key, total_data in value.items():
                    total += 1
                    if isinstance(total_data, dict) and total_data.get("valid", True):
                        valid += 1
                    elif total_data is not None:
                        valid += 1
            elif isinstance(value, dict):
                sub_total, sub_valid = self._count_fields(value)
                total += sub_total
                valid += sub_valid
            else:
                total += 1
                if self._is_valid_value(value):
                    valid += 1
        
        return total, valid
    
    def _count_item_fields(self, item: dict) -> tuple[int, int]:
        """Conta campos em um item de lista."""
        if not isinstance(item, dict):
            return 1, 1 if item is not None else 0
        
        total = 0
        valid = 0
        
        for key, value in item.items():
            if key.startswith("_") or key in ("id", "page"):
                continue
            
            if isinstance(value, dict):
                sub_total, sub_valid = self._count_item_fields(value)
                total += sub_total
                valid += sub_valid
            else:
                total += 1
                if self._is_valid_value(value):
                    valid += 1
        
        return total, valid
    
    def _is_valid_value(self, value: Any) -> bool:
        """Verifica se um valor e valido."""
        if value is None:
            return False
        if isinstance(value, str):
            return value.strip() != "" and value != "N/A"
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return True
    
    def get_missing_sections(
        self,
        detected_sections: set[str],
        section_results: dict[str, SectionConfidence]
    ) -> list[str]:
        """Retorna lista de secoes detectadas mas nao extraidas."""
        missing = []
        for section_name, result in section_results.items():
            if result.detected and not result.extracted:
                missing.append(section_name)
        return missing
    
    def get_low_confidence_sections(
        self,
        section_results: dict[str, SectionConfidence],
        threshold: float = 0.7
    ) -> list[str]:
        """Retorna secoes com confianca abaixo do limiar."""
        low_conf = []
        for section_name, result in section_results.items():
            if result.extracted and result.confidence < threshold:
                low_conf.append(section_name)
        return low_conf
