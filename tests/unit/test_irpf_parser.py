"""Testes unitários para o parser de IRPF."""

import pytest
from pathlib import Path

from irpf_processor.infrastructure.extraction import (
    IRPFParser,
    IRPFDeclarationResult,
    VersionDetector,
    DocumentProfile,
    ExtractionContext,
    TaxpayerExtractor,
)


DOCS_DIR = Path(__file__).parent.parent.parent / "docs" / "IRPF"
PDF_FILE = DOCS_DIR / "Geral-IRPF-2025-2024.pdf"


class TestVersionDetector:
    """Testes do detector de versão."""
    
    def test_detect_exercise_year(self):
        detector = VersionDetector()
        
        context = ExtractionContext(
            full_text="DECLARAÇÃO DE AJUSTE ANUAL EXERCÍCIO 2025 ANO-CALENDÁRIO 2024",
            pages_text={1: ""},
            total_pages=1
        )
        
        profile = detector.detect(context)
        
        assert profile.exercise_year == "2025"
        assert profile.calendar_year == "2024"
    
    def test_detect_taxpayer_cpf(self):
        detector = VersionDetector()
        
        context = ExtractionContext(
            full_text="CPF: 886.978.040-60\nNome: GENESIS LOPES",
            pages_text={1: ""},
            total_pages=1
        )
        
        profile = detector.detect(context)
        
        assert "886" in profile.taxpayer_cpf or "886.978.040-60" in profile.taxpayer_cpf
    
    def test_detect_sections(self):
        detector = VersionDetector()
        
        context = ExtractionContext(
            full_text="""
            DECLARAÇÃO DE BENS E DIREITOS
            RENDIMENTOS ISENTOS E NÃO TRIBUTÁVEIS
            ATIVIDADE RURAL
            """,
            pages_text={1: ""},
            total_pages=1
        )
        
        profile = detector.detect(context)
        
        assert "assets_declaration" in profile.detected_sections
        assert "exempt_income" in profile.detected_sections
    
    def test_has_section_method(self):
        profile = DocumentProfile()
        profile.detected_sections = ["assets_declaration", "exempt_income"]
        
        assert profile.has_section("assets_declaration") is True
        assert profile.has_section("income_pj") is False
    
    def test_profile_to_dict(self):
        profile = DocumentProfile(
            exercise_year="2025",
            calendar_year="2024",
            taxpayer_name="TEST",
            total_pages=5
        )
        
        result = profile.to_dict()
        
        assert isinstance(result, dict)
        assert result["exercise_year"] == "2025"
        assert result["total_pages"] == 5


class TestIRPFParser:
    """Testes para o parser de IRPF."""
    
    @pytest.fixture
    def sample_irpf_text(self) -> str:
        return """
        DECLARAÇÃO DE AJUSTE ANUAL
        EXERCÍCIO 2025
        Ano-calendário 2024
        
        IDENTIFICAÇÃO DO CONTRIBUINTE
        CPF: 886.978.040-60
        Nome: GENESIS LOPES
        
        Natureza da Ocupação: PROPRIETÁRIO DE EMPRESA
        
        DECLARAÇÃO DE BENS E DIREITOS
        Total: R$ 25.040.026,18
        """
    
    def test_parser_creates_extractors_dynamically(self):
        parser = IRPFParser(auto_detect=True)
        assert hasattr(parser, "_version_detector")
    
    def test_parser_with_custom_extractors(self):
        custom_extractors = [TaxpayerExtractor()]
        parser = IRPFParser(extractors=custom_extractors, auto_detect=False)
        
        assert parser._custom_extractors == custom_extractors
    
    def test_get_document_profile_initially_none(self):
        parser = IRPFParser()
        assert parser.get_document_profile() is None
    
    @pytest.mark.skipif(not PDF_FILE.exists(), reason="PDF file not found")
    def test_parse_real_pdf(self):
        parser = IRPFParser()
        result = parser.parse(PDF_FILE)
        
        assert result is not None
        assert result.total_pages == 11
        
        profile = parser.get_document_profile()
        assert profile is not None
        assert profile.exercise_year == "2025"


