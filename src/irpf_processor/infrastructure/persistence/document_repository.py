"""Repositório de documentos no MongoDB."""

import time
from datetime import datetime
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from irpf_processor.domain.entities.document import Document
from irpf_processor.domain.enums import DocumentStatus
from irpf_processor.shared.logging import get_logger
from irpf_processor.shared.metrics import (
    DATABASE_OPERATIONS_TOTAL,
    DATABASE_OPERATION_DURATION_SECONDS,
)

logger = get_logger(__name__)


class MongoDocumentRepository:
    """Implementação do repositório de documentos usando MongoDB."""

    COLLECTION_NAME = "documents"

    def __init__(self, database: AsyncIOMotorDatabase) -> None:
        self._db = database
        self._collection = database[self.COLLECTION_NAME]

    async def create(self, document: Document) -> None:
        doc_dict = {
            "document_id": document.document_id,
            "tenant_id": document.tenant_id,
            "filename": document.filename,
            "content_type": document.content_type,
            "storage_uri": document.storage_uri,
            "sha256": document.sha256,
            "status": document.status.value,
            "pdf_type": document.pdf_type.value if document.pdf_type else None,
            "confidence": document.confidence,
            "error_message": document.error_message,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
        }

        start_time = time.perf_counter()
        status = "success"
        try:
            await self._collection.insert_one(doc_dict)
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            DATABASE_OPERATIONS_TOTAL.labels(
                collection=self.COLLECTION_NAME, operation="insert", status=status
            ).inc()
            DATABASE_OPERATION_DURATION_SECONDS.labels(
                collection=self.COLLECTION_NAME, operation="insert"
            ).observe(duration)

        logger.info(
            "Document created",
            document_id=document.document_id,
            tenant_id=document.tenant_id,
            status=document.status.value,
        )

    async def get_by_id(
        self, document_id: str, tenant_id: str
    ) -> Optional[Document]:
        start_time = time.perf_counter()
        status = "success"
        try:
            doc = await self._collection.find_one({
                "document_id": document_id,
                "tenant_id": tenant_id,
            })
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            DATABASE_OPERATIONS_TOTAL.labels(
                collection=self.COLLECTION_NAME, operation="find_one", status=status
            ).inc()
            DATABASE_OPERATION_DURATION_SECONDS.labels(
                collection=self.COLLECTION_NAME, operation="find_one"
            ).observe(duration)

        if not doc:
            return None

        return self._to_entity(doc)

    async def get_by_sha256(
        self, sha256: str, tenant_id: str
    ) -> Optional[Document]:
        start_time = time.perf_counter()
        status = "success"
        try:
            doc = await self._collection.find_one({
                "tenant_id": tenant_id,
                "sha256": sha256,
            })
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            DATABASE_OPERATIONS_TOTAL.labels(
                collection=self.COLLECTION_NAME, operation="find_one", status=status
            ).inc()
            DATABASE_OPERATION_DURATION_SECONDS.labels(
                collection=self.COLLECTION_NAME, operation="find_one"
            ).observe(duration)

        if not doc:
            return None

        return self._to_entity(doc)

    async def find_by_sha256(
        self, tenant_id: str, sha256: str
    ) -> Optional[Document]:
        return await self.get_by_sha256(sha256, tenant_id)

    async def update(self, document: Document) -> None:
        doc_dict = {
            "filename": document.filename,
            "content_type": document.content_type,
            "storage_uri": document.storage_uri,
            "sha256": document.sha256,
            "status": document.status.value,
            "pdf_type": document.pdf_type.value if document.pdf_type else None,
            "confidence": document.confidence,
            "error_message": document.error_message,
            "updated_at": datetime.utcnow(),
        }

        start_time = time.perf_counter()
        status = "success"
        try:
            await self._collection.update_one(
                {"document_id": document.document_id, "tenant_id": document.tenant_id},
                {"$set": doc_dict},
            )
        except Exception:
            status = "error"
            raise
        finally:
            duration = time.perf_counter() - start_time
            DATABASE_OPERATIONS_TOTAL.labels(
                collection=self.COLLECTION_NAME, operation="update_one", status=status
            ).inc()
            DATABASE_OPERATION_DURATION_SECONDS.labels(
                collection=self.COLLECTION_NAME, operation="update_one"
            ).observe(duration)

        logger.info(
            "Document updated",
            document_id=document.document_id,
            status=document.status.value,
        )

    async def delete(self, document_id: str, tenant_id: str) -> None:
        await self._collection.delete_one({
            "document_id": document_id,
            "tenant_id": tenant_id,
        })

        logger.info(
            "Document deleted",
            document_id=document_id,
            tenant_id=tenant_id,
        )

    async def list_by_status(
        self, tenant_id: str, status: str, limit: int = 100
    ) -> list[Document]:
        query = {"tenant_id": tenant_id, "status": status}

        cursor = self._collection.find(query).limit(limit).sort("created_at", -1)

        documents = []
        async for doc in cursor:
            documents.append(self._to_entity(doc))

        return documents

    async def update_status(
        self,
        document_id: str,
        tenant_id: str,
        status: DocumentStatus,
        pdf_type: Optional[str] = None,
        confidence: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        update_fields = {
            "status": status.value,
            "updated_at": datetime.utcnow(),
        }

        if pdf_type is not None:
            update_fields["pdf_type"] = pdf_type
        if confidence is not None:
            update_fields["confidence"] = confidence
        if error_message is not None:
            update_fields["error_message"] = error_message

        result = await self._collection.update_one(
            {"document_id": document_id, "tenant_id": tenant_id},
            {"$set": update_fields},
        )

        if result.modified_count > 0:
            logger.info(
                "Document status updated",
                document_id=document_id,
                status=status.value,
            )

        return result.modified_count > 0

    async def list_by_tenant(
        self,
        tenant_id: str,
        status: Optional[DocumentStatus] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> list[Document]:
        query = {"tenant_id": tenant_id}

        if status:
            query["status"] = status.value

        cursor = self._collection.find(query).skip(skip).limit(limit).sort("created_at", -1)

        documents = []
        async for doc in cursor:
            documents.append(self._to_entity(doc))

        return documents

    def _to_entity(self, doc: dict) -> Document:
        from irpf_processor.domain.enums import PdfType

        pdf_type = None
        if doc.get("pdf_type"):
            pdf_type = PdfType(doc["pdf_type"])

        return Document(
            document_id=doc["document_id"],
            tenant_id=doc["tenant_id"],
            filename=doc["filename"],
            content_type=doc["content_type"],
            storage_uri=doc["storage_uri"],
            sha256=doc.get("sha256"),
            status=DocumentStatus(doc["status"]),
            pdf_type=pdf_type,
            confidence=doc.get("confidence"),
            error_message=doc.get("error_message"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )
