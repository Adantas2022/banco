"""Testes unitarios para os novos extratores."""

import pytest
from irpf_processor.infrastructure.extraction.extractors import (
    IncomePJDependentsExtractor,
    IncomePFExtractor,
    AccumulatedIncomePJExtractor,
    ExtractionContext,
)
from irpf_processor.infrastructure.extraction.extractors.rural import (
    LivestockMovementExtractor,
)


class TestIncomePJDependentsExtractor:
    """Testes para IncomePJDependentsExtractor."""
    
    @pytest.fixture
    def extractor(self):
        return IncomePJDependentsExtractor()
    
    @pytest.fixture
    def sample_text(self):
        return """
        RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOAS JURÍDICAS PELOS DEPENDENTES
        
        EMPRESA XYZ LTDA                    50.000,00    5.500,00    7.500,00    4.166,67    625,00
        12.345.678/0001-90
        Dependente: JOAO DA SILVA
        CPF: 123.456.789-00
        
        EMPRESA ABC SA                      30.000,00    3.300,00    4.500,00    2.500,00    375,00
        98.765.432/0001-10
        Dependente: MARIA DA SILVA
        CPF: 987.654.321-00
        
        TOTAL                               80.000,00    8.800,00   12.000,00    6.666,67  1.000,00
        """
    
    @pytest.fixture
    def context(self, sample_text):
        return ExtractionContext(
            full_text=sample_text,
            pages_text={1: sample_text},
            total_pages=1
        )
    
    def test_can_extract_with_section_marker(self, extractor, context):
        assert extractor.can_extract(context) is True
    
    def test_cannot_extract_without_marker(self, extractor):
        context = ExtractionContext(
            full_text="Some random text without the marker",
            pages_text={1: "Some random text"},
            total_pages=1
        )
        assert extractor.can_extract(context) is False
    
    def test_section_name(self, extractor):
        assert extractor.section_name == "income_from_legal_person_to_dependents"


class TestIncomePFExtractor:
    """Testes para IncomePFExtractor."""
    
    @pytest.fixture
    def extractor(self):
        return IncomePFExtractor()
    
    @pytest.fixture
    def sample_text(self):
        return """
        RENDIMENTOS TRIBUTÁVEIS RECEBIDOS DE PESSOA FÍSICA E DO EXTERIOR PELO TITULAR
        
        JOAO DA SILVA                       100.000,00   10.000,00   15.000,00    5.000,00    2.000,00
        123.456.789-00
        
        TOTAL                               100.000,00   10.000,00   15.000,00    5.000,00    2.000,00
        """
    
    @pytest.fixture
    def context(self, sample_text):
        return ExtractionContext(
            full_text=sample_text,
            pages_text={1: sample_text},
            total_pages=1
        )
    
    def test_can_extract_with_section_marker(self, extractor, context):
        assert extractor.can_extract(context) is True
    
    def test_cannot_extract_without_marker(self, extractor):
        context = ExtractionContext(
            full_text="Some random text without the marker",
            pages_text={1: "Some random text"},
            total_pages=1
        )
        assert extractor.can_extract(context) is False
    
    def test_section_name(self, extractor):
        assert extractor.section_name == "income_from_individual_to_holder"


class TestAccumulatedIncomePJExtractor:
    """Testes para AccumulatedIncomePJExtractor."""
    
    @pytest.fixture
    def extractor(self):
        return AccumulatedIncomePJExtractor()
    
    @pytest.fixture
    def sample_text(self):
        return """
        RENDIMENTOS TRIBUTÁVEIS DE PESSOA JURÍDICA RECEBIDOS ACUMULADAMENTE PELO TITULAR
        
        EMPRESA XYZ LTDA                    200.000,00   22.000,00   30.000,00   10.000,00
        12.345.678/0001-90
        Meses: 36
        
        TOTAL                               200.000,00   22.000,00   30.000,00   10.000,00
        """
    
    @pytest.fixture
    def context(self, sample_text):
        return ExtractionContext(
            full_text=sample_text,
            pages_text={1: sample_text},
            total_pages=1
        )
    
    def test_can_extract_with_section_marker(self, extractor, context):
        assert extractor.can_extract(context) is True
    
    def test_cannot_extract_without_marker(self, extractor):
        context = ExtractionContext(
            full_text="Some random text without the marker",
            pages_text={1: "Some random text"},
            total_pages=1
        )
        assert extractor.can_extract(context) is False
    
    def test_section_name(self, extractor):
        assert extractor.section_name == "accumulated_income_from_legal_person_to_holder"


class TestLivestockMovementExtractor:
    """Testes para LivestockMovementExtractor."""
    
    @pytest.fixture
    def extractor(self):
        return LivestockMovementExtractor()
    
    @pytest.fixture
    def sample_text(self):
        return """
        MOVIMENTAÇÃO DO REBANHO - BRASIL
        
        CÓDIGO  ESPÉCIE        QUANTIDADE   NASCIMENTO  COMPRAS   MORTES    VENDAS
                               EM 01/01
        01      BOVINOS        100          20          10        5         30
        02      EQUINOS        50           5           2         1         10
        
        TOTAL                  150          25          12        6         40
        """
    
    @pytest.fixture
    def context(self, sample_text):
        return ExtractionContext(
            full_text=sample_text,
            pages_text={1: sample_text},
            total_pages=1
        )
    
    def test_can_extract_with_section_marker(self, extractor, context):
        assert extractor.can_extract(context) is True
    
    def test_cannot_extract_without_marker(self, extractor):
        context = ExtractionContext(
            full_text="Some random text without the marker",
            pages_text={1: "Some random text"},
            total_pages=1
        )
        assert extractor.can_extract(context) is False
    
    def test_section_name(self, extractor):
        assert extractor.section_name == "livestock_movement_in_brazil"


class TestExtractorImports:
    """Testes para verificar que os novos extratores sao importaveis."""
    
    def test_income_pj_dependents_import(self):
        from irpf_processor.infrastructure.extraction.extractors import IncomePJDependentsExtractor
        extractor = IncomePJDependentsExtractor()
        assert extractor is not None
    
    def test_income_pf_import(self):
        from irpf_processor.infrastructure.extraction.extractors import IncomePFExtractor
        extractor = IncomePFExtractor()
        assert extractor is not None
    
    def test_accumulated_income_pj_import(self):
        from irpf_processor.infrastructure.extraction.extractors import AccumulatedIncomePJExtractor
        extractor = AccumulatedIncomePJExtractor()
        assert extractor is not None
    
    def test_livestock_movement_import(self):
        from irpf_processor.infrastructure.extraction.extractors.rural import LivestockMovementExtractor
        extractor = LivestockMovementExtractor()
        assert extractor is not None
