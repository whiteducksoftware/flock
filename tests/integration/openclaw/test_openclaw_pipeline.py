"""Integration tests for OpenClaw + native mixed pipeline behavior (Phase 1)."""

from __future__ import annotations

import httpx
import pytest
import respx
from pydantic import BaseModel, Field

from flock import Flock
from flock.components.agent import EngineComponent
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

    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-int-1",
                "result": '{"draft":"Implement endpoint adapter"}',
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

    respx.post("http://localhost:19789/api/sessions/spawn").mock(
        return_value=httpx.Response(
            200,
            json={
                "ok": True,
                "sessionKey": "iso-int-2",
                "result": '{"draft":"Add retry policy docs"}',
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
