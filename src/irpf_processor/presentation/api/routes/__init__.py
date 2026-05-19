from .auth import router as auth_router
from .documents import router as documents_router
from .health import router as health_router
from .metrics import router as metrics_router
from .search import router as search_router

__all__ = [
    "auth_router",
    "documents_router",
    "health_router",
    "metrics_router",
    "search_router",
]
