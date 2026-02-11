"""TDD tests for OpenClawEngine spawn transport + parsing + error mapping (Phase 1)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import BaseModel, Field

from flock import Flock
from flock.integrations.openclaw import GatewayConfig, OpenClawConfig
from flock.registry import flock_type


@flock_type(name="OpenClawEngineInput")
class OpenClawEngineInput(BaseModel):
    prompt: str = Field(description="Prompt payload")


@flock_type(name="OpenClawEngineOutput")
class OpenClawEngineOutput(BaseModel):
    result: str = Field(description="Engine result payload")


def _config() -> OpenClawConfig:
    return OpenClawConfig(
        gateways={
            "codie": GatewayConfig(
                url="http://localhost:19789",
                token="token-codie",
                token_env="OPENCLAW_CODIE_TOKEN",
            )
        }
    )


async def _invoke_once(*, timeout: int = 120, retries: int = 1):
    flock = Flock(openclaw=_config())
    builder = (
        flock.openclaw_agent("codie", timeout=timeout, retries=retries)
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

    outputs = await _invoke_once(timeout=120, retries=1)

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
