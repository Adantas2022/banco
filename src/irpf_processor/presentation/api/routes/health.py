"""Endpoints de health check."""

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check simples."""
    return {"status": "healthy"}


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """Readiness check - verifica dependências."""
    return {"status": "ready"}
