"""End-to-end integration tests for the engine-based external-agent path.

These exercise the full pipeline: declare an external agent on Flock,
publish an artifact, the auto-attached ExternalEngineComponent drives
a mock subprocess, returns typed Pydantic output, and downstream
internal agents pick up the cascade.

Complements tests/integration/test_meta_orchestrator_e2e.py (which
covers the standalone changelog/auth/SSE surface).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from pydantic import BaseModel, Field

from flock import Flock
from flock.integrations.external.engine import ExternalEngineComponent
from flock.integrations.external.models import (
    AgentOutcome,
    SpawnConfig,
    SpawnResult,
)
from flock.registry import flock_type, type_registry


# ---------------------------------------------------------------------------
# Test types
# ---------------------------------------------------------------------------


@flock_type
class _Question(BaseModel):
    text: str


@flock_type
class _Answer(BaseModel):
    answer: str
    confidence: str = "high"


@flock_type
class _SecurityReview(BaseModel):
    verdict: str
    issues: list[str] = Field(default_factory=list)


@flock_type
class _PerformanceReview(BaseModel):
    verdict: str
    suggestions: list[str] = Field(default_factory=list)


@flock_type
class _PRDiff(BaseModel):
    repo: str
    pr_number: int


# ---------------------------------------------------------------------------
# Mock adapter (returns canned JSON)
# ---------------------------------------------------------------------------


class _FakeProcess:
    def __init__(self, pid: int = 99999) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def kill(self) -> None:
        self.returncode = -9


class _MockAdapter:
    """Adapter that returns a pre-configured JSON outcome."""

    def __init__(self, *, stdout: str, session_id: str = "mock-session") -> None:
        self.stdout = stdout
        self.session_id = session_id
        self.spawn_calls: list[SpawnConfig] = []
        self._counter = 0

    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        self._counter += 1
        self.spawn_calls.append(config)
        return SpawnResult(
            pid=99999 + self._counter,
            session_id=config.session_id or self.session_id,
            process=_FakeProcess(pid=99999 + self._counter),
        )

    async def monitor(self, result: SpawnResult) -> AgentOutcome:
        return AgentOutcome(
            success=True,
            returncode=0,
            stdout=self.stdout,
            stderr="",
            session_id=result.session_id,
        )

    async def terminate(self, result: SpawnResult) -> None:
        pass


# ---------------------------------------------------------------------------
# SC1: external agent → cascade to internal agent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_agent_cascades_to_downstream_internal_agent() -> None:
    """SC1: publish A → external engine produces B → B is in the store."""
    adapter = _MockAdapter(
        stdout=json.dumps({"answer": "use list comprehensions", "confidence": "high"})
    )

    flock = Flock()

    (flock.agent("answerer")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
        .with_engines(ExternalEngineComponent(adapter=adapter)))

    await flock.publish(_Question(text="how to filter a list?"))
    await flock.run_until_idle()

    # The external engine spawned and produced an Answer
    assert len(adapter.spawn_calls) == 1
    artifacts, _ = await flock.store.query_artifacts(limit=100)
    answers = [a for a in artifacts if a.type == type_registry.name_for(_Answer)]
    assert len(answers) == 1
    assert answers[0].payload["answer"] == "use list comprehensions"


@pytest.mark.asyncio
async def test_external_agent_prompt_carries_input_payload() -> None:
    adapter = _MockAdapter(stdout=json.dumps({"answer": "ok"}))

    flock = Flock()
    (flock.agent("a")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
        .description("Be concise.")
        .with_engines(ExternalEngineComponent(adapter=adapter)))

    await flock.publish(_Question(text="what is recursion?"))
    await flock.run_until_idle()

    prompt = adapter.spawn_calls[0].prompt
    assert "what is recursion?" in prompt
    assert "Be concise." in prompt
    # Trace context (Unit 8)
    assert "Trace context" in prompt


# ---------------------------------------------------------------------------
# SC2-style: multi-agent fan-out / fan-in
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_two_external_agents_fan_out_from_one_artifact() -> None:
    """Two external agents both subscribe to PRDiff and produce different reviews."""
    sec_adapter = _MockAdapter(
        stdout=json.dumps({"verdict": "changes_requested", "issues": ["sql injection"]})
    )
    perf_adapter = _MockAdapter(
        stdout=json.dumps({"verdict": "approved", "suggestions": ["use generator"]})
    )

    flock = Flock()
    (flock.agent("security")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_PRDiff)
        .publishes(_SecurityReview)
        .with_engines(ExternalEngineComponent(adapter=sec_adapter)))

    (flock.agent("performance")
        .kind("external")
        .adapter("codex")
        .working_dir(".")
        .consumes(_PRDiff)
        .publishes(_PerformanceReview)
        .with_engines(ExternalEngineComponent(adapter=perf_adapter)))

    await flock.publish(_PRDiff(repo="x", pr_number=1))
    await flock.run_until_idle()

    artifacts, _ = await flock.store.query_artifacts(limit=100)
    sec = [a for a in artifacts if a.type == type_registry.name_for(_SecurityReview)]
    perf = [a for a in artifacts if a.type == type_registry.name_for(_PerformanceReview)]
    assert len(sec) == 1
    assert sec[0].payload["verdict"] == "changes_requested"
    assert len(perf) == 1
    assert perf[0].payload["verdict"] == "approved"


# ---------------------------------------------------------------------------
# SC3: session resume across publishes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_mode_reuses_session_across_publishes() -> None:
    adapter = _MockAdapter(
        stdout=json.dumps({"answer": "x"}), session_id="returned-sid"
    )

    flock = Flock()
    (flock.agent("a")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
        .session_mode("resume")
        .with_engines(ExternalEngineComponent(adapter=adapter)))

    # First publish: no stored session yet → falls back to new
    await flock.publish(_Question(text="first?"))
    await flock.run_until_idle()
    assert adapter.spawn_calls[0].session_id is None
    assert adapter.spawn_calls[0].session_mode == "new"

    # Second publish: session_id from first run was stored → resume
    await flock.publish(_Question(text="second?"))
    await flock.run_until_idle()
    assert adapter.spawn_calls[1].session_id == "returned-sid"
    assert adapter.spawn_calls[1].session_mode == "resume"


# ---------------------------------------------------------------------------
# Cascade depth fail-safe still applies (regression check)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cascade_depth_safeguard_applies_to_external_agents() -> None:
    """An external agent that publishes a type it consumes should hit the
    cascade-depth fail-safe (not infinite loop)."""

    # Adapter returns a Question payload — feeding the agent's own input back.
    adapter = _MockAdapter(stdout=json.dumps({"text": "loop"}))

    flock = Flock()

    # Agent consumes Question and publishes Question (loop) — this normally
    # would be prevented by prevent_self_trigger, so disable that to actually
    # exercise cascade depth.
    builder = (flock.agent("loopy")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Question)
        .with_engines(ExternalEngineComponent(adapter=adapter)))
    builder.agent.prevent_self_trigger = False

    await flock.publish(_Question(text="trigger"))
    await flock.run_until_idle()

    # Cascade is bounded — adapter is called many times but not infinitely.
    # The exact number depends on the depth limit (default 10).
    assert len(adapter.spawn_calls) <= 11, (
        f"Cascade should be bounded, got {len(adapter.spawn_calls)} spawns"
    )
