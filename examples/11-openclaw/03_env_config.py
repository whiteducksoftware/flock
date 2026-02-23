"""
OpenClaw Integration: Environment-Based Configuration

This example demonstrates auto-discovery of OpenClaw gateways from environment
variables — the recommended approach for production deployments.

Convention:
    OPENCLAW_<ALIAS>_URL   → Gateway URL
    OPENCLAW_<ALIAS>_TOKEN → Auth token

Multiple gateways can be configured simultaneously for multi-agent workflows.

🔧 SETUP:
    1) Enable gateway.http.endpoints.responses.enabled=true on each OpenClaw gateway
    2) export OPENCLAW_CODEX_URL=http://localhost:19789
    3) export OPENCLAW_CODEX_TOKEN=your-codex-token
    4) export OPENCLAW_CLAUDE_URL=http://localhost:18789
    5) export OPENCLAW_CLAUDE_TOKEN=your-claude-token

Run:
    uv run python examples/11-openclaw/03_env_config.py

Dashboard streaming note:
    OpenClaw agents stream automatically when a Flock dashboard/WebSocket sink is active.
    Headless usage remains unchanged.
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock, OpenClawConfig
from flock.registry import flock_type


@flock_type
class Brief(BaseModel):
    topic: str = Field(description="Topic to write about")
    tone: str = Field(default="professional", description="Writing tone")


@flock_type
class Draft(BaseModel):
    title: str = Field(description="Article title")
    body: str = Field(description="Article body text")
    word_count: int = Field(description="Approximate word count")


@flock_type
class EditedDraft(BaseModel):
    title: str = Field(description="Final title")
    body: str = Field(description="Edited body text")
    changes_made: list[str] = Field(description="List of editorial changes")


# ============================================================================
# Setup: Auto-discover gateways from environment
# ============================================================================
# This reads OPENCLAW_*_URL and OPENCLAW_*_TOKEN from environment variables.
# Fails fast with clear error if required variables are missing.
flock = Flock(openclaw=OpenClawConfig.from_env())


# ============================================================================
# Multi-agent workflow: Two different OpenClaw agents collaborate
# ============================================================================
# Codex writes the draft
writer = (
    flock.openclaw_agent("codex")
    .description("Technical writer who creates clear, engaging articles")
    .consumes(Brief)
    .publishes(Draft)
)

# Claude edits and refines
editor = (
    flock.openclaw_agent("claude", timeout=180)
    .description("Senior editor who refines drafts for clarity and impact")
    .consumes(Draft)
    .publishes(EditedDraft)
)


# ============================================================================
# Run
# ============================================================================
async def main():
    brief = Brief(
        topic="Why blackboard architecture is making a comeback in AI agent systems",
        tone="conversational but technical",
    )

    print(f"📝 Brief: {brief.topic}")
    print(f"   Tone: {brief.tone}")
    print()
    print("🔄 Pipeline: Brief → [Codex writes] → Draft → [Claude edits] → EditedDraft")
    print()

    await flock.publish(brief)
    await flock.run_until_idle()

    edits = await flock.store.get_by_type(EditedDraft)
    if edits:
        edit = edits[0]
        print(f"📰 Final: {edit.title}")
        print(f"   Changes: {len(edit.changes_made)}")
        for change in edit.changes_made[:3]:
            print(f"     - {change}")

    print("\n✅ Multi-gateway workflow complete — two OpenClaw agents, one pipeline.")


if __name__ == "__main__":
    asyncio.run(main())
