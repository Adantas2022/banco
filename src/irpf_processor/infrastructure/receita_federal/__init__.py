"""Módulo para integração com a Receita Federal.

Este módulo fornece ferramentas para:
- Download de leiautes oficiais da DIRPF
- Cache local de documentos técnicos
- Atualização automática de templates
- Geração de PDFs de teste para diferentes anos
"""

from .layout_loader import (
    LayoutLoader,
    LayoutInfo,
    DownloadResult,
)
from .test_pdf_generator import (
    TestPDFGenerator,
    TestDeclaration,
    AdvancedTestGenerator,
    generate_valid_cpf,
    generate_valid_cnpj,
    generate_random_name,
)

__all__ = [
    "LayoutLoader",
    "LayoutInfo",
    "DownloadResult",
    "TestPDFGenerator",
    "TestDeclaration",
    "AdvancedTestGenerator",
    "generate_valid_cpf",
    "generate_valid_cnpj",
    "generate_random_name",
]
