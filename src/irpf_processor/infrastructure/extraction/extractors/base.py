"""Interface base para extratores de seção - Strategy Pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ExtractionContext:
    """Contexto compartilhado entre extratores."""
    
    full_text: str
    pages_text: dict[int, str]
    total_pages: int = 0
    pdf_path: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    
    def add_warning(self, message: str) -> None:
        self.warnings.append(message)
    
    def get_page_text(self, page_num: int) -> str:
        return self.pages_text.get(page_num, "")
    
    def find_pages_containing(self, text: str) -> list[int]:
        return [
            page_num 
            for page_num, page_text in self.pages_text.items()
            if text.upper() in page_text.upper()
        ]


class ISectionExtractor(ABC):
    """Interface para extratores de seção (Strategy Pattern)."""
    
    @property
    @abstractmethod
    def section_name(self) -> str:
        """Nome da seção que este extrator processa."""
        pass
    
    @abstractmethod
    def can_extract(self, context: ExtractionContext) -> bool:
        """Verifica se há dados desta seção no documento."""
        pass
    
    @abstractmethod
    def extract(self, context: ExtractionContext) -> Optional[dict[str, Any]]:
        """Extrai dados da seção."""
        pass
