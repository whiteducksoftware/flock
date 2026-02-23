"""Integration tests for OpenClaw + native mixed pipeline behavior (Phase 1)."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from pydantic import BaseModel, Field

from flock import Flock
from flock.api.collector import DashboardEventCollector
from flock.components.agent import EngineComponent
from flock.components.agent.output_utility import OutputUtilityComponent
from flock.core.subscription import BatchSpec
from flock.integrations.openclaw.engine import OpenClawEngine
from flock.integrations.openclaw.streaming import OpenClawSSEConsumer, SSEFrame
from flock.registry import flock_type
from flock.core.store import InMemoryBlackboardStore
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


@flock_type(name="OpenClawPipelineSummary")
class OpenClawPipelineSummary(BaseModel):
    summary: str = Field(description="Execution summary")


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
    collector = DashboardEventCollector(store=InMemoryBlackboardStore())

    (
        flock.openclaw_agent("codie")
        .consumes(OpenClawPipelineInput)
        .publishes(OpenClawPipelineDraft)
        .with_utilities(collector)
    )

    input_artifact = await flock.publish(OpenClawPipelineInput(feature="adapter layer"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]

    assert len(drafts) == 1
    assert drafts[0].payload == {"draft": "Implement endpoint adapter"}
    assert drafts[0].correlation_id == input_artifact.correlation_id

    activated_events = [
        e
        for e in collector.events
        if type(e).__name__ == "AgentActivatedEvent" and e.agent_name == "codie"
    ]
    assert len(activated_events) == 1
    assert activated_events[0].correlation_id == input_artifact.correlation_id
    assert "openclaw" in activated_events[0].labels


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
@respx.mock
async def test_openclaw_second_agent_request_includes_context_history() -> None:
    """Downstream OpenClaw agent should receive serialized context guidance."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    seen_payloads: list[dict[str, object]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        seen_payloads.append(payload)

        if len(seen_payloads) == 1:
            return httpx.Response(
                200,
                json={
                    "id": "resp-int-context-1",
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
                                    "text": '{"draft":"context seed"}',
                                }
                            ],
                        }
                    ],
                },
            )

        return httpx.Response(
            200,
            json={
                "id": "resp-int-context-2",
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
                                "text": '{"verdict":"context-aware review","source":"codie-reviewer"}',
                            }
                        ],
                    }
                ],
            },
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

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

    flock.openclaw_agent("codie", name="codie-scout").consumes(
        OpenClawPipelineInput
    ).publishes(OpenClawPipelineDraft)
    flock.openclaw_agent("codie", name="codie-reviewer").consumes(
        OpenClawPipelineDraft
    ).publishes(OpenClawPipelineReview)

    await flock.publish(OpenClawPipelineInput(feature="context parity"))
    await flock.run_until_idle()

    assert len(seen_payloads) == 2
    assert "Context:" not in str(seen_payloads[0].get("input", ""))
    assert "Context:" in str(seen_payloads[1].get("input", ""))


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_batchspec_request_marks_batch_mode() -> None:
    """BatchSpec-triggered OpenClaw runs should include batch request guidance."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    seen_payloads: list[dict[str, object]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        seen_payloads.append(payload)
        return httpx.Response(
            200,
            json={
                "id": "resp-int-batch-1",
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
                                "text": '{"draft":"batched result"}',
                            }
                        ],
                    }
                ],
            },
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

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

    flock.openclaw_agent("codie").consumes(
        OpenClawPipelineInput,
        batch=BatchSpec(size=2),
    ).publishes(OpenClawPipelineDraft)

    await flock.publish(OpenClawPipelineInput(feature="batch item 1"))
    await flock.publish(OpenClawPipelineInput(feature="batch item 2"))
    await flock.run_until_idle()

    assert len(seen_payloads) == 1
    assert "batch mode" in str(seen_payloads[0].get("input", "")).lower()


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_fixed_fan_out_publishes_exact_artifact_count() -> None:
    """Fixed fan-out should publish exactly N artifacts from one OpenClaw response."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-int-fanout-fixed",
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
                                "text": '[{"draft":"A"},{"draft":"B"},{"draft":"C"}]',
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
        OpenClawPipelineDraft,
        fan_out=3,
    )

    await flock.publish(OpenClawPipelineInput(feature="fan-out fixed"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]

    assert len(drafts) == 3
    assert [d.payload["draft"] for d in drafts] == ["A", "B", "C"]


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_dynamic_fan_out_remains_pipeline_compatible() -> None:
    """Dynamic fan-out outputs should flow to downstream native agents unchanged."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-int-fanout-dynamic",
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
                                "text": (
                                    '[{"draft":"One"},{"draft":"Two"},'
                                    '{"draft":"Three"},{"draft":"Four"}]'
                                ),
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
        OpenClawPipelineDraft,
        fan_out=(3, 5),
    )

    (
        flock.agent("native-reviewer")
        .consumes(OpenClawPipelineDraft)
        .publishes(OpenClawPipelineReview)
        .with_engines(NativeReviewEngine())
    )

    await flock.publish(OpenClawPipelineInput(feature="fan-out dynamic"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]
    reviews = [a for a in artifacts if a.type == "OpenClawPipelineReview"]

    assert len(drafts) == 4
    assert len(reviews) == 4
    assert {r.payload["source"] for r in reviews} == {"native-reviewer"}


@pytest.mark.asyncio
@respx.mock
async def test_openclaw_multi_output_single_activation_publishes_multiple_types() -> (
    None
):
    """One OpenClaw activation should publish multiple output types from envelope response."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    calls = 0

    def _handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "id": "resp-int-multi-out-1",
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
                                "text": (
                                    '{"OpenClawPipelineDraft":{"draft":"multi draft"},'
                                    '"OpenClawPipelineSummary":{"summary":"multi summary"}}'
                                ),
                            }
                        ],
                    }
                ],
            },
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

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
        OpenClawPipelineDraft,
        OpenClawPipelineSummary,
    )

    await flock.publish(OpenClawPipelineInput(feature="multi-output integration"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]
    summaries = [a for a in artifacts if a.type == "OpenClawPipelineSummary"]

    assert calls == 1
    assert len(drafts) == 1
    assert len(summaries) == 1
    assert drafts[0].payload == {"draft": "multi draft"}
    assert summaries[0].payload == {"summary": "multi summary"}
    assert drafts[0].correlation_id == summaries[0].correlation_id


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_publish_flows_to_mixed_native_and_openclaw_downstream() -> (
    None
):
    """Multi-output publish should feed both native and OpenClaw downstream consumers."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    calls = 0

    def _handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1

        if calls == 1:
            return httpx.Response(
                200,
                json={
                    "id": "resp-int-multi-mixed-1",
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
                                    "text": (
                                        '{"OpenClawPipelineDraft":{"draft":"downstream draft"},'
                                        '"OpenClawPipelineSummary":{"summary":"downstream summary"}}'
                                    ),
                                }
                            ],
                        }
                    ],
                },
            )

        return httpx.Response(
            200,
            json={
                "id": "resp-int-multi-mixed-2",
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
                                "text": '{"verdict":"summary approved","source":"codie-summary-reviewer"}',
                            }
                        ],
                    }
                ],
            },
        )

    respx.post("http://localhost:19789/v1/responses").mock(side_effect=_handler)

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

    flock.openclaw_agent("codie", name="codie-multi-producer").consumes(
        OpenClawPipelineInput
    ).publishes(
        OpenClawPipelineDraft,
        OpenClawPipelineSummary,
    )

    (
        flock.agent("native-reviewer")
        .consumes(OpenClawPipelineDraft)
        .publishes(OpenClawPipelineReview)
        .with_engines(NativeReviewEngine())
    )

    flock.openclaw_agent("codie", name="codie-summary-reviewer").consumes(
        OpenClawPipelineSummary
    ).publishes(OpenClawPipelineReview)

    await flock.publish(OpenClawPipelineInput(feature="mixed downstream multi-output"))
    await flock.run_until_idle()

    artifacts = await flock.store.list()
    drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]
    summaries = [a for a in artifacts if a.type == "OpenClawPipelineSummary"]
    reviews = [a for a in artifacts if a.type == "OpenClawPipelineReview"]

    assert calls == 2
    assert len(drafts) == 1
    assert len(summaries) == 1
    assert len(reviews) == 2
    assert {r.payload["source"] for r in reviews} == {
        "native-reviewer",
        "codie-summary-reviewer",
    }


@pytest.mark.asyncio
@respx.mock
async def test_multi_output_invalid_envelope_surfaces_contract_failure() -> None:
    """Invalid multi-output envelope should fail with surfaced contract error."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    respx.post("http://localhost:19789/v1/responses").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "resp-int-multi-invalid-1",
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
                                "text": (
                                    '{"OpenClawPipelineDraft":{"draft":"ok"},'
                                    '"UnknownSlot":{"value":"boom"}}'
                                ),
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
        ),
        no_output=True,
    )

    agent = (
        flock.openclaw_agent("codie")
        .consumes(OpenClawPipelineInput)
        .publishes(OpenClawPipelineDraft, OpenClawPipelineSummary)
        .agent
    )

    with pytest.raises(RuntimeError, match="unknown slot|envelope|parse"):
        await flock.invoke(
            agent,
            OpenClawPipelineInput(feature="invalid envelope contract"),
            publish_outputs=False,
        )


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
        yield SSEFrame(
            event="response.output_text.delta", data='{"delta":"{\\"draft\\":\\"stre"}'
        )
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

        builder = (
            flock.openclaw_agent("codie")
            .consumes(OpenClawPipelineInput)
            .publishes(OpenClawPipelineDraft)
        )
        builder.agent.engines[0].stream = True

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
async def test_openclaw_cli_streaming_releases_counter_without_live_state_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI streaming should release counter; static final table is handled by OutputUtility."""
    OpenClawConfig, GatewayConfig = _openclaw_config_classes()

    from flock.core import Agent

    original_broadcast = Agent._websocket_broadcast_global
    original_counter = Agent._streaming_counter
    Agent._websocket_broadcast_global = None
    Agent._streaming_counter = 0

    seen: dict[str, object] = {}

    async def _fake_streaming_attempt(self, **kwargs):
        seen["is_dashboard_stream"] = kwargs.get("is_dashboard_stream")
        seen["counter_during_attempt"] = Agent._streaming_counter
        seen["ctx"] = kwargs.get("ctx")
        seen["engine_no_output"] = getattr(self, "no_output", None)
        return {"draft": "streamed-cli"}

    monkeypatch.setattr(
        OpenClawEngine,
        "_execute_streaming_attempt",
        _fake_streaming_attempt,
    )

    original_on_post_evaluate = OutputUtilityComponent.on_post_evaluate

    async def _capture_post_evaluate(self, agent, ctx, inputs, result):
        seen["stream_live_before_output_utility"] = bool(
            ctx.get_variable("_flock_stream_live_active", False)
        )
        return await original_on_post_evaluate(self, agent, ctx, inputs, result)

    monkeypatch.setattr(
        OutputUtilityComponent,
        "on_post_evaluate",
        _capture_post_evaluate,
    )

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
            )
        )

        builder = (
            flock.openclaw_agent("codie")
            .consumes(OpenClawPipelineInput)
            .publishes(OpenClawPipelineDraft)
        )
        builder.agent.engines[0].stream = True
        builder.agent.engines[0].no_output = False

        await flock.publish(
            OpenClawPipelineInput(feature="cli streaming state contract")
        )
        await flock.run_until_idle()

        artifacts = await flock.store.list()
        drafts = [a for a in artifacts if a.type == "OpenClawPipelineDraft"]

        assert len(drafts) == 1
        assert drafts[0].payload == {"draft": "streamed-cli"}
        assert seen["is_dashboard_stream"] is False
        assert seen["counter_during_attempt"] == 1
        assert seen["engine_no_output"] is False

        ctx = seen.get("ctx")
        assert ctx is not None
        assert seen["stream_live_before_output_utility"] is False
        assert Agent._streaming_counter == 0
    finally:
        Agent._websocket_broadcast_global = original_broadcast
        Agent._streaming_counter = original_counter


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

        builder = (
            flock.openclaw_agent("codie")
            .consumes(OpenClawPipelineInput)
            .publishes(OpenClawPipelineDraft)
        )
        builder.agent.engines[0].stream = True

        await flock.publish(
            OpenClawPipelineInput(feature="stream fallback integration")
        )
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
