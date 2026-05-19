import pytest
from pathlib import Path

from tests.e2e.conftest import E2EHelpers


@pytest.mark.e2e
class TestDocumentUploadFlow:

    def test_upload_pdf_returns_document_id(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        result = e2e_helpers.upload_document(test_pdf_path)
        
        assert "document_id" in result
        assert result["status"] in ["RECEIVED", "READY"]
        assert len(result["document_id"]) == 36

    def test_upload_same_pdf_returns_existing_document(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        result1 = e2e_helpers.upload_document(test_pdf_path)
        result2 = e2e_helpers.upload_document(test_pdf_path)
        
        assert result1["document_id"] == result2["document_id"]
        assert "already exists" in result2.get("message", "").lower() or result2["status"] != "RECEIVED"

    def test_get_document_status_returns_valid_status(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        
        status = e2e_helpers.get_status(document_id)
        
        assert status["document_id"] == document_id
        assert status["status"] in ["RECEIVED", "ROUTED", "EXTRACTED", "READY", "FAILED"]
        assert "created_at" in status
        assert "updated_at" in status


@pytest.mark.e2e
class TestDocumentProcessingFlow:

    @pytest.mark.timeout(300)
    def test_document_processes_to_ready(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        
        final_status = e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        assert final_status["status"] == "READY"
        assert final_status.get("confidence") is not None
        assert final_status["confidence"] > 0.0

    @pytest.mark.timeout(300)
    def test_extraction_result_contains_taxpayer_data(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        result = e2e_helpers.get_result(document_id)
        
        assert "data" in result
        assert "taxpayer_identification" in result["data"]
        
        taxpayer = result["data"]["taxpayer_identification"]
        assert "cpf" in taxpayer or "normalized_cpf" in taxpayer
        assert "name" in taxpayer

    @pytest.mark.timeout(300)
    def test_extraction_result_contains_confidence(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        result = e2e_helpers.get_result(document_id)
        
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0

    @pytest.mark.timeout(300)
    def test_extraction_result_contains_template_version(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        result = e2e_helpers.get_result(document_id)
        
        assert "template_version" in result
        assert result["template_version"] in ["2023", "2024", "2025"]


@pytest.mark.e2e
class TestDocumentErrorHandling:

    def test_get_nonexistent_document_returns_404(
        self,
        e2e_helpers: E2EHelpers,
    ):
        import httpx
        
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            e2e_helpers.get_status("nonexistent-document-id-12345")
        
        assert exc_info.value.response.status_code == 404

    def test_upload_without_auth_returns_401(
        self,
        http_client,
        test_pdf_path: Path,
    ):
        with open(test_pdf_path, "rb") as f:
            files = {"file": (test_pdf_path.name, f, "application/pdf")}
            response = http_client.post("/v1/documents", files=files)
        
        assert response.status_code == 401
