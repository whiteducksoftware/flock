"""OpenClaw SSE streaming primitives (Phase 2).

This module contains low-level SSE parsing + transport helpers used by
OpenClaw streaming execution.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Iterable, Iterator, Sequence
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Literal, Protocol

import httpx


class OpenClawResponseFailedError(RuntimeError):
    """Raised when the OpenClaw API reports response.failed during streaming."""


class SinkProtocol(Protocol):
    async def on_status(self, text: str) -> None: ...

    async def on_token(self, text: str, signature_field: str | None) -> None: ...

    async def on_final(self, result: Any, tokens_emitted: int) -> None: ...

    async def flush(self) -> None: ...


@dataclass(frozen=True)
class SSEFrame:
    """Single parsed SSE frame."""

    event: str
    data: str
    event_id: str | None = None
    retry_ms: int | None = None


def parse_sse_lines(lines: Iterable[str]) -> Iterator[SSEFrame]:
    """Parse SSE protocol lines into frames.

    Multiple ``data:`` lines in one frame are joined with newlines as required
    by the SSE spec.
    """
    event: str | None = None
    data_lines: list[str] = []
    event_id: str | None = None
    retry_ms: int | None = None

    def flush() -> SSEFrame | None:
        nonlocal event, data_lines, event_id, retry_ms
        if not data_lines:
            event = None
            event_id = None
            retry_ms = None
            return None

        frame = SSEFrame(
            event=event or "message",
            data="\n".join(data_lines),
            event_id=event_id,
            retry_ms=retry_ms,
        )
        event = None
        data_lines = []
        event_id = None
        retry_ms = None
        return frame

    for raw_line in lines:
        line = raw_line.rstrip("\r")

        # Frame separator
        if line == "":
            frame = flush()
            if frame is not None:
                yield frame
            continue

        # Comment
        if line.startswith(":"):
            continue

        field, sep, raw_value = line.partition(":")
        if not sep:
            continue

        value = raw_value[1:] if raw_value.startswith(" ") else raw_value

        if field == "event":
            event = value
        elif field == "data":
            data_lines.append(value)
        elif field == "id":
            event_id = value
        elif field == "retry":
            try:
                retry_ms = int(value)
            except Exception:
                # Ignore malformed retry hints.
                pass

    # Flush trailing frame if stream ended without final blank line.
    trailing = flush()
    if trailing is not None:
        yield trailing


def map_sse_event_type(event: str) -> Literal["on_token", "on_final", "error", "noop"]:
    """Map OpenClaw SSE event name to sink action type."""
    if event == "response.output_text.delta":
        return "on_token"
    if event == "response.completed":
        return "on_final"
    if event == "response.failed":
        return "error"
    return "noop"


class OpenClawSSEDispatcher:
    """Dispatch OpenClaw SSE frames to StreamSink callbacks."""

    def __init__(
        self,
        *,
        sinks: Sequence[SinkProtocol],
        output_field: str = "output",
    ) -> None:
        self._sinks = list(sinks)
        self._output_field = output_field
        self._chunks: list[str] = []
        self._tokens_emitted = 0
        self._usage: dict[str, Any] | None = None
        self._final_text: str = ""

    @property
    def full_text(self) -> str:
        return "".join(self._chunks)

    @property
    def tokens_emitted(self) -> int:
        return self._tokens_emitted

    @property
    def usage(self) -> dict[str, Any] | None:
        return self._usage

    @property
    def final_text(self) -> str:
        return self._final_text or self.full_text

    async def dispatch(self, frame: SSEFrame) -> None:
        """Dispatch a parsed frame to sinks according to event mapping."""
        # SSE stream terminator: not a dispatchable event.
        if frame.data == "[DONE]":
            return

        event = frame.event

        if event == "response.created":
            await self._dispatch("on_status", "OpenClaw agent started")
            return

        if event == "response.in_progress":
            await self._dispatch("on_status", "Processing...")
            return

        if event == "response.output_text.delta":
            text = self._extract_delta_text(frame.data)
            if not text:
                return
            self._chunks.append(text)
            self._tokens_emitted += 1
            await self._dispatch("on_token", text, self._output_field)
            return

        if event == "response.completed":
            payload = self._parse_json(frame.data)
            self._usage = self._extract_usage(payload)

            completed_text = self._extract_completed_text(payload)
            if completed_text:
                final_text = completed_text
            else:
                final_text = self.full_text

            self._final_text = final_text
            final_payload = SimpleNamespace(output=final_text)
            await self._dispatch("on_final", final_payload, self._tokens_emitted)
            return

        if event == "response.failed":
            payload = self._parse_json(frame.data)
            message = self._extract_error_message(payload)
            raise OpenClawResponseFailedError(f"OpenClaw response failed: {message}")

        # Other OpenResponses events are currently informational/no-op for sinks.

    async def flush(self) -> None:
        for sink in self._sinks:
            await sink.flush()

    async def _dispatch(self, method: str, *args: Any) -> None:
        for sink in self._sinks:
            await getattr(sink, method)(*args)

    @staticmethod
    def _parse_json(data: str) -> dict[str, Any]:
        try:
            parsed = json.loads(data)
        except Exception:
            return {}
        if isinstance(parsed, dict):
            return parsed
        return {}

    @staticmethod
    def _extract_delta_text(data: str) -> str:
        payload = OpenClawSSEDispatcher._parse_json(data)

        delta = payload.get("delta")
        if isinstance(delta, str):
            return delta
        if isinstance(delta, dict):
            text = delta.get("text")
            if isinstance(text, str):
                return text

        text = payload.get("text")
        if isinstance(text, str):
            return text

        return ""

    @staticmethod
    def _extract_completed_text(payload: dict[str, Any]) -> str:
        output = payload.get("output")
        if not isinstance(output, list):
            return ""

        chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "output_text":
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)

        return "".join(chunks)

    @staticmethod
    def _extract_usage(payload: dict[str, Any]) -> dict[str, Any] | None:
        usage = payload.get("usage")
        if isinstance(usage, dict):
            return usage

        response = payload.get("response")
        if isinstance(response, dict):
            response_usage = response.get("usage")
            if isinstance(response_usage, dict):
                return response_usage

        return None

    @staticmethod
    def _extract_error_message(payload: dict[str, Any]) -> str:
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message.strip():
                return message

        message = payload.get("message")
        if isinstance(message, str) and message.strip():
            return message

        return "OpenClaw streaming failed"


@dataclass(frozen=True)
class OpenClawStreamingResult:
    """Aggregated streaming execution result for downstream parsing."""

    full_text: str
    tokens_emitted: int
    usage: dict[str, Any] | None = None
    final_text: str | None = None


class OpenClawStreamingExecutor:
    """Run OpenClaw SSE stream end-to-end and dispatch to sinks."""

    def __init__(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        sinks: Sequence[SinkProtocol],
        output_field: str = "output",
        timeout: int = 120,
        stream_events_factory: Callable[[], Any] | None = None,
        fallback_non_streaming_factory: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers)
        self.payload = dict(payload)
        self.sinks = list(sinks)
        self.output_field = output_field
        self.timeout = timeout
        self.stream_events_factory = stream_events_factory
        self.fallback_non_streaming_factory = fallback_non_streaming_factory

    async def execute(self) -> OpenClawStreamingResult:
        dispatcher = OpenClawSSEDispatcher(
            sinks=self.sinks,
            output_field=self.output_field,
        )

        try:
            event_iter = await self._build_stream_iterator()
            async for frame in event_iter:
                await dispatcher.dispatch(frame)

            return OpenClawStreamingResult(
                full_text=dispatcher.full_text,
                tokens_emitted=dispatcher.tokens_emitted,
                usage=dispatcher.usage,
                final_text=dispatcher.final_text,
            )
        except OpenClawResponseFailedError:
            # API-level failures (response.failed) should not be
            # swallowed by the streaming fallback — re-raise immediately.
            raise
        except Exception:
            if self.fallback_non_streaming_factory is None:
                raise

            fallback_text = await self.fallback_non_streaming_factory()
            fallback_text = str(fallback_text)

            await self._dispatch_fallback_final(fallback_text)
            return OpenClawStreamingResult(
                full_text=fallback_text,
                tokens_emitted=0,
                usage=None,
                final_text=fallback_text,
            )
        finally:
            await dispatcher.flush()

    async def _build_stream_iterator(self) -> Any:
        if self.stream_events_factory is not None:
            maybe_iter = self.stream_events_factory()
            if hasattr(maybe_iter, "__aiter__"):
                return maybe_iter
            if hasattr(maybe_iter, "__await__"):
                resolved = await maybe_iter
                if hasattr(resolved, "__aiter__"):
                    return resolved
            raise TypeError("stream_events_factory must return an async iterator")

        consumer = OpenClawSSEConsumer(
            endpoint=self.endpoint,
            headers=self.headers,
            payload=self.payload,
            timeout=self.timeout,
        )
        return consumer.stream_events()

    async def _dispatch_fallback_final(self, fallback_text: str) -> None:
        fallback_result = SimpleNamespace(output=fallback_text)
        for sink in self.sinks:
            await sink.on_final(fallback_result, 0)


class OpenClawSSEConsumer:
    """Low-level SSE consumer for OpenClaw `/v1/responses` streaming."""

    def __init__(
        self,
        *,
        endpoint: str,
        headers: dict[str, str],
        payload: dict,
        timeout: int = 120,
    ) -> None:
        self.endpoint = endpoint
        self.headers = dict(headers)
        self.payload = dict(payload)
        self.timeout = timeout

    async def stream_events(self) -> AsyncIterator[SSEFrame]:
        """Open SSE stream and yield parsed frames.

        Always enforces ``stream=True`` in request payload.
        """
        request_payload = dict(self.payload)
        request_payload["stream"] = True

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                self.endpoint,
                headers=self.headers,
                json=request_payload,
            ) as response:
                response.raise_for_status()

                async for frame in self._iter_frames(response):
                    yield frame

    async def _iter_frames(self, response: httpx.Response) -> AsyncIterator[SSEFrame]:
        event: str | None = None
        data_lines: list[str] = []
        event_id: str | None = None
        retry_ms: int | None = None

        def flush() -> SSEFrame | None:
            nonlocal event, data_lines, event_id, retry_ms
            if not data_lines:
                event = None
                event_id = None
                retry_ms = None
                return None

            frame = SSEFrame(
                event=event or "message",
                data="\n".join(data_lines),
                event_id=event_id,
                retry_ms=retry_ms,
            )
            event = None
            data_lines = []
            event_id = None
            retry_ms = None
            return frame

        async for raw_line in response.aiter_lines():
            line = raw_line.rstrip("\r")

            if line == "":
                frame = flush()
                if frame is not None:
                    yield frame
                continue

            if line.startswith(":"):
                continue

            field, sep, raw_value = line.partition(":")
            if not sep:
                continue

            value = raw_value[1:] if raw_value.startswith(" ") else raw_value

            if field == "event":
                event = value
            elif field == "data":
                data_lines.append(value)
            elif field == "id":
                event_id = value
            elif field == "retry":
                try:
                    retry_ms = int(value)
                except Exception:
                    pass

        trailing = flush()
        if trailing is not None:
            yield trailing


__all__ = [
    "OpenClawResponseFailedError",
    "OpenClawSSEConsumer",
    "OpenClawSSEDispatcher",
    "OpenClawStreamingExecutor",
    "OpenClawStreamingResult",
    "SSEFrame",
    "map_sse_event_type",
    "parse_sse_lines",
]
