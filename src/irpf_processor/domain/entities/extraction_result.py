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

    @property
    def extracted_data(self) -> dict[str, Any]:
        """Alias para formatted_data para compatibilidade com LLM providers."""
        return self.formatted_data

    @classmethod
    def from_extraction(
        cls,
        document_filename: str,
        extracted_data: dict[str, Any],
        processing_time: float,
    ):
        """Cria um resultado de extração a partir dos dados extraídos.
        
        Nota: Este é um construtor simplificado para uso em LLM extraction.
        """
        # Importar aqui para evitar circular imports
        from irpf_processor.domain.enums import PdfType
        from irpf_processor.domain.value_objects import Confidence, DocumentId, TenantId
        
        return cls(
            document_id=DocumentId(value=document_filename),
            tenant_id=TenantId(value="llm_extraction"),
            pdf_type=PdfType.UNKNOWN,
            raw_data={},
            formatted_data=extracted_data,
            confidence=Confidence(overall=1.0, extraction_method="digital"),
            processing_time_ms=int(processing_time * 1000),
        )
