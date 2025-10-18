"""Comprehensive tests for utilities module to achieve 80%+ coverage."""

import asyncio
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console
from rich.json import JSON
from rich.panel import Panel
from rich.table import Table

from flock.utils.utilities import LoggingUtility, MetricsUtility


class TestMetricsUtility:
    """Tests for MetricsUtility class."""

    @pytest.fixture
    def metrics_utility(self):
        """Create a MetricsUtility instance."""
        return MetricsUtility()

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = Mock()
        agent.name = "test_agent"
        return agent

    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        ctx = Mock()
        ctx.state = {}
        ctx.task_id = "task_123"
        return ctx

    @pytest.fixture
    def mock_inputs(self):
        """Create mock inputs."""
        inputs = Mock()
        inputs.artifacts = []
        return inputs

    @pytest.fixture
    def mock_result(self):
        """Create a mock result."""
        result = Mock()
        result.metrics = {}
        result.artifacts = []
        result.logs = []
        return result

    @pytest.mark.asyncio
    async def test_metrics_utility_name(self, metrics_utility):
        """Test that MetricsUtility has correct name."""
        assert metrics_utility.name == "metrics"

    @pytest.mark.asyncio
    async def test_on_pre_evaluate_records_start_time(
        self, metrics_utility, mock_agent, mock_context, mock_inputs
    ):
        """Test that on_pre_evaluate records start time."""
        # Act
        result = await metrics_utility.on_pre_evaluate(
            mock_agent, mock_context, mock_inputs
        )

        # Assert
        assert result == mock_inputs
        assert f"{mock_agent.name}:start" in mock_context.state["metrics"]
        assert isinstance(
            mock_context.state["metrics"][f"{mock_agent.name}:start"], float
        )

    @pytest.mark.asyncio
    async def test_on_post_evaluate_calculates_duration(
        self, metrics_utility, mock_agent, mock_context, mock_inputs, mock_result
    ):
        """Test that on_post_evaluate calculates duration."""
        # Arrange
        start_time = time.perf_counter()
        mock_context.state["metrics"] = {f"{mock_agent.name}:start": start_time}

        # Act
        await asyncio.sleep(0.01)  # Small delay to ensure measurable duration
        result = await metrics_utility.on_post_evaluate(
            mock_agent, mock_context, mock_inputs, mock_result
        )

        # Assert
        assert result == mock_result
        duration_key = f"{mock_agent.name}:duration_ms"
        assert duration_key in mock_context.state["metrics"]
        assert mock_context.state["metrics"][duration_key] > 0
        assert duration_key in result.metrics

    @pytest.mark.asyncio
    async def test_on_post_evaluate_no_start_time(
        self, metrics_utility, mock_agent, mock_context, mock_inputs, mock_result
    ):
        """Test on_post_evaluate when no start time is recorded."""
        # Arrange - no start time in state
        mock_context.state = {}

        # Act
        result = await metrics_utility.on_post_evaluate(
            mock_agent, mock_context, mock_inputs, mock_result
        )

        # Assert
        assert result == mock_result
        assert f"{mock_agent.name}:duration_ms" not in result.metrics

    @pytest.mark.asyncio
    async def test_metrics_flow_integration(
        self, metrics_utility, mock_agent, mock_context, mock_inputs, mock_result
    ):
        """Test complete metrics flow from pre to post evaluate."""
        # Act - Pre-evaluate
        await metrics_utility.on_pre_evaluate(mock_agent, mock_context, mock_inputs)

        # Small delay
        await asyncio.sleep(0.01)

        # Act - Post-evaluate
        await metrics_utility.on_post_evaluate(
            mock_agent, mock_context, mock_inputs, mock_result
        )

        # Assert
        assert f"{mock_agent.name}:duration_ms" in mock_result.metrics
        assert mock_result.metrics[f"{mock_agent.name}:duration_ms"] > 0


