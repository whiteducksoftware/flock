"""
External Agents: Mixed Pipeline (Claude Code + Codex + Native LLM)

Mix external CLI agents with native Flock agents in one workflow.
The blackboard doesn't care where the compute comes from.

Pipeline:
    Spec → [Claude Code: implements] → Code → [Codex: tests] → Tests → [LLM: reviews] → Review

🔧 SETUP:
    1) claude --version
    2) codex --version
    3) export ANTHROPIC_API_KEY=...
    4) export OPENAI_API_KEY=...

Run:
    uv run python examples/12-external-agents/02_mixed_pipeline.py
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class FeatureSpec(BaseModel):
    feature: str = Field(description="Feature to implement")
    language: str = Field(default="Python")
    requirements: list[str] = Field(description="Key requirements")


@flock_type
class Implementation(BaseModel):
    code: str = Field(description="The implemented source code")
    explanation: str = Field(description="Approach explanation")
    files_changed: list[str] = Field(description="Files modified")


@flock_type
class TestSuite(BaseModel):
    test_code: str = Field(description="The test source code")
    test_count: int = Field(description="Number of test cases")
    coverage_notes: str = Field(description="What's covered and what's not")


@flock_type
class CodeReview(BaseModel):
    approved: bool = Field(description="Whether the code is approved")
    score: int = Field(ge=1, le=10, description="Quality score 1-10")
    feedback: list[str] = Field(description="Review feedback items")


# ============================================================================
# Three compute backends, one workflow
# ============================================================================
flock = Flock()

# Claude Code implements — has file access, tools, reasoning
implementer = (
    flock.agent("implementer")
    .kind("external")
    .adapter("claude_code")
    .consumes(FeatureSpec)
    .publishes(Implementation)
)

# Codex writes tests — different agent, different strengths
test_writer = (
    flock.agent("test-writer")
    .kind("external")
    .adapter("codex")
    .consumes(Implementation)
    .publishes(TestSuite)
)

# Native Flock LLM reviews — pure reasoning, no tools needed
reviewer = (
    flock.agent("reviewer")
    .description("Senior engineer reviewing implementation and tests for quality")
    .consumes(Implementation, TestSuite)
    .publishes(CodeReview)
)


async def main():
    spec = FeatureSpec(
        feature="Add WebSocket support to the API server",
        language="Python",
        requirements=[
            "Connection lifecycle management",
            "Room-based broadcasting",
            "Heartbeat/ping-pong keepalive",
        ],
    )

    print(f"📋 Feature: {spec.feature}")
    print("🔄 Spec → [Claude Code] → Code → [Codex] → Tests → [LLM] → Review\n")

    await flock.publish(spec)
    await flock.run_until_idle()

    reviews = await flock.store.get_by_type(CodeReview)
    if reviews:
        review = reviews[0]
        status = "✅ Approved" if review.approved else "❌ Changes Requested"
        print(f"📝 {status} ({review.score}/10)")
        for fb in review.feedback[:3]:
            print(f"   → {fb}")

    print("\n✅ Three backends, one workflow. External agents are just agents.")


if __name__ == "__main__":
    asyncio.run(main())
