"""Testes unitários para extraction_texts_repository.

Task #87259 - Verifica o armazenamento e recuperação de textos usados
na extração via REGEX.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

from irpf_processor.infrastructure.persistence.extraction_texts_repository import (
    save_extraction_texts,
    get_extraction_texts,
    COLLECTION_NAME,
)


@pytest.fixture
def mock_db():
    """Cria um mock do banco MongoDB."""
    db = MagicMock()
    db[COLLECTION_NAME] = MagicMock()
    return db


class TestSaveExtractionTexts:

    def test_saves_with_correct_structure(self, mock_db):
        """Deve salvar documento com estrutura correta no MongoDB."""
        result = save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="Texto completo do documento",
            pages_text={1: "Página 1", 2: "Página 2"},
            total_pages=2,
        )

        assert result is True
        mock_db[COLLECTION_NAME].update_one.assert_called_once()

        # Verificar argumentos do update_one
        args = mock_db[COLLECTION_NAME].update_one.call_args
        filter_doc = args[0][0]
        update_doc = args[0][1]

        assert filter_doc == {"document_id": "doc-123", "tenant_id": "tenant-xyz"}
        assert "$set" in update_doc
        assert "$setOnInsert" in update_doc

        set_doc = update_doc["$set"]
        assert set_doc["document_id"] == "doc-123"
        assert set_doc["tenant_id"] == "tenant-xyz"
        assert set_doc["document_type"] == "DIGITAL"
        assert set_doc["full_text"] == "Texto completo do documento"
        assert set_doc["total_pages"] == 2

    def test_converts_page_keys_to_strings(self, mock_db):
        """Deve converter keys de páginas de int para string (MongoDB requirement)."""
        save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="texto",
            pages_text={1: "P1", 2: "P2", 10: "P10"},
            total_pages=10,
        )

        args = mock_db[COLLECTION_NAME].update_one.call_args
        pages = args[0][1]["$set"]["pages_text"]
        assert all(isinstance(k, str) for k in pages.keys())
        assert pages == {"1": "P1", "2": "P2", "10": "P10"}

    def test_uses_upsert(self, mock_db):
        """Deve usar upsert=True para criar ou atualizar."""
        save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="texto",
            pages_text={1: "P1"},
            total_pages=1,
        )

        args = mock_db[COLLECTION_NAME].update_one.call_args
        assert args[1]["upsert"] is True

    def test_includes_timestamps(self, mock_db):
        """Deve incluir updated_at no $set e created_at no $setOnInsert."""
        save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="texto",
            pages_text={1: "P1"},
            total_pages=1,
        )

        args = mock_db[COLLECTION_NAME].update_one.call_args
        update_doc = args[0][1]

        assert "updated_at" in update_doc["$set"]
        assert "created_at" in update_doc["$setOnInsert"]
        assert isinstance(update_doc["$set"]["updated_at"], datetime)
        assert isinstance(update_doc["$setOnInsert"]["created_at"], datetime)

    def test_returns_false_on_error(self, mock_db):
        """Deve retornar False (e não levantar exceção) quando MongoDB falha."""
        mock_db[COLLECTION_NAME].update_one.side_effect = Exception("Connection failed")

        result = save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="texto",
            pages_text={1: "P1"},
            total_pages=1,
        )

        assert result is False

    def test_never_raises_exception(self, mock_db):
        """Deve NUNCA propagar exceções — padrão fire-and-forget."""
        mock_db[COLLECTION_NAME].update_one.side_effect = RuntimeError("Catastrophic DB failure")

        # Não deve levantar exceção
        result = save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="texto",
            pages_text={1: "P1"},
            total_pages=1,
        )

        assert result is False

    def test_saves_image_document_type(self, mock_db):
        """Deve salvar com document_type IMAGE para documentos OCR."""
        save_extraction_texts(
            db=mock_db,
            document_id="doc-456",
            tenant_id="tenant-abc",
            document_type="IMAGE",
            full_text="Texto OCR",
            pages_text={1: "OCR P1"},
            total_pages=1,
        )

        args = mock_db[COLLECTION_NAME].update_one.call_args
        assert args[0][1]["$set"]["document_type"] == "IMAGE"

    def test_handles_empty_pages_text(self, mock_db):
        """Deve lidar com dicionário de páginas vazio."""
        result = save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text="",
            pages_text={},
            total_pages=0,
        )

        assert result is True
        args = mock_db[COLLECTION_NAME].update_one.call_args
        assert args[0][1]["$set"]["pages_text"] == {}

    def test_handles_large_text(self, mock_db):
        """Deve lidar com textos grandes sem erro."""
        large_text = "A" * 1_000_000  # 1MB de texto
        result = save_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
            document_type="DIGITAL",
            full_text=large_text,
            pages_text={1: large_text},
            total_pages=1,
        )

        assert result is True


class TestGetExtractionTexts:

    def test_returns_document_when_found(self, mock_db):
        """Deve retornar o documento encontrado."""
        expected = {
            "document_id": "doc-123",
            "tenant_id": "tenant-xyz",
            "full_text": "Texto completo",
            "pages_text": {"1": "Página 1"},
        }
        mock_db[COLLECTION_NAME].find_one.return_value = expected

        result = get_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
        )

        assert result == expected

    def test_excludes_mongo_id(self, mock_db):
        """Deve excluir o campo _id do MongoDB na query."""
        get_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
        )

        args = mock_db[COLLECTION_NAME].find_one.call_args
        # Segundo argumento é a projeção
        assert args[0][1] == {"_id": 0}

    def test_returns_none_when_not_found(self, mock_db):
        """Deve retornar None quando documento não é encontrado."""
        mock_db[COLLECTION_NAME].find_one.return_value = None

        result = get_extraction_texts(
            db=mock_db,
            document_id="nonexistent",
            tenant_id="tenant-xyz",
        )

        assert result is None

    def test_returns_none_on_error(self, mock_db):
        """Deve retornar None (e não levantar exceção) quando MongoDB falha."""
        mock_db[COLLECTION_NAME].find_one.side_effect = Exception("Connection failed")

        result = get_extraction_texts(
            db=mock_db,
            document_id="doc-123",
            tenant_id="tenant-xyz",
        )

        assert result is None


class TestIRPFParserLastContext:
    """Testes para a property last_extraction_context do IRPFParser."""

    def test_last_context_is_none_before_parsing(self):
        """Deve ser None antes de qualquer parsing."""
        from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser

        parser = IRPFParser()
        assert parser.last_extraction_context is None

    def test_last_context_contains_text_after_parse_from_pages_text(self):
        """Deve conter os textos após parse_from_pages_text."""
        from irpf_processor.infrastructure.extraction.irpf_parser import IRPFParser

        parser = IRPFParser()
        pages = {1: "DECLARAÇÃO COMPLETA DO IRPF\nAno 2024"}

        result = parser.parse_from_pages_text(
            pages_text=pages,
            full_text="DECLARAÇÃO COMPLETA DO IRPF\nAno 2024",
            total_pages=1,
        )

        ctx = parser.last_extraction_context
        assert ctx is not None
        assert "DECLARAÇÃO COMPLETA DO IRPF" in ctx.full_text
        assert 1 in ctx.pages_text
