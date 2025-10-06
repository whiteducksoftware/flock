"""Comprehensive tests for logging configuration module."""

import io
import logging
import sys
from unittest.mock import Mock, patch

import pytest

from flock.logging.logging import (
    BOLD_CATEGORIES,
    COLOR_MAP,
    LOG_LEVELS,
    LOGGERS,
    MAX_LENGTH,
    DummyLogger,
    FlockLogger,
    ImmediateFlushSink,
    PrintAndFlushSink,
    color_for_category,
    configure_logging,
    custom_format,
    dummy_logger,
    get_current_trace_id,
    get_default_severity,
    get_logger,
    get_module_loggers,
    in_workflow_context,
    truncate_for_logging,
)


class TestLogLevels:
    """Test log level constants and mappings."""

    def test_log_levels_mapping(self):
        """Test that LOG_LEVELS contains expected mappings."""
        assert LOG_LEVELS["CRITICAL"] == logging.CRITICAL
        assert LOG_LEVELS["ERROR"] == logging.ERROR
        assert LOG_LEVELS["WARNING"] == logging.WARNING
        assert LOG_LEVELS["INFO"] == logging.INFO
        assert LOG_LEVELS["DEBUG"] == logging.DEBUG
        assert LOG_LEVELS["SUCCESS"] == 35
        assert LOG_LEVELS["NO_LOGS"] == 100

    def test_get_default_severity_with_string(self):
        """Test get_default_severity with string levels."""
        assert get_default_severity("DEBUG") == LOG_LEVELS["DEBUG"]
        assert get_default_severity("INFO") == LOG_LEVELS["INFO"]
        assert get_default_severity("WARNING") == LOG_LEVELS["WARNING"]
        assert get_default_severity("ERROR") == LOG_LEVELS["ERROR"]
        assert get_default_severity("CRITICAL") == LOG_LEVELS["CRITICAL"]
        assert get_default_severity("SUCCESS") == LOG_LEVELS["SUCCESS"]
        assert get_default_severity("NO_LOGS") == LOG_LEVELS["NO_LOGS"]

    def test_get_default_severity_with_int(self):
        """Test get_default_severity with integer levels."""
        assert get_default_severity(10) == 10
        assert get_default_severity(20) == 20
        assert get_default_severity(30) == 30

    def test_get_default_severity_unknown_string(self):
        """Test get_default_severity with unknown string defaults to ERROR."""
        assert get_default_severity("UNKNOWN") == LOG_LEVELS["ERROR"]


class TestWorkflowContext:
    """Test workflow context detection."""

    def test_in_workflow_context_returns_false(self):
        """Test that in_workflow_context always returns False (as per implementation)."""
        assert in_workflow_context() is False


class TestTraceId:
    """Test trace ID functionality."""

    @patch("flock.logging.logging.trace.get_current_span")
    def test_get_current_trace_id_valid(self, mock_get_span):
        """Test getting trace ID with valid span."""
        mock_span = Mock()
        mock_context = Mock()
        mock_context.is_valid = True
        mock_context.trace_id = 0x12345678ABCDEF
        mock_span.get_span_context.return_value = mock_context
        mock_get_span.return_value = mock_span

        trace_id = get_current_trace_id()
        assert trace_id == "00000000000000000012345678abcdef"

    @patch("flock.logging.logging.trace.get_current_span")
    def test_get_current_trace_id_invalid(self, mock_get_span):
        """Test getting trace ID with invalid span."""
        mock_span = Mock()
        mock_context = Mock()
        mock_context.is_valid = False
        mock_span.get_span_context.return_value = mock_context
        mock_get_span.return_value = mock_span

        trace_id = get_current_trace_id()
        assert trace_id == "no-trace"


