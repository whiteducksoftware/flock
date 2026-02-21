"""TDD tests for OpenClawEngine responses transport + parsing + error mapping."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

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


@flock_type(name="OpenClawEngineAuxOutput")
class OpenClawEngineAuxOutput(BaseModel):
    note: str = Field(description="Auxiliary output payload")


@pytest.fixture(autouse=True)
def _reset_openclaw_reliability_counters() -> None:
    OpenClawEngine._reset_reliability_counters_for_tests()
    yield
    OpenClawEngine._reset_reliability_counters_for_tests()


def _config(
    *, token: str | None = "token-codie", agent_id: str = "main"
) -> OpenClawConfig:
    return OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token=token,
                token_env="OPENCLAW_CODIE_TOKEN" if token is not None else None,
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
    stream: bool | None = None,
):
    flock = Flock(openclaw=config or _config(), no_output=True)
    builder = (
        flock.openclaw_agent(
            "codie", timeout=timeout_seconds, retries=retries, mode=mode
        )
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )
    if stream is not None:
        builder.agent.engines[0].stream = stream

    return await flock.invoke(
        builder.agent,
        OpenClawEngineInput(prompt="make pizza"),
        publish_outputs=False,
    )


async def _invoke_fan_out_once(
    *,
    fan_out,
    timeout_seconds: int = 120,
    retries: int = 1,
    config: OpenClawConfig | None = None,
):
    flock = Flock(openclaw=config or _config(), no_output=True)
    builder = (
        flock.openclaw_agent(
            "codie", timeout=timeout_seconds, retries=retries, mode="spawn"
        )
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, fan_out=fan_out)
    )

    return await flock.invoke(
        builder.agent,
        OpenClawEngineInput(prompt="map competitors"),
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
async def test_responses_request_contains_expected_contract_fields_and_headers() -> (
    None
):
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
    # Schema in prompt text (fallback) + text.format (enforcement)
    assert "Schema:" in payload["input"]
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
async def test_unrecognized_text_format_falls_back_without_it() -> None:
    """Gateway rejecting text.format should retry without it and succeed."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        payload = json.loads(request.content.decode("utf-8"))
        if "text" in payload:
            return httpx.Response(
                400,
                json={"error": {"message": 'Unrecognized key: "text"'}},
            )
        return httpx.Response(
            200, json=_responses_completed('{"result":"fallback ok"}')
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)
    assert calls == 2
    assert outputs[0].payload["result"] == "fallback ok"

    counters = OpenClawEngine._get_reliability_counters()
    assert counters["requests_total"] == 1
    assert counters["attempts_total"] == 2
    assert counters["attempts_with_text_format"] == 1
    assert counters["attempts_without_text_format"] == 1
    assert counters["fallback_unsupported_text_format"] == 1
    assert counters["responses_success"] == 1
    assert counters["responses_failure"] == 0


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
    builder.agent.engines[
        0
    ].mode = "session"  # Bypass model literal validation to test runtime guard.

    with pytest.raises(ValueError, match="Unsupported OpenClaw mode"):
        await flock.invoke(
            builder.agent,
            OpenClawEngineInput(prompt="make pizza"),
            publish_outputs=False,
        )


def test_parse_responses_output_validates_shapes() -> None:
    """Parser should validate output text presence and JSON shape per output contract."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )

    engine = builder.agent.engines[0]
    output_group = builder.agent.output_groups[0]

    assert engine._parse_responses_output(
        _responses_completed('{"result":"ok"}'),
        output_group=output_group,
    ) == {"result": "ok"}

    with pytest.raises(ValueError, match="result JSON must be an object"):
        engine._parse_responses_output(
            _responses_completed('["x"]'),
            output_group=output_group,
        )

    with pytest.raises(ValueError, match="missing output text|output"):
        engine._parse_responses_output(
            {"id": "resp_x", "status": "completed", "output": []},
            output_group=output_group,
        )


def test_stream_default_uses_pytest_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default stream should be runtime-true but auto-off when PYTEST_CURRENT_TEST is set."""
    gateway = _config().get_gateway("codie")

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_openclaw_engine.py::test")
    engine_in_pytest = OpenClawEngine(alias="codie", gateway=gateway)
    assert engine_in_pytest.stream is False

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    engine_outside_pytest = OpenClawEngine(alias="codie", gateway=gateway)
    assert engine_outside_pytest.stream is True


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


