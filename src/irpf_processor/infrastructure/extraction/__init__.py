"""Módulo de extração de dados de PDFs.

Arquitetura:
- IRPFParser: Orquestrador principal (Facade Pattern)
- ReceiptParser: Parser específico para recibos de entrega
- ISectionExtractor: Interface para extratores (Strategy Pattern)
- Extractors: Implementações específicas por seção
- VersionDetector: Detecção dinâmica de versão e seções
"""

from .irpf_parser import IRPFParser, IRPFDeclarationResult
from .receipt_parser import ReceiptParser, IRPFReceiptResult
from .version_detector import VersionDetector, DocumentProfile
from .text_extractor import PdfTextExtractor
from .table_extractor import TableExtractor, ExtractedTable, parse_currency, generate_item_id
from .field_extractors import (
    extract_cpf,
    extract_cnpj,
    extract_currency,
    extract_date,
    normalize_cpf,
    normalize_cnpj,
    validate_cpf,
    validate_cnpj,
)
from .extractors import (
    ISectionExtractor,
    ExtractionContext,
    TaxpayerExtractor,
    AssetsExtractor,
    IncomePJExtractor,
    ExemptIncomeExtractor,
    ExclusiveIncomeExtractor,
    ReceiptExtractor,
    is_receipt_document,
    RuralPropertiesExtractor,
    RuralIncomeExpenditureExtractor,
    RuralResultsExtractor,
    RuralAssetsExtractor,
    RuralDebtsExtractor,
)

__all__ = [
    "IRPFParser",
    "IRPFDeclarationResult",
    "ReceiptParser",
    "IRPFReceiptResult",
    
    "VersionDetector",
    "DocumentProfile",
    
    "ISectionExtractor",
    "ExtractionContext",
    
    "TaxpayerExtractor",
    "AssetsExtractor",
    "IncomePJExtractor",
    "ExemptIncomeExtractor",
    "ExclusiveIncomeExtractor",
    "ReceiptExtractor",
    "is_receipt_document",
    "RuralPropertiesExtractor",
    "RuralIncomeExpenditureExtractor",
    "RuralResultsExtractor",
    "RuralAssetsExtractor",
    "RuralDebtsExtractor",
    
    "PdfTextExtractor",
    "TableExtractor",
    "ExtractedTable",
    "parse_currency",
    "generate_item_id",
    
    "extract_cpf",
    "extract_cnpj",
    "extract_currency",
    "extract_date",
    "normalize_cpf",
    "normalize_cnpj",
    "validate_cpf",
    "validate_cnpj",
]
