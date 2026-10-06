"""End-to-end tests against the real Responses host (in-process ASGI)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from flock import Flock, FlockApplication
from flock.integrations.foundry import IdentityPolicy

from .conftest import Answer, Question, Recorder, make_adapter


def sse_events(body: str) -> list[dict]:
    return [
        json.loads(line[len("data: ") :])
        for line in body.splitlines()
        if line.startswith("data: ")
    ]


def output_texts(response: dict) -> list[str]:
    return [
        part["text"]
        for item in response.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    ]


def wait_for_status(client: TestClient, response_id: str, statuses: set[str]) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        body = client.get(f"/responses/{response_id}").json()
        if body.get("status") in statuses:
            return body
        time.sleep(0.05)
    raise AssertionError(f"status never reached {statuses}: {body}")


def test_json_and_sse_agree(recorder: Recorder):
    with TestClient(make_adapter(recorder).app) as client:
        plain = client.post("/responses", json={"input": "hello"}).json()
        streamed = client.post(
            "/responses", json={"input": "hello", "stream": True}
        ).text

    events = sse_events(streamed)
    terminal = events[-1]
    assert plain["status"] == "completed"
    assert terminal["type"] == "response.completed"
    assert output_texts(plain) == ["echo:hello"]
    assert output_texts(terminal["response"]) == output_texts(plain)
    deltas = [e["delta"] for e in events if e["type"] == "response.output_text.delta"]
    assert deltas == ["echo:hello"]
    # every response is its own workflow
    assert [c.workflow_id for c in recorder.contexts[1:]] == [
        plain["id"],
        terminal["response"]["id"],
    ]


def test_background_poll_and_stored_result(recorder: Recorder):
    with TestClient(make_adapter(recorder).app) as client:
        created = client.post(
            "/responses", json={"input": "hello", "background": True, "store": True}
        ).json()
        assert created["status"] in {"queued", "in_progress", "completed"}
        done = wait_for_status(client, created["id"], {"completed"})

    assert output_texts(done) == ["echo:hello"]


def test_background_cancel_stops_only_that_workflow(recorder: Recorder):
    with TestClient(make_adapter(recorder).app) as client:
        slow = client.post(
            "/responses", json={"input": "slow one", "background": True, "store": True}
        ).json()
        wait = time.monotonic() + 5
        while not recorder.started.is_set() and time.monotonic() < wait:
            time.sleep(0.02)
        other = client.post("/responses", json={"input": "fast"}).json()
        cancel = client.post(f"/responses/{slow['id']}/cancel")
        final = wait_for_status(
            client, slow["id"], {"cancelled", "failed", "completed"}
        )

    assert other["status"] == "completed"
    assert cancel.status_code == 200
    assert final["status"] == "cancelled"
    assert recorder.cancelled == 1


def test_agent_failure_is_failed_without_leaking_details(recorder: Recorder):
    with TestClient(make_adapter(recorder).app) as client:
        body = client.post("/responses", json={"input": "fail please"}).json()

    assert body["status"] == "failed"
    assert body["error"]["code"] == "server_error"
    assert "agent_failed" in body["error"]["message"]
    assert "private detail" not in json.dumps(body)


@pytest.mark.parametrize(
    "payload",
    [
        {"input": "x", "tools": [{"type": "function", "name": "f", "parameters": {}}]},
        {"input": "x", "max_output_tokens": 50},
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_image",
                            "image_url": "https://example.com/a.png",
                        }
                    ],
                }
            ]
        },
    ],
)
def test_unsupported_features_are_rejected_before_execution(
    recorder: Recorder, payload
):
    with TestClient(make_adapter(recorder).app) as client:
        body = client.post("/responses", json=payload).json()

    assert body["status"] == "failed"
    assert body["error"]["code"] == "invalid_prompt"
    assert recorder.inputs == []


def test_hosted_identity_is_required(recorder: Recorder, monkeypatch):
    monkeypatch.setenv("FOUNDRY_HOSTING_ENVIRONMENT", "production")
    adapter = make_adapter(recorder, identity=IdentityPolicy())
    with TestClient(adapter.app) as client:
        anonymous = client.post("/responses", json={"input": "hi"}).json()
        known = client.post(
            "/responses",
            json={"input": "hi"},
            headers={"x-agent-user-id": "user-key-1"},
        ).json()

    assert anonymous["status"] == "failed"
    assert known["status"] == "completed"
    assert recorder.contexts[-1].principal_id == "user-key-1"


def test_identity_header_is_not_trusted_outside_foundry(
    recorder: Recorder, monkeypatch
):
    monkeypatch.delenv("FOUNDRY_HOSTING_ENVIRONMENT", raising=False)
    adapter = make_adapter(recorder, identity=IdentityPolicy())
    with TestClient(adapter.app) as client:
        spoofed = client.post(
            "/responses", json={"input": "hi"}, headers={"x-agent-user-id": "victim"}
        ).json()

    assert spoofed["status"] == "failed"
    assert recorder.inputs == []


def test_readiness_recovers_after_a_transient_start_failure(recorder: Recorder):
    attempts = {"n": 0}

    def flaky_factory() -> Flock:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("credential not reachable yet")
        flock = Flock(no_output=True)
        flock.agent("a").consumes(Question).publishes(Answer)
        return flock

    flaky = FlockApplication(flaky_factory, input_type=Question, output_types=(Answer,))
    with TestClient(make_adapter(recorder, application=flaky).app) as client:
        assert client.get("/readiness").status_code == 503
        assert client.get("/readiness").status_code == 200


def test_two_turn_conversation_keeps_roles_without_rerunning_inputs(recorder: Recorder):
    with TestClient(make_adapter(recorder, history_mode="conversation").app) as client:
        first = client.post("/responses", json={"input": "my name is Ada"}).json()
        second = client.post(
            "/responses",
            json={"input": "what is my name?", "previous_response_id": first["id"]},
        ).json()

    assert second["status"] == "completed"
    assert [q.text for q in recorder.inputs] == ["my name is Ada", "what is my name?"]
    assert recorder.inputs[1].history == [
        {"role": "user", "content": "my name is Ada"},
        {"role": "assistant", "content": "echo:my name is Ada"},
    ]


def test_readiness_reflects_application_contract(recorder: Recorder):
    def broken_factory() -> Flock:
        return Flock(no_output=True)  # consumes nothing

    broken = FlockApplication(
        broken_factory, input_type=Question, output_types=(Answer,)
    )
    with TestClient(make_adapter(recorder, application=broken).app) as client:
        assert client.get("/readiness").status_code == 503

    adapter = make_adapter(recorder)
    with TestClient(adapter.app) as client:
        assert client.get("/readiness").status_code == 200
        adapter.application.begin_drain()
        assert client.get("/readiness").status_code == 503


def test_capacity_limit_answers_rate_limit_exceeded(recorder: Recorder):
    adapter = make_adapter(recorder, app_options={"max_active_workflows": 1})
    with TestClient(adapter.app) as client:
        slow = client.post(
            "/responses", json={"input": "slow one", "background": True, "store": True}
        ).json()
        wait = time.monotonic() + 5
        while not recorder.started.is_set() and time.monotonic() < wait:
            time.sleep(0.02)
        busy = client.post("/responses", json={"input": "fast"}).json()
        client.post(f"/responses/{slow['id']}/cancel")
        wait_for_status(client, slow["id"], {"cancelled", "failed", "completed"})

    assert busy["status"] == "failed"
    assert busy["error"]["code"] == "rate_limit_exceeded"
    assert [q.text for q in recorder.inputs] == ["slow one"]


def test_unbounded_application_is_flagged_at_construction(
    recorder: Recorder, monkeypatch
):
    log = MagicMock()
    monkeypatch.setattr("flock.integrations.foundry.adapter.logger", log)

    make_adapter(recorder)
    make_adapter(recorder, app_options={"max_active_workflows": 4})

    unbounded = [
        call
        for call in log.warning.call_args_list
        if "max_active_workflows" in call.args[0]
    ]
    assert len(unbounded) == 1


def test_readiness_logs_a_repeated_start_failure_once(recorder: Recorder, monkeypatch):
    log = MagicMock()
    monkeypatch.setattr("flock.integrations.foundry.adapter.logger", log)
    broken = FlockApplication(
        lambda: Flock(no_output=True), input_type=Question, output_types=(Answer,)
    )

    with TestClient(make_adapter(recorder, application=broken).app) as client:
        statuses = [client.get("/readiness").status_code for _ in range(3)]

    assert statuses == [503, 503, 503]
    not_ready = [
        call for call in log.warning.call_args_list if "not ready" in call.args[0]
    ]
    assert len(not_ready) == 1


def test_foundry_exports_resolve_lazily():
    code = (
        "import sys, flock.integrations.foundry as foundry; "
        "before = 'azure.ai.agentserver.responses' in sys.modules; "
        "foundry.FoundryResponsesAdapter; "
        "after = 'azure.ai.agentserver.responses' in sys.modules; "
        "print(f'LAZY={before},{after}')"
    )
    lines = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.splitlines()

    assert [line for line in lines if line.startswith("LAZY=")] == ["LAZY=False,True"]