def test_to_json_safe_normalizes_datetime_uuid_and_nested_values() -> None:
    """JSON-safe helper should normalize non-JSON-native runtime values."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )

    engine = builder.agent.engines[0]

    normalized = engine._to_json_safe({
        "seen_at": datetime.now(UTC),
        "ids": [uuid4(), uuid4()],
        "nested": {
            "window": (datetime.now(UTC), datetime.now(UTC)),
            "tags": {"a", "b"},
        },
    })

    assert isinstance(normalized["seen_at"], str)
    assert all(isinstance(i, str) for i in normalized["ids"])
    assert isinstance(normalized["nested"]["window"], list)
    assert all(isinstance(i, str) for i in normalized["nested"]["window"])
    assert isinstance(normalized["nested"]["tags"], list)


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
    assert "Schema:" in payload["input"]
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True


def test_build_responses_payload_includes_context_history_when_available() -> None:
    """Context artifacts should be included in OpenClaw request guidance when enabled."""
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
        ctx=SimpleNamespace(
            correlation_id="cid-test",
            artifacts=[
                SimpleNamespace(
                    type="UpstreamArtifact",
                    payload={"note": "already discovered"},
                    produced_by="upstream-agent",
                )
            ],
            is_batch=False,
        ),
        inputs=SimpleNamespace(
            artifacts=[
                SimpleNamespace(
                    payload={"prompt": "make pizza"},
                    correlation_id="cid-test",
                )
            ],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert "Context:" in payload["input"]
    assert "UpstreamArtifact" in payload["input"]


def test_build_responses_payload_serializes_datetime_in_context_payload() -> None:
    """Context payload serialization should tolerate datetime values."""
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
        ctx=SimpleNamespace(
            correlation_id="cid-test-datetime-context",
            artifacts=[
                SimpleNamespace(
                    type="UpstreamArtifact",
                    payload={"seen_at": datetime.now(UTC)},
                    produced_by="upstream-agent",
                )
            ],
            is_batch=False,
        ),
        inputs=SimpleNamespace(
            artifacts=[
                SimpleNamespace(
                    payload={"prompt": "make pizza"},
                    correlation_id="cid-test-datetime-context",
                )
            ],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert "Context:" in payload["input"]
    assert "seen_at" in payload["input"]


def test_build_responses_payload_marks_batch_mode_in_task_text() -> None:
    """Batch executions should include explicit batch processing guidance."""
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
        ctx=SimpleNamespace(correlation_id="cid-batch", artifacts=[], is_batch=True),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert "batch" in payload["input"].lower()


def test_build_responses_payload_serializes_datetime_in_input_payload() -> None:
    """Input payload serialization should tolerate datetime values."""
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
        ctx=SimpleNamespace(
            correlation_id="cid-test-datetime-input", artifacts=[], is_batch=False
        ),
        inputs=SimpleNamespace(
            artifacts=[
                SimpleNamespace(
                    payload={"prompt": "make pizza", "created_at": datetime.now(UTC)},
                    correlation_id="cid-test-datetime-input",
                )
            ],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert "Input:" in payload["input"]
    assert "created_at" in payload["input"]


def test_build_responses_payload_includes_group_description_override() -> None:
    """publishes(..., description=...) should be reflected in OpenClaw task guidance."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, description="Return concise bullet outputs")
    )

    engine = builder.agent.engines[0]
    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-desc"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert "Return concise bullet outputs" in payload["input"]


def test_engine_instructions_override_takes_precedence_over_agent_description() -> None:
    """Engine-level instructions should override agent.description when provided."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Agent-level description")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )

    engine = OpenClawEngine(
        alias="codie",
        gateway=_config().get_gateway("codie"),
        instructions="Engine override instructions",
    )

    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-override"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert payload["instructions"] == "Engine override instructions"


def test_response_mode_prompt_only_disables_text_format_contract() -> None:
    """response_mode should influence payload contract rather than being dead config."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )

    engine = OpenClawEngine(
        alias="codie",
        gateway=_config().get_gateway("codie"),
        response_mode="prompt_only",
    )

    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-response-mode"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    assert "text" not in payload


