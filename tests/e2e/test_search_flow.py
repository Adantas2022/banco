import pytest
from pathlib import Path

from tests.e2e.conftest import E2EHelpers


@pytest.mark.e2e
class TestSearchByFilters:

    @pytest.mark.timeout(300)
    def test_search_returns_paginated_results(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        search_result = e2e_helpers.search(page=1, page_size=10)
        
        assert "total" in search_result
        assert "page" in search_result
        assert "page_size" in search_result
        assert "total_pages" in search_result
        assert "results" in search_result
        assert isinstance(search_result["results"], list)

    @pytest.mark.timeout(300)
    def test_search_by_exercise_year(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        result = e2e_helpers.get_result(document_id)
        exercise_year = result["data"]["taxpayer_identification"].get("exercise_year", "2025")
        
        search_result = e2e_helpers.search(exercise_year=exercise_year)
        
        assert search_result["total"] >= 1
        for item in search_result["results"]:
            assert item["exercise_year"] == exercise_year

    @pytest.mark.timeout(300)
    def test_search_by_min_confidence(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        search_result = e2e_helpers.search(min_confidence=0.5)
        
        for item in search_result["results"]:
            assert item["confidence"] >= 0.5


@pytest.mark.e2e
class TestSearchByCPF:

    @pytest.mark.timeout(300)
    def test_search_by_cpf_returns_declarations(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        result = e2e_helpers.get_result(document_id)
        cpf = result["data"]["taxpayer_identification"].get("cpf", "")
        
        if not cpf:
            pytest.skip("Document does not have CPF extracted")
        
        search_results = e2e_helpers.search_by_cpf(cpf)
        
        assert isinstance(search_results, list)
        assert len(search_results) >= 1
        
        cpf_normalized = "".join(filter(str.isdigit, cpf))
        for item in search_results:
            assert item["taxpayer"]["normalized_cpf"] == cpf_normalized

    def test_search_by_invalid_cpf_returns_400(
        self,
        e2e_helpers: E2EHelpers,
    ):
        import httpx
        
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            e2e_helpers.search_by_cpf("123")
        
        assert exc_info.value.response.status_code == 400

    @pytest.mark.timeout(300)
    def test_search_by_nonexistent_cpf_returns_empty(
        self,
        e2e_helpers: E2EHelpers,
    ):
        results = e2e_helpers.search_by_cpf("00000000000")
        
        assert isinstance(results, list)
        assert len(results) == 0


@pytest.mark.e2e
class TestSearchResultContent:

    @pytest.mark.timeout(300)
    def test_search_result_contains_taxpayer_summary(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        search_result = e2e_helpers.search()
        
        assert len(search_result["results"]) >= 1
        
        item = search_result["results"][0]
        assert "taxpayer" in item
        assert "cpf" in item["taxpayer"]
        assert "name" in item["taxpayer"]

    @pytest.mark.timeout(300)
    def test_search_result_contains_assets_summary(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        search_result = e2e_helpers.search()
        
        assert len(search_result["results"]) >= 1
        
        item = search_result["results"][0]
        assert "assets" in item
        assert "total_items" in item["assets"]

    @pytest.mark.timeout(300)
    def test_search_result_contains_income_summary(
        self,
        e2e_helpers: E2EHelpers,
        test_pdf_path: Path,
    ):
        upload_result = e2e_helpers.upload_document(test_pdf_path)
        document_id = upload_result["document_id"]
        e2e_helpers.wait_for_ready(document_id, max_wait=120)
        
        search_result = e2e_helpers.search()
        
        assert len(search_result["results"]) >= 1
        
        item = search_result["results"][0]
        assert "income" in item
