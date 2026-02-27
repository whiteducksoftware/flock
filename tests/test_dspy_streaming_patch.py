from __future__ import annotations

from types import SimpleNamespace

import pytest

from flock.patches.dspy_streaming_patch import patched_alitellm_responses_completion


class _FakeAsyncSendStream:
    def __init__(self) -> None:
        self.sent: list[object] = []

    async def send(self, event: object) -> None:
        self.sent.append(event)


class _FakeAsyncResponsesIterator:
    def __init__(self, events: list[object]) -> None:
        self._events = list(events)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._events:
            return self._events.pop(0)
        raise StopAsyncIteration


@pytest.mark.asyncio
async def test_responses_async_bridge_streams_events_and_returns_completed_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dspy.clients.lm as dspy_lm
    import litellm

    stream = _FakeAsyncSendStream()
    completed_response = SimpleNamespace(model="azure/gpt-5", output=[], usage={})

    async def _mock_aresponses(**kwargs):
        assert kwargs["stream"] is True
        return _FakeAsyncResponsesIterator(
            [
                SimpleNamespace(type="response.output_text.delta", delta="hel"),
                SimpleNamespace(type="response.output_text.delta", delta="lo"),
                SimpleNamespace(
                    type="response.completed", response=completed_response
                ),
            ]
        )

    monkeypatch.setattr(
        "flock.patches.dspy_streaming_patch._stream_context", lambda: (stream, 321)
    )
    monkeypatch.setattr(
        dspy_lm,
        "_convert_chat_request_to_responses_request",
        lambda request: dict(request),
    )
    monkeypatch.setattr(
        dspy_lm,
        "_add_dspy_identifier_to_headers",
        lambda headers: headers or {},
    )
    monkeypatch.setattr(litellm, "aresponses", _mock_aresponses)

    result = await patched_alitellm_responses_completion(
        request={"model": "azure/gpt-5", "messages": []},
        num_retries=1,
        cache=None,
    )

    assert result is completed_response
    assert len(stream.sent) == 3
    assert stream.sent[0].predict_id == 321
    assert stream.sent[1].predict_id == 321


@pytest.mark.asyncio
async def test_responses_async_bridge_falls_back_to_original_without_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dspy.clients.lm as dspy_lm

    sentinel = SimpleNamespace(kind="fallback")

    async def _mock_original(**kwargs):
        return sentinel

    monkeypatch.setattr(
        "flock.patches.dspy_streaming_patch._stream_context", lambda: (None, None)
    )
    monkeypatch.setattr(
        dspy_lm,
        "_flock_original_alitellm_responses_completion",
        _mock_original,
        raising=False,
    )

    result = await patched_alitellm_responses_completion(
        request={"model": "azure/gpt-5", "messages": []},
        num_retries=1,
        cache=None,
    )

    assert result is sentinel


@pytest.mark.asyncio
async def test_responses_async_bridge_requires_completed_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dspy.clients.lm as dspy_lm
    import litellm

    stream = _FakeAsyncSendStream()

    async def _mock_aresponses(**kwargs):
        return _FakeAsyncResponsesIterator(
            [SimpleNamespace(type="response.output_text.delta", delta="partial")]
        )

    monkeypatch.setattr(
        "flock.patches.dspy_streaming_patch._stream_context", lambda: (stream, None)
    )
    monkeypatch.setattr(
        dspy_lm,
        "_convert_chat_request_to_responses_request",
        lambda request: dict(request),
    )
    monkeypatch.setattr(
        dspy_lm,
        "_add_dspy_identifier_to_headers",
        lambda headers: headers or {},
    )
    monkeypatch.setattr(litellm, "aresponses", _mock_aresponses)

    with pytest.raises(
        RuntimeError,
        match="did not receive a response.completed event",
    ):
        await patched_alitellm_responses_completion(
            request={"model": "azure/gpt-5", "messages": []},
            num_retries=1,
            cache=None,
        )


@pytest.mark.asyncio
async def test_responses_async_bridge_emits_synthetic_deltas_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import dspy.clients.lm as dspy_lm
    import litellm

    stream = _FakeAsyncSendStream()
    completed_response = {
        "model": "azure/gpt-5",
        "output": [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": "hello synthetic"}],
            }
        ],
        "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
    }

    async def _mock_aresponses(**kwargs):
        return _FakeAsyncResponsesIterator(
            [SimpleNamespace(type="response.completed", response=completed_response)]
        )

    monkeypatch.setattr(
        "flock.patches.dspy_streaming_patch._stream_context", lambda: (stream, 99)
    )
    monkeypatch.setattr(
        dspy_lm,
        "_convert_chat_request_to_responses_request",
        lambda request: dict(request),
    )
    monkeypatch.setattr(
        dspy_lm,
        "_add_dspy_identifier_to_headers",
        lambda headers: headers or {},
    )
    monkeypatch.setattr(litellm, "aresponses", _mock_aresponses)

    result = await patched_alitellm_responses_completion(
        request={"model": "azure/gpt-5", "messages": []},
        num_retries=1,
        cache=None,
    )

    assert result is not None
    delta_events = [
        event
        for event in stream.sent
        if isinstance(event, dict) and event.get("type") == "response.output_text.delta"
    ]
    assert delta_events
