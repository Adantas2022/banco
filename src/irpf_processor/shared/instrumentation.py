import logging
from irpf_processor.config import get_settings

logger = logging.getLogger(__name__)


def instrument_dependencies() -> None:
    settings = get_settings()
    
    if not settings.otel_enabled:
        return
    
    try:
        from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
        PymongoInstrumentor().instrument()
        logger.info("PyMongo instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("PyMongo instrumentation not available")
    except Exception as e:
        logger.warning("Failed to instrument PyMongo", extra={"error": str(e)})

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.info("Redis instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("Redis instrumentation not available")
    except Exception as e:
        logger.warning("Failed to instrument Redis", extra={"error": str(e)})

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("HTTPX instrumentation not available")
    except Exception as e:
        logger.warning("Failed to instrument HTTPX", extra={"error": str(e)})

    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().instrument(set_logging_format=False)
        logger.info("Logging instrumented with OpenTelemetry")
    except ImportError:
        logger.debug("Logging instrumentation not available")
    except Exception as e:
        logger.warning("Failed to instrument Logging", extra={"error": str(e)})


def uninstrument_dependencies() -> None:
    try:
        from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
        PymongoInstrumentor().uninstrument()
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().uninstrument()
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().uninstrument()
    except Exception:
        pass

    try:
        from opentelemetry.instrumentation.logging import LoggingInstrumentor
        LoggingInstrumentor().uninstrument()
    except Exception:
        pass
