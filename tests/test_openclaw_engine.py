"""TDD tests for OpenClawEngine responses transport + parsing + error mapping."""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
import respx
from pydantic import BaseModel, Field

from flock import Flock
from flock.integrations.openclaw import GatewayConfig, OpenClawConfig
from flock.integrations.openclaw.engine import OpenClawEngine
from flock.integrations.openclaw.streaming import (
    OpenClawSSEConsumer,
    OpenClawStreamingExecutor,
    OpenClawStreamingResult,
)
from flock.registry import flock_type


@flock_type(name="OpenClawEngineInput")
class OpenClawEngineInput(BaseModel):
    prompt: str = Field(description="Prompt payload")


@flock_type(name="OpenClawEngineOutput")
class OpenClawEngineOutput(BaseModel):
    result: str = Field(description="Engine result payload")


def _config(
    *, token: str | None = "token-codie", agent_id: str = "main"
) -> OpenClawConfig:
    return OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token=token,
                token_env="OPENCLAW_CODIE_TOKEN",
                agent_id=agent_id,
            )
        }
    )


async def _invoke_once(
    *,
    timeout_seconds: int = 120,
    retries: int = 1,
    mode: str = "spawn",
    config: OpenClawConfig | None = None,
):
    flock = Flock(openclaw=config or _config(), no_output=True)
    builder = (
        flock.openclaw_agent(
            "codie", timeout=timeout_seconds, retries=retries, mode=mode
        )
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )
    return await flock.invoke(
        builder.agent,
        OpenClawEngineInput(prompt="make pizza"),
        publish_outputs=False,
    )


