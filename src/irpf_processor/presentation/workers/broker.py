"""Configuracao do broker Dramatiq com Redis e OpenTelemetry."""

import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import CurrentMessage, Retries, Middleware

from irpf_processor.config import get_settings
from irpf_processor.shared.logging import configure_logging, get_logger, set_correlation_id
from irpf_processor.shared.tracing import (
    configure_tracing,
    inject_context,
    extract_context,
    get_trace_id,
    add_span_attributes,
    set_span_error,
)
from irpf_processor.shared.instrumentation import instrument_dependencies

logger = get_logger(__name__)


class OpenTelemetryMiddleware(Middleware):
    
    def before_enqueue(self, broker, message, delay):
        carrier = {}
        inject_context(carrier)
        if carrier:
            message.options["trace_context"] = carrier
        return message

    def before_process_message(self, broker, message):
        trace_context = message.options.get("trace_context", {})
        if trace_context:
            extract_context(trace_context)
        
        trace_id = get_trace_id()
        if trace_id:
            set_correlation_id(trace_id)
        
        add_span_attributes(
            dramatiq_actor_name=message.actor_name,
            dramatiq_queue_name=message.queue_name,
            dramatiq_message_id=message.message_id,
        )

    def after_process_message(self, broker, message, *, result=None, exception=None):
        if exception:
            set_span_error(exception)


settings = get_settings()

configure_logging()
configure_tracing(service_name_suffix="worker")
instrument_dependencies()

dramatiq_broker = RedisBroker(url=settings.redis_url)

dramatiq_broker.add_middleware(CurrentMessage())
dramatiq_broker.add_middleware(OpenTelemetryMiddleware())
dramatiq_broker.add_middleware(
    Retries(
        max_retries=settings.max_retry_attempts,
        min_backoff=1000,
        max_backoff=600000,
    )
)

dramatiq.set_broker(dramatiq_broker)

from irpf_processor.presentation.workers.extraction_worker import process_document

__all__ = ["process_document", "dramatiq_broker"]
