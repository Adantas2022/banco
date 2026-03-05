"""Repositório para armazenar textos usados na extração via REGEX.

Task #87259 - MongoDB: Armazenar os textos das expressões regulares.

Armazena na coleção `extraction_texts` os textos (full_text e pages_text)
utilizados durante a aplicação de REGEX nos documentos DIGITAL e IMAGEM/MIXED.
"""

from datetime import datetime, timezone
from typing import Optional

from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

COLLECTION_NAME = "extraction_texts"


def save_extraction_texts(
    db,
    document_id: str,
    tenant_id: str,
    document_type: str,
    full_text: str,
    pages_text: dict[int, str],
    total_pages: int,
) -> bool:
    """Salva ou atualiza os textos usados na extração REGEX.

    Os textos são armazenados na coleção `extraction_texts` e identificados
    pelo `document_id` + `tenant_id`. Se já existir um registro para o mesmo
    documento, ele é atualizado (upsert).

    Args:
        db: Instância sync do banco MongoDB (PyMongo).
        document_id: ID único do documento.
        tenant_id: ID do tenant.
        document_type: Tipo do documento ("DIGITAL" ou "IMAGE").
        full_text: Texto completo extraído do documento.
        pages_text: Dicionário com texto por página {pagina: texto}.
        total_pages: Total de páginas do documento.

    Returns:
        True se salvou com sucesso, False em caso de erro.
    """
    try:
        # MongoDB não aceita chaves inteiras em subdocumentos,
        # então convertemos para string
        pages_text_str_keys = {
            str(page_num): text
            for page_num, text in pages_text.items()
        }

        now = datetime.now(timezone.utc)

        extraction_text_doc = {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "document_type": document_type,
            "full_text": full_text,
            "pages_text": pages_text_str_keys,
            "total_pages": total_pages,
            "updated_at": now,
        }

        db[COLLECTION_NAME].update_one(
            {"document_id": document_id, "tenant_id": tenant_id},
            {
                "$set": extraction_text_doc,
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

        logger.info(
            "Extraction texts saved",
            document_id=document_id,
            tenant_id=tenant_id,
            document_type=document_type,
            total_pages=total_pages,
            text_length=len(full_text),
        )
        return True

    except Exception as e:
        # Falha no armazenamento de textos NÃO deve interromper o pipeline
        # de extração. Logamos o erro e seguimos em frente.
        logger.error(
            "Failed to save extraction texts",
            document_id=document_id,
            tenant_id=tenant_id,
            error=str(e),
        )
        return False


def get_extraction_texts(
    db,
    document_id: str,
    tenant_id: str,
) -> Optional[dict]:
    """Recupera os textos armazenados para um documento.

    Args:
        db: Instância sync do banco MongoDB (PyMongo).
        document_id: ID único do documento.
        tenant_id: ID do tenant.

    Returns:
        Dicionário com os dados ou None se não encontrado.
    """
    try:
        return db[COLLECTION_NAME].find_one(
            {"document_id": document_id, "tenant_id": tenant_id},
            {"_id": 0},
        )
    except Exception as e:
        logger.error(
            "Failed to get extraction texts",
            document_id=document_id,
            tenant_id=tenant_id,
            error=str(e),
        )
        return None
