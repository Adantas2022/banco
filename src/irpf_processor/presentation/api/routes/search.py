"""Endpoints de busca de declarações IRPF."""

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from irpf_processor.domain.entities import ApiKey
from irpf_processor.domain.enums import AuthScope
from irpf_processor.infrastructure.persistence.database import get_database
from irpf_processor.presentation.api.dependencies import CurrentTenant, require_scope
from irpf_processor.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/irpf", tags=["Search"])


class TaxpayerSummary(BaseModel):
    cpf: str
    normalized_cpf: str
    name: str
    city: Optional[str] = None
    state: Optional[str] = None


class AssetsSummary(BaseModel):
    total_items: int = 0
    last_year_total: float = 0.0
    current_year_total: float = 0.0


class IncomeSummary(BaseModel):
    total_pj_income: float = 0.0
    total_exempt_income: float = 0.0
    total_exclusive_income: float = 0.0


class SearchResultItem(BaseModel):
    document_id: str
    tenant_id: str
    template_version: str
    exercise_year: str
    calendar_year: str
    confidence: float
    taxpayer: TaxpayerSummary
    assets: AssetsSummary
    income: IncomeSummary
    created_at: Optional[str] = None


class SearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[SearchResultItem]


class SearchFilters(BaseModel):
    cpf: Optional[str] = None
    name: Optional[str] = None
    exercise_year: Optional[str] = None
    calendar_year: Optional[str] = None
    min_confidence: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None


def normalize_cpf(cpf: str) -> str:
    return "".join(filter(str.isdigit, cpf))


def build_search_query(tenant_id: str, filters: SearchFilters) -> dict:
    query = {"tenant_id": tenant_id}
    base_path = "data.ir_response.declaration.taxpayer_identification"
    
    if filters.cpf:
        normalized = normalize_cpf(filters.cpf)
        query[f"{base_path}.normalized_cpf"] = normalized
    
    if filters.name:
        query[f"{base_path}.name"] = {
            "$regex": filters.name,
            "$options": "i"
        }
    
    if filters.exercise_year:
        query[f"{base_path}.exercise_year"] = filters.exercise_year
    
    if filters.calendar_year:
        query[f"{base_path}.calendar_year"] = filters.calendar_year
    
    if filters.min_confidence:
        query["confidence"] = {"$gte": filters.min_confidence}
    
    if filters.city:
        query[f"{base_path}.contact_and_address.city"] = {
            "$regex": filters.city,
            "$options": "i"
        }
    
    if filters.state:
        query[f"{base_path}.contact_and_address.uf"] = filters.state.upper()
    
    return query


