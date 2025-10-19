"""Shared streaming sink implementations for DSPy execution.

This module provides a composable sink pattern for consuming streaming output
from DSPy programs and routing it to different presentation layers (Rich terminal,
WebSocket dashboard, etc.).

Architecture
------------
The StreamSink protocol defines a minimal interface that all sinks must implement.
Sinks receive normalized streaming events (status messages, tokens, final predictions)
and handle presentation-specific logic (Rich display updates, WebSocket broadcasts, etc.).

Sinks are designed to be:
- Composable: Multiple sinks can consume the same stream in parallel
- Isolated: Each sink maintains its own state and error handling
- Testable: Sinks can be tested independently with mock dependencies

Error Handling Contract
-----------------------
Sinks SHOULD NOT raise exceptions during normal streaming operations. Instead:
- Log errors and continue processing remaining events
- Use defensive programming (null checks, try/except where appropriate)
- Only raise exceptions for unrecoverable errors (e.g., invalid configuration)

The streaming loop treats sink exceptions as fatal and will abort the stream.
For fault tolerance, sinks should catch and log their own errors.

Example Usage
-------------
Basic WebSocket-only streaming:

    async def ws_broadcast(event: StreamingOutputEvent) -> None:
        await websocket_manager.broadcast(event)

    def event_factory(output_type, content, seq, is_final):
        return StreamingOutputEvent(
            correlation_id="123",
            agent_name="agent",
            run_id="run-1",
            output_type=output_type,
            content=content,
            sequence=seq,
            is_final=is_final,
        )

    sink = WebSocketSink(ws_broadcast=ws_broadcast, event_factory=event_factory)

    async for value in stream:
        kind, text, field, final = normalize_value(value)
        if kind == "status":
            await sink.on_status(text)
        elif kind == "token":
            await sink.on_token(text, field)
        elif kind == "prediction":
            await sink.on_final(final, token_count)
            break

    await sink.flush()

Dual-sink composition (CLI with WebSocket):

    sinks = []
    if rich_enabled:
        sinks.append(RichSink(...))
    if ws_enabled:
        sinks.append(WebSocketSink(...))

    # Dispatch to all sinks
    for sink in sinks:
        await sink.on_token(text, field)
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, MutableMapping, Sequence
from typing import (
    Any,
    Protocol,
    runtime_checkable,
)

from pydantic import BaseModel

from flock.dashboard.events import StreamingOutputEvent
from flock.logging.logging import get_logger


logger = get_logger(__name__)


@runtime_checkable
class StreamSink(Protocol):
    """Minimal sink protocol for consuming normalized stream events.

    Sinks receive streaming events from DSPy execution and handle
    presentation-specific logic (Rich display, WebSocket broadcast, etc.).

    Implementations must be idempotent for on_final() to handle edge cases
    where the stream loop might call it multiple times.

    Error Handling
    --------------
    Implementations SHOULD catch and log their own errors rather than raising,
    to prevent one sink failure from aborting the entire stream. Only raise
    exceptions for unrecoverable errors during initialization/configuration.
    """

    async def on_status(self, text: str) -> None:
        """Process a status message from the LLM.

        Status messages are typically intermediate reasoning steps or
        progress indicators (e.g., "Analyzing input...", "Generating response...").

        Args:
            text: Status message text (may include newlines)

        Note:
            Empty text should be ignored. Implementations should handle
            this gracefully without raising.
        """
        ...

    async def on_token(self, text: str, signature_field: str | None) -> None:
        """Process a single token from the LLM output stream.

        Tokens are emitted as the LLM generates text. signature_field indicates
        which output field this token belongs to (for multi-field signatures).

        Args:
            text: Token text (typically a single word or word fragment)
            signature_field: Name of the signature field being streamed,
                or None if the token doesn't belong to a specific field

        Note:
            Empty text should be ignored. The field "description" is typically
            skipped as it's the input prompt, not output.
        """
        ...

    async def on_final(self, result: Any, tokens_emitted: int) -> None:
        """Process the final prediction result.

        Called once when streaming completes successfully. Contains the
        complete DSPy Prediction object with all output fields populated.

        Args:
            result: DSPy Prediction object with output fields
            tokens_emitted: Total number of tokens emitted during streaming

        Note:
            Implementations MUST be idempotent - this may be called multiple
            times in edge cases. Use a finalization guard flag if necessary.
        """
        ...

    async def flush(self) -> None:
        """Flush any pending async operations.

        Called after streaming completes to ensure all async tasks
        (e.g., WebSocket broadcasts) complete before returning.

        Implementations should await any background tasks and handle
        errors gracefully (log but don't raise).

        Note:
            For synchronous sinks (e.g., Rich terminal), this is a no-op.
        """
        ...


class RichSink(StreamSink):
    """Rich terminal sink responsible for mutating live display data.

    This sink updates a mutable display_data dictionary that represents
    the artifact being streamed. It accumulates status messages and tokens
    in buffers, then replaces them with final structured data when streaming
    completes.

    The sink integrates with Rich's Live display context, calling a refresh
    callback after each update to trigger terminal re-rendering.

    Display Data Flow
    -----------------
    1. Initialization: display_data contains empty payload fields and "streaming..." timestamp
    2. on_status(): Accumulates status messages in a buffer, updates display_data["status"]
    3. on_token(): Accumulates tokens in field-specific buffers, updates display_data["payload"]["_streaming"]
    4. on_final(): Replaces streaming buffers with final Prediction fields, removes "status", adds real timestamp
    5. flush(): No-op (Rich rendering is synchronous)

    Error Handling
    --------------
    - refresh_panel() errors are caught and logged, never raised
    - Idempotent: on_final() checks _finalized flag to prevent double-finalization
    - Defensive: Uses setdefault() and get() to handle missing dictionary keys

    Thread Safety
    -------------
    NOT thread-safe. Assumes single-threaded async execution within a single
    Rich Live context. Multiple concurrent streams should use separate RichSink instances.

    Example
    -------
        display_data = OrderedDict([("id", "artifact-123"), ("payload", {}), ...])
        stream_buffers = defaultdict(list)

        def refresh():
            live.update(formatter.format_result(display_data, ...))

        sink = RichSink(
            display_data=display_data,
            stream_buffers=stream_buffers,
            status_field="_status",
            signature_order=["output", "summary"],
            formatter=formatter,
            theme_dict=theme,
            styles=styles,
            agent_label="Agent - gpt-4",
            refresh_panel=refresh,
            timestamp_factory=lambda: datetime.now(UTC).isoformat(),
        )

        await sink.on_status("Processing...")
        await sink.on_token("Hello", "output")
        await sink.on_final(prediction, tokens_emitted=5)
        await sink.flush()
    """

    def __init__(
        self,
        *,
        display_data: MutableMapping[str, Any],
        stream_buffers: MutableMapping[str, list[str]],
        status_field: str,
        signature_order: Sequence[str],
        formatter: Any | None,
        theme_dict: dict[str, Any] | None,
        styles: dict[str, Any] | None,
        agent_label: str | None,
        refresh_panel: Callable[[], None],
        timestamp_factory: Callable[[], str],
    ) -> None:
        self._display_data = display_data
        self._stream_buffers = stream_buffers
        self._status_field = status_field
        self._signature_order = list(signature_order)
        self._formatter = formatter
        self._theme_dict = theme_dict
        self._styles = styles
        self._agent_label = agent_label
        self._refresh_panel = refresh_panel
        self._timestamp_factory = timestamp_factory
        self._final_display = (
            formatter,
            display_data,
            theme_dict,
            styles,
            agent_label,
        )
        # Ensure buffers exist for status updates
        self._stream_buffers.setdefault(status_field, [])
        self._finalized = False

    def _refresh(self) -> None:
        try:
            self._refresh_panel()
        except Exception:
            logger.debug("Rich sink refresh panel callable failed", exc_info=True)

    async def on_status(self, text: str) -> None:
        if not text:
            return

        buffer = self._stream_buffers.setdefault(self._status_field, [])
        buffer.append(f"{text}\n")
        self._display_data["status"] = "".join(buffer)
        self._refresh()

    async def on_token(self, text: str, signature_field: str | None) -> None:
        if not text:
            return

        if signature_field and signature_field != "description":
            buffer_key = f"_stream_{signature_field}"
            buffer = self._stream_buffers.setdefault(buffer_key, [])
            buffer.append(str(text))
            payload = self._display_data.setdefault("payload", {})
            payload["_streaming"] = "".join(buffer)
        else:
            buffer = self._stream_buffers.setdefault(self._status_field, [])
            buffer.append(str(text))
            self._display_data["status"] = "".join(buffer)

        self._refresh()

    async def on_final(self, result: Any, tokens_emitted: int) -> None:  # noqa: ARG002
        if self._finalized:
            return

        payload_section: MutableMapping[str, Any] = self._display_data.setdefault(
            "payload", {}
        )
        payload_section.clear()

        for field_name in self._signature_order:
            if field_name == "description":
                continue
            if not hasattr(result, field_name):
                continue

            value = getattr(result, field_name)
            if isinstance(value, list):
                payload_section[field_name] = [
                    item.model_dump() if isinstance(item, BaseModel) else item
                    for item in value
                ]
            elif isinstance(value, BaseModel):
                payload_section[field_name] = value.model_dump()
            else:
                payload_section[field_name] = value

        self._display_data["created_at"] = self._timestamp_factory()
        self._display_data.pop("status", None)
        payload_section.pop("_streaming", None)
        self._refresh()
        self._finalized = True

    async def flush(self) -> None:
        # Rich sink has no async resources to drain.
        return None

    @property
    def final_display_data(
        self,
    ) -> tuple[
        Any,
        MutableMapping[str, Any],
        dict[str, Any] | None,
        dict[str, Any] | None,
        str | None,
    ]:
        return self._final_display


class WebSocketSink(StreamSink):
    """WebSocket-only sink that mirrors dashboard streaming behaviour.

    This sink broadcasts StreamingOutputEvent messages via WebSocket for
    real-time dashboard updates. It uses fire-and-forget task scheduling
    to avoid blocking the streaming loop while ensuring all events are
    delivered via flush().

    Event Sequence
    --------------
    Each event gets a monotonically increasing sequence number for ordering:
    - on_status("Loading"): seq=0, output_type="log", content="Loading\\n"
    - on_token("Hello", field): seq=1, output_type="llm_token", content="Hello"
    - on_token(" world", field): seq=2, output_type="llm_token", content=" world"
    - on_final(pred, 2): seq=3, output_type="log", content="\\nAmount of output tokens: 2", is_final=True
    -                    seq=4, output_type="log", content="--- End of output ---", is_final=True

    The two terminal events are required for dashboard compatibility and must
    appear in this exact order with is_final=True.

    Task Management
    ---------------
    Events are broadcast using asyncio.create_task() to avoid blocking the
    streaming loop. Tasks are tracked in a set and awaited during flush()
    to ensure delivery before the stream completes.

    Task lifecycle:
    1. _schedule() creates task and adds to _tasks set
    2. Task completion callback removes it from _tasks
    3. flush() awaits remaining tasks with error handling

    Error Handling
    --------------
    - Scheduling errors: Logged and ignored (event dropped)
    - Broadcast errors: Caught during flush(), logged but don't raise
    - Idempotent: on_final() checks _finalized flag to prevent duplicate terminal events

    Thread Safety
    -------------
    NOT thread-safe. Assumes single-threaded async execution. Multiple
    concurrent streams should use separate WebSocketSink instances.

    Example
    -------
        async def broadcast(event: StreamingOutputEvent):
            await websocket_manager.send_json(event.model_dump())

        def event_factory(output_type, content, seq, is_final):
            return StreamingOutputEvent(
                correlation_id="corr-123",
                agent_name="analyzer",
                run_id="run-456",
                output_type=output_type,
                content=content,
                sequence=seq,
                is_final=is_final,
                artifact_id="artifact-789",
                artifact_type="Report",
            )

        sink = WebSocketSink(ws_broadcast=broadcast, event_factory=event_factory)

        await sink.on_status("Processing input")
        await sink.on_token("Analysis", "output")
        await sink.on_final(prediction, tokens_emitted=1)
        await sink.flush()  # Ensures all broadcasts complete
    """

    def __init__(
        self,
        *,
        ws_broadcast: Callable[[StreamingOutputEvent], Awaitable[None]] | None,
        event_factory: Callable[[str, str, int, bool], StreamingOutputEvent],
    ) -> None:
        self._ws_broadcast = ws_broadcast
        self._event_factory = event_factory
        self._sequence = 0
        self._tasks: set[asyncio.Task[Any]] = set()
        self._finalized = False

    def _schedule(
        self,
        output_type: str,
        content: str,
        *,
        is_final: bool,
        advance_sequence: bool = True,
    ) -> None:
        if not self._ws_broadcast:
            return

        event = self._event_factory(output_type, content, self._sequence, is_final)
        try:
            task = asyncio.create_task(self._ws_broadcast(event))
        except Exception as exc:  # pragma: no cover - scheduling should rarely fail
            logger.warning(f"Failed to schedule streaming event: {exc}")
            return

        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

        if advance_sequence:
            self._sequence += 1

    async def on_status(self, text: str) -> None:
        if not text:
            return
        self._schedule("log", f"{text}\n", is_final=False)

    async def on_token(self, text: str, signature_field: str | None) -> None:  # noqa: ARG002
        if not text:
            return
        self._schedule("llm_token", text, is_final=False)

    async def on_final(self, result: Any, tokens_emitted: int) -> None:  # noqa: ARG002
        if self._finalized:
            return

        self._schedule(
            "log",
            f"\nAmount of output tokens: {tokens_emitted}",
            is_final=True,
        )
        self._schedule(
            "log",
            "--- End of output ---",
            is_final=True,
        )

        self._finalized = True

    async def flush(self) -> None:
        if not self._tasks:
            return

        pending = list(self._tasks)
        self._tasks.clear()

        results = await asyncio.gather(*pending, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Streaming broadcast task failed: {result}")


__all__ = ["RichSink", "StreamSink", "WebSocketSink"]
