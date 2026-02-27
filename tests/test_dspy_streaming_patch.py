from __future__ import annotations

import warnings
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from flock.patches.dspy_streaming_patch import (
    _ORIGINAL_LITELLM_LOGGING_EXTRACTOR_ATTR,
    patched_alitellm_responses_completion,
    patched_extract_response_obj_and_hidden_params,
)


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


def test_normalize_completed_response_coerces_chat_usage_shape() -> None:
    from flock.patches.dspy_streaming_patch import _normalize_completed_response

    raw = {
        "id": "resp_123",
        "created_at": 0,
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "metadata": {},
        "model": "azure/gpt-5",
        "object": "response",
        "output": [],
        "parallel_tool_calls": True,
        "temperature": 1.0,
        "tool_choice": "auto",
        "tools": [],
        "top_p": 1.0,
        "max_output_tokens": None,
        "previous_response_id": None,
        "reasoning": None,
        "status": "completed",
        "text": None,
        "truncation": "disabled",
        "usage": {
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
        },
        "user": None,
        "store": True,
    }

    normalized = _normalize_completed_response(raw)
    usage = getattr(normalized, "usage", None)
    assert usage is not None
    assert getattr(usage, "input_tokens", None) == 11
    assert getattr(usage, "output_tokens", None) == 7
    assert getattr(usage, "total_tokens", None) == 18


def test_logging_extractor_patch_suppresses_serializer_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from litellm.litellm_core_utils import litellm_logging

    class WarningModel(BaseModel):
        value: int = 1

        def model_dump(self, *args, **kwargs):
            warnings.warn(
                "Pydantic serializer warnings:\n  mocked warning",
                UserWarning,
                stacklevel=1,
            )
            return {"value": self.value}

    monkeypatch.setattr(
        litellm_logging,
        _ORIGINAL_LITELLM_LOGGING_EXTRACTOR_ATTR,
        lambda init_response_obj, original_exception: ({}, None),
        raising=False,
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        response_obj, hidden_params = patched_extract_response_obj_and_hidden_params(
            WarningModel(),
            None,
        )

    assert response_obj == {"value": 1}
    assert hidden_params is None
    assert all(
        "Pydantic serializer warnings" not in str(warning.message)
        for warning in caught
    )
