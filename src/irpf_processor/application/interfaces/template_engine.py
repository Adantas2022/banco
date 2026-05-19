"""Interface para engine de templates."""

from abc import abstractmethod
from typing import Any, Protocol

from irpf_processor.domain.value_objects import FieldValue


class ITemplateEngine(Protocol):
    """Interface para motor de transformação de dados."""

    @abstractmethod
    async def transform(
        self,
        raw_data: dict[str, FieldValue],
        template_name: str,
    ) -> dict[str, Any]:
        """Transforma dados brutos usando template. Retorna JSON formatado."""
        ...

    @abstractmethod
    def get_available_templates(self) -> list[str]:
        """Retorna lista de templates disponíveis."""
        ...

    @abstractmethod
    def template_exists(self, template_name: str) -> bool:
        """Verifica se template existe."""
        ...
