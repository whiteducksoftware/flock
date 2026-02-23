"""TDD: OpenClawStreamingExecutor behavior with mocked SSE streams."""

from __future__ import annotations

import pytest

from flock.integrations.openclaw.streaming import (
    OpenClawResponseFailedError,
    OpenClawStreamingExecutor,
    SSEFrame,
)


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
async def test_executor_dispatches_mocked_sse_frames_to_sinks() -> None:
    sink = _CaptureSink()

    async def _mock_stream_events():
        yield SSEFrame(event="response.created", data="{}")
        yield SSEFrame(event="response.in_progress", data="{}")
        yield SSEFrame(event="response.output_text.delta", data='{"delta":"Hel"}')
        yield SSEFrame(event="response.output_text.delta", data='{"delta":"lo"}')
        yield SSEFrame(event="response.completed", data='{"usage":{"output_tokens":2}}')
        yield SSEFrame(event="done", data="[DONE]")

    executor = OpenClawStreamingExecutor(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer token"},
        payload={"model": "openclaw", "input": "ping"},
        sinks=[sink],
        output_field="output",
        timeout=30,
        stream_events_factory=_mock_stream_events,
    )

    result = await executor.execute()

    assert sink.statuses == ["OpenClaw agent started", "Processing..."]
    assert sink.tokens == [("Hel", "output"), ("lo", "output")]
    assert len(sink.finals) == 1
    assert sink.flushed is True

    assert result.full_text == "Hello"
    assert result.tokens_emitted == 2
    assert result.usage == {"output_tokens": 2}


@pytest.mark.asyncio
async def test_executor_accumulates_delta_text_when_completed_has_no_output_text() -> (
    None
):
    sink = _CaptureSink()

    async def _mock_stream_events():
        yield SSEFrame(event="response.output_text.delta", data='{"delta":"alpha"}')
        yield SSEFrame(event="response.output_text.delta", data='{"delta":" beta"}')
        yield SSEFrame(event="response.completed", data='{"usage":{"output_tokens":2}}')
        yield SSEFrame(event="done", data="[DONE]")

    executor = OpenClawStreamingExecutor(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer token"},
        payload={"model": "openclaw", "input": "ping"},
        sinks=[sink],
        output_field="output",
        timeout=30,
        stream_events_factory=_mock_stream_events,
    )

    result = await executor.execute()

    assert result.full_text == "alpha beta"
    assert result.tokens_emitted == 2

    final_result, final_tokens = sink.finals[0]
    assert getattr(final_result, "output") == "alpha beta"
    assert final_tokens == 2


@pytest.mark.asyncio
async def test_executor_prefers_completed_output_text_when_present() -> None:
    sink = _CaptureSink()

    async def _mock_stream_events():
        yield SSEFrame(event="response.output_text.delta", data='{"delta":"partial"}')
        yield SSEFrame(
            event="response.completed",
            data=(
                '{"output":[{"type":"message","role":"assistant","content":'
                '[{"type":"output_text","text":"final json string"}]}]}'
            ),
        )
        yield SSEFrame(event="done", data="[DONE]")

    executor = OpenClawStreamingExecutor(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer token"},
        payload={"model": "openclaw", "input": "ping"},
        sinks=[sink],
        output_field="output",
        timeout=30,
        stream_events_factory=_mock_stream_events,
    )

    result = await executor.execute()

    assert result.full_text == "partial"

    final_result, _final_tokens = sink.finals[0]
    assert getattr(final_result, "output") == "final json string"


@pytest.mark.asyncio
async def test_executor_falls_back_to_non_streaming_when_sse_stream_fails() -> None:
    sink = _CaptureSink()
    fallback_calls = 0

    async def _failing_stream_events():
        raise RuntimeError("sse transport failed")
        yield  # pragma: no cover

    async def _fallback_non_streaming() -> str:
        nonlocal fallback_calls
        fallback_calls += 1
        return '{"result":"fallback"}'

    executor = OpenClawStreamingExecutor(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer token"},
        payload={"model": "openclaw", "input": "ping"},
        sinks=[sink],
        output_field="output",
        timeout=30,
        stream_events_factory=_failing_stream_events,
        fallback_non_streaming_factory=_fallback_non_streaming,
    )

    result = await executor.execute()

    assert fallback_calls == 1
    assert result.full_text == '{"result":"fallback"}'
    assert result.tokens_emitted == 0
    assert len(sink.tokens) == 0

    final_result, final_tokens = sink.finals[0]
    assert getattr(final_result, "output") == '{"result":"fallback"}'
    assert final_tokens == 0


@pytest.mark.asyncio
async def test_executor_propagates_sse_error_when_no_fallback_is_configured() -> None:
    sink = _CaptureSink()

    async def _failing_stream_events():
        raise RuntimeError("sse transport failed")
        yield  # pragma: no cover

    executor = OpenClawStreamingExecutor(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer token"},
        payload={"model": "openclaw", "input": "ping"},
        sinks=[sink],
        output_field="output",
        timeout=30,
        stream_events_factory=_failing_stream_events,
    )

    with pytest.raises(RuntimeError, match="sse transport failed"):
        await executor.execute()

    assert sink.finals == []


@pytest.mark.asyncio
async def test_executor_does_not_fallback_on_response_failed() -> None:
    """response.failed should raise immediately, not trigger streaming fallback."""
    sink = _CaptureSink()
    fallback_calls = 0

    async def _stream_with_response_failed():
        yield SSEFrame(event="response.created", data="{}")
        yield SSEFrame(
            event="response.failed",
            data='{"error":{"message":"model overloaded"}}',
        )

    async def _fallback_non_streaming() -> str:
        nonlocal fallback_calls
        fallback_calls += 1
        return '{"result":"should not reach"}'

    executor = OpenClawStreamingExecutor(
        endpoint="http://localhost:19789/v1/responses",
        headers={"Authorization": "Bearer token"},
        payload={"model": "openclaw", "input": "ping"},
        sinks=[sink],
        output_field="output",
        timeout=30,
        stream_events_factory=_stream_with_response_failed,
        fallback_non_streaming_factory=_fallback_non_streaming,
    )

    with pytest.raises(OpenClawResponseFailedError, match="model overloaded"):
        await executor.execute()

    assert fallback_calls == 0
