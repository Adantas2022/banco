from typing import Optional
import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, Span
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode, get_current_span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from irpf_processor.config import get_settings
from irpf_processor.shared.logging import set_correlation_id, get_correlation_id

logger = logging.getLogger(__name__)

_tracer_provider: Optional[TracerProvider] = None
_propagator = TraceContextTextMapPropagator()


def configure_tracing(service_name_suffix: str = "") -> Optional[TracerProvider]:
    global _tracer_provider
    
    settings = get_settings()
    
    if not settings.otel_enabled:
        logger.info("OpenTelemetry tracing is disabled")
        return None
    
    if _tracer_provider is not None:
        return _tracer_provider
    
    full_service_name = settings.otel_service_name
    if service_name_suffix:
        full_service_name = f"{settings.otel_service_name}-{service_name_suffix}"
    
    resource = Resource.create({
        SERVICE_NAME: full_service_name,
        SERVICE_VERSION: "0.1.0",
        "deployment.environment": settings.app_env,
    })
    
    sampler = TraceIdRatioBased(settings.otel_sample_rate)
    
    _tracer_provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )
    
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_endpoint,
        insecure=True,
    )
    
    span_processor = BatchSpanProcessor(otlp_exporter)
    _tracer_provider.add_span_processor(span_processor)
    
    trace.set_tracer_provider(_tracer_provider)
    
    set_global_textmap(_propagator)
    
    logger.info(
        "OpenTelemetry tracing configured",
        extra={
            "service_name": full_service_name,
            "exporter_endpoint": settings.otel_exporter_endpoint,
            "sample_rate": settings.otel_sample_rate,
        }
    )
    
    return _tracer_provider


def get_tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def get_trace_id() -> Optional[str]:
    span = get_current_span()
    if span and span.is_recording():
        return format(span.get_span_context().trace_id, '032x')
    return None


def get_span_id() -> Optional[str]:
    span = get_current_span()
    if span and span.is_recording():
        return format(span.get_span_context().span_id, '016x')
    return None


def sync_trace_id_with_correlation_id() -> None:
    trace_id = get_trace_id()
    if trace_id:
        set_correlation_id(trace_id)


def set_span_error(exception: Exception) -> None:
    span = get_current_span()
    if span and span.is_recording():
        span.set_status(Status(StatusCode.ERROR, str(exception)))
        span.record_exception(exception)


def add_span_attributes(**attributes: str) -> None:
    span = get_current_span()
    if span and span.is_recording():
        for key, value in attributes.items():
            span.set_attribute(key, value)


def inject_context(carrier: dict) -> dict:
    _propagator.inject(carrier)
    return carrier


def extract_context(carrier: dict):
    from opentelemetry import context
    ctx = _propagator.extract(carrier)
    context.attach(ctx)
    return ctx


def shutdown_tracing() -> None:
    global _tracer_provider
    if _tracer_provider:
        _tracer_provider.shutdown()
        _tracer_provider = None
        logger.info("OpenTelemetry tracing shutdown complete")
