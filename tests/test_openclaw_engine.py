"""TDD tests for OpenClawEngine spawn transport + parsing + error mapping (Phase 1)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import BaseModel, Field

from flock import Flock
from flock.integrations.openclaw import GatewayConfig, OpenClawConfig
from flock.integrations.openclaw.engine import OpenClawEngine
from flock.registry import flock_type


@flock_type(name="OpenClawEngineInput")
class OpenClawEngineInput(BaseModel):
    prompt: str = Field(description="Prompt payload")


@flock_type(name="OpenClawEngineOutput")
class OpenClawEngineOutput(BaseModel):
    result: str = Field(description="Engine result payload")


def _config(*, token: str | None = "token-codie") -> OpenClawConfig:
    return OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token=token,
                token_env="OPENCLAW_CODIE_TOKEN",
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
    # Keep transport tests independent from terminal rendering/theme state.
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


@pytest.mark.asyncio
@respx.mock
async def test_spawn_request_contains_expected_contract_fields() -> None:
    """Engine should call spawn endpoint with Phase 1 request contract."""
    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-123",
                "result": '{"result":"margherita"}',
            },
        )

    route = respx.post("http://localhost:19789/api/sessions/spawn").mock(
        side_effect=_handler
    )

    outputs = await _invoke_once(timeout_seconds=120, retries=1)

    assert route.called
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert "task" in payload
    assert payload["runTimeoutSeconds"] == 120
    assert payload["cleanup"] == "delete"
    assert str(payload["label"]).startswith("flock-codie-")
    assert outputs[0].payload["result"] == "margherita"


@pytest.mark.asyncio
@respx.mock
async def test_valid_json_result_is_parsed_into_typed_output() -> None:
    """Engine should parse JSON result and materialize typed artifact."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-124",
                "result": '{"result":"pepperoni"}',
            },
        )
    )

    outputs = await _invoke_once()

    assert len(outputs) == 1
    assert outputs[0].type == "OpenClawEngineOutput"
    assert outputs[0].payload == {"result": "pepperoni"}


@pytest.mark.asyncio
@respx.mock
async def test_malformed_json_triggers_single_repair_attempt() -> None:
    """Malformed first response should trigger exactly one repair retry."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "sessionKey": "iso-bad",
                    "result": "not-json-response",
                },
            )
        return httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-fixed",
                "result": '{"result":"fixed"}',
            },
        )

    respx.post("http://localhost:19789/api/sessions/spawn").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)

    assert calls == 2
    assert outputs[0].payload["result"] == "fixed"


@pytest.mark.asyncio
@respx.mock
async def test_timeout_failure_maps_to_runtime_error() -> None:
    """Timeout should map to RuntimeError in Phase 1."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        side_effect=httpx.TimeoutException("gateway timeout")
    )

    with pytest.raises(RuntimeError, match="timeout|timed out|Timeout"):
        await _invoke_once()


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_maps_to_value_error() -> None:
    """Authentication/token failures should fail fast with ValueError."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            401,
            json={"ok": False, "error": "auth_error", "message": "Invalid token"},
        )
    )

    with pytest.raises(ValueError, match="auth|token|401|Invalid"):
        await _invoke_once()


@pytest.mark.asyncio
@respx.mock
async def test_transport_failure_maps_to_runtime_error() -> None:
    """Gateway connection failures should map to RuntimeError."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    with pytest.raises(
        RuntimeError,
        match="connection refused|connect error|gateway connection",
    ):
        await _invoke_once()


@pytest.mark.asyncio
@respx.mock
async def test_timeout_is_retriable_and_can_recover() -> None:
    """Timeouts should be retried up to retry budget."""
    calls = 0

    def _handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.TimeoutException("gateway timeout")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-recovered",
                "result": '{"result":"recovered"}',
            },
        )

    respx.post("http://localhost:19789/api/sessions/spawn").mock(side_effect=_handler)

    outputs = await _invoke_once(retries=1)

    assert calls == 2
    assert outputs[0].payload["result"] == "recovered"


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


