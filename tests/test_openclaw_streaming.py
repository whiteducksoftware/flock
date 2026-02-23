"""TDD for OpenClaw SSE streaming parser and dispatch behavior."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from flock.integrations.openclaw.streaming import (
    OpenClawSSEConsumer,
    OpenClawSSEDispatcher,
    SSEFrame,
    map_sse_event_type,
    parse_sse_lines,
)


def test_parse_sse_lines_extracts_event_and_data_payload() -> None:
    lines = [
        "event: response.output_text.delta",
        'data: {"delta":"Hel"}',
        "",
    ]

    frames = list(parse_sse_lines(lines))

    assert len(frames) == 1
    assert frames[0].event == "response.output_text.delta"
    assert frames[0].data == '{"delta":"Hel"}'


def test_parse_sse_lines_joins_multiline_data_fields() -> None:
    lines = [
        "event: response.output_text.delta",
        'data: {"delta":"Line 1"}',
        'data: {"delta":"Line 2"}',
        "",
    ]

    frames = list(parse_sse_lines(lines))

    assert len(frames) == 1
    assert frames[0].event == "response.output_text.delta"
    assert frames[0].data == '{"delta":"Line 1"}\n{"delta":"Line 2"}'


def test_parse_sse_lines_preserves_done_sentinel() -> None:
    lines = [
        "event: done",
        "data: [DONE]",
        "",
    ]

    frames = list(parse_sse_lines(lines))

    assert len(frames) == 1
    assert frames[0].event == "done"
    assert frames[0].data == "[DONE]"


def test_map_sse_event_type_delta_to_on_token() -> None:
    assert map_sse_event_type("response.output_text.delta") == "on_token"


def test_map_sse_event_type_completed_to_on_final() -> None:
    assert map_sse_event_type("response.completed") == "on_final"


def test_map_sse_event_type_failed_to_error() -> None:
    assert map_sse_event_type("response.failed") == "error"


@pytest.mark.asyncio
@respx.mock
async def test_sse_consumer_posts_stream_true_and_yields_frames() -> None:
    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            text="event: response.output_text.delta\n"
            'data: {"delta":"hi"}\n\n'
            "event: done\n"
            "data: [DONE]\n\n",
            headers={"Content-Type": "text/event-stream"},
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    consumer = OpenClawSSEConsumer(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer test"},
        payload={"model": "openclaw", "input": "ping"},
        timeout=30,
    )

    frames = [frame async for frame in consumer.stream_events()]

    assert len(frames) == 2
    assert frames[0].event == "response.output_text.delta"
    assert frames[0].data == '{"delta":"hi"}'
    assert frames[1].event == "done"
    assert frames[1].data == "[DONE]"

    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["stream"] is True


class _CaptureSink:
    def __init__(self) -> None:
        self.statuses: list[str] = []
        self.tokens: list[tuple[str, str | None]] = []
        self.finals: list[tuple[object, int]] = []
        self.flushed = False

    async def on_status(self, text: str) -> None:
        self.statuses.append(text)

    async def on_token(self, text: str, signature_field: str | None) -> None:
        self.tokens.append((text, signature_field))

    async def on_final(self, result: object, tokens_emitted: int) -> None:
        self.finals.append((result, tokens_emitted))

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_sse_dispatcher_maps_frames_to_sink_callbacks() -> None:
    sink = _CaptureSink()
    dispatcher = OpenClawSSEDispatcher(sinks=[sink], output_field="output")

    frames = [
        SSEFrame(event="response.created", data="{}"),
        SSEFrame(event="response.in_progress", data="{}"),
        SSEFrame(event="response.output_text.delta", data='{"delta":"Hel"}'),
        SSEFrame(event="response.output_text.delta", data='{"delta":{"text":"lo"}}'),
        SSEFrame(event="response.completed", data='{"usage":{"output_tokens":7}}'),
        SSEFrame(event="done", data="[DONE]"),
    ]

    for frame in frames:
        await dispatcher.dispatch(frame)
    await dispatcher.flush()

    assert sink.statuses == ["OpenClaw agent started", "Processing..."]
    assert sink.tokens == [("Hel", "output"), ("lo", "output")]
    assert len(sink.finals) == 1
    final_result, final_tokens = sink.finals[0]
    assert getattr(final_result, "output") == "Hello"
    assert final_tokens == 2
    assert dispatcher.full_text == "Hello"
    assert dispatcher.tokens_emitted == 2
    assert dispatcher.usage == {"output_tokens": 7}
    assert sink.flushed is True


@pytest.mark.asyncio
async def test_sse_dispatcher_raises_runtime_error_on_failed_event() -> None:
    sink = _CaptureSink()
    dispatcher = OpenClawSSEDispatcher(sinks=[sink])

    failed = SSEFrame(
        event="response.failed",
        data='{"error":{"message":"boom"}}',
    )

    with pytest.raises(RuntimeError, match="boom"):
        await dispatcher.dispatch(failed)