@pytest.mark.asyncio
@respx.mock
async def test_single_output_bypasses_multi_output_envelope_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single-output execution should not call multi-output envelope builders."""

    def _explode_slot_map(self, output_group):
        raise AssertionError("single-output path must not build multi-output slot map")

    def _explode_multi_schema(self, slot_map):
        raise AssertionError(
            "single-output path must not build multi-output envelope schema"
        )

    monkeypatch.setattr(
        OpenClawEngine, "_build_multi_output_slot_map", _explode_slot_map
    )
    monkeypatch.setattr(
        OpenClawEngine,
        "_build_multi_output_schema_contract",
        _explode_multi_schema,
    )

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(200, json=_responses_completed('{"result":"ok"}'))
    )

    outputs = await _invoke_once(retries=0)

    assert len(outputs) == 1
    assert outputs[0].type == "OpenClawEngineOutput"
    assert outputs[0].payload["result"] == "ok"


def test_multi_output_slot_map_is_deterministic_by_declaration_order() -> None:
    """Slot mapping should preserve output declaration order deterministically."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
    )

    engine = builder.agent.engines[0]
    slot_map = engine._build_multi_output_slot_map(builder.agent.output_groups[0])

    assert list(slot_map.keys()) == ["OpenClawEngineOutput", "OpenClawEngineAuxOutput"]


def test_build_responses_payload_uses_envelope_schema_for_multi_output_group() -> None:
    """Multi-output groups should build one envelope schema with typed slots."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
    )

    engine = builder.agent.engines[0]
    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-multi-output"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    schema = payload["text"]["format"]["schema"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False

    props = schema["properties"]
    assert "OpenClawEngineOutput" in props
    assert "OpenClawEngineAuxOutput" in props
    assert props["OpenClawEngineOutput"]["type"] == "object"
    assert props["OpenClawEngineAuxOutput"]["type"] == "object"
    assert set(schema["required"]) == {
        "OpenClawEngineOutput",
        "OpenClawEngineAuxOutput",
    }


def test_build_responses_payload_uses_array_schema_for_fan_out_range() -> None:
    """Fan-out declarations should produce an array schema request contract."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Discovers competitors")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, fan_out=(3, 8))
    )

    engine = builder.agent.engines[0]
    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-fanout"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "find competitors"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    schema = payload["text"]["format"]["schema"]
    assert schema["type"] == "array"
    assert schema["minItems"] == 3
    assert schema["maxItems"] == 8
    assert "between 3 and 8" in payload["input"]


@pytest.mark.asyncio
@respx.mock
async def test_fan_out_fixed_materializes_multiple_artifacts() -> None:
    """Fixed fan-out should materialize one artifact per returned item."""
    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json=_responses_completed(
                '[{"result":"one"},{"result":"two"},{"result":"three"}]'
            ),
        )
    )

    outputs = await _invoke_fan_out_once(fan_out=3, retries=0)

    assert len(outputs) == 3
    assert [item.payload["result"] for item in outputs] == ["one", "two", "three"]


def test_fan_out_materialization_does_not_reuse_single_artifact_id() -> None:
    """Fan-out artifacts should not all reuse one pre-generated artifact id."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, fan_out=3)
    )

    engine = builder.agent.engines[0]
    output_group = builder.agent.output_groups[0]

    artifacts = engine._materialize_artifacts_for_output_group(
        [
            {"result": "one"},
            {"result": "two"},
            {"result": "three"},
        ],
        output_group=output_group,
        produced_by="codie",
        metadata={
            "correlation_id": "cid-fanout-id",
            # Simulates streaming path metadata with pre-generated id.
            "artifact_id": uuid4(),
        },
    )

    assert len(artifacts) == 3
    assert len({str(a.id) for a in artifacts}) == 3


@pytest.mark.asyncio
@respx.mock
async def test_fan_out_fixed_count_mismatch_retries_then_fails() -> None:
    """Count mismatch should follow retry policy and fail with contract error."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=_responses_completed('[{"result":"one"},{"result":"two"}]'),
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    with pytest.raises(RuntimeError, match="fan-out|count|Expected|expected"):
        await _invoke_fan_out_once(fan_out=3, retries=1)

    assert calls == 2


