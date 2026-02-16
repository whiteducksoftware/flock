"""Integration tests for OpenClaw + native mixed pipeline behavior (Phase 1)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import BaseModel, Field

from flock import Flock
from flock.components.agent import EngineComponent
from flock.integrations.openclaw.streaming import OpenClawSSEConsumer, SSEFrame
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


@flock_type(name="OpenClawPipelineInput")
class OpenClawPipelineInput(BaseModel):
    feature: str = Field(description="Requested feature")


@flock_type(name="OpenClawPipelineDraft")
class OpenClawPipelineDraft(BaseModel):
    draft: str = Field(description="Draft implementation")


@flock_type(name="OpenClawPipelineReview")
class OpenClawPipelineReview(BaseModel):
    verdict: str = Field(description="Review verdict")
    source: str = Field(description="Reviewer source")


def _openclaw_config_classes():
    """Require OpenClaw config exports from canonical package namespaces."""
    import flock as flock_pkg
    import flock.core as core_pkg

    assert hasattr(flock_pkg, "OpenClawConfig"), (
        "Expected flock.OpenClawConfig export for integration setup"
    )
    assert hasattr(flock_pkg, "GatewayConfig"), (
        "Expected flock.GatewayConfig export for integration setup"
    )
    assert hasattr(core_pkg, "OpenClawConfig"), (
        "Expected flock.core.OpenClawConfig export for integration setup"
    )
    assert hasattr(core_pkg, "GatewayConfig"), (
        "Expected flock.core.GatewayConfig export for integration setup"
    )

    return flock_pkg.OpenClawConfig, flock_pkg.GatewayConfig


class NativeReviewEngine(EngineComponent):
    async def evaluate(self, agent, ctx, inputs, output_group) -> EvalResult:
        draft = OpenClawPipelineDraft(**inputs.artifacts[0].payload)
        review = OpenClawPipelineReview(
            verdict=f"approved: {draft.draft}",
            source=agent.name,
        )
        return EvalResult.from_object(review, agent=agent)


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_agent_publishes_validated_artifact_to_blackboard() -> None:
    """OpenClaw agent output should be validated and persisted via normal pipeline."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-int-1",
                "object": "response",
                "status": "completed",
                "model": "openclaw",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"draft":"Implement endpoint adapter"}',
                            }
                        ],
                    }
                ],
            },
        )
    )

    flock = Flock(
        openclaw=OpenClawConfig(
            gateways={
                "codie": GatewayConfig(
                    url="http://localhost:19789",
                    token="token-codie",
                    token_env="OPENCLAW_CODIE_TOKEN",
                )
            }
        )
    )

    flock.openclaw_agent("codie").consumes(OpenClawPipelineInput).publishes(
        OpenClawPipelineDraft
    )

    input_artifact = await flock.publish(OpenClawPipelineInput(feature="adapter layer"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]

    assert len(drafts) == 1
    assert drafts[0].payload == {"draft": "Implement endpoint adapter"}
    assert drafts[0].correlation_id == input_artifact.correlation_id


@pytest.mark.asyncio
@respx.mock
async def test_mixed_openclaw_and_native_pipeline_stays_compatible() -> None:
    """OpenClaw and non-OpenClaw agents should compose in one workflow unchanged."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-int-2",
                "object": "response",
                "status": "completed",
                "model": "openclaw",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"draft":"Add retry policy docs"}',
                            }
                        ],
                    }
                ],
            },
        )
    )

    flock = Flock(
        openclaw=OpenClawConfig(
            gateways={
                "codie": GatewayConfig(
                    url="http://localhost:19789",
                    token="token-codie",
                    token_env="OPENCLAW_CODIE_TOKEN",
                )
            }
        )
    )

    flock.openclaw_agent("codie").consumes(OpenClawPipelineInput).publishes(
        OpenClawPipelineDraft
    )

    (
        flock.agent("native-reviewer")
        .consumes(OpenClawPipelineDraft)
        .publishes(OpenClawPipelineReview)
        .with_engines(NativeReviewEngine())
    )

    await flock.publish(OpenClawPipelineInput(feature="docs + retries"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    types = {a.type for a in artifacts}

    assert "OpenClawPipelineDraft" in types
    assert "OpenClawPipelineReview" in types

    reviews = [a for a in artifacts if a.type == "OpenClawPipelineReview"]
    assert len(reviews) == 1
    assert reviews[0].payload["verdict"].startswith("approved: Add retry policy docs")
    assert reviews[0].payload["source"] == "native-reviewer"


@pytest.mark.asyncio
async def test_openclaw_streaming_emits_websocket_events_compatible_with_dashboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Streaming path should emit WebSocket events compatible with DSPy sink contracts."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    from flock.components.server.models.events import StreamingOutputEvent
    from flock.core import Agent

    captured: list[StreamingOutputEvent] = []

    async def _broadcast(event: StreamingOutputEvent) -> None:
        captured.append(event)

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = _broadcast

    async def _mock_stream_events(self):
        yield SSEFrame(event="response.created", data="{}")
        yield SSEFrame(event="response.in_progress", data="{}")
        yield SSEFrame(event="response.output_text.delta", data='{"delta":"{\\"draft\\":\\"stre"}')
        yield SSEFrame(event="response.output_text.delta", data='{"delta":"amed\\"}"}')
        yield SSEFrame(event="response.completed", data='{"usage":{"output_tokens":2}}')
        yield SSEFrame(event="done", data="[DONE]")

    monkeypatch.setattr(OpenClawSSEConsumer, "stream_events", _mock_stream_events)

    try:
        flock = Flock(
            openclaw=OpenClawConfig(
                gateways={
                    "codie": GatewayConfig(
                        url="http://localhost:19789",
                        token="token-codie",
                        token_env="OPENCLAW_CODIE_TOKEN",
                    )
                }
            ),
            no_output=True,
        )

        flock.openclaw_agent("codie").consumes(OpenClawPipelineInput).publishes(
            OpenClawPipelineDraft
        )

        await flock.publish(OpenClawPipelineInput(feature="streaming compatibility"))
        await flock.run_until_idle()
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]
    assert len(drafts) == 1
    assert drafts[0].payload == {"draft": "streamed"}

    assert captured, "Expected streaming events to be broadcast"
    assert [event.sequence for event in captured] == list(range(len(captured)))

    # DSPy-compatible WebSocket sink behavior: status logs, token deltas, then
    # terminal final logs.
    assert captured[0].output_type == "log"
    assert captured[1].output_type == "log"
    assert any(event.output_type == "llm_token" for event in captured)
    assert captured[-2].is_final is True
    assert captured[-1].is_final is True
    assert captured[-1].content == "--- End of output ---"

    artifact_ids = {event.artifact_id for event in captured}
    assert len(artifact_ids) == 1
    assert "" not in artifact_ids
    assert all(event.artifact_type == "OpenClawPipelineDraft" for event in captured)


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_streaming_sse_failure_falls_back_and_returns_valid_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When SSE stream fails, engine should fall back to non-streaming and still succeed."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    from flock.components.server.models.events import StreamingOutputEvent
    from flock.core import Agent

    captured: list[StreamingOutputEvent] = []

    async def _broadcast(event: StreamingOutputEvent) -> None:
        captured.append(event)

    original_broadcast = Agent._websocket_broadcast_global
    Agent._websocket_broadcast_global = _broadcast

    async def _failing_stream_events(self):
        raise RuntimeError("sse transport failed")
        yield  # pragma: no cover

    monkeypatch.setattr(OpenClawSSEConsumer, "stream_events", _failing_stream_events)

    seen: dict[str, object] = {}

    def _handler(request: httpx.Request) -> httpx.Response:
        seen["payload"] = request.content.decode("utf-8")
        return httpx.Response(
            200,
            json={
                "id": "resp-fallback-int",
                "object": "response",
                "status": "completed",
                "model": "openclaw",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"draft":"from fallback"}',
                            }
                        ],
                    }
                ],
            },
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

    try:
        flock = Flock(
            openclaw=OpenClawConfig(
                gateways={
                    "codie": GatewayConfig(
                        url="http://localhost:19789",
                        token="token-codie",
                        token_env="OPENCLAW_CODIE_TOKEN",
                    )
                }
            ),
            no_output=True,
        )

        flock.openclaw_agent("codie").consumes(OpenClawPipelineInput).publishes(
            OpenClawPipelineDraft
        )

        await flock.publish(OpenClawPipelineInput(feature="stream fallback integration"))
        await flock.run_until_idle()
    finally:
        Agent._websocket_broadcast_global = original_broadcast

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]
    assert len(drafts) == 1
    assert drafts[0].payload == {"draft": "from fallback"}

    # Fallback still sends terminal websocket events so dashboard closes stream UI.
    assert captured
    assert captured[-2].is_final is True
    assert captured[-1].is_final is True
    assert captured[-1].content == "--- End of output ---"
    assert not any(event.output_type == "llm_token" for event in captured)

    payload_text = str(seen.get("payload", ""))
    parsed_payload = json.loads(payload_text) if payload_text else {}
    assert parsed_payload.get("stream") is False
