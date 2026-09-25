"""Handler-level tests for signals the HTTP client cannot easily produce."""

from __future__ import annotations

import asyncio

import pytest
from azure.ai.agentserver.responses import CreateResponse, ResponseContext
from azure.ai.agentserver.responses.models.runtime import ResponseModeFlags

from flock.integrations.foundry import TextTurn
from flock.integrations.foundry.turns import (
    UnsupportedRequestError,
    history_messages,
    input_text,
)

from .conftest import Recorder, make_adapter


def context_for(text: str, response_id: str) -> tuple[CreateResponse, ResponseContext]:
    request = CreateResponse({"input": text})
    context = ResponseContext(
        response_id=response_id,
        mode_flags=ResponseModeFlags(stream=True, store=False, background=False),
        request=request,
    )
    return request, context


async def collect(adapter, request, context, signal) -> list[dict]:
    return [event async for event in adapter._handle(request, context, signal)]


def event_types(events) -> list[str]:
    return [event["type"] for event in events]


@pytest.mark.asyncio
async def test_cancellation_signal_cancels_workflow_without_terminal_event(
    recorder: Recorder,
):
    adapter = make_adapter(recorder)
    request, context = context_for("slow task", "resp_cancel_1")
    signal = asyncio.Event()

    task = asyncio.create_task(collect(adapter, request, context, signal))
    await asyncio.wait_for(recorder.started.wait(), 5)
    signal.set()
    events = await asyncio.wait_for(task, 5)

    assert recorder.cancelled == 1
    assert not {"response.completed", "response.failed"} & set(event_types(events))


@pytest.mark.asyncio
async def test_shutdown_drains_briefly_then_never_reports_success(recorder: Recorder):
    adapter = make_adapter(recorder, drain_timeout=0.2)
    request, context = context_for("slow task", "resp_shutdown_1")
    signal = asyncio.Event()

    task = asyncio.create_task(collect(adapter, request, context, signal))
    await asyncio.wait_for(recorder.started.wait(), 5)
    # SDK 2.1.0 sets both signals on foreground shutdown
    context.shutdown.set()
    signal.set()
    events = await asyncio.wait_for(task, 5)

    assert "response.completed" not in event_types(events)
    assert recorder.cancelled == 1
    assert not adapter.application.accepting


@pytest.mark.asyncio
async def test_other_workflow_unaffected_by_cancellation(recorder: Recorder):
    adapter = make_adapter(recorder)
    slow_request, slow_context = context_for("slow task", "resp_slow")
    fast_request, fast_context = context_for("fast", "resp_fast")
    slow_signal = asyncio.Event()

    slow = asyncio.create_task(
        collect(adapter, slow_request, slow_context, slow_signal)
    )
    await asyncio.wait_for(recorder.started.wait(), 5)
    fast_events = await collect(adapter, fast_request, fast_context, asyncio.Event())
    slow_signal.set()
    await asyncio.wait_for(slow, 5)

    assert event_types(fast_events)[-1] == "response.completed"


def test_turn_mapping_rejects_non_text_and_keeps_history_roles():
    with pytest.raises(UnsupportedRequestError):
        input_text([{"type": "function_call_output", "call_id": "c", "output": "x"}])
    with pytest.raises(UnsupportedRequestError):
        input_text([{"type": "message", "role": "assistant", "content": "x"}])

    history = history_messages([
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "a"}],
        },
        {"type": "reasoning", "summary": []},
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "output_text", "text": "b"}],
        },
    ])
    turn = TextTurn(text="c", history=history)
    assert turn.history_dicts() == [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": "b"},
    ]


def test_local_development_identity_is_refused_in_foundry(monkeypatch):
    from flock.integrations.foundry import IdentityPolicy

    monkeypatch.setenv("FOUNDRY_HOSTING_ENVIRONMENT", "production")
    with pytest.raises(ValueError, match="local_development"):
        IdentityPolicy(local_development=True)


def test_identity_can_be_optional_but_never_a_shared_principal(monkeypatch):
    from types import SimpleNamespace

    from flock.integrations.foundry import IdentityPolicy

    monkeypatch.setenv("FOUNDRY_HOSTING_ENVIRONMENT", "production")
    anonymous = SimpleNamespace(platform_context=SimpleNamespace(user_id_key=None))
    known = SimpleNamespace(platform_context=SimpleNamespace(user_id_key="user-1"))

    optional = IdentityPolicy(required=False)
    assert optional.principal_for(anonymous) is None
    assert optional.principal_for(known) == "user-1"
    with pytest.raises(PermissionError):
        IdentityPolicy().principal_for(anonymous)
