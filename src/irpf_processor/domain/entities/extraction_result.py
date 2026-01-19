"""Entidade ExtractionResult - resultado da extração de um documento."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from irpf_processor.domain.enums import PdfType
from irpf_processor.domain.value_objects import Confidence, DocumentId, FieldValue, TenantId


@dataclass
class ExtractionResult:
    """Resultado da extração de dados de um documento PDF."""

    document_id: DocumentId
    tenant_id: TenantId
    pdf_type: PdfType
    raw_data: dict[str, FieldValue]
    formatted_data: dict[str, Any]
    confidence: Confidence
    created_at: datetime = field(default_factory=datetime.utcnow)
    warnings: list[str] = field(default_factory=list)
    processing_time_ms: int = 0

    def add_warning(self, warning: str) -> None:
        """Adiciona um aviso ao resultado."""
        self.warnings.append(warning)

    def is_high_confidence(self, threshold: float = 0.95) -> bool:
        """Verifica se a extração tem alta confiança."""
        return self.confidence.overall >= threshold

    def is_low_confidence(self, threshold: float = 0.6) -> bool:
        """Verifica se a extração tem baixa confiança."""
        return self.confidence.overall < threshold

    def get_field_confidence(self, field_name: str) -> Optional[float]:
        """Retorna a confiança de um campo específico."""
        if field_name in self.raw_data:
            return self.raw_data[field_name].confidence
        return None

    def has_warnings(self) -> bool:
        """Verifica se há avisos."""
        return len(self.warnings) > 0