def _responses_completed(text: str) -> dict[str, object]:
    return {
        "id": "resp_123",
        "object": "response",
        "status": "completed",
        "model": "openclaw",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


@pytest.mark.asyncio
@respx.mock
async def test_responses_request_contains_expected_contract_fields_and_headers() -> None:
    """Engine should call /v1/responses with OpenResponses contract."""
    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        seen["authorization"] = request.headers.get("authorization")
        seen["agent_id"] = request.headers.get("x-openclaw-agent-id")
        return httpx.Response(200, json=_responses_completed('{"result":"margherita"}'))

    route = respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(timeout_seconds=120, retries=1)

    assert route.called
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "openclaw"
    assert payload["stream"] is False
    assert isinstance(payload["input"], str)
    # Schema is now enforced via text.format.json_schema, not inlined in prompt
    assert "text" in payload
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert isinstance(payload["text"]["format"]["schema"], dict)
    assert seen["authorization"] == "Bearer token-codie"
    assert seen["agent_id"] == "main"
    assert outputs[0].payload["result"] == "margherita"


@pytest.mark.asyncio
@respx.mock
async def test_custom_agent_id_header_is_sent() -> None:
    """GatewayConfig.agent_id should control x-openclaw-agent-id header."""
    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["agent_id"] = request.headers.get("x-openclaw-agent-id")
        return httpx.Response(200, json=_responses_completed('{"result":"ok"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(config=_config(agent_id="beta"))

    assert outputs[0].payload["result"] == "ok"
    assert seen["agent_id"] == "beta"


@pytest.mark.asyncio
@respx.mock
async def test_responses_without_token_does_not_send_authorization_header() -> None:
    """Tokenless gateway config should omit Authorization header."""
    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json=_responses_completed('{"result":"ok"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(config=_config(token=None))

    assert outputs[0].payload["result"] == "ok"
    assert seen["authorization"] is None


@pytest.mark.asyncio
@respx.mock
async def test_valid_json_output_text_is_parsed_into_typed_output() -> None:
    """Engine should parse JSON from OpenResponses output text."""
    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json=_responses_completed('{"result":"pepperoni"}'),
        )
    )

    outputs = await _invoke_once()

    assert len(outputs) == 1
    assert outputs[0].type == "OpenClawEngineOutput"
    assert outputs[0].payload == {"result": "pepperoni"}


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_output_text_triggers_single_repair_attempt() -> None:
    """Malformed output_text should trigger exactly one repair retry."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(200, json=_responses_completed("not-json-response"))
        return httpx.Response(200, json=_responses_completed('{"result":"fixed"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)

    assert calls == 2
    assert outputs[0].payload["result"] == "fixed"


@pytest.mark.asyncio
@respx.mock
async def test_timeout_failure_maps_to_runtime_error() -> None:
    """Timeout should map to RuntimeError."""
    respx.post("http://localhost:19789/v1/responses").mock(
        side_effect=httpx.TimeoutException("gateway timeout")
    )

    with pytest.raises(RuntimeError, match="timeout|timed out|Timeout"):
        await _invoke_once()


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_maps_to_value_error() -> None:
    """401/403 failures should map to ValueError and fail fast."""
    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            401,
            json={"error": {"type": "auth_error", "message": "Invalid token"}},
        )
    )

    with pytest.raises(ValueError, match="auth|token|401|Invalid"):
        await _invoke_once()


@pytest.mark.asyncio
@respx.mock
async def test_bad_request_400_is_not_retried() -> None:
    """HTTP 400 should raise RuntimeError and not consume retry budget."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            400,
            json={"error": {"type": "invalid_request_error", "message": "bad body"}},
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    with pytest.raises(RuntimeError, match="400|bad body|request failed"):
        await _invoke_once(retries=3)

    assert calls == 1


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_429_is_retriable_and_can_recover() -> None:
    """HTTP 429 should be retried as a transient runtime error."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                429,
                json={"error": {"type": "rate_limit", "message": "slow down"}},
            )
        return httpx.Response(200, json=_responses_completed('{"result":"recovered"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)

    assert calls == 2
    assert outputs[0].payload["result"] == "recovered"


@pytest.mark.asyncio
@respx.mock
async def test_http_500_is_retriable_and_can_recover() -> None:
    """HTTP 5xx should be retried as transient runtime errors."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, json={"message": "Gateway unavailable"})
        return httpx.Response(200, json=_responses_completed('{"result":"recovered"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)

    assert calls == 2
    assert outputs[0].payload["result"] == "recovered"


@pytest.mark.asyncio
@respx.mock
async def test_status_failed_response_is_retriable() -> None:
    """OpenResponses status=failed should map to RuntimeError and retry."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "id": "resp_failed",
                    "object": "response",
                    "status": "failed",
                    "error": {"code": "api_error", "message": "internal error"},
                    "output": [],
                },
            )
        return httpx.Response(200, json=_responses_completed('{"result":"ok"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)

    assert calls == 2
    assert outputs[0].payload["result"] == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_mode_other_than_spawn_fails_fast() -> None:
    """Unsupported modes should fail before transport."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )
    builder.agent.engines[0].mode = "session"  # Bypass model literal validation to test runtime guard.

    with pytest.raises(ValueError, match="Unsupported OpenClaw mode"):
        await flock.invoke(
            builder.agent,
            OpenClawEngineInput(prompt="make pizza"),
            publish_outputs=False,
        )


def test_parse_responses_output_validates_shapes() -> None:
    """Parser should validate output text presence and JSON object shape."""
    engine = OpenClawEngine(alias="codie", gateway=_config().get_gateway("codie"))

    assert engine._parse_responses_output(_responses_completed('{"result":"ok"}')) == {
        "result": "ok"
    }

    with pytest.raises(ValueError, match="result JSON must be an object"):
        engine._parse_responses_output(_responses_completed('["x"]'))

    with pytest.raises(ValueError, match="missing output text|output"):
        engine._parse_responses_output({"id": "resp_x", "status": "completed", "output": []})


def test_strict_schema_transform_adds_required_and_additional_properties() -> None:
    """Strict schema transform should add required + additionalProperties: false."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )

    engine = builder.agent.engines[0]
    raw_schema = OpenClawEngineOutput.model_json_schema()
    strict = engine._make_strict_schema(raw_schema)

    assert strict["additionalProperties"] is False
    assert strict["required"] == list(raw_schema.get("properties", {}).keys())
    assert strict["type"] == "object"


def test_build_responses_payload_includes_description_as_instructions() -> None:
    """Responses payload should place agent description in instructions."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )

    engine = builder.agent.engines[0]
    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-test"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert payload["instructions"] == "Plans meals"
    assert payload["model"] == "openclaw"
    assert payload["stream"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True


@pytest.mark.asyncio
async def test_streaming_executor_is_used_when_dashboard_websocket_is_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global

    async def _broadcast(_event) -> None:
        return None

    Agent._websocket_broadcast_global = _broadcast
    captured: dict[str, object] = {}

    async def _fake_execute(self):
        captured["sinks"] = self.sinks
        return OpenClawStreamingResult(
            full_text='{"result":"streamed"}',
            final_text='{"result":"streamed"}',
            tokens_emitted=2,
            usage={"output_tokens": 2},
        )

    async def _should_not_call_non_streaming(self, **kwargs):
        raise AssertionError("non-streaming transport should not be called")

    monkeypatch.setattr(OpenClawStreamingExecutor, "execute", _fake_execute)
    monkeypatch.setattr(
        OpenClawEngine,
        "_call_responses_api",
        _should_not_call_non_streaming,
    )

    try:
        outputs = await _invoke_once()
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    assert outputs[0].payload["result"] == "streamed"
    sinks = captured.get("sinks")
    assert isinstance(sinks, list)
    assert len(sinks) == 1


@pytest.mark.asyncio
@respx.mock
async def test_streaming_path_falls_back_to_non_streaming_when_sse_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global

    async def _broadcast(_event) -> None:
        return None

    Agent._websocket_broadcast_global = _broadcast

    async def _failing_stream_events(self):
        raise RuntimeError("sse transport failed")
        yield  # pragma: no cover

    monkeypatch.setattr(OpenClawSSEConsumer, "stream_events", _failing_stream_events)

    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json=_responses_completed('{"result":"fallback"}'))

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    try:
        outputs = await _invoke_once(retries=0)
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    assert outputs[0].payload["result"] == "fallback"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["stream"] is False
