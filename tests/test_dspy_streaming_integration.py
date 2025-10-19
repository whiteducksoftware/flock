"""Integration tests for DSPy streaming executor with end-to-end flow.

These tests validate the complete streaming pipeline from DSPy generator
through normalization to sink dispatch, ensuring both WebSocket and Rich
sinks work correctly in composition.
"""

import asyncio
from collections import OrderedDict
from types import SimpleNamespace
from uuid import uuid4

import pytest

from flock.dashboard.events import StreamingOutputEvent
from flock.engines.dspy.streaming_executor import DSPyStreamingExecutor


class FakeDSPyModule:
    """Mock DSPy module with streaming support."""

    class Prediction:
        """Mock DSPy Prediction."""

        def __init__(self, output: str, summary: str) -> None:
            self.output = output
            self.summary = summary

    class streaming:  # noqa: N801 - matches DSPy's lowercase class name
        """Mock streaming module."""

        class StatusMessage:
            def __init__(self, message: str) -> None:
                self.message = message

        class StreamResponse:
            def __init__(
                self, chunk: str, signature_field_name: str | None = None
            ) -> None:
                self.chunk = chunk
                self.signature_field_name = signature_field_name

        class StreamListener:
            def __init__(self, signature_field_name: str) -> None:
                self.signature_field_name = signature_field_name

    @staticmethod
    def streamify(program, is_async_program=True, stream_listeners=None):  # noqa: ARG004
        """Mock streamify that returns a callable."""
        return program


class FakeSignature:
    """Mock DSPy Signature."""

    def __init__(self) -> None:
        self.output_fields = {
            "description": SimpleNamespace(annotation=str),
            "output": SimpleNamespace(annotation=str),
            "summary": SimpleNamespace(annotation=str),
        }


async def fake_stream_generator():
    """Mock async generator that yields streaming events."""
    # Yield status message
    yield FakeDSPyModule.streaming.StatusMessage("Processing input...")

    # Yield tokens for output field
    yield FakeDSPyModule.streaming.StreamResponse(
        "Hello", signature_field_name="output"
    )
    yield FakeDSPyModule.streaming.StreamResponse(" ", signature_field_name="output")
    yield FakeDSPyModule.streaming.StreamResponse(
        "world", signature_field_name="output"
    )

    # Yield tokens for summary field
    yield FakeDSPyModule.streaming.StreamResponse(
        "Brief", signature_field_name="summary"
    )
    yield FakeDSPyModule.streaming.StreamResponse(
        " summary", signature_field_name="summary"
    )

    # Yield final prediction
    yield FakeDSPyModule.Prediction(output="Hello world", summary="Brief summary")


@pytest.mark.asyncio
async def test_execute_streaming_websocket_only_end_to_end():
    """Integration test: WebSocket-only streaming (dashboard mode).

    Validates:
    - Stream is consumed correctly
    - All events are emitted in order
    - Terminal events appear with correct format
    - Final result is returned
    - flush() awaits all broadcast tasks
    """
    # Arrange
    executor = DSPyStreamingExecutor(
        status_output_field="_status",
        stream_vertical_overflow="crop",
        theme="afterglow",
        no_output=True,
    )

    correlation_id = uuid4()
    ctx = SimpleNamespace(correlation_id=correlation_id, task_id="task-123")
    agent = SimpleNamespace(name="test_agent", outputs=[])
    artifact_id = uuid4()

    events: list[StreamingOutputEvent] = []
    broadcast_call_count = 0

    async def mock_broadcast(event: StreamingOutputEvent) -> None:
        nonlocal broadcast_call_count
        broadcast_call_count += 1
        events.append(event)
        # Simulate network delay
        await asyncio.sleep(0.001)

    # Mock the global broadcast function
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = mock_broadcast

    try:
        # Create a fake program that returns our generator
        def fake_program(**kwargs):
            return fake_stream_generator()

        # Act
        result, display_data = await executor.execute_streaming_websocket_only(
            dspy_mod=FakeDSPyModule,
            program=fake_program,
            signature=FakeSignature(),
            description="Test description",
            payload={"description": "Test description", "input": "test"},
            agent=agent,
            ctx=ctx,
            pre_generated_artifact_id=artifact_id,
            output_group=None,
        )

        # Assert - Final result
        assert result is not None
        assert isinstance(result, FakeDSPyModule.Prediction)
        assert result.output == "Hello world"
        assert result.summary == "Brief summary"
        assert display_data is None  # WebSocket-only returns None for display

        # Assert - All events were emitted
        assert len(events) >= 7  # 1 status + 5 tokens + 2 terminal events (minimum)

        # Assert - Event sequence is monotonic
        sequences = [e.sequence for e in events]
        assert sequences == list(range(len(events)))

        # Assert - First event is status
        assert events[0].output_type == "log"
        assert "Processing input..." in events[0].content

        # Assert - Middle events are tokens
        token_events = [e for e in events if e.output_type == "llm_token"]
        assert len(token_events) == 5  # "Hello", " ", "world", "Brief", " summary"

        # Assert - Terminal events exist and are correct
        terminal_events = [e for e in events if e.is_final]
        assert len(terminal_events) == 2
        assert "Amount of output tokens: 5" in terminal_events[0].content
        assert terminal_events[0].output_type == "log"
        assert terminal_events[1].content == "--- End of output ---"
        assert terminal_events[1].output_type == "log"

        # Assert - All events have correct metadata
        for event in events:
            assert event.correlation_id == str(correlation_id)
            assert event.agent_name == "test_agent"
            assert event.run_id == "task-123"
            assert event.artifact_id == str(artifact_id)
            assert event.artifact_type == "output"

    finally:
        # Restore original broadcast
        Agent._websocket_broadcast_global = original_broadcast


