from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from ..extractors.base import ExtractionContext


class GuardStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"


@dataclass
class GuardResult:
    status: GuardStatus
    section_name: str
    valid_total: Optional[bool] = None
    extracted_sum: Optional[float] = None
    pdf_total: Optional[float] = None
    difference: Optional[float] = None
    coverage: float = 1.0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    should_retry: bool = False
    
    @property
    def is_valid(self) -> bool:
        return self.status in (GuardStatus.PASSED, GuardStatus.WARNING)


class ISectionGuard(ABC):
    
    @property
    @abstractmethod
    def section_name(self) -> str:
        pass
    
    @property
    @abstractmethod
    def sum_fields(self) -> list[str]:
        pass
    
    @abstractmethod
    def validate(
        self, 
        extracted_data: dict[str, Any], 
        context: ExtractionContext
    ) -> GuardResult:
        pass
    
    def _sum_items(
        self, 
        items: list[dict[str, Any]], 
        field_name: str
    ) -> float:
        total = 0.0
        
        for item in items:
            value = item.get(field_name)
            if value is not None:
                if isinstance(value, (int, float)):
                    total += float(value)
        
        return round(total, 2)
    
    def _create_result(
        self,
        valid_total: Optional[bool],
        extracted_sum: float,
        pdf_total: Optional[float],
        warnings: list[str] = None,
        errors: list[str] = None,
    ) -> GuardResult:
        warnings = warnings or []
        errors = errors or []
        
        if valid_total is None:
            status = GuardStatus.SKIPPED
        elif valid_total:
            status = GuardStatus.PASSED
        elif errors:
            status = GuardStatus.FAILED
        else:
            status = GuardStatus.WARNING
        
        difference = None
        if pdf_total is not None:
            difference = round(extracted_sum - pdf_total, 2)
        
        return GuardResult(
            status=status,
            section_name=self.section_name,
            valid_total=valid_total,
            extracted_sum=extracted_sum,
            pdf_total=pdf_total,
            difference=difference,
            warnings=warnings,
            errors=errors,
            should_retry=not (valid_total is True or valid_total is None),
        )