class TestColorMapping:
    """Test color mapping for categories."""

    def test_color_for_category_exact_match(self):
        """Test color_for_category with exact match."""
        assert color_for_category("flock") == "magenta"
        assert color_for_category("agent") == "blue"
        assert color_for_category("memory") == "yellow"
        assert color_for_category("api.ui") == "light-blue"

    def test_color_for_category_hierarchical(self):
        """Test color_for_category with hierarchical matching."""
        # Should match parent 'api'
        assert color_for_category("api.unknown.subsystem") == "white"
        # Should match parent 'module'
        assert color_for_category("module.new_module") == "light-green"

    def test_color_for_category_unknown(self):
        """Test color_for_category with unknown category."""
        assert color_for_category("completely.unknown.category") == "light-black"
        assert color_for_category("unknown") == "light-black"

    def test_bold_categories(self):
        """Test that BOLD_CATEGORIES contains expected values."""
        assert "flock" in BOLD_CATEGORIES
        assert "agent" in BOLD_CATEGORIES
        assert "workflow" in BOLD_CATEGORIES
        assert "registry" in BOLD_CATEGORIES
        assert "api" in BOLD_CATEGORIES
        assert "api.ui" in BOLD_CATEGORIES


class TestCustomFormat:
    """Test custom log formatting."""

    def test_custom_format_basic(self):
        """Test basic custom format function."""
        mock_level = Mock()
        mock_level.name = "INFO"
        record = {
            "time": Mock(strftime=Mock(return_value="2025-01-01 12:00:00")),
            "level": mock_level,
            "extra": {"category": "flock", "trace_id": "test-trace"},
            "message": "Test message",
        }

        formatted = custom_format(record)
        assert "2025-01-01 12:00:00" in formatted
        assert "INFO" in formatted
        assert "[flock]" in formatted
        assert "test-trace" in formatted
        assert "Test message" in formatted

    def test_custom_format_truncation(self):
        """Test message truncation in custom format."""
        long_message = "x" * (MAX_LENGTH + 100)
        mock_level = Mock()
        mock_level.name = "DEBUG"
        record = {
            "time": Mock(strftime=Mock(return_value="2025-01-01 12:00:00")),
            "level": mock_level,
            "extra": {"category": "test", "trace_id": "no-trace"},
            "message": long_message,
        }

        formatted = custom_format(record)
        assert "...+(100 chars)" in formatted
        # The formatted message contains truncated message plus formatting overhead
        # We just need to ensure the truncation indicator is present

    def test_custom_format_bold_category(self):
        """Test custom format with bold category."""
        mock_level = Mock()
        mock_level.name = "INFO"
        record = {
            "time": Mock(strftime=Mock(return_value="2025-01-01 12:00:00")),
            "level": mock_level,
            "extra": {"category": "flock", "trace_id": "test-trace"},
            "message": "Test",
        }

        formatted = custom_format(record)
        # Should contain bold tags for flock category
        assert "<bold>" in formatted
        assert "</bold>" in formatted
        assert "[flock]" in formatted

    def test_custom_format_escapes_braces(self):
        """Test that custom format escapes braces in messages."""
        mock_level = Mock()
        mock_level.name = "INFO"
        record = {
            "time": Mock(strftime=Mock(return_value="2025-01-01 12:00:00")),
            "level": mock_level,
            "extra": {"category": "test", "trace_id": "no-trace"},
            "message": "Message with {braces} and {more}",
        }

        formatted = custom_format(record)
        assert "{{braces}}" in formatted
        assert "{{more}}" in formatted


class TestSinks:
    """Test custom sink classes."""

    def test_immediate_flush_sink_default_stream(self):
        """Test ImmediateFlushSink with default stream."""
        sink = ImmediateFlushSink()
        assert sink._stream == sys.stderr

    def test_immediate_flush_sink_custom_stream(self):
        """Test ImmediateFlushSink with custom stream."""
        custom_stream = io.StringIO()
        sink = ImmediateFlushSink(stream=custom_stream)

        sink.write("Test message")
        assert custom_stream.getvalue() == "Test message"

    def test_immediate_flush_sink_flush_called(self):
        """Test that ImmediateFlushSink calls flush."""
        mock_stream = Mock()
        sink = ImmediateFlushSink(stream=mock_stream)

        sink.write("Test message")
        mock_stream.write.assert_called_once_with("Test message")
        mock_stream.flush.assert_called()

    def test_print_and_flush_sink(self, capsys):
        """Test PrintAndFlushSink."""
        sink = PrintAndFlushSink()

        # Write a message
        sink.write("Test message\n")

        # Check it was printed
        captured = capsys.readouterr()
        assert captured.out == "Test message\n"

    def test_print_and_flush_sink_flush(self):
        """Test PrintAndFlushSink flush method."""
        sink = PrintAndFlushSink()
        # Should not raise
        sink.flush()


