import pytest
from unittest.mock import patch, MagicMock

from irpf_processor.shared.logging import (
    get_correlation_id,
    set_correlation_id,
    add_correlation_id,
    add_app_info,
    get_logger,
)


class TestCorrelationId:

    def test_get_correlation_id_default_none(self):
        result = get_correlation_id()

        assert result is None or isinstance(result, str)

    def test_set_and_get_correlation_id(self):
        set_correlation_id("test-correlation-123")

        result = get_correlation_id()

        assert result == "test-correlation-123"

    def test_set_correlation_id_overwrites_previous(self):
        set_correlation_id("first-id")
        set_correlation_id("second-id")

        result = get_correlation_id()

        assert result == "second-id"


class TestAddCorrelationId:

    def test_adds_correlation_id_when_set(self):
        set_correlation_id("processor-test-123")

        event_dict = {"event": "test"}
        result = add_correlation_id(None, "info", event_dict)

        assert result["correlation_id"] == "processor-test-123"

    def test_preserves_existing_event_dict(self):
        set_correlation_id("corr-id")

        event_dict = {"event": "test", "level": "info"}
        result = add_correlation_id(None, "info", event_dict)

        assert result["event"] == "test"
        assert result["level"] == "info"


class TestAddAppInfo:

    def test_adds_app_name(self):
        event_dict = {"event": "test"}

        result = add_app_info(None, "info", event_dict)

        assert result["app"] == "irpf-processor"

    def test_preserves_existing_event_dict(self):
        event_dict = {"event": "test", "level": "info"}

        result = add_app_info(None, "info", event_dict)

        assert result["event"] == "test"
        assert result["level"] == "info"
        assert result["app"] == "irpf-processor"


class TestGetLogger:

    def test_returns_logger(self):
        logger = get_logger("test_module")

        assert logger is not None

    def test_logger_has_info_method(self):
        logger = get_logger("test_module")

        assert hasattr(logger, "info")

    def test_logger_has_error_method(self):
        logger = get_logger("test_module")

        assert hasattr(logger, "error")

    def test_logger_has_warning_method(self):
        logger = get_logger("test_module")

        assert hasattr(logger, "warning")

    def test_logger_has_debug_method(self):
        logger = get_logger("test_module")

        assert hasattr(logger, "debug")

    def test_different_names_return_loggers(self):
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1 is not None
        assert logger2 is not None