@pytest.mark.asyncio
@respx.mock
async def test_fan_out_dynamic_under_min_retries_then_fails() -> None:
    """Dynamic fan-out below min should retry and then fail explicitly."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=_responses_completed('[{"result":"one"},{"result":"two"}]'),
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    with pytest.raises(RuntimeError, match="fan-out|range|Expected|expected"):
        await _invoke_fan_out_once(fan_out=(3, 8), retries=1)

    assert calls == 2


@pytest.mark.asyncio
@respx.mock
async def test_fan_out_dynamic_over_max_is_capped() -> None:
    """Dynamic fan-out over max should cap outputs at declared max bound."""
    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json=_responses_completed(
                '[{"result":"one"},{"result":"two"},{"result":"three"},{"result":"four"}]'
            ),
        )
    )

    outputs = await _invoke_fan_out_once(fan_out=(2, 3), retries=0)

    assert len(outputs) == 3
    assert [item.payload["result"] for item in outputs] == ["one", "two", "three"]


def test_multi_output_group_envelope_slots_use_array_shape_when_fan_out_is_enabled() -> (
    None
):
    """Multi-output slots should become arrays when declarations are fan-out enabled."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput, fan_out=2)
    )

    engine = builder.agent.engines[0]
    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-multi-fanout-shape"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    schema = payload["text"]["format"]["schema"]
    output_slot = schema["properties"]["OpenClawEngineOutput"]
    aux_slot = schema["properties"]["OpenClawEngineAuxOutput"]

    assert output_slot["type"] == "array"
    assert aux_slot["type"] == "array"
    assert output_slot["minItems"] == 2
    assert output_slot["maxItems"] == 2
    assert aux_slot["minItems"] == 2
    assert aux_slot["maxItems"] == 2