class TestDummyLogger:
    """Test DummyLogger class."""

    def test_dummy_logger_methods(self):
        """Test that all DummyLogger methods exist and do nothing."""
        logger = DummyLogger()

        # All methods should exist and not raise
        logger.debug("test")
        logger.info("test")
        logger.warning("test")
        logger.error("test")
        logger.exception("test")
        logger.success("test")

    def test_dummy_logger_singleton(self):
        """Test that dummy_logger is available as module-level singleton."""
        assert dummy_logger is not None
        assert isinstance(dummy_logger, DummyLogger)


class TestFlockLogger:
    """Test FlockLogger class."""

    def test_flock_logger_initialization(self):
        """Test FlockLogger initialization."""
        logger = FlockLogger("test", LOG_LEVELS["INFO"])
        assert logger.name == "test"
        assert logger.min_level_severity == LOG_LEVELS["INFO"]

    @patch("flock.logging.logging.get_current_trace_id")
    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_get_logger(self, mock_loguru, mock_trace_id):
        """Test FlockLogger _get_logger method."""
        mock_trace_id.return_value = "test-trace-id"
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["INFO"])
        result = logger._get_logger()

        mock_loguru.bind.assert_called_once_with(
            name="test", category="test", trace_id="test-trace-id"
        )
        assert result == mock_bound

    def test_flock_logger_truncate_message(self):
        """Test FlockLogger message truncation."""
        logger = FlockLogger("test", LOG_LEVELS["INFO"])

        # Short message - no truncation
        short = "short message"
        assert logger._truncate_message(short, 100) == short

        # Long message - should truncate
        long = "x" * 150
        truncated = logger._truncate_message(long, 100)
        assert len(truncated) > 100  # Includes truncation indicator
        assert "...<yellow>+(50 chars)</yellow>" in truncated

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_debug(self, mock_loguru):
        """Test FlockLogger debug method."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["DEBUG"])
        logger.debug("test message")

        mock_bound.debug.assert_called_once_with("test message")

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_debug_filtered(self, mock_loguru):
        """Test FlockLogger debug method when level is filtered."""
        logger = FlockLogger("test", LOG_LEVELS["INFO"])
        logger.debug("test message")

        # Should not call loguru at all if filtered
        mock_loguru.bind.assert_not_called()

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_info(self, mock_loguru):
        """Test FlockLogger info method."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["INFO"])
        logger.info("test message")

        mock_bound.info.assert_called_once_with("test message")

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_warning(self, mock_loguru):
        """Test FlockLogger warning method."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["WARNING"])
        logger.warning("test message")

        mock_bound.warning.assert_called_once_with("test message")

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_error(self, mock_loguru):
        """Test FlockLogger error method."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["ERROR"])
        logger.error("test message")

        mock_bound.error.assert_called_once_with("test message")

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_exception(self, mock_loguru):
        """Test FlockLogger exception method."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["ERROR"])
        logger.exception("test exception")

        mock_bound.exception.assert_called_once_with("test exception")

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_success(self, mock_loguru):
        """Test FlockLogger success method."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["DEBUG"])
        logger.success("test success")

        mock_bound.success.assert_called_once_with("test success")

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_no_logs_level(self, mock_loguru):
        """Test FlockLogger with NO_LOGS level filters all messages."""
        logger = FlockLogger("test", LOG_LEVELS["NO_LOGS"])

        logger.debug("test")
        logger.info("test")
        logger.warning("test")
        logger.error("test")
        logger.exception("test")
        logger.success("test")

        # Should not call loguru at all
        mock_loguru.bind.assert_not_called()

    @patch("flock.logging.logging.loguru_logger")
    def test_flock_logger_with_max_length(self, mock_loguru):
        """Test FlockLogger respects max_length parameter."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["INFO"])
        long_message = "x" * 200

        logger.info(long_message, max_length=50)

        # Check that the message was truncated
        call_args = mock_bound.info.call_args[0][0]
        assert "...<yellow>+(150 chars)</yellow>" in call_args


class TestLoggerManagement:
    """Test logger management functions."""

    def test_get_logger_creates_new(self):
        """Test get_logger creates new logger if not cached."""
        # Clear cache first
        from flock.logging.logging import _LOGGER_CACHE

        _LOGGER_CACHE.clear()

        logger = get_logger("test_new")
        assert logger is not None
        assert logger.name == "test_new"
        assert "test_new" in _LOGGER_CACHE

    def test_get_logger_returns_cached(self):
        """Test get_logger returns cached logger."""
        from flock.logging.logging import _LOGGER_CACHE

        _LOGGER_CACHE.clear()

        logger1 = get_logger("test_cached")
        logger2 = get_logger("test_cached")
        assert logger1 is logger2

    def test_get_logger_default_name(self):
        """Test get_logger with default name."""
        logger = get_logger()
        assert logger.name == "flock"

    def test_get_logger_respects_specific_severity(self):
        """Test get_logger respects specific severity settings."""
        from flock.logging.logging import _LOGGER_CACHE, _SPECIFIC_SEVERITIES

        _LOGGER_CACHE.clear()
        _SPECIFIC_SEVERITIES["test_specific"] = LOG_LEVELS["DEBUG"]

        logger = get_logger("test_specific")
        assert logger.min_level_severity == LOG_LEVELS["DEBUG"]

    def test_get_module_loggers(self):
        """Test get_module_loggers returns module loggers."""
        from flock.logging.logging import _LOGGER_CACHE

        _LOGGER_CACHE.clear()

        # Create some module loggers
        get_logger("module.test1")
        get_logger("module.test2")
        get_logger("non_module")

        module_loggers = get_module_loggers()
        logger_names = [l.name for l in module_loggers]

        assert "module.test1" in logger_names
        assert "module.test2" in logger_names
        assert "non_module" not in logger_names


class TestConfigureLogging:
    """Test configure_logging function."""

    @patch("flock.logging.logging.logging.basicConfig")
    def test_configure_logging_basic(self, mock_basic_config):
        """Test basic configure_logging."""
        configure_logging("INFO", "WARNING", None)

        mock_basic_config.assert_called_with(level=LOG_LEVELS["WARNING"])
        # Check that the global variable was updated
        import flock.logging.logging as logging_module

        assert LOG_LEVELS["INFO"] == logging_module._DEFAULT_FLOCK_SEVERITY

    @patch("flock.logging.logging.logging.basicConfig")
    def test_configure_logging_with_specific_levels(self, mock_basic_config):
        """Test configure_logging with specific levels."""
        from flock.logging.logging import _LOGGER_CACHE, _SPECIFIC_SEVERITIES

        _LOGGER_CACHE.clear()
        _SPECIFIC_SEVERITIES.clear()

        # Create some loggers first
        logger1 = get_logger("test1")
        logger2 = get_logger("test2")

        specific = {"test1": "DEBUG", "test2": "ERROR"}

        configure_logging("INFO", "WARNING", specific)

        assert logger1.min_level_severity == LOG_LEVELS["DEBUG"]
        assert logger2.min_level_severity == LOG_LEVELS["ERROR"]
        assert _SPECIFIC_SEVERITIES["test1"] == LOG_LEVELS["DEBUG"]
        assert _SPECIFIC_SEVERITIES["test2"] == LOG_LEVELS["ERROR"]

    @patch("flock.logging.logging.logging.basicConfig")
    def test_configure_logging_with_int_levels(self, mock_basic_config):
        """Test configure_logging with integer levels."""
        configure_logging(20, 30, {"test": 10})

        mock_basic_config.assert_called_with(level=30)
        from flock.logging.logging import _DEFAULT_FLOCK_SEVERITY

        assert _DEFAULT_FLOCK_SEVERITY == 20


class TestTruncateForLogging:
    """Test truncate_for_logging utility function."""

    def test_truncate_string(self):
        """Test truncating long strings."""
        long_string = "x" * 200
        result = truncate_for_logging(long_string, max_item_length=50)
        assert "... (150 more chars)" in result

    def test_truncate_dict(self):
        """Test truncating dictionaries."""
        large_dict = {f"key{i}": f"value{i}" for i in range(20)}
        result = truncate_for_logging(large_dict, max_items=5)
        assert len(result) == 5

    def test_truncate_dict_recursive(self):
        """Test truncating nested dictionaries."""
        nested = {"key1": "x" * 200, "key2": {"nested": "y" * 200}}
        result = truncate_for_logging(nested, max_item_length=100)
        assert "... (100 more chars)" in result["key1"]
        # The nested dictionary is also recursively truncated
        assert isinstance(result["key2"], dict)
        assert "... (100 more chars)" in result["key2"]["nested"]

    def test_truncate_list(self):
        """Test truncating lists."""
        large_list = [f"item{i}" for i in range(20)]
        result = truncate_for_logging(large_list, max_items=5)
        assert len(result) == 6  # 5 items + truncation indicator
        assert "... (15 more items)" in result[-1]

    def test_truncate_list_recursive(self):
        """Test truncating lists with nested structures."""
        nested = ["x" * 200, ["y" * 200]]
        result = truncate_for_logging(nested, max_item_length=100)
        assert "... (100 more chars)" in result[0]
        # The nested list is also recursively truncated
        assert isinstance(result[1], list)
        assert "... (100 more chars)" in result[1][0]

    def test_truncate_other_types(self):
        """Test that other types are returned unchanged."""
        assert truncate_for_logging(42) == 42
        assert truncate_for_logging(3.14) == 3.14
        assert truncate_for_logging(True) is True
        assert truncate_for_logging(None) is None


class TestLoggerConstants:
    """Test logger constant definitions."""

    def test_loggers_list(self):
        """Test that LOGGERS list contains expected values."""
        assert "flock" in LOGGERS
        assert "agent" in LOGGERS
        assert "context" in LOGGERS
        assert "registry" in LOGGERS
        assert "workflow" in LOGGERS
        assert "api" in LOGGERS

    def test_color_map_completeness(self):
        """Test that COLOR_MAP has reasonable coverage."""
        # Check some key categories are mapped
        assert "flock" in COLOR_MAP
        assert "agent" in COLOR_MAP
        assert "unknown" in COLOR_MAP

        # All values should be strings (color names)
        for color in COLOR_MAP.values():
            assert isinstance(color, str)


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @patch("flock.logging.logging.loguru_logger")
    def test_logger_with_extra_args_kwargs(self, mock_loguru):
        """Test logger methods with extra args and kwargs."""
        mock_bound = Mock()
        mock_loguru.bind.return_value = mock_bound

        logger = FlockLogger("test", LOG_LEVELS["INFO"])
        logger.info("test {}", "arg", extra_kwarg="value")

        # The message gets its braces escaped in the FlockLogger._truncate_message
        # But actually the escaping happens in custom_format, not in FlockLogger
        # So the logger passes the message as-is
        mock_bound.info.assert_called_once_with("test {}", "arg", extra_kwarg="value")

    def test_custom_format_missing_fields(self):
        """Test custom format with missing fields in record."""
        mock_level = Mock()
        mock_level.name = "INFO"
        record = {
            "time": Mock(strftime=Mock(return_value="2025-01-01 12:00:00")),
            "level": mock_level,
            "extra": {},  # Missing category and trace_id
            "message": "Test",
        }

        # Should use defaults without crashing
        formatted = custom_format(record)
        assert "unknown" in formatted
        assert "no-trace" in formatted


@pytest.fixture(autouse=True)
def cleanup_logger_cache():
    """Clean up logger cache after each test."""
    yield
    # Clear the caches to avoid state pollution between tests
    from flock.logging.logging import _LOGGER_CACHE, _SPECIFIC_SEVERITIES

    _LOGGER_CACHE.clear()
    _SPECIFIC_SEVERITIES.clear()
