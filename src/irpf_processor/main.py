import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from irpf_processor import __version__
from irpf_processor.config import get_settings
from irpf_processor.domain.exceptions import DomainException
from irpf_processor.infrastructure.persistence import (
    close_database,
    close_redis,
    init_database,
    init_redis,
)
from irpf_processor.presentation.api.routes import (
    auth_router,
    documents_router,
    health_router,
    metrics_router,
    search_router,
)
from irpf_processor.shared.logging import configure_logging, get_logger, set_correlation_id
from irpf_processor.shared.metrics import (
    API_REQUESTS_IN_PROGRESS,
    record_api_request,
    set_app_info,
)
from irpf_processor.shared.tracing import (
    configure_tracing,
    get_trace_id,
    shutdown_tracing,
)
from irpf_processor.shared.instrumentation import instrument_dependencies

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    configure_logging()
    configure_tracing(service_name_suffix="api")
    instrument_dependencies()
    set_app_info(version=__version__, environment=settings.app_env)
    logger.info("Starting IRPF Processor API", version=__version__)

    await init_database()
    logger.info("MongoDB connected")

    await init_redis()
    logger.info("Redis connected")

    yield

    logger.info("Shutting down IRPF Processor API")
    shutdown_tracing()
    await close_database()
    await close_redis()


def create_app() -> FastAPI:
    """Factory para criar a aplicação FastAPI."""
    settings = get_settings()

    app = FastAPI(
        title="IRPF Processor API",
        description="API para extração de dados de Declarações de Imposto de Renda",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path
        API_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start_time
            record_api_request(method, endpoint, response.status_code, duration)
            return response
        except Exception:
            duration = time.perf_counter() - start_time
            record_api_request(method, endpoint, 500, duration)
            raise
        finally:
            API_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        trace_id = get_trace_id()
        correlation_id = trace_id or request.headers.get(
            settings.correlation_id_header,
            str(uuid.uuid4()),
        )
        set_correlation_id(correlation_id)
        response = await call_next(request)
        response.headers[settings.correlation_id_header] = correlation_id
        if trace_id:
            response.headers["X-Trace-ID"] = trace_id
        return response

    @app.exception_handler(DomainException)
    async def domain_exception_handler(request: Request, exc: DomainException):
        return JSONResponse(
            status_code=400,
            content={
                "error": exc.code,
                "message": exc.message,
            },
        )

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(search_router)

    if OTEL_AVAILABLE and settings.otel_enabled:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls="health,ready,metrics",
        )
        logger.info("FastAPI instrumented with OpenTelemetry")

    return app


app = create_app()
