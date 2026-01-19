import pytest
from unittest.mock import patch, MagicMock

from irpf_processor.shared import instrumentation


class TestInstrumentDependencies:

    def test_instrument_dependencies_is_callable(self):
        assert callable(instrumentation.instrument_dependencies)

    @patch("irpf_processor.shared.instrumentation.get_settings")
    def test_does_nothing_when_otel_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(otel_enabled=False)

        instrumentation.instrument_dependencies()

    @patch("irpf_processor.shared.instrumentation.get_settings")
    @patch("irpf_processor.shared.instrumentation.PymongoInstrumentor", create=True)
    @patch("irpf_processor.shared.instrumentation.RedisInstrumentor", create=True)
    @patch("irpf_processor.shared.instrumentation.HTTPXClientInstrumentor", create=True)
    @patch("irpf_processor.shared.instrumentation.LoggingInstrumentor", create=True)
    def test_instruments_all_dependencies_when_enabled(
        self, mock_logging, mock_httpx, mock_redis, mock_pymongo, mock_settings
    ):
        mock_settings.return_value = MagicMock(otel_enabled=True)

        instrumentation.instrument_dependencies()

    @patch("irpf_processor.shared.instrumentation.get_settings")
    def test_handles_import_error_gracefully(self, mock_settings):
        mock_settings.return_value = MagicMock(otel_enabled=True)

        with patch.dict("sys.modules", {
            "opentelemetry.instrumentation.pymongo": None,
            "opentelemetry.instrumentation.redis": None,
            "opentelemetry.instrumentation.httpx": None,
            "opentelemetry.instrumentation.logging": None,
        }):
            instrumentation.instrument_dependencies()


class TestUninstrumentDependencies:

    def test_uninstrument_dependencies_is_callable(self):
        assert callable(instrumentation.uninstrument_dependencies)

    def test_uninstrument_handles_exceptions_gracefully(self):
        instrumentation.uninstrument_dependencies()

    @patch("irpf_processor.shared.instrumentation.PymongoInstrumentor", create=True)
    @patch("irpf_processor.shared.instrumentation.RedisInstrumentor", create=True)
    @patch("irpf_processor.shared.instrumentation.HTTPXClientInstrumentor", create=True)
    @patch("irpf_processor.shared.instrumentation.LoggingInstrumentor", create=True)
    def test_uninstruments_all_dependencies(
        self, mock_logging, mock_httpx, mock_redis, mock_pymongo
    ):
        instrumentation.uninstrument_dependencies()


class TestModuleIntegration:

    @patch("irpf_processor.shared.instrumentation.get_settings")
    def test_instrument_and_uninstrument_cycle(self, mock_settings):
        mock_settings.return_value = MagicMock(otel_enabled=True)

        instrumentation.instrument_dependencies()
        instrumentation.uninstrument_dependencies()