class TestLoggingUtility:
    """Tests for LoggingUtility class."""

    @pytest.fixture
    def mock_console(self):
        """Create a mock console."""
        console = Mock(spec=Console)
        console.log = Mock()
        console.print = Mock()
        return console

    @pytest.fixture
    def logging_utility(self, mock_console):
        """Create a LoggingUtility instance with mock console."""
        return LoggingUtility(console=mock_console)

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = Mock()
        agent.name = "test_agent"
        return agent

    @pytest.fixture
    def mock_context(self):
        """Create a mock context."""
        ctx = Mock()
        ctx.state = {}
        ctx.task_id = "task_123"
        return ctx

    @pytest.fixture
    def mock_inputs(self):
        """Create mock eval inputs."""
        inputs = Mock()
        inputs.artifacts = []
        return inputs

    @pytest.fixture
    def mock_result(self):
        """Create a mock eval result."""
        result = Mock()
        result.metrics = {"test_metric": 100.5}
        result.artifacts = []
        result.logs = ["log line 1", "log line 2"]
        return result

    def test_logging_utility_initialization_default_console(self):
        """Test LoggingUtility initialization with default console."""
        with (
            patch("flock.utils.utilities.Console") as MockConsole,
            patch("sys.stdout") as mock_stdout,
        ):
            mock_console_instance = Mock()
            MockConsole.return_value = mock_console_instance

            utility = LoggingUtility()

            MockConsole.assert_called_once_with(
                file=mock_stdout,
                force_terminal=True,
                highlight=False,
                log_time=True,
                log_path=False,
            )
            assert utility._console == mock_console_instance
            assert utility._highlight_json is True
            assert utility._stream_tokens is True

    def test_logging_utility_initialization_custom_settings(self, mock_console):
        """Test LoggingUtility initialization with custom settings."""
        utility = LoggingUtility(
            console=mock_console, highlight_json=False, stream_tokens=False
        )

        assert utility._console == mock_console
        assert utility._highlight_json is False
        assert utility._stream_tokens is False
        assert utility._stream_context == {}

    @pytest.mark.asyncio
    async def test_on_initialize_logs_start(
        self, logging_utility, mock_console, mock_agent, mock_context
    ):
        """Test on_initialize logs agent start."""
        # Act
        await logging_utility.on_initialize(mock_agent, mock_context)

        # Assert
        mock_console.log.assert_called_once_with(
            f"[{mock_agent.name}] start task={mock_context.task_id}"
        )

    @pytest.mark.asyncio
    async def test_on_pre_consume_with_artifacts(
        self, logging_utility, mock_console, mock_agent, mock_context
    ):
        """Test on_pre_consume with artifacts."""
        # Arrange
        artifact1 = Mock()
        artifact1.id = "art123456789"
        artifact1.type = "TestArtifact"
        artifacts = [artifact1]

        with patch.object(logging_utility, "_render_artifacts") as mock_render:
            # Act
            result = await logging_utility.on_pre_consume(
                mock_agent, mock_context, artifacts
            )

            # Assert
            assert result == artifacts
            mock_console.log.assert_called_once()
            log_message = mock_console.log.call_args[0][0]
            assert f"[{mock_agent.name}] consume n=1 artifacts" in log_message
            mock_render.assert_called_once_with(
                mock_agent.name, artifacts, role="input"
            )

    @pytest.mark.asyncio
    async def test_on_pre_consume_empty_artifacts(
        self, logging_utility, mock_console, mock_agent, mock_context
    ):
        """Test on_pre_consume with no artifacts."""
        # Arrange
        artifacts = []

        # Act
        result = await logging_utility.on_pre_consume(
            mock_agent, mock_context, artifacts
        )

        # Assert
        assert result == artifacts
        log_message = mock_console.log.call_args[0][0]
        assert "<none>" in log_message

    @pytest.mark.asyncio
    async def test_on_pre_evaluate_starts_stream(
        self, logging_utility, mock_agent, mock_context, mock_inputs
    ):
        """Test on_pre_evaluate starts streaming when enabled."""
        with patch.object(logging_utility, "_maybe_start_stream") as mock_start:
            # Act
            result = await logging_utility.on_pre_evaluate(
                mock_agent, mock_context, mock_inputs
            )

            # Assert
            assert result == mock_inputs
            mock_start.assert_called_once_with(mock_agent, mock_context)

    @pytest.mark.asyncio
    async def test_on_pre_evaluate_no_stream(
        self, mock_console, mock_agent, mock_context, mock_inputs
    ):
        """Test on_pre_evaluate doesn't start stream when disabled."""
        utility = LoggingUtility(console=mock_console, stream_tokens=False)

        with patch.object(utility, "_maybe_start_stream") as mock_start:
            # Act
            result = await utility.on_pre_evaluate(
                mock_agent, mock_context, mock_inputs
            )

            # Assert
            assert result == mock_inputs
            mock_start.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_post_evaluate_renders_all(
        self,
        logging_utility,
        mock_console,
        mock_agent,
        mock_context,
        mock_inputs,
        mock_result,
    ):
        """Test on_post_evaluate renders metrics, artifacts, and logs."""
        with (
            patch.object(logging_utility, "_render_metrics") as mock_metrics,
            patch.object(logging_utility, "_render_artifacts") as mock_artifacts,
            patch.object(logging_utility, "_render_logs") as mock_logs,
            patch.object(logging_utility, "_finalize_stream") as mock_finalize,
        ):
            # Act
            result = await logging_utility.on_post_evaluate(
                mock_agent, mock_context, mock_inputs, mock_result
            )

            # Assert
            assert result == mock_result
            mock_metrics.assert_called_once_with(mock_agent.name, mock_result.metrics)
            mock_artifacts.assert_called_once_with(
                mock_agent.name, mock_result.artifacts, role="output"
            )
            mock_logs.assert_called_once_with(mock_agent.name, mock_result.logs)
            mock_finalize.assert_called_once_with(mock_agent, mock_context)

    @pytest.mark.asyncio
    async def test_on_post_publish(
        self, logging_utility, mock_console, mock_agent, mock_context
    ):
        """Test on_post_publish logs published artifact."""
        # Arrange
        artifact = Mock()
        artifact.visibility = Mock()
        artifact.visibility.kind = "Private"
        artifact.id = "art123"
        artifact.type = "TestArtifact"
        artifact.payload = {"test": "data"}

        with patch.object(logging_utility, "_build_artifact_panel") as mock_build:
            mock_panel = Mock(spec=Panel)
            mock_build.return_value = mock_panel

            # Act
            await logging_utility.on_post_publish(mock_agent, mock_context, artifact)

            # Assert
            mock_build.assert_called_once_with(
                artifact, role="published", subtitle="visibility=Private"
            )
            mock_console.print.assert_called_once_with(mock_panel)

    @pytest.mark.asyncio
    async def test_on_error_logs_and_aborts_stream(
        self, logging_utility, mock_console, mock_agent, mock_context
    ):
        """Test on_error logs error and aborts stream."""
        error = ValueError("Test error")

        with patch.object(logging_utility, "_abort_stream") as mock_abort:
            # Act
            await logging_utility.on_error(mock_agent, mock_context, error)

            # Assert
            mock_console.log.assert_called_once()
            log_call = mock_console.log.call_args
            assert f"[{mock_agent.name}] error" in log_call[0][0]
            assert log_call[1]["style"] == "bold red"
            mock_abort.assert_called_once_with(mock_agent, mock_context)

    @pytest.mark.asyncio
    async def test_on_terminate_logs_end(
        self, logging_utility, mock_console, mock_agent, mock_context
    ):
        """Test on_terminate logs end and aborts stream."""
        with patch.object(logging_utility, "_abort_stream") as mock_abort:
            # Act
            await logging_utility.on_terminate(mock_agent, mock_context)

            # Assert
            mock_console.log.assert_called_once_with(
                f"[{mock_agent.name}] end task={mock_context.task_id}"
            )
            mock_abort.assert_called_once_with(mock_agent, mock_context)

    def test_render_artifacts(self, logging_utility, mock_console, mock_agent):
        """Test _render_artifacts method."""
        # Arrange
        artifact = Mock()
        artifact.id = "art123"
        artifact.type = "TestArtifact"
        artifacts = [artifact]

        with patch.object(logging_utility, "_build_artifact_panel") as mock_build:
            mock_panel = Mock(spec=Panel)
            mock_build.return_value = mock_panel

            # Act
            logging_utility._render_artifacts(mock_agent.name, artifacts, role="test")

            # Assert
            mock_build.assert_called_once_with(artifact, role="test")
            mock_console.print.assert_called_once_with(mock_panel)

    def test_build_artifact_panel_with_metadata(self, logging_utility):
        """Test _build_artifact_panel with full metadata."""
        # Arrange
        artifact = Mock()
        artifact.id = "art123456789"
        artifact.type = "TestArtifact"
        artifact.produced_by = "producer_agent"
        artifact.visibility = Mock()
        artifact.visibility.kind = "Public"
        artifact.payload = {"test": "data"}

        with patch.object(logging_utility, "_render_payload") as mock_render:
            mock_render.return_value = "rendered_payload"

            # Act
            panel = logging_utility._build_artifact_panel(artifact, role="test")

            # Assert
            assert isinstance(panel, Panel)
            assert panel.title == "test • TestArtifact@art12345"
            assert "from=producer_agent" in panel.subtitle
            assert "visibility=Public" in panel.subtitle
            mock_render.assert_called_once_with(artifact.payload)

    def test_build_artifact_panel_custom_subtitle(self, logging_utility):
        """Test _build_artifact_panel with custom subtitle."""
        # Arrange
        artifact = Mock()
        artifact.id = "art123"
        artifact.type = "TestArtifact"
        artifact.payload = None

        with patch.object(logging_utility, "_render_payload") as mock_render:
            # Act
            panel = logging_utility._build_artifact_panel(
                artifact, role="test", subtitle="custom"
            )

            # Assert
            assert panel.subtitle == "custom"

    def test_render_payload_none(self, logging_utility):
        """Test _render_payload with None."""
        from rich.pretty import Pretty

        result = logging_utility._render_payload(None)
        assert isinstance(result, Pretty)

    def test_render_payload_dict_with_json(self, logging_utility):
        """Test _render_payload with dictionary when JSON highlighting enabled."""
        payload = {"key": "value", "number": 42}
        result = logging_utility._render_payload(payload)
        assert isinstance(result, JSON)

    def test_render_payload_dict_no_json(self, mock_console):
        """Test _render_payload with dictionary when JSON highlighting disabled."""
        from rich.pretty import Pretty

        utility = LoggingUtility(console=mock_console, highlight_json=False)
        payload = {"key": "value"}
        result = utility._render_payload(payload)
        assert isinstance(result, Pretty)

    def test_render_payload_list(self, logging_utility):
        """Test _render_payload with list."""
        from rich.pretty import Pretty

        payload = [1, 2, 3]
        result = logging_utility._render_payload(payload)
        assert isinstance(result, Pretty)

    def test_render_payload_pydantic_model(self, logging_utility):
        """Test _render_payload with Pydantic-like model."""
        # Arrange
        payload = Mock()
        payload.model_dump = Mock(return_value={"field": "value"})

        # Act
        result = logging_utility._render_payload(payload)

        # Assert
        assert isinstance(result, JSON)
        payload.model_dump.assert_called_once()

    def test_render_payload_other(self, logging_utility):
        """Test _render_payload with other types."""
        from rich.pretty import Pretty

        payload = "simple string"
        result = logging_utility._render_payload(payload)
        assert isinstance(result, Pretty)

    def test_render_metrics(self, logging_utility, mock_console):
        """Test _render_metrics with various metric types."""
        # Arrange
        metrics = {"duration_ms": 123.456, "count": 10, "status": "success"}

        # Act
        logging_utility._render_metrics("agent", metrics)

        # Assert
        mock_console.print.assert_called_once()
        printed_table = mock_console.print.call_args[0][0]
        assert isinstance(printed_table, Table)

    def test_render_metrics_empty(self, logging_utility, mock_console):
        """Test _render_metrics with empty metrics."""
        logging_utility._render_metrics("agent", {})
        mock_console.print.assert_not_called()

    def test_render_logs_with_mixed_content(self, logging_utility, mock_console):
        """Test _render_logs with text and JSON output."""
        # Arrange
        logs = [
            "regular log line",
            'dspy.output={"result": "test", "score": 0.95}',
            "another log",
            "dspy.output=invalid json {",
        ]

        # Act
        logging_utility._render_logs("agent", logs)

        # Assert
        # Should print 2 panels: 1 for JSON, 1 for text
        assert mock_console.print.call_count == 2

        # Check JSON panel
        first_call = mock_console.print.call_args_list[0]
        json_panel = first_call[0][0]
        assert isinstance(json_panel, Panel)
        assert "dspy.output" in json_panel.title

        # Check text panel
        second_call = mock_console.print.call_args_list[1]
        text_panel = second_call[0][0]
        assert isinstance(text_panel, Panel)
        assert "logs" in text_panel.title

    def test_render_logs_empty(self, logging_utility, mock_console):
        """Test _render_logs with empty logs."""
        logging_utility._render_logs("agent", [])
        mock_console.print.assert_not_called()

    def test_summarize_artifact_with_id(self, logging_utility):
        """Test _summarize_artifact with artifact having ID."""
        artifact = Mock()
        artifact.id = "art123456789"
        artifact.type = "TestArtifact"

        result = logging_utility._summarize_artifact(artifact)
        assert result == "TestArtifact@art12345"

    def test_summarize_artifact_no_id(self, logging_utility):
        """Test _summarize_artifact with artifact having no ID."""
        artifact = Mock()
        artifact.id = None
        artifact.type = "TestArtifact"

        result = logging_utility._summarize_artifact(artifact)
        assert result == "TestArtifact@?"

    def test_summarize_artifact_exception(self, logging_utility):
        """Test _summarize_artifact when exception occurs."""
        artifact = Mock()
        artifact.id = Mock(side_effect=Exception("error"))

        result = logging_utility._summarize_artifact(artifact)
        assert "Mock" in result  # Will return repr(artifact)

    def test_stream_key_generation(self, logging_utility, mock_agent, mock_context):
        """Test _stream_key method."""
        key = logging_utility._stream_key(mock_agent, mock_context)
        assert key == f"{mock_context.task_id}:{mock_agent.name}"

    def test_attach_stream_queue(self, logging_utility):
        """Test _attach_stream_queue method."""
        state = {}
        queue = asyncio.Queue()

        logging_utility._attach_stream_queue(state, queue)

        assert "_logging" in state
        assert state["_logging"]["stream_queue"] == queue

    def test_detach_stream_queue(self, logging_utility):
        """Test _detach_stream_queue method."""
        queue = asyncio.Queue()
        state = {"_logging": {"stream_queue": queue, "other": "data"}}

        logging_utility._detach_stream_queue(state)

        assert "stream_queue" not in state["_logging"]
        assert state["_logging"]["other"] == "data"

    def test_detach_stream_queue_no_logging_state(self, logging_utility):
        """Test _detach_stream_queue with no logging state."""
        state = {}
        logging_utility._detach_stream_queue(state)  # Should not raise

    def test_detach_stream_queue_exception(self, logging_utility):
        """Test _detach_stream_queue handles exceptions."""
        state = {"_logging": Mock(side_effect=Exception("error"))}
        logging_utility._detach_stream_queue(state)  # Should not raise

    def test_maybe_start_stream_new(self, logging_utility, mock_agent, mock_context):
        """Test _maybe_start_stream creates new stream."""
        with (
            patch.object(logging_utility, "_attach_stream_queue") as mock_attach,
            patch("asyncio.create_task") as mock_create_task,
        ):
            mock_task = Mock()
            mock_create_task.return_value = mock_task

            # Act
            logging_utility._maybe_start_stream(mock_agent, mock_context)

            # Assert
            stream_key = logging_utility._stream_key(mock_agent, mock_context)
            assert stream_key in logging_utility._stream_context
            queue, task = logging_utility._stream_context[stream_key]
            assert isinstance(queue, asyncio.Queue)
            assert task == mock_task
            mock_attach.assert_called_once()

    def test_maybe_start_stream_existing(
        self, logging_utility, mock_agent, mock_context
    ):
        """Test _maybe_start_stream with existing stream."""
        # Arrange
        stream_key = logging_utility._stream_key(mock_agent, mock_context)
        existing_queue = Mock()
        existing_task = Mock()
        logging_utility._stream_context[stream_key] = (existing_queue, existing_task)

        with patch.object(logging_utility, "_attach_stream_queue") as mock_attach:
            # Act
            logging_utility._maybe_start_stream(mock_agent, mock_context)

            # Assert
            mock_attach.assert_not_called()
            # Should keep existing stream
            assert logging_utility._stream_context[stream_key] == (
                existing_queue,
                existing_task,
            )

    @pytest.mark.asyncio
    async def test_finalize_stream(self, logging_utility, mock_agent, mock_context):
        """Test _finalize_stream method."""
        # Arrange
        stream_key = logging_utility._stream_key(mock_agent, mock_context)
        queue = AsyncMock()
        task = Mock()  # Use regular Mock instead of AsyncMock for synchronous methods
        task.done = Mock(return_value=False)
        logging_utility._stream_context[stream_key] = (queue, task)

        with (
            patch.object(logging_utility, "_detach_stream_queue") as mock_detach,
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            # Act
            await logging_utility._finalize_stream(mock_agent, mock_context)

            # Assert
            assert stream_key not in logging_utility._stream_context
            mock_detach.assert_called_once_with(mock_context.state)
            queue.put.assert_called_once_with({"kind": "end"})
            task.done.assert_called_once()
            mock_wait.assert_called_once()

    @pytest.mark.asyncio
    async def test_finalize_stream_timeout(
        self, logging_utility, mock_agent, mock_context
    ):
        """Test _finalize_stream with timeout."""
        # Arrange
        stream_key = logging_utility._stream_key(mock_agent, mock_context)
        queue = AsyncMock()
        task = Mock()
        task.done = Mock(return_value=False)
        task.cancel = Mock()
        logging_utility._stream_context[stream_key] = (queue, task)

        with (
            patch.object(logging_utility, "_detach_stream_queue"),
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            # Act
            await logging_utility._finalize_stream(mock_agent, mock_context)

            # Assert
            task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_abort_stream(self, logging_utility, mock_agent, mock_context):
        """Test _abort_stream method."""
        # Arrange
        stream_key = logging_utility._stream_key(mock_agent, mock_context)
        queue = AsyncMock()

        # Create a coroutine that can be awaited
        async def dummy_coro():
            raise asyncio.CancelledError()

        task = asyncio.create_task(dummy_coro())
        task.done = Mock(return_value=False)
        task.cancel = Mock()
        logging_utility._stream_context[stream_key] = (queue, task)

        with patch.object(logging_utility, "_detach_stream_queue") as mock_detach:
            # Act
            await logging_utility._abort_stream(mock_agent, mock_context)

            # Assert
            assert stream_key not in logging_utility._stream_context
            mock_detach.assert_called_once_with(mock_context.state)
            queue.put.assert_called_once_with({"kind": "end", "error": "aborted"})
            task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_consume_stream_text_chunks(self, mock_console):
        """Test _consume_stream processes text chunks."""
        # Create utility with proper mocked Live
        utility = LoggingUtility(console=mock_console, stream_tokens=True)

        # Arrange
        queue = asyncio.Queue()
        await queue.put({"kind": "chunk", "chunk": "Hello "})
        await queue.put({"kind": "chunk", "chunk": "World"})
        await queue.put({"kind": "end"})

        with patch("flock.utils.utilities.Live") as MockLive:
            mock_live_instance = Mock()
            mock_live_instance.__enter__ = Mock(return_value=mock_live_instance)
            mock_live_instance.__exit__ = Mock(return_value=None)
            mock_live_instance.update = Mock()
            MockLive.return_value = mock_live_instance

            # Act
            await utility._consume_stream("agent", "key", queue)

            # Assert
            mock_console.print.assert_called_once()
            panel = mock_console.print.call_args[0][0]
            assert isinstance(panel, Panel)
            assert "stream transcript" in panel.title

    @pytest.mark.asyncio
    async def test_consume_stream_status_message(self, mock_console):
        """Test _consume_stream processes status messages."""
        # Create utility with proper mocked Live
        utility = LoggingUtility(console=mock_console, stream_tokens=True)

        # Arrange
        queue = asyncio.Queue()
        await queue.put({"kind": "status", "message": "Processing", "stage": "init"})
        await queue.put({"kind": "end"})

        with patch("flock.utils.utilities.Live") as MockLive:
            mock_live_instance = Mock()
            mock_live_instance.__enter__ = Mock(return_value=mock_live_instance)
            mock_live_instance.__exit__ = Mock(return_value=None)
            mock_live_instance.update = Mock()
            MockLive.return_value = mock_live_instance

            # Act
            await utility._consume_stream("agent", "key", queue)

            # Assert
            mock_console.print.assert_called_once()
            panel = mock_console.print.call_args[0][0]
            assert isinstance(panel, Panel)

    @pytest.mark.asyncio
    async def test_consume_stream_error_message(self, mock_console):
        """Test _consume_stream processes error messages."""
        # Create utility with proper mocked Live
        utility = LoggingUtility(console=mock_console, stream_tokens=True)

        # Arrange
        queue = asyncio.Queue()
        await queue.put({"kind": "error", "message": "Something went wrong"})
        await queue.put({"kind": "end"})

        with patch("flock.utils.utilities.Live") as MockLive:
            mock_live_instance = Mock()
            mock_live_instance.__enter__ = Mock(return_value=mock_live_instance)
            mock_live_instance.__exit__ = Mock(return_value=None)
            mock_live_instance.update = Mock()
            MockLive.return_value = mock_live_instance

            # Act
            await utility._consume_stream("agent", "key", queue)

            # Assert
            mock_console.print.assert_called_once()

    @pytest.mark.asyncio
    async def test_consume_stream_empty(self, logging_utility):
        """Test _consume_stream with empty stream."""
        # Arrange
        queue = asyncio.Queue()
        await queue.put({"kind": "end"})

        with patch.object(logging_utility._console, "print") as mock_print:
            # Act
            await logging_utility._consume_stream("agent", "key", queue)

            # Assert
            mock_print.assert_not_called()  # No transcript if body is empty


class TestIntegration:
    """Integration tests for utilities module."""

    @pytest.mark.asyncio
    async def test_metrics_and_logging_together(self):
        """Test MetricsUtility and LoggingUtility working together."""
        # Arrange
        mock_console = Mock(spec=Console)
        metrics_util = MetricsUtility()
        logging_util = LoggingUtility(console=mock_console, stream_tokens=False)

        agent = Mock()
        agent.name = "integration_agent"

        ctx = Mock()
        ctx.state = {}
        ctx.task_id = "task_integration"

        inputs = Mock()
        inputs.artifacts = []

        result = Mock()
        result.metrics = {}
        result.artifacts = []
        result.logs = []

        # Act
        await metrics_util.on_pre_evaluate(agent, ctx, inputs)
        await logging_util.on_initialize(agent, ctx)

        await asyncio.sleep(0.01)

        await metrics_util.on_post_evaluate(agent, ctx, inputs, result)
        await logging_util.on_terminate(agent, ctx)

        # Assert
        assert f"{agent.name}:duration_ms" in result.metrics
        assert mock_console.log.call_count >= 2  # At least start and end logs

    @pytest.mark.asyncio
    async def test_error_handling_flow(self):
        """Test error handling flow in LoggingUtility."""
        # Arrange
        mock_console = Mock(spec=Console)
        logging_util = LoggingUtility(console=mock_console)

        agent = Mock()
        agent.name = "error_agent"

        ctx = Mock()
        ctx.state = {}
        ctx.task_id = "task_error"

        error = RuntimeError("Test error")

        # Act
        await logging_util.on_initialize(agent, ctx)
        await logging_util.on_error(agent, ctx, error)

        # Assert
        # Check that error was logged
        error_log_called = any(
            "error" in str(call) and "RuntimeError" in str(call)
            for call in mock_console.log.call_args_list
        )
        assert error_log_called
