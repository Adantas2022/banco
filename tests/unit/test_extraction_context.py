import pytest

from irpf_processor.infrastructure.extraction.extractors.base import (
    ExtractionContext,
    ISectionExtractor,
)


class TestExtractionContext:

    def test_create_context(self):
        context = ExtractionContext(
            full_text="Full document text",
            pages_text={1: "Page 1 text", 2: "Page 2 text"},
            total_pages=2,
        )

        assert context.full_text == "Full document text"
        assert context.total_pages == 2
        assert len(context.pages_text) == 2

    def test_default_warnings_empty(self):
        context = ExtractionContext(
            full_text="",
            pages_text={},
            total_pages=0,
        )

        assert context.warnings == []

    def test_add_warning(self):
        context = ExtractionContext(
            full_text="",
            pages_text={},
            total_pages=0,
        )

        context.add_warning("Warning message")

        assert len(context.warnings) == 1
        assert context.warnings[0] == "Warning message"

    def test_add_multiple_warnings(self):
        context = ExtractionContext(
            full_text="",
            pages_text={},
            total_pages=0,
        )

        context.add_warning("Warning 1")
        context.add_warning("Warning 2")
        context.add_warning("Warning 3")

        assert len(context.warnings) == 3

    def test_get_page_text_existing_page(self):
        context = ExtractionContext(
            full_text="",
            pages_text={1: "First page", 2: "Second page", 3: "Third page"},
            total_pages=3,
        )

        assert context.get_page_text(1) == "First page"
        assert context.get_page_text(2) == "Second page"
        assert context.get_page_text(3) == "Third page"

    def test_get_page_text_nonexistent_page(self):
        context = ExtractionContext(
            full_text="",
            pages_text={1: "Page 1"},
            total_pages=1,
        )

        result = context.get_page_text(99)

        assert result == ""

    def test_find_pages_containing_single_match(self):
        context = ExtractionContext(
            full_text="",
            pages_text={
                1: "This is the first page",
                2: "DECLARACAO DE BENS E DIREITOS",
                3: "This is the third page",
            },
            total_pages=3,
        )

        result = context.find_pages_containing("DECLARACAO DE BENS")

        assert result == [2]

    def test_find_pages_containing_multiple_matches(self):
        context = ExtractionContext(
            full_text="",
            pages_text={
                1: "CPF: 123.456.789-00",
                2: "Some other content",
                3: "CPF: 987.654.321-00",
            },
            total_pages=3,
        )

        result = context.find_pages_containing("CPF")

        assert 1 in result
        assert 3 in result
        assert 2 not in result

    def test_find_pages_containing_no_match(self):
        context = ExtractionContext(
            full_text="",
            pages_text={
                1: "Page one",
                2: "Page two",
            },
            total_pages=2,
        )

        result = context.find_pages_containing("NONEXISTENT")

        assert result == []

    def test_find_pages_containing_case_insensitive(self):
        context = ExtractionContext(
            full_text="",
            pages_text={
                1: "declaracao de ajuste anual",
                2: "DECLARACAO DE AJUSTE ANUAL",
                3: "Declaracao De Ajuste Anual",
            },
            total_pages=3,
        )

        result = context.find_pages_containing("DECLARACAO DE AJUSTE")

        assert 1 in result
        assert 2 in result
        assert 3 in result

    def test_find_pages_containing_empty_pages(self):
        context = ExtractionContext(
            full_text="",
            pages_text={
                1: "",
                2: "Content here",
                3: "",
            },
            total_pages=3,
        )

        result = context.find_pages_containing("Content")

        assert result == [2]


class TestISectionExtractor:

    def test_interface_cannot_be_instantiated(self):
        with pytest.raises(TypeError):
            ISectionExtractor()

    def test_concrete_implementation(self):
        class ConcreteSectionExtractor(ISectionExtractor):
            @property
            def section_name(self) -> str:
                return "test_section"

            def can_extract(self, context: ExtractionContext) -> bool:
                return "TEST" in context.full_text.upper()

            def extract(self, context: ExtractionContext):
                return {"extracted": True}

        extractor = ConcreteSectionExtractor()

        assert extractor.section_name == "test_section"

        context_with_test = ExtractionContext(
            full_text="This is a TEST document",
            pages_text={},
            total_pages=1,
        )
        assert extractor.can_extract(context_with_test) is True

        context_without_test = ExtractionContext(
            full_text="This document has no keyword",
            pages_text={},
            total_pages=1,
        )
        assert extractor.can_extract(context_without_test) is False

        result = extractor.extract(context_with_test)
        assert result == {"extracted": True}
