from fastapi import APIRouter, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from irpf_processor.shared.metrics import get_registry


router = APIRouter(tags=["Metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    registry = get_registry()
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )
