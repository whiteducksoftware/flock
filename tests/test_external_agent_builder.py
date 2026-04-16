"""Tests for external-agent auto-wiring on Flock orchestrator init.

Verifies that agents declared with .kind("external").adapter("...") get an
ExternalEngineComponent attached to their engines list at orchestrator
initialise time, with the correct adapter, working_dir, spawn_timeout,
and session store.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from pydantic import BaseModel

from flock import Flock
from flock.integrations.external.adapters.claude_code import ClaudeCodeRuntime
from flock.integrations.external.adapters.codex import CodexRuntime
from flock.integrations.external.engine import ExternalEngineComponent
from flock.integrations.external.models import (
    ExternalSessionStore,
    LazySQLiteExternalSessionStore,
)
from flock.registry import flock_type, type_registry


# ---------------------------------------------------------------------------
# Test types (registered via flock_type decorator)
# ---------------------------------------------------------------------------


@flock_type
class _Question(BaseModel):
    text: str


@flock_type
class _Answer(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _initialize_orchestrator(flock: Flock) -> None:
    """Drive Flock through enough of its lifecycle that components init."""
    # _run_initialize is the hook that auto-wires components.
    await flock._run_initialize()  # noqa: SLF001


# ---------------------------------------------------------------------------
# Auto-attach happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_agent_gets_engine_attached() -> None:
    flock = Flock()
    agent = (
        flock.agent("answerer")
        .kind("external")
        .adapter("claude_code")
        .working_dir("/tmp/test")
        .spawn_timeout(60.0)
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    assert agent.engines == []  # no engine yet

    await _initialize_orchestrator(flock)

    assert len(agent.engines) == 1
    engine = agent.engines[0]
    assert isinstance(engine, ExternalEngineComponent)
    assert isinstance(engine.adapter, ClaudeCodeRuntime)
    assert engine.working_dir == "/tmp/test"
    assert engine.spawn_timeout == 60.0


@pytest.mark.asyncio
async def test_external_agent_with_codex_adapter() -> None:
    flock = Flock()
    agent = (
        flock.agent("perf-reviewer")
        .kind("external")
        .adapter("codex")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    await _initialize_orchestrator(flock)

    assert len(agent.engines) == 1
    assert isinstance(agent.engines[0].adapter, CodexRuntime)


@pytest.mark.asyncio
async def test_two_external_agents_with_different_adapters() -> None:
    flock = Flock()
    a1 = (
        flock.agent("claude-reviewer")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent
    a2 = (
        flock.agent("codex-reviewer")
        .kind("external")
        .adapter("codex")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    await _initialize_orchestrator(flock)

    assert isinstance(a1.engines[0].adapter, ClaudeCodeRuntime)
    assert isinstance(a2.engines[0].adapter, CodexRuntime)


@pytest.mark.asyncio
async def test_user_supplied_engine_is_preserved() -> None:
    """If the agent already has engines, auto-wire is a no-op (idempotent)."""
    flock = Flock()
    custom_adapter = ClaudeCodeRuntime()
    custom_engine = ExternalEngineComponent(adapter=custom_adapter, working_dir="/custom")

    agent = (
        flock.agent("custom")
        .kind("external")
        .adapter("claude_code")
        .working_dir("/ignored")
        .consumes(_Question)
        .publishes(_Answer)
        .with_engines(custom_engine)
    ).agent

    await _initialize_orchestrator(flock)

    assert len(agent.engines) == 1
    assert agent.engines[0] is custom_engine
    assert agent.engines[0].working_dir == "/custom"


# ---------------------------------------------------------------------------
# Mixed internal + external
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mixed_internal_and_external_agents() -> None:
    flock = Flock()
    external_agent = (
        flock.agent("ext")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent
    # An internal agent stays without an engine until first run (DSPy is the default).
    internal_agent = (
        flock.agent("internal")
        .consumes(_Answer)
        .publishes(_Question)  # arbitrary
    ).agent

    await _initialize_orchestrator(flock)

    assert len(external_agent.engines) == 1
    assert isinstance(external_agent.engines[0], ExternalEngineComponent)
    # Internal agent's engine list stays empty until first run (defaults are
    # resolved lazily in Agent._resolve_engines).
    assert internal_agent.engines == []


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_agent_without_adapter_raises() -> None:
    flock = Flock()
    (
        flock.agent("oops")
        .kind("external")
        # no .adapter(...) call
        .consumes(_Question)
        .publishes(_Answer)
    )

    with pytest.raises(ValueError, match="no .adapter"):
        await _initialize_orchestrator(flock)


@pytest.mark.asyncio
async def test_external_agent_with_unknown_adapter_raises() -> None:
    flock = Flock()
    (
        flock.agent("oops")
        .kind("external")
        .adapter("nonsense_adapter")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    )

    with pytest.raises(ValueError, match="unknown.*adapter|nonsense_adapter"):
        await _initialize_orchestrator(flock)


# ---------------------------------------------------------------------------
# Session store defaults
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_in_memory_blackboard_uses_in_memory_session_store() -> None:
    flock = Flock()  # default = InMemoryBlackboardStore
    agent = (
        flock.agent("a")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    await _initialize_orchestrator(flock)

    assert isinstance(agent.engines[0]._session_store, ExternalSessionStore)


@pytest.mark.asyncio
async def test_sqlite_blackboard_uses_lazy_sqlite_session_store(tmp_path: Path) -> None:
    from flock.core.store import SQLiteBlackboardStore

    sqlite_store = SQLiteBlackboardStore(db_path=tmp_path / "test.db")
    flock = Flock(store=sqlite_store)
    agent = (
        flock.agent("a")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    await _initialize_orchestrator(flock)

    assert isinstance(agent.engines[0]._session_store, LazySQLiteExternalSessionStore)


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_init_is_idempotent() -> None:
    """Calling _run_initialize twice should not double-attach engines."""
    flock = Flock()
    agent = (
        flock.agent("a")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    await _initialize_orchestrator(flock)
    await _initialize_orchestrator(flock)

    assert len(agent.engines) == 1


# ---------------------------------------------------------------------------
# Spawn env propagation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spawn_env_is_propagated_to_engine() -> None:
    flock = Flock()
    agent = (
        flock.agent("a")
        .kind("external")
        .adapter("claude_code")
        .working_dir(".")
        .spawn_env({"MY_VAR": "value"})
        .consumes(_Question)
        .publishes(_Answer)
    ).agent

    await _initialize_orchestrator(flock)

    assert agent.engines[0].additional_env == {"MY_VAR": "value"}
