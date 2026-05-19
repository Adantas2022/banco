import pytest
from unittest.mock import MagicMock, patch


class TestOpenTelemetryMiddleware:

    def test_middleware_is_importable(self):
        with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")
            with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                    with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                        with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                            from irpf_processor.presentation.workers.broker import OpenTelemetryMiddleware
                            assert OpenTelemetryMiddleware is not None

    def test_before_enqueue_injects_context(self):
        mock_message = MagicMock()
        mock_message.options = {}

        with patch("irpf_processor.presentation.workers.broker.inject_context") as mock_inject:
            mock_inject.side_effect = lambda carrier: carrier.update({"traceparent": "test"})

            with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")
                with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                    with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                        with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                            with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                                from irpf_processor.presentation.workers.broker import OpenTelemetryMiddleware
                                middleware = OpenTelemetryMiddleware()
                                result = middleware.before_enqueue(MagicMock(), mock_message, 0)
                                assert "trace_context" in mock_message.options

    def test_before_process_message_extracts_context(self):
        mock_message = MagicMock()
        mock_message.options = {"trace_context": {"traceparent": "test-trace"}}
        mock_message.actor_name = "test_actor"
        mock_message.queue_name = "test_queue"
        mock_message.message_id = "test-123"

        with patch("irpf_processor.presentation.workers.broker.extract_context") as mock_extract:
            with patch("irpf_processor.presentation.workers.broker.get_trace_id") as mock_get_trace:
                mock_get_trace.return_value = "trace-123"
                with patch("irpf_processor.presentation.workers.broker.set_correlation_id"):
                    with patch("irpf_processor.presentation.workers.broker.add_span_attributes"):
                        with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
                            mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")
                            with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                                with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                                    with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                                        with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                                            from irpf_processor.presentation.workers.broker import OpenTelemetryMiddleware
                                            middleware = OpenTelemetryMiddleware()
                                            middleware.before_process_message(MagicMock(), mock_message)
                                            mock_extract.assert_called_with({"traceparent": "test-trace"})

    def test_after_process_message_handles_exception(self):
        mock_message = MagicMock()
        test_exception = Exception("Test error")

        with patch("irpf_processor.presentation.workers.broker.set_span_error") as mock_set_error:
            with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")
                with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                    with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                        with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                            with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                                from irpf_processor.presentation.workers.broker import OpenTelemetryMiddleware
                                middleware = OpenTelemetryMiddleware()
                                middleware.after_process_message(MagicMock(), mock_message, exception=test_exception)
                                mock_set_error.assert_called_once_with(test_exception)

    def test_after_process_message_no_error_when_success(self):
        mock_message = MagicMock()

        with patch("irpf_processor.presentation.workers.broker.set_span_error") as mock_set_error:
            with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(redis_url="redis://localhost:6379")
                with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                    with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                        with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                            with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                                from irpf_processor.presentation.workers.broker import OpenTelemetryMiddleware
                                middleware = OpenTelemetryMiddleware()
                                middleware.after_process_message(MagicMock(), mock_message, result="success")
                                mock_set_error.assert_not_called()


class TestBrokerConfiguration:

    def test_broker_module_is_importable(self):
        from irpf_processor.presentation.workers import broker
        assert broker is not None


class TestBrokerExports:

    def test_exports_process_document(self):
        with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                max_retry_attempts=3
            )
            with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                    with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                        with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                            from irpf_processor.presentation.workers.broker import __all__
                            assert "process_document" in __all__

    def test_exports_dramatiq_broker(self):
        with patch("irpf_processor.presentation.workers.broker.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                max_retry_attempts=3
            )
            with patch("irpf_processor.presentation.workers.broker.configure_logging"):
                with patch("irpf_processor.presentation.workers.broker.configure_tracing"):
                    with patch("irpf_processor.presentation.workers.broker.instrument_dependencies"):
                        with patch("irpf_processor.presentation.workers.broker.RedisBroker"):
                            from irpf_processor.presentation.workers.broker import __all__
                            assert "dramatiq_broker" in __all__