def extract_result_item(doc: dict) -> SearchResultItem:
    data = doc.get("data", {})
    ir_response = data.get("ir_response", {})
    declaration = ir_response.get("declaration", {}) or {}
    
    taxpayer = declaration.get("taxpayer_identification", {})
    assets = declaration.get("assets_declaration", {})
    contact = taxpayer.get("contact_and_address", {})
    
    income_pj = declaration.get("income_from_legal_person_to_holder", {})
    exempt = declaration.get("exempt_income", {})
    exclusive = declaration.get("exclusive_taxation_income", {})
    
    total_pj = 0.0
    if income_pj and income_pj.get("total_values"):
        total_pj = income_pj["total_values"].get("income_from_legal_person", {}).get("amount", 0.0)
    
    return SearchResultItem(
        document_id=doc.get("document_id", ""),
        tenant_id=doc.get("tenant_id", ""),
        template_version=doc.get("template_version", ""),
        exercise_year=taxpayer.get("exercise_year", ""),
        calendar_year=taxpayer.get("calendar_year", ""),
        confidence=doc.get("confidence", 0.0),
        taxpayer=TaxpayerSummary(
            cpf=taxpayer.get("cpf", ""),
            normalized_cpf=taxpayer.get("normalized_cpf", ""),
            name=taxpayer.get("name", ""),
            city=contact.get("city"),
            state=contact.get("uf"),
        ),
        assets=AssetsSummary(
            total_items=len(assets.get("items", [])) if assets else 0,
            last_year_total=assets.get("last_year_total_value", 0.0) if assets else 0.0,
            current_year_total=assets.get("current_year_total_value", 0.0) if assets else 0.0,
        ),
        income=IncomeSummary(
            total_pj_income=total_pj,
            total_exempt_income=exempt.get("total_value", 0.0) if exempt else 0.0,
            total_exclusive_income=exclusive.get("total_value", 0.0) if exclusive else 0.0,
        ),
        created_at=doc.get("created_at").isoformat() if doc.get("created_at") else None,
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    summary="Buscar declarações IRPF",
    description="Busca declarações por CPF, nome, ano-exercício e outros filtros.",
)
async def search_irpf(
    tenant_id: CurrentTenant,
    _: Annotated[ApiKey, Depends(require_scope(AuthScope.SEARCH_READ.value))] = None,
    cpf: Optional[str] = Query(None, description="CPF do contribuinte (com ou sem formatação)"),
    name: Optional[str] = Query(None, description="Nome do contribuinte (busca parcial)"),
    exercise_year: Optional[str] = Query(None, description="Ano-exercício (ex: 2025)"),
    calendar_year: Optional[str] = Query(None, description="Ano-calendário (ex: 2024)"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Confiança mínima (0.0 a 1.0)"),
    city: Optional[str] = Query(None, description="Cidade (busca parcial)"),
    state: Optional[str] = Query(None, max_length=2, description="UF (ex: SP, RJ)"),
    page: int = Query(1, ge=1, description="Página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
) -> SearchResponse:
    filters = SearchFilters(
        cpf=cpf,
        name=name,
        exercise_year=exercise_year,
        calendar_year=calendar_year,
        min_confidence=min_confidence,
        city=city,
        state=state,
    )
    
    query = build_search_query(tenant_id, filters)
    
    logger.info(
        "Searching IRPF declarations",
        tenant_id=tenant_id,
        filters=filters.model_dump(exclude_none=True),
    )
    
    db = await get_database()
    collection = db["extraction_results"]
    
    total = await collection.count_documents(query)
    
    skip = (page - 1) * page_size
    cursor = collection.find(query).skip(skip).limit(page_size).sort("_id", -1)
    
    results = []
    async for doc in cursor:
        try:
            item = extract_result_item(doc)
            results.append(item)
        except Exception as e:
            logger.warning(
                "Failed to extract search result",
                document_id=doc.get("document_id"),
                error=str(e),
            )
    
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    return SearchResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        results=results,
    )


@router.get(
    "/search/by-cpf/{cpf}",
    response_model=list[SearchResultItem],
    summary="Buscar declarações por CPF",
    description="Retorna todas as declarações de um CPF específico.",
)
async def search_by_cpf(
    cpf: str,
    tenant_id: CurrentTenant,
    _: Annotated[ApiKey, Depends(require_scope(AuthScope.SEARCH_READ.value))] = None,
) -> list[SearchResultItem]:
    normalized = normalize_cpf(cpf)
    
    if len(normalized) != 11:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CPF deve ter 11 dígitos",
        )
    
    db = await get_database()
    collection = db["extraction_results"]
    
    query = {
        "tenant_id": tenant_id,
        "data.ir_response.declaration.taxpayer_identification.normalized_cpf": normalized,
    }
    
    cursor = collection.find(query).sort("data.ir_response.declaration.taxpayer_identification.exercise_year", -1)
    
    results = []
    async for doc in cursor:
        try:
            item = extract_result_item(doc)
            results.append(item)
        except Exception as e:
            logger.warning(
                "Failed to extract search result",
                document_id=doc.get("document_id"),
                error=str(e),
            )
    
    return results


@router.get(
    "/stats",
    summary="Estatísticas das declarações",
    description="Retorna estatísticas agregadas das declarações do tenant.",
)
async def get_stats(
    tenant_id: CurrentTenant,
    _: Annotated[ApiKey, Depends(require_scope(AuthScope.SEARCH_READ.value))] = None,
) -> dict:
    db = await get_database()
    collection = db["extraction_results"]
    
    pipeline = [
        {"$match": {"tenant_id": tenant_id}},
        {
            "$group": {
                "_id": None,
                "total_declarations": {"$sum": 1},
                "avg_confidence": {"$avg": "$confidence"},
                "exercise_years": {"$addToSet": "$data.ir_response.declaration.taxpayer_identification.exercise_year"},
                "total_assets_value": {"$sum": "$data.ir_response.declaration.assets_declaration.current_year_total_value"},
                "unique_cpfs": {"$addToSet": "$data.ir_response.declaration.taxpayer_identification.normalized_cpf"},
            }
        },
    ]
    
    result = await collection.aggregate(pipeline).to_list(1)
    
    if not result:
        return {
            "total_declarations": 0,
            "unique_contributors": 0,
            "avg_confidence": 0.0,
            "exercise_years": [],
            "total_assets_value": 0.0,
        }
    
    stats = result[0]
    return {
        "total_declarations": stats.get("total_declarations", 0),
        "unique_contributors": len(stats.get("unique_cpfs", [])),
        "avg_confidence": round(stats.get("avg_confidence", 0.0), 2),
        "exercise_years": sorted(stats.get("exercise_years", []), reverse=True),
        "total_assets_value": stats.get("total_assets_value", 0.0),
    }
