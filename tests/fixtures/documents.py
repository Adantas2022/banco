from datetime import datetime
from typing import Optional

from irpf_processor.domain.entities import Document
from irpf_processor.domain.enums import DocumentStatus, PdfType

SAMPLE_TENANT_ID = "test-tenant-001"
SAMPLE_DOCUMENT_ID = "doc-test-12345678-1234-1234-1234-123456789012"

SAMPLE_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n"
    b"<< /Type /Catalog /Pages 2 0 R >>\n"
    b"endobj\n"
    b"2 0 obj\n"
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
    b"endobj\n"
    b"3 0 obj\n"
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\n"
    b"endobj\n"
    b"xref\n"
    b"0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"trailer\n"
    b"<< /Size 4 /Root 1 0 R >>\n"
    b"startxref\n"
    b"198\n"
    b"%%EOF"
)


def create_pdf_bytes(content: str = "Test PDF") -> bytes:
    return SAMPLE_PDF_BYTES


def create_sample_document(
    document_id: Optional[str] = None,
    tenant_id: str = SAMPLE_TENANT_ID,
    filename: str = "test_irpf_2025.pdf",
    status: DocumentStatus = DocumentStatus.RECEIVED,
    pdf_type: Optional[PdfType] = None,
    confidence: Optional[float] = None,
    sha256: str = "abc123def456789",
) -> Document:
    doc = Document(
        tenant_id=tenant_id,
        filename=filename,
        content_type="application/pdf",
        storage_uri=f"s3://documents/{tenant_id}/test.pdf",
        sha256=sha256,
    )

    if document_id:
        doc.document_id = document_id

    doc.status = status

    if pdf_type:
        doc.pdf_type = pdf_type

    if confidence is not None:
        doc.confidence = confidence

    return doc
