import pytest

from irpf_processor.presentation.api.routes.search import (
    normalize_cpf,
    build_search_query,
    SearchFilters,
    TaxpayerSummary,
    AssetsSummary,
    IncomeSummary,
    SearchResultItem,
    SearchResponse,
)


class TestNormalizeCpf:

    def test_removes_dots(self):
        result = normalize_cpf("123.456.789-00")

        assert result == "12345678900"

    def test_removes_hyphen(self):
        result = normalize_cpf("12345678900")

        assert result == "12345678900"

    def test_handles_partial_formatting(self):
        result = normalize_cpf("123456789-00")

        assert result == "12345678900"

    def test_handles_spaces(self):
        result = normalize_cpf("123 456 789 00")

        assert result == "12345678900"

    def test_handles_mixed_characters(self):
        result = normalize_cpf("123.456.789-00 CPF")

        assert result == "12345678900"

    def test_handles_empty_string(self):
        result = normalize_cpf("")

        assert result == ""

    def test_handles_only_digits(self):
        result = normalize_cpf("12345678900")

        assert result == "12345678900"


class TestSearchFilters:

    def test_default_values(self):
        filters = SearchFilters()

        assert filters.cpf is None
        assert filters.name is None
        assert filters.exercise_year is None
        assert filters.calendar_year is None
        assert filters.min_confidence is None
        assert filters.city is None
        assert filters.state is None

    def test_with_cpf(self):
        filters = SearchFilters(cpf="123.456.789-00")

        assert filters.cpf == "123.456.789-00"

    def test_with_all_filters(self):
        filters = SearchFilters(
            cpf="123.456.789-00",
            name="GENESIS LOPES",
            exercise_year="2025",
            calendar_year="2024",
            min_confidence=0.8,
            city="SAO PAULO",
            state="SP"
        )

        assert filters.cpf == "123.456.789-00"
        assert filters.name == "GENESIS LOPES"
        assert filters.exercise_year == "2025"
        assert filters.calendar_year == "2024"
        assert filters.min_confidence == 0.8
        assert filters.city == "SAO PAULO"
        assert filters.state == "SP"


class TestBuildSearchQuery:

    def test_basic_query_with_tenant_id(self):
        filters = SearchFilters()

        query = build_search_query("tenant-123", filters)

        assert query["tenant_id"] == "tenant-123"

    def test_adds_cpf_filter(self):
        filters = SearchFilters(cpf="123.456.789-00")

        query = build_search_query("tenant-123", filters)

        assert query["data.taxpayer_identification.normalized_cpf"] == "12345678900"

    def test_adds_name_filter(self):
        filters = SearchFilters(name="GENESIS")

        query = build_search_query("tenant-123", filters)

        assert "data.taxpayer_identification.name" in query

    def test_adds_exercise_year_filter(self):
        filters = SearchFilters(exercise_year="2025")

        query = build_search_query("tenant-123", filters)

        assert query["data.taxpayer_identification.exercise_year"] == "2025"

    def test_adds_calendar_year_filter(self):
        filters = SearchFilters(calendar_year="2024")

        query = build_search_query("tenant-123", filters)

        assert query["data.taxpayer_identification.calendar_year"] == "2024"

    def test_adds_min_confidence_filter(self):
        filters = SearchFilters(min_confidence=0.8)

        query = build_search_query("tenant-123", filters)

        assert "confidence" in query
        assert query["confidence"]["$gte"] == 0.8

    def test_adds_city_filter(self):
        filters = SearchFilters(city="SAO PAULO")

        query = build_search_query("tenant-123", filters)

        assert "data.taxpayer_identification.contact_and_address.city" in query

    def test_adds_state_filter(self):
        filters = SearchFilters(state="SP")

        query = build_search_query("tenant-123", filters)

        assert query["data.taxpayer_identification.contact_and_address.uf"] == "SP"

    def test_multiple_filters(self):
        filters = SearchFilters(
            cpf="123.456.789-00",
            exercise_year="2025",
            min_confidence=0.9
        )

        query = build_search_query("tenant-123", filters)

        assert query["tenant_id"] == "tenant-123"
        assert query["data.taxpayer_identification.normalized_cpf"] == "12345678900"
        assert query["data.taxpayer_identification.exercise_year"] == "2025"
        assert query["confidence"]["$gte"] == 0.9


