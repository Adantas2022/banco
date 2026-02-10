import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from pydantic import BaseModel

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.entities.document import Document
from irpf_processor.domain.enums import AuthScope, DocumentStatus
from irpf_processor.infrastructure.persistence.database import get_database
from irpf_processor.infrastructure.persistence.document_repository import MongoDocumentRepository
from irpf_processor.infrastructure.storage import get_storage_service
from irpf_processor.config import get_settings
from irpf_processor.presentation.api.dependencies import CurrentTenant, require_scope
from irpf_processor.presentation.workers.router_worker import route_document
from irpf_processor.shared.logging import get_logger


class MonetaryEncoder(json.JSONEncoder):
    def iterencode(self, o, _one_shot=False):
        if isinstance(o, float):
            yield f"{o:.2f}"
        elif isinstance(o, dict):
            yield "{"
            first = True
            for key, value in o.items():
                if not first:
                    yield ", "
                first = False
                yield from self.iterencode(key)
                yield ": "
                yield from self.iterencode(value)
            yield "}"
        elif isinstance(o, list):
            yield "["
            first = True
            for item in o:
                if not first:
                    yield ", "
                first = False
                yield from self.iterencode(item)
            yield "]"
        else:
            yield from super().iterencode(o, _one_shot)
from irpf_processor.shared.metrics import record_document_upload, record_queue_send_failure, record_failure

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/documents", tags=["Documents"])


class UploadResponse(BaseModel):
    document_id: str
    status: str
    message: str
    warnings: Optional[list[str]] = None


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    pdf_type: Optional[str] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str


async def get_document_repository():
    db = await get_database()
    return MongoDocumentRepository(db)


async def get_storage_service_dependency():
    return get_storage_service()


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    tenant_id: CurrentTenant,
    file: UploadFile = File(...),
    force: bool = False,
    _: Annotated[ApiKey, Depends(require_scope(AuthScope.DOCUMENTS_WRITE.value))] = None,
    doc_repo: MongoDocumentRepository = Depends(get_document_repository),
    storage = Depends(get_storage_service_dependency),
) -> UploadResponse:
    """Upload de documento PDF para processamento assíncrono.
    
    Args:
        file: Arquivo PDF para processar
        force: Se True, reprocessa mesmo se o documento já existir (ignora cache SHA256)
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    sha256 = Document.calculate_sha256(content)

    settings = get_settings()
    
    # Verificar duplicata apenas se:
    # 1. force=False (parâmetro da request)
    # 2. SKIP_DUPLICATE_CHECK=false (variável de ambiente)
    skip_check = force or settings.skip_duplicate_check
    
    if not skip_check:
        existing = await doc_repo.find_by_sha256(tenant_id, sha256)
        if existing:
            logger.info(
                "Duplicate document detected",
                existing_id=existing.document_id,
                sha256=sha256,
            )
            return UploadResponse(
                document_id=existing.document_id,
                status=existing.status.value,
                message="Document already exists. Use force=true to reprocess.",
            )
    else:
        logger.info(
            "Duplicate check skipped",
            sha256=sha256,
            reason="force=true" if force else "SKIP_DUPLICATE_CHECK=true",
        )

    document = Document(
        tenant_id=tenant_id,
        filename=file.filename,
        content_type=file.content_type or "application/pdf",
        storage_uri="",
        sha256=sha256,
    )

    storage_key = f"{tenant_id}/{document.document_id}/{file.filename}"
    warnings: list[str] = []

    try:
        storage_uri = await storage.upload(
            content=content,
            key=storage_key,
            content_type=document.content_type,
        )
        document.storage_uri = storage_uri
    except Exception as e:
        logger.error(
            "Failed to upload document to storage",
            document_id=document.document_id,
            tenant_id=tenant_id,
            error=str(e),
        )
        record_failure(tenant_id, "upload", "storage_unavailable")
        warnings.append("Document was not saved to storage. Storage service may be unavailable.")

    await doc_repo.create(document)

    record_document_upload(tenant_id, len(content))

    logger.info(
        "Document uploaded",
        document_id=document.document_id,
        tenant_id=tenant_id,
        filename=file.filename,
        size_bytes=len(content),
        storage_warning=len(warnings) > 0,
    )

    try:
        route_document.send(document.document_id, tenant_id)
    except Exception as e:
        logger.error(
            "Failed to queue document for processing",
            document_id=document.document_id,
            tenant_id=tenant_id,
            error=str(e),
        )
        record_queue_send_failure(tenant_id, "extraction-router")
        await doc_repo.delete(document.document_id, tenant_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to queue document for processing. The message broker may be temporarily unavailable. Please try again later.",
        )

    return UploadResponse(
        document_id=document.document_id,
        status=document.status.value,
        message="Document received and queued for routing",
        warnings=warnings if warnings else None,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
)
async def get_document_status(
    document_id: str,
    tenant_id: CurrentTenant,
    _: Annotated[ApiKey, Depends(require_scope(AuthScope.DOCUMENTS_READ.value))] = None,
    doc_repo: MongoDocumentRepository = Depends(get_document_repository),
) -> DocumentStatusResponse:
    document = await doc_repo.get_by_id(document_id, tenant_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return DocumentStatusResponse(
        document_id=document.document_id,
        status=document.status.value,
        pdf_type=document.pdf_type.value if document.pdf_type else None,
        confidence=document.confidence,
        error_message=document.error_message,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
    )


@router.get("/{document_id}")
async def get_document_result(
    document_id: str,
    tenant_id: CurrentTenant,
    _: Annotated[ApiKey, Depends(require_scope(AuthScope.DOCUMENTS_READ.value))] = None,
    doc_repo: MongoDocumentRepository = Depends(get_document_repository),
) -> dict:
    document = await doc_repo.get_by_id(document_id, tenant_id)

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    if document.status != DocumentStatus.READY:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Document is still being processed. Current status: {document.status.value}",
        )

    db = await get_database()
    extraction_collection = db["extraction_results"]
    result = await extraction_collection.find_one({
        "document_id": document_id,
        "tenant_id": tenant_id,
    })

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extraction result not found",
        )

    result.pop("_id", None)

    return Response(
        content=json.dumps(result, cls=MonetaryEncoder, ensure_ascii=False, default=str),
        media_type="application/json",
    )
