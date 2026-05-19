import pytest
from unittest.mock import patch, MagicMock

from irpf_processor.shared import tracing


class TestConfigureTracing:

    def test_configure_tracing_is_callable(self):
        assert callable(tracing.configure_tracing)

    @patch("irpf_processor.shared.tracing.get_settings")
    def test_returns_none_when_disabled(self, mock_settings):
        mock_settings.return_value = MagicMock(otel_enabled=False)
        tracing._tracer_provider = None

        result = tracing.configure_tracing()

        assert result is None

    @patch("irpf_processor.shared.tracing.get_settings")
    @patch("irpf_processor.shared.tracing.OTLPSpanExporter")
    @patch("irpf_processor.shared.tracing.BatchSpanProcessor")
    @patch("irpf_processor.shared.tracing.trace.set_tracer_provider")
    @patch("irpf_processor.shared.tracing.set_global_textmap")
    def test_configures_tracing_when_enabled(
        self, mock_set_textmap, mock_set_provider, mock_processor, mock_exporter, mock_settings
    ):
        mock_settings.return_value = MagicMock(
            otel_enabled=True,
            otel_service_name="irpf-processor",
            otel_exporter_endpoint="localhost:4317",
            otel_sample_rate=1.0,
            app_env="test"
        )
        tracing._tracer_provider = None

        result = tracing.configure_tracing()

        assert result is not None
        mock_set_provider.assert_called_once()

        tracing._tracer_provider = None


class TestGetTracer:

    def test_get_tracer_returns_tracer(self):
        result = tracing.get_tracer("test-tracer")
        assert result is not None


class TestGetTraceId:

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_get_trace_id_returns_none_when_no_span(self, mock_get_span):
        mock_get_span.return_value = None

        result = tracing.get_trace_id()

        assert result is None

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_get_trace_id_returns_none_when_not_recording(self, mock_get_span):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = False
        mock_get_span.return_value = mock_span

        result = tracing.get_trace_id()

        assert result is None

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_get_trace_id_returns_formatted_trace_id(self, mock_get_span):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_context = MagicMock()
        mock_context.trace_id = 123456789
        mock_span.get_span_context.return_value = mock_context
        mock_get_span.return_value = mock_span

        result = tracing.get_trace_id()

        assert result is not None
        assert len(result) == 32


class TestGetSpanId:

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_get_span_id_returns_none_when_no_span(self, mock_get_span):
        mock_get_span.return_value = None

        result = tracing.get_span_id()

        assert result is None

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_get_span_id_returns_formatted_span_id(self, mock_get_span):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_context = MagicMock()
        mock_context.span_id = 987654321
        mock_span.get_span_context.return_value = mock_context
        mock_get_span.return_value = mock_span

        result = tracing.get_span_id()

        assert result is not None
        assert len(result) == 16


class TestSyncTraceIdWithCorrelationId:

    @patch("irpf_processor.shared.tracing.get_trace_id")
    @patch("irpf_processor.shared.tracing.set_correlation_id")
    def test_sets_correlation_id_when_trace_id_exists(self, mock_set_id, mock_get_trace):
        mock_get_trace.return_value = "abc123def456"

        tracing.sync_trace_id_with_correlation_id()

        mock_set_id.assert_called_once_with("abc123def456")

    @patch("irpf_processor.shared.tracing.get_trace_id")
    @patch("irpf_processor.shared.tracing.set_correlation_id")
    def test_does_not_set_when_no_trace_id(self, mock_set_id, mock_get_trace):
        mock_get_trace.return_value = None

        tracing.sync_trace_id_with_correlation_id()

        mock_set_id.assert_not_called()


class TestSetSpanError:

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_sets_error_status_on_span(self, mock_get_span):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_get_span.return_value = mock_span

        exception = ValueError("Test error")
        tracing.set_span_error(exception)

        mock_span.set_status.assert_called_once()
        mock_span.record_exception.assert_called_once_with(exception)

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_does_nothing_when_no_span(self, mock_get_span):
        mock_get_span.return_value = None

        tracing.set_span_error(ValueError("Test"))


class TestAddSpanAttributes:

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_adds_attributes_to_span(self, mock_get_span):
        mock_span = MagicMock()
        mock_span.is_recording.return_value = True
        mock_get_span.return_value = mock_span

        tracing.add_span_attributes(key1="value1", key2="value2")

        assert mock_span.set_attribute.call_count == 2

    @patch("irpf_processor.shared.tracing.get_current_span")
    def test_does_nothing_when_no_span(self, mock_get_span):
        mock_get_span.return_value = None

        tracing.add_span_attributes(key="value")


class TestInjectContext:

    def test_inject_context_returns_carrier(self):
        carrier = {}

        result = tracing.inject_context(carrier)

        assert result is carrier


class TestExtractContext:

    def test_extract_context_is_callable(self):
        assert callable(tracing.extract_context)


class TestShutdownTracing:

    def test_shutdown_tracing_when_provider_exists(self):
        mock_provider = MagicMock()
        tracing._tracer_provider = mock_provider

        tracing.shutdown_tracing()

        mock_provider.shutdown.assert_called_once()
        assert tracing._tracer_provider is None

    def test_shutdown_tracing_when_no_provider(self):
        tracing._tracer_provider = None

        tracing.shutdown_tracing()

        assert tracing._tracer_provider is None


class TestModuleVariables:

    def test_propagator_exists(self):
        assert hasattr(tracing, "_propagator")
        assert tracing._propagator is not None