class TestTaxpayerSummary:

    def test_required_fields(self):
        summary = TaxpayerSummary(
            cpf="123.456.789-00",
            normalized_cpf="12345678900",
            name="GENESIS LOPES"
        )

        assert summary.cpf == "123.456.789-00"
        assert summary.normalized_cpf == "12345678900"
        assert summary.name == "GENESIS LOPES"

    def test_optional_fields(self):
        summary = TaxpayerSummary(
            cpf="123.456.789-00",
            normalized_cpf="12345678900",
            name="GENESIS LOPES",
            city="SAO PAULO",
            state="SP"
        )

        assert summary.city == "SAO PAULO"
        assert summary.state == "SP"

    def test_default_optional_fields(self):
        summary = TaxpayerSummary(
            cpf="123.456.789-00",
            normalized_cpf="12345678900",
            name="GENESIS LOPES"
        )

        assert summary.city is None
        assert summary.state is None


class TestAssetsSummary:

    def test_default_values(self):
        summary = AssetsSummary()

        assert summary.total_items == 0
        assert summary.last_year_total == 0.0
        assert summary.current_year_total == 0.0

    def test_with_values(self):
        summary = AssetsSummary(
            total_items=10,
            last_year_total=500000.0,
            current_year_total=600000.0
        )

        assert summary.total_items == 10
        assert summary.last_year_total == 500000.0
        assert summary.current_year_total == 600000.0


class TestIncomeSummary:

    def test_default_values(self):
        summary = IncomeSummary()

        assert summary.total_pj_income == 0.0
        assert summary.total_exempt_income == 0.0
        assert summary.total_exclusive_income == 0.0

    def test_with_values(self):
        summary = IncomeSummary(
            total_pj_income=120000.0,
            total_exempt_income=5000.0,
            total_exclusive_income=10000.0
        )

        assert summary.total_pj_income == 120000.0
        assert summary.total_exempt_income == 5000.0
        assert summary.total_exclusive_income == 10000.0


class TestSearchResultItem:

    def test_required_fields(self):
        taxpayer = TaxpayerSummary(
            cpf="123.456.789-00",
            normalized_cpf="12345678900",
            name="GENESIS LOPES"
        )
        assets = AssetsSummary()
        income = IncomeSummary()

        item = SearchResultItem(
            document_id="doc-123",
            tenant_id="tenant-456",
            template_version="2025",
            exercise_year="2025",
            calendar_year="2024",
            confidence=0.95,
            taxpayer=taxpayer,
            assets=assets,
            income=income
        )

        assert item.document_id == "doc-123"
        assert item.tenant_id == "tenant-456"
        assert item.template_version == "2025"
        assert item.exercise_year == "2025"
        assert item.calendar_year == "2024"
        assert item.confidence == 0.95
        assert item.created_at is None

    def test_with_created_at(self):
        taxpayer = TaxpayerSummary(
            cpf="123.456.789-00",
            normalized_cpf="12345678900",
            name="GENESIS LOPES"
        )
        assets = AssetsSummary()
        income = IncomeSummary()

        item = SearchResultItem(
            document_id="doc-123",
            tenant_id="tenant-456",
            template_version="2025",
            exercise_year="2025",
            calendar_year="2024",
            confidence=0.95,
            taxpayer=taxpayer,
            assets=assets,
            income=income,
            created_at="2025-04-15T14:30:00Z"
        )

        assert item.created_at == "2025-04-15T14:30:00Z"


class TestSearchResponse:

    def test_basic_response(self):
        response = SearchResponse(
            total=0,
            page=1,
            page_size=20,
            total_pages=0,
            results=[]
        )

        assert response.total == 0
        assert response.page == 1
        assert response.page_size == 20
        assert response.total_pages == 0
        assert response.results == []

    def test_with_results(self):
        taxpayer = TaxpayerSummary(
            cpf="123.456.789-00",
            normalized_cpf="12345678900",
            name="GENESIS LOPES"
        )
        assets = AssetsSummary()
        income = IncomeSummary()

        item = SearchResultItem(
            document_id="doc-123",
            tenant_id="tenant-456",
            template_version="2025",
            exercise_year="2025",
            calendar_year="2024",
            confidence=0.95,
            taxpayer=taxpayer,
            assets=assets,
            income=income
        )

        response = SearchResponse(
            total=1,
            page=1,
            page_size=20,
            total_pages=1,
            results=[item]
        )

        assert response.total == 1
        assert len(response.results) == 1
        assert response.results[0].document_id == "doc-123"

    def test_pagination(self):
        response = SearchResponse(
            total=55,
            page=3,
            page_size=20,
            total_pages=3,
            results=[]
        )

        assert response.total == 55
        assert response.page == 3
        assert response.page_size == 20
        assert response.total_pages == 3