@pytest.mark.asyncio
@respx.mock
async def test_missing_result_after_repair_budget_raises_parse_runtime_error() -> None:
    """If result field is still missing after retries, raise parse RuntimeError."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-no-result",
            },
        )
    )

    with pytest.raises(RuntimeError, match="response parse error|missing 'result'"):
        await _invoke_once(retries=0)


@pytest.mark.asyncio
@respx.mock
async def test_non_auth_ok_false_maps_to_runtime_error() -> None:
    """Gateway-level non-auth rejection should raise RuntimeError (not parse retry)."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": False,
                "error": "agent_error",
                "message": "Upstream failed",
            },
        )
    )

    with pytest.raises(RuntimeError, match="Upstream failed|rejected"):
        await _invoke_once(retries=0)


@pytest.mark.asyncio
@respx.mock
async def test_http_500_maps_to_runtime_error_with_gateway_message() -> None:
    """HTTP >= 400 should map to RuntimeError with extracted message."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            500,
            json={
                "message": "Gateway unavailable",
            },
        )
    )

    with pytest.raises(RuntimeError, match="500|Gateway unavailable"):
        await _invoke_once(retries=0)


@pytest.mark.asyncio
@respx.mock
async def test_non_json_gateway_response_maps_to_runtime_error() -> None:
    """Non-JSON gateway responses should fail with RuntimeError."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            200,
            text="not-json",
            headers={"content-type": "text/plain"},
        )
    )

    with pytest.raises(RuntimeError, match="non-JSON response"):
        await _invoke_once(retries=0)


@pytest.mark.asyncio
@respx.mock
async def test_non_object_gateway_json_response_maps_to_runtime_error() -> None:
    """Gateway must return a JSON object, not arrays or primitives."""
    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(200, json=["bad", "shape"])
    )

    with pytest.raises(RuntimeError, match="must be a JSON object"):
        await _invoke_once(retries=0)


def test_parse_result_payload_validates_missing_and_invalid_shapes() -> None:
    """Parser should validate missing result, non-object JSON, and non-string/object types."""
    engine = OpenClawEngine(alias="codie", gateway=_config().get_gateway("codie"))

    with pytest.raises(ValueError, match="missing 'result'"):
        engine._parse_result_payload({})

    assert engine._parse_result_payload({"result": {"result": "ok"}}) == {
        "result": "ok"
    }

    with pytest.raises(ValueError, match="result JSON must be an object"):
        engine._parse_result_payload({"result": '["x"]'})

    with pytest.raises(ValueError, match="result must be a JSON string or object"):
        engine._parse_result_payload({"result": 123})


def test_extract_error_message_fallbacks_for_text_and_unknown_payloads() -> None:
    """Error extraction should handle non-JSON text and unknown JSON shapes."""
    engine = OpenClawEngine(alias="codie", gateway=_config().get_gateway("codie"))

    assert engine._extract_error_message(httpx.Response(500, text="plain failure")) == "plain failure"
    assert engine._extract_error_message(httpx.Response(500, text="")) == "no error body"
    assert engine._extract_error_message(httpx.Response(500, json={"foo": "bar"})) == "unknown error"


@pytest.mark.asyncio
@respx.mock
async def test_spawn_without_token_does_not_send_authorization_header() -> None:
    """Tokenless gateway config should omit Authorization header."""
    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-no-token",
                "result": '{"result":"ok"}',
            },
        )

    respx.post("http://localhost:19789/api/sessions/spawn").mock(side_effect=_handler)

    outputs = await _invoke_once(config=_config(token=None))

    assert outputs[0].payload["result"] == "ok"
    assert seen["authorization"] is None


@pytest.mark.asyncio
@respx.mock
async def test_auth_failure_is_fail_fast_not_retried() -> None:
    """Auth failures should not consume retry budget."""
    calls = 0

    def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            401,
            json={"ok": False, "error": "auth_error", "message": "Invalid token"},
        )

    respx.post("http://localhost:19789/api/sessions/spawn").mock(side_effect=_handler)

    with pytest.raises(ValueError, match="auth|token|401|Invalid"):
        await _invoke_once(retries=3)

    assert calls == 1
