"""Shared streaming sink implementations."""

from __future__ import annotations

import asyncio
from typing import (
    Any,
    Awaitable,
    Callable,
    MutableMapping,
    Protocol,
    Sequence,
    runtime_checkable,
)

from pydantic import BaseModel

from flock.dashboard.events import StreamingOutputEvent
from flock.logging.logging import get_logger


logger = get_logger(__name__)


@runtime_checkable
class StreamSink(Protocol):
    """Minimal sink protocol for consuming normalized stream events."""

    async def on_status(self, text: str) -> None: ...

    async def on_token(self, text: str, signature_field: str | None) -> None: ...

    async def on_final(self, result: Any, tokens_emitted: int) -> None: ...

    async def flush(self) -> None: ...


class RichSink(StreamSink):
    """Rich terminal sink responsible for mutating live display data."""

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
    """WebSocket-only sink that mirrors dashboard streaming behaviour."""

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


__all__ = ["StreamSink", "RichSink", "WebSocketSink"]
