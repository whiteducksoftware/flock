"""
OpenClaw Integration: Mixed Pipeline (OpenClaw + Native Agents)

This example shows the real power of OpenClaw integration: mixing OpenClaw-backed
agents with standard LLM agents in the same workflow. The blackboard doesn't care
where the compute comes from — it's all just typed artifacts.

Pipeline:
    Spec → [OpenClaw: Codex writes code] → Implementation → [LLM: reviews it] → Review

🔧 SETUP:
    1) Enable gateway.http.endpoints.responses.enabled=true in OpenClaw config
    2) export OPENCLAW_CODEX_URL=http://localhost:19789
    3) export OPENCLAW_CODEX_TOKEN=your-token
    4) export DEFAULT_MODEL=openai/gpt-4.1  (for the native reviewer agent)

Run:
    uv run python examples/11-openclaw/02_mixed_pipeline.py

Dashboard streaming note:
    With a Flock dashboard/WebSocket sink active, OpenClaw streaming is enabled automatically.
    No per-agent streaming config is required in this example.
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, GatewayConfig, OpenClawConfig
from flock.registry import flock_type


@flock_type
class FeatureSpec(BaseModel):
    feature: str = Field(description="Feature to implement")
    language: str = Field(default="Python", description="Programming language")
    requirements: list[str] = Field(
        description="Key requirements for the implementation"
    )


@flock_type
class Implementation(BaseModel):
    code: str = Field(description="The implemented code")
    explanation: str = Field(description="Brief explanation of the approach")
    files_changed: list[str] = Field(description="List of files that would be modified")


@flock_type
class CodeReview(BaseModel):
    approved: bool = Field(description="Whether the code is approved")
    score: int = Field(ge=1, le=10, description="Quality score from 1-10")
    feedback: list[str] = Field(description="Review feedback items")
    suggestions: list[str] = Field(description="Improvement suggestions")


# ============================================================================
# Setup: One OpenClaw gateway + standard LLM model
# ============================================================================
flock = Flock(
    openclaw=OpenClawConfig(
        gateways={
            "codex": GatewayConfig(
                url="http://localhost:19789",
                token_env="OPENCLAW_CODEX_TOKEN",
            )
        }
    )
)


# ============================================================================
# Mixed pipeline: OpenClaw agent → Native LLM agent
# ============================================================================
# Codex (OpenClaw) writes the code — can use tools, search, file access
implementer = (
    flock.openclaw_agent("codex")
    .description("Senior developer who implements features from specs")
    .consumes(FeatureSpec)
    .publishes(Implementation)
)

# Standard LLM agent reviews — pure structured output, no tools needed
reviewer = (
    flock.agent("reviewer")
    .description(
        "Code reviewer who evaluates implementations for quality and correctness"
    )
    .consumes(Implementation)
    .publishes(CodeReview)
)


# ============================================================================
# Run
# ============================================================================
async def main():
    spec = FeatureSpec(
        feature="Add rate limiting middleware",
        language="Python",
        requirements=[
            "Token bucket algorithm",
            "Configurable per-route limits",
            "Redis-backed for distributed deployments",
            "Return 429 with Retry-After header",
        ],
    )

    print(f"📋 Feature: {spec.feature}")
    print(f"   Language: {spec.language}")
    print(f"   Requirements: {len(spec.requirements)}")
    print()
    print(
        "🔄 Pipeline: Spec → [OpenClaw: Codex] → Implementation → [LLM: Reviewer] → CodeReview"
    )
    print()

    await flock.publish(spec)
    await flock.run_until_idle()

    reviews = await flock.store.get_by_type(CodeReview)
    if reviews:
        review = reviews[0]
        print(
            f"📝 Review: {'✅ Approved' if review.approved else '❌ Changes Requested'}"
        )
        print(f"   Score: {review.score}/10")
        print(f"   Feedback: {len(review.feedback)} items")
        for item in review.feedback[:3]:
            print(f"     - {item}")

    print(
        "\n✅ Mixed pipeline complete — OpenClaw and native agents worked together seamlessly."
    )


if __name__ == "__main__":
    asyncio.run(main())