def test_multi_output_group_envelope_slots_use_object_shape_for_non_fan_out() -> None:
    """Non-fan-out multi-output slots should each be modeled as object slots."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
    )

    engine = builder.agent.engines[0]
    payload = engine._build_responses_payload(
        agent=builder.agent,
        ctx=SimpleNamespace(correlation_id="cid-multi-shape"),
        inputs=SimpleNamespace(
            artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
            state={},
        ),
        output_group=builder.agent.output_groups[0],
    )

    schema = payload["text"]["format"]["schema"]
    assert schema["properties"]["OpenClawEngineOutput"]["type"] == "object"
    assert schema["properties"]["OpenClawEngineAuxOutput"]["type"] == "object"


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_group_rejects_unknown_envelope_slot() -> None:
    """Strict multi-output envelope should fail when unknown slot keys are returned."""
    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
        .agent
    )

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json=_responses_completed(
                '{"OpenClawEngineOutput":{"result":"ok"},'
                '"OpenClawEngineAuxOutput":{"note":"ok"},'
                '"UnknownSlot":{"x":"boom"}}'
            ),
        )
    )

    with pytest.raises(RuntimeError, match="unknown slot|undeclared slot|envelope"):
        await flock.invoke(
            agent,
            OpenClawEngineInput(prompt="multi-output unknown slot"),
            publish_outputs=False,
        )


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_group_rejects_missing_required_envelope_slot() -> None:
    """Strict multi-output envelope should fail when declared slots are missing."""
    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
        .agent
    )

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json=_responses_completed('{"OpenClawEngineOutput":{"result":"ok"}}'),
        )
    )

    with pytest.raises(RuntimeError, match="missing slot|required slot|envelope"):
        await flock.invoke(
            agent,
            OpenClawEngineInput(prompt="multi-output missing slot"),
            publish_outputs=False,
        )


def test_multi_output_group_slot_name_collision_fails_fast() -> None:
    """Duplicate slot keys must fail fast with collision/alias guidance."""
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .description("Plans meals")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineOutput)
    )

    engine = builder.agent.engines[0]

    with pytest.raises(ValueError, match="slot|collision|duplicate|alias"):
        engine._build_responses_payload(
            agent=builder.agent,
            ctx=SimpleNamespace(correlation_id="cid-slot-collision"),
            inputs=SimpleNamespace(
                artifacts=[SimpleNamespace(payload={"prompt": "make pizza"})],
                state={},
            ),
            output_group=builder.agent.output_groups[0],
        )


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_malformed_envelope_retries_then_fails() -> None:
    """Malformed multi-output envelope should trigger retry/repair then fail if still invalid."""
    calls = 0

    def _handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json=_responses_completed('{"OpenClawEngineOutput":{"result":"ok"}'),
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie", retries=1)
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
        .agent
    )

    with pytest.raises(RuntimeError, match="parse|json|envelope"):
        await flock.invoke(
            agent,
            OpenClawEngineInput(prompt="multi-output malformed envelope"),
            publish_outputs=False,
        )

    assert calls == 2


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_malformed_envelope_repairs_and_succeeds() -> None:
    """Malformed first attempt should be repairable on retry for multi-output envelope."""
    calls = 0

    def _handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json=_responses_completed('{"OpenClawEngineOutput":{"result":"ok"}'),
            )

        return httpx.Response(
            200,
            json=_responses_completed(
                '{"OpenClawEngineOutput":{"result":"ok"},"OpenClawEngineAuxOutput":{"note":"fixed"}}'
            ),
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie", retries=1)
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
        .agent
    )

    outputs = await flock.invoke(
        agent,
        OpenClawEngineInput(prompt="multi-output repair success"),
        publish_outputs=False,
    )

    assert calls == 2
    assert len(outputs) == 2
    assert {item.type for item in outputs} == {
        "OpenClawEngineOutput",
        "OpenClawEngineAuxOutput",
    }


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_envelope_fixed_fan_out_count_mismatch_retries_then_fails() -> (
    None
):
    """Per-slot fixed fan-out count violations should retry then fail in envelope path."""
    calls = 0

    def _handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        # fan_out=2 for both slots, but aux slot returns only 1 item (violation)
        return httpx.Response(
            200,
            json=_responses_completed(
                '{"OpenClawEngineOutput":[{"result":"a"},{"result":"b"}],'
                '"OpenClawEngineAuxOutput":[{"note":"only-one"}]}'
            ),
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie", retries=1)
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput, fan_out=2)
        .agent
    )

    with pytest.raises(
        RuntimeError, match="fan-out contract violation|expected exactly"
    ):
        await flock.invoke(
            agent,
            OpenClawEngineInput(prompt="multi-output fan-out mismatch"),
            publish_outputs=False,
        )

    assert calls == 2


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_envelope_dynamic_fan_out_over_max_is_capped() -> None:
    """Per-slot dynamic fan-out should cap over-max arrays in multi-output envelope."""
    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json=_responses_completed(
                '{"OpenClawEngineOutput":[{"result":"a"},{"result":"b"},{"result":"c"}],'
                '"OpenClawEngineAuxOutput":[{"note":"x"},{"note":"y"},{"note":"z"}]}'
            ),
        )
    )

    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie", retries=0)
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput, fan_out=(1, 2))
        .agent
    )

    outputs = await flock.invoke(
        agent,
        OpenClawEngineInput(prompt="multi-output fan-out cap"),
        publish_outputs=False,
    )

    assert len(outputs) == 4
    assert [o.type for o in outputs] == [
        "OpenClawEngineOutput",
        "OpenClawEngineOutput",
        "OpenClawEngineAuxOutput",
        "OpenClawEngineAuxOutput",
    ]


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_engine_rejects_non_envelope_for_multi_output_group() -> None:
    """Multi-output groups should reject legacy single-object non-envelope payloads."""
    flock = Flock(openclaw=_config(), no_output=True)
    agent = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput, OpenClawEngineAuxOutput)
        .agent
    )

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(200, json=_responses_completed('{"result":"ok"}'))
    )

    with pytest.raises(RuntimeError, match="unknown slot|envelope|parse"):
        await flock.invoke(
            agent,
            OpenClawEngineInput(prompt="multi-output"),
            publish_outputs=False,
        )


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
        outputs = await _invoke_once(stream=True)
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    assert outputs[0].payload["result"] == "streamed"
    sinks = captured.get("sinks")
    assert isinstance(sinks, list)
    assert len(sinks) == 1


@pytest.mark.asyncio
async def test_stream_false_forces_non_streaming_even_with_dashboard_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global

    async def _broadcast(_event) -> None:
        return None

    Agent._websocket_broadcast_global = _broadcast
    seen: dict[str, object] = {}

    async def _should_not_stream(self, **kwargs):
        raise AssertionError(
            "streaming attempt should not be used when engine.stream is False"
        )

    async def _fake_non_streaming(self, **kwargs):
        seen["payload"] = kwargs.get("payload")
        return _responses_completed('{"result":"non-stream"}')

    monkeypatch.setattr(
        OpenClawEngine,
        "_execute_streaming_attempt",
        _should_not_stream,
    )
    monkeypatch.setattr(
        OpenClawEngine,
        "_call_responses_api",
        _fake_non_streaming,
    )

    try:
        outputs = await _invoke_once(stream=False)
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    assert outputs[0].payload["result"] == "non-stream"
    payload = seen.get("payload")
    assert isinstance(payload, dict)
    assert payload["stream"] is False


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
        outputs = await _invoke_once(retries=0, stream=True)
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    assert outputs[0].payload["result"] == "fallback"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["stream"] is False


@pytest.mark.asyncio
async def test_cli_streaming_is_used_when_stream_enabled_without_dashboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    original_counter = Agent._streaming_counter
    Agent._websocket_broadcast_global = None
    Agent._streaming_counter = 0

    captured: dict[str, object] = {}

    async def _fake_streaming_attempt(self, **kwargs):
        captured["is_dashboard_stream"] = kwargs.get("is_dashboard_stream")
        return {"result": "streamed-cli"}

    async def _should_not_call_non_streaming(self, **kwargs):
        raise AssertionError("non-streaming transport should not be called")

    monkeypatch.setattr(
        OpenClawEngine,
        "_execute_streaming_attempt",
        _fake_streaming_attempt,
    )
    monkeypatch.setattr(
        OpenClawEngine,
        "_call_responses_api",
        _should_not_call_non_streaming,
    )

    try:
        outputs = await _invoke_once(stream=True)
        assert Agent._streaming_counter == 0
    finally:
        Agent._websocket_broadcast_global = original_broadcast
        Agent._streaming_counter = original_counter

    assert outputs[0].payload["result"] == "streamed-cli"
    assert captured["is_dashboard_stream"] is False


@pytest.mark.asyncio
async def test_cli_streaming_counter_decrements_in_finally_when_streaming_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    original_counter = Agent._streaming_counter
    Agent._websocket_broadcast_global = None
    Agent._streaming_counter = 0

    async def _boom_streaming_attempt(self, **kwargs):
        raise RuntimeError("streaming exploded")

    monkeypatch.setattr(
        OpenClawEngine,
        "_execute_streaming_attempt",
        _boom_streaming_attempt,
    )

    try:
        with pytest.raises(RuntimeError, match="streaming exploded"):
            await _invoke_once(stream=True, retries=0)

        assert Agent._streaming_counter == 0
    finally:
        Agent._websocket_broadcast_global = original_broadcast
        Agent._streaming_counter = original_counter


def test_resolve_streaming_mode_marks_output_queued_when_cli_slot_busy() -> None:
    from flock.core import Agent

    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )
    engine = builder.agent.engines[0]
    engine.stream = True

    ctx = SimpleNamespace(state={})

    original_broadcast = Agent._websocket_broadcast_global
    original_counter = Agent._streaming_counter
    Agent._websocket_broadcast_global = None
    Agent._streaming_counter = 1

    try:
        should_stream, is_dashboard, claimed_slot = engine._resolve_streaming_mode(ctx)
    finally:
        Agent._websocket_broadcast_global = original_broadcast
        Agent._streaming_counter = original_counter

    assert should_stream is False
    assert is_dashboard is False
    assert claimed_slot is False
    assert ctx.state["_flock_output_queued"] is True


def test_resolve_output_utility_theme_prefers_output_component_theme() -> None:
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )
    engine = builder.agent.engines[0]

    fake_agent = SimpleNamespace(
        utilities=[
            SimpleNamespace(
                name="output",
                config=SimpleNamespace(theme=SimpleNamespace(value="catppuccin-mocha")),
            )
        ]
    )

    assert engine._resolve_output_utility_theme(fake_agent) == "catppuccin-mocha"


def test_build_cli_streaming_sinks_uses_openclaw_lobster_label() -> None:
    flock = Flock(openclaw=_config(), no_output=True)
    builder = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawEngineInput)
        .publishes(OpenClawEngineOutput)
    )
    engine = builder.agent.engines[0]

    # Override no_output so CLI streaming sink can be created in this unit test.
    engine.no_output = False

    output_group = builder.agent.output_groups[0]
    ctx = SimpleNamespace(correlation_id="cid-stream", state={})

    sinks, _live_cm, _live_ref = engine._build_cli_streaming_sinks(
        agent=builder.agent,
        ctx=ctx,
        output_group=output_group,
        artifact_id="artifact-stream-id",
    )

    assert sinks
    rich_sink = sinks[0]
    assert rich_sink.final_display_data[4] == "codie 🦞"