@pytest.mark.asyncio
async def test_execute_streaming_cli_with_websocket_end_to_end(monkeypatch):
    """Integration test: CLI mode with both Rich and WebSocket sinks.

    Validates:
    - Both sinks receive all events
    - Rich display_data is populated correctly
    - WebSocket events are broadcast
    - Final display data is returned for rendering
    - flush() awaits WebSocket tasks
    """
    # Mock Rich components to avoid terminal rendering
    from unittest.mock import MagicMock

    mock_console = MagicMock()
    mock_live = MagicMock()
    mock_live.__enter__ = MagicMock(return_value=mock_live)
    mock_live.__exit__ = MagicMock(return_value=None)

    def mock_live_constructor(*args, **kwargs):
        return mock_live

    monkeypatch.setattr("rich.console.Console", lambda: mock_console)
    monkeypatch.setattr("rich.live.Live", mock_live_constructor)

    # Arrange
    executor = DSPyStreamingExecutor(
        status_output_field="_status",
        stream_vertical_overflow="crop",
        theme="afterglow",
        no_output=False,  # Enable output to test RichSink
    )

    correlation_id = uuid4()
    ctx = SimpleNamespace(correlation_id=correlation_id, task_id="task-456")
    agent = SimpleNamespace(name="cli_agent", outputs=[])
    artifact_id = uuid4()

    events: list[StreamingOutputEvent] = []

    async def mock_broadcast(event: StreamingOutputEvent) -> None:
        events.append(event)
        await asyncio.sleep(0.001)

    # Mock the global broadcast function
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = mock_broadcast

    try:

        def fake_program(**kwargs):
            return fake_stream_generator()

        # Act
        result, display_tuple = await executor.execute_streaming(
            dspy_mod=FakeDSPyModule,
            program=fake_program,
            signature=FakeSignature(),
            description="CLI test",
            payload={"description": "CLI test", "input": "test"},
            agent=agent,
            ctx=ctx,
            pre_generated_artifact_id=artifact_id,
            output_group=None,
        )

        # Assert - Final result
        assert result is not None
        assert isinstance(result, FakeDSPyModule.Prediction)
        assert result.output == "Hello world"
        assert result.summary == "Brief summary"

        # Assert - Display tuple is returned
        assert display_tuple is not None
        formatter, display_data, theme_dict, styles, agent_label = display_tuple

        # Assert - Display data is populated correctly
        assert isinstance(display_data, OrderedDict)
        assert display_data["id"] == str(artifact_id)
        assert display_data["produced_by"] == "cli_agent"
        assert display_data["correlation_id"] == str(correlation_id)

        # Assert - Payload contains final values (not streaming buffers)
        payload = display_data["payload"]
        assert payload["output"] == "Hello world"
        assert payload["summary"] == "Brief summary"
        assert "_streaming" not in payload  # Streaming buffer removed

        # Assert - Status field is removed after finalization
        assert "status" not in display_data

        # Assert - Timestamp is set
        assert display_data["created_at"] != "streaming..."
        assert "T" in display_data["created_at"]  # ISO format

        # Assert - WebSocket events were also emitted
        assert len(events) >= 7
        terminal_events = [e for e in events if e.is_final]
        assert len(terminal_events) == 2
        assert "Amount of output tokens: 5" in terminal_events[0].content
        assert terminal_events[1].content == "--- End of output ---"

    finally:
        Agent._websocket_broadcast_global = original_broadcast