class TestExtractionContext:
    """Testes do contexto de extração."""
    
    def test_create_context(self):
        context = ExtractionContext(
            full_text="Sample text",
            pages_text={1: "Page 1", 2: "Page 2"},
            total_pages=2
        )
        
        assert context.full_text == "Sample text"
        assert len(context.pages_text) == 2
        assert context.total_pages == 2
    
    def test_context_add_warning(self):
        context = ExtractionContext(
            full_text="",
            pages_text={},
            total_pages=0
        )
        
        context.add_warning("Test warning")
        
        assert "Test warning" in context.warnings


class TestTaxpayerExtractor:
    """Testes do extrator de contribuinte."""
    
    def test_section_name(self):
        extractor = TaxpayerExtractor()
        assert extractor.section_name == "taxpayer_identification"
    
    def test_can_extract_returns_bool(self):
        extractor = TaxpayerExtractor()
        
        context = ExtractionContext(
            full_text="Any text with DECLARAÇÃO DE AJUSTE ANUAL",
            pages_text={1: ""},
            total_pages=1
        )
        
        result = extractor.can_extract(context)
        assert isinstance(result, bool)
    
    def test_extract_cpf(self):
        extractor = TaxpayerExtractor()
        
        context = ExtractionContext(
            full_text="CPF: 886.978.040-60\nNome: TEST\nEXERCÍCIO 2025",
            pages_text={1: ""},
            total_pages=1
        )
        
        result = extractor.extract(context)
        
        assert result["normalized_cpf"] == "88697804060"
    
    def test_extract_name(self):
        extractor = TaxpayerExtractor()
        
        context = ExtractionContext(
            full_text="CPF: 886.978.040-60\nNome: GENESIS LOPES\nEXERCÍCIO 2025",
            pages_text={1: ""},
            total_pages=1
        )
        
        result = extractor.extract(context)
        
        assert result["name"] == "GENESIS LOPES"
    
    def test_extract_exercise_year(self):
        extractor = TaxpayerExtractor()
        
        context = ExtractionContext(
            full_text="EXERCÍCIO 2025 ANO-CALENDÁRIO 2024\nCPF: 123.456.789-09",
            pages_text={1: ""},
            total_pages=1
        )
        
        result = extractor.extract(context)
        
        assert result["exercise_year"] == "2025"
        assert result["calendar_year"] == "2024"


class TestIRPFDeclarationResult:
    """Testes do resultado da declaração."""
    
    def test_default_values(self):
        result = IRPFDeclarationResult(total_pages=1)
        
        assert result.total_pages == 1
        assert result.confidence == 0.0
        assert result.warnings == []
        assert result.taxpayer_identification == {}
        assert result.assets_declaration is None
    
    def test_with_data(self):
        result = IRPFDeclarationResult(
            total_pages=11,
            taxpayer_identification={"cpf": "12345678900"},
            assets_declaration={"items": []},
            confidence=0.95,
            warnings=["Warning 1"]
        )
        
        assert result.total_pages == 11
        assert result.taxpayer_identification["cpf"] == "12345678900"
        assert result.confidence == 0.95
        assert len(result.warnings) == 1
    
    def test_to_dict_has_required_keys(self):
        result = IRPFDeclarationResult(
            total_pages=11,
            taxpayer_identification={"cpf": "123"},
            assets_declaration={"items": [{"id": "1"}]},
        )
        
        d = result.to_dict()
        
        assert "total_pages" in d
        assert "taxpayer_identification" in d
        assert "assets_declaration" in d
        assert d["total_pages"] == 11
        assert d["taxpayer_identification"]["cpf"] == "123"
        assert len(d["assets_declaration"]["items"]) == 1
    
    def test_to_dict_structure(self):
        result = IRPFDeclarationResult(total_pages=5)
        d = result.to_dict()
        
        expected_keys = [
            "taxpayer_identification",
            "total_value",
            "valid_total",
            "assets_declaration",
            "exempt_income",
            "income_from_legal_person_to_holder",
            "total_pages"
        ]
        
        for key in expected_keys:
            assert key in d, f"Missing key: {key}"