@pytest.mark.asyncio
async def test_execute_streaming_handles_empty_tokens():
    """Integration test: Streaming with empty/None tokens (should be filtered)."""

    async def sparse_stream_generator():
        yield FakeDSPyModule.streaming.StatusMessage("Starting")
        yield FakeDSPyModule.streaming.StreamResponse(
            "", signature_field_name="output"
        )  # Empty
        yield FakeDSPyModule.streaming.StreamResponse(
            "Token", signature_field_name="output"
        )
        yield FakeDSPyModule.streaming.StreamResponse(
            None, signature_field_name="output"
        )  # None
        yield FakeDSPyModule.Prediction(output="Token", summary="Done")

    executor = DSPyStreamingExecutor(
        status_output_field="_status",
        stream_vertical_overflow="crop",
        theme="afterglow",
        no_output=True,
    )

    ctx = SimpleNamespace(correlation_id=uuid4(), task_id="task-789")
    agent = SimpleNamespace(name="filter_agent", outputs=[])
    artifact_id = uuid4()

    events: list[StreamingOutputEvent] = []

    async def mock_broadcast(event: StreamingOutputEvent) -> None:
        events.append(event)

    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = mock_broadcast

    try:

        def fake_program(**kwargs):
            return sparse_stream_generator()

        result, _ = await executor.execute_streaming_websocket_only(
            dspy_mod=FakeDSPyModule,
            program=fake_program,
            signature=FakeSignature(),
            description="Filter test",
            payload={"description": "Filter test", "input": "test"},
            agent=agent,
            ctx=ctx,
            pre_generated_artifact_id=artifact_id,
            output_group=None,
        )

        # Assert - Only non-empty tokens are emitted
        token_events = [e for e in events if e.output_type == "llm_token"]
        assert len(token_events) == 1  # Only "Token", not empty or None
        assert token_events[0].content == "Token"

        # Assert - Terminal events report correct count (1 token)
        terminal_events = [e for e in events if e.is_final]
        assert "Amount of output tokens: 1" in terminal_events[0].content

    finally:
        Agent._websocket_broadcast_global = original_broadcast


@pytest.mark.asyncio
async def test_execute_streaming_without_websocket_manager(monkeypatch):
    """Integration test: CLI streaming without WebSocket manager (fallback behavior)."""
    # Mock Rich components
    from unittest.mock import MagicMock

    mock_console = MagicMock()
    mock_live = MagicMock()
    mock_live.__enter__ = MagicMock(return_value=mock_live)
    mock_live.__exit__ = MagicMock(return_value=None)

    monkeypatch.setattr("rich.console.Console", lambda: mock_console)
    monkeypatch.setattr("rich.live.Live", lambda *args, **kwargs: mock_live)

    executor = DSPyStreamingExecutor(
        status_output_field="_status",
        stream_vertical_overflow="crop",
        theme="afterglow",
        no_output=False,
    )

    ctx = SimpleNamespace(correlation_id=uuid4(), task_id="task-no-ws")
    agent = SimpleNamespace(name="no_ws_agent", outputs=[])
    artifact_id = uuid4()

    # Mock no WebSocket manager
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = None

    try:

        def fake_program(**kwargs):
            return fake_stream_generator()

        # Act - Should work without WebSocket
        result, display_tuple = await executor.execute_streaming(
            dspy_mod=FakeDSPyModule,
            program=fake_program,
            signature=FakeSignature(),
            description="No WS test",
            payload={"description": "No WS test", "input": "test"},
            agent=agent,
            ctx=ctx,
            pre_generated_artifact_id=artifact_id,
            output_group=None,
        )

        # Assert - Result is correct
        assert result.output == "Hello world"

        # Assert - Display data is still populated
        _, display_data, _, _, _ = display_tuple
        assert display_data["payload"]["output"] == "Hello world"

    finally:
        Agent._websocket_broadcast_global = original_broadcast


@pytest.mark.asyncio
async def test_websocket_only_fallback_to_standard_execution():
    """Integration test: WebSocket-only mode falls back to standard execution when no WS manager."""
    executor = DSPyStreamingExecutor(
        status_output_field="_status",
        stream_vertical_overflow="crop",
        theme="afterglow",
        no_output=True,
    )

    ctx = SimpleNamespace(correlation_id=uuid4(), task_id="task-fallback")
    agent = SimpleNamespace(name="fallback_agent", outputs=[])
    artifact_id = uuid4()

    # Mock no WebSocket manager
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = None

    try:
        # Create a simple non-streaming program
        def simple_program(**kwargs):
            return FakeDSPyModule.Prediction(
                output="Standard output", summary="Standard summary"
            )

        # Act - Should fallback to execute_standard
        result, display_data = await executor.execute_streaming_websocket_only(
            dspy_mod=FakeDSPyModule,
            program=simple_program,
            signature=FakeSignature(),
            description="Fallback test",
            payload={"description": "Fallback test", "input": "test"},
            agent=agent,
            ctx=ctx,
            pre_generated_artifact_id=artifact_id,
            output_group=None,
        )

        # Assert - Result is correct (from standard execution)
        assert result.output == "Standard output"
        assert result.summary == "Standard summary"
        assert display_data is None  # WebSocket-only always returns None for display

    finally:
        Agent._websocket_broadcast_global = original_broadcast
