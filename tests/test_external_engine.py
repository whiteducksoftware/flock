"""Tests for ExternalEngineComponent.

Covers prompt composition, JSON parsing/validation, session resume + fallback,
side-effect-only agents (empty output_group), error propagation, and
integration through the Agent._run_engines path.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from flock.integrations.external.engine import (
    ExternalEngineComponent,
    ExternalEngineExecutionError,
)
from flock.integrations.external.models import (
    AgentOutcome,
    ExternalSessionStore,
    SpawnConfig,
    SpawnResult,
)
from flock.registry import type_registry
from flock.utils.runtime import Context, EvalInputs, EvalResult


# ---------------------------------------------------------------------------
# Test types
# ---------------------------------------------------------------------------


class _Question(BaseModel):
    text: str
    language: str = "python"


class _Answer(BaseModel):
    answer: str
    confidence: str = "high"


class _Tagline(BaseModel):
    line: str


# Register types so type_registry.name_for() works inside EvalResult.from_objects
type_registry.register(_Question)
type_registry.register(_Answer)
type_registry.register(_Tagline)


# ---------------------------------------------------------------------------
# Mock adapter
# ---------------------------------------------------------------------------


class _FakeProcess:
    def __init__(self, pid: int = 42) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def kill(self) -> None:
        self.returncode = -9


class _MockAdapter:
    """Adapter whose monitor() returns a pre-configured outcome.

    The outcome can be set per-test via ``set_outcome(...)``. ``spawn_calls``
    records every SpawnConfig the engine sent in.
    """

    def __init__(self, outcome: AgentOutcome | None = None) -> None:
        self.spawn_calls: list[SpawnConfig] = []
        self.terminate_calls: list[SpawnResult] = []
        self._outcome = outcome
        self._spawn_error: Exception | None = None
        self._monitor_error: Exception | None = None
        self._counter = 0

    def set_outcome(self, outcome: AgentOutcome) -> None:
        self._outcome = outcome

    def set_spawn_error(self, exc: Exception) -> None:
        self._spawn_error = exc

    def set_monitor_error(self, exc: Exception) -> None:
        self._monitor_error = exc

    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        if self._spawn_error is not None:
            raise self._spawn_error
        self._counter += 1
        sid = config.session_id or f"sess-{self._counter}"
        self.spawn_calls.append(config)
        return SpawnResult(pid=1000 + self._counter, session_id=sid, process=_FakeProcess())

    async def monitor(self, result: SpawnResult) -> AgentOutcome:
        if self._monitor_error is not None:
            raise self._monitor_error
        if self._outcome is None:
            return AgentOutcome(
                success=False,
                returncode=-1,
                stdout="",
                stderr="no outcome configured",
                session_id=result.session_id,
            )
        # Carry the spawn's session_id into the outcome unless explicitly overridden.
        return AgentOutcome(
            success=self._outcome.success,
            returncode=self._outcome.returncode,
            stdout=self._outcome.stdout,
            stderr=self._outcome.stderr,
            session_id=self._outcome.session_id or result.session_id,
        )

    async def terminate(self, result: SpawnResult) -> None:
        self.terminate_calls.append(result)


# ---------------------------------------------------------------------------
# Stub Agent / OutputGroup that look the way the engine expects
# ---------------------------------------------------------------------------


@dataclass
class _StubSpec:
    type_name: str
    model: type[BaseModel]


@dataclass
class _StubOutput:
    spec: _StubSpec


@dataclass
class _StubOutputGroup:
    outputs: list[_StubOutput] = field(default_factory=list)


@dataclass
class _StubSubscription:
    type_names: list[str] = field(default_factory=list)
    session_mode: str | None = None


@dataclass
class _StubAgent:
    name: str
    description: str | None = None
    output_groups: list[_StubOutputGroup] = field(default_factory=list)
    subscriptions: list[_StubSubscription] = field(default_factory=list)


def _make_agent(
    output_types: list[type[BaseModel]] | None = None,
    *,
    description: str | None = None,
    session_mode: str | None = None,
) -> _StubAgent:
    output_types = output_types or []
    outputs = [
        _StubOutput(spec=_StubSpec(type_name=type_registry.name_for(t), model=t))
        for t in output_types
    ]
    return _StubAgent(
        name="test-agent",
        description=description,
        output_groups=[_StubOutputGroup(outputs=outputs)],
        subscriptions=[_StubSubscription(session_mode=session_mode)] if session_mode else [],
    )


def _make_inputs(payload: dict[str, Any], type_cls: type[BaseModel] = _Question) -> EvalInputs:
    from flock.core.artifacts import Artifact

    type_name = type_registry.name_for(type_cls)
    artifact = Artifact(type=type_name, payload=payload, produced_by="caller")
    return EvalInputs(artifacts=[artifact])


def _ctx() -> Context:
    return Context(task_id="t1")


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evaluate_single_output_returns_typed_artifact() -> None:
    adapter = _MockAdapter(
        AgentOutcome(
            success=True,
            returncode=0,
            stdout=json.dumps({"type": "Answer", "data": {"answer": "use a list comprehension"}}),
            stderr="",
            session_id="s-1",
        )
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer], description="Answer the question.")
    inputs = _make_inputs({"text": "How to filter a list?"})

    result = await engine.evaluate(agent, _ctx(), inputs, agent.output_groups[0])

    assert isinstance(result, EvalResult)
    assert len(result.artifacts) == 1
    assert result.artifacts[0].type == type_registry.name_for(_Answer)
    assert result.artifacts[0].payload["answer"] == "use a list comprehension"
    assert result.artifacts[0].payload["confidence"] == "high"  # default
    assert result.artifacts[0].produced_by == "test-agent"


@pytest.mark.asyncio
async def test_evaluate_accepts_bare_object_without_envelope() -> None:
    """Agent ignores envelope hint, returns a bare object — engine still parses."""
    adapter = _MockAdapter(
        AgentOutcome(
            success=True,
            returncode=0,
            stdout='{"answer": "42", "confidence": "low"}',
            stderr="",
            session_id="s-1",
        )
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    result = await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    assert result.artifacts[0].payload == {"answer": "42", "confidence": "low"}


@pytest.mark.asyncio
async def test_evaluate_strips_markdown_code_fences() -> None:
    adapter = _MockAdapter(
        AgentOutcome(
            success=True,
            returncode=0,
            stdout='```json\n{"answer": "fenced"}\n```',
            stderr="",
            session_id="s",
        )
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    result = await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])
    assert result.artifacts[0].payload["answer"] == "fenced"


@pytest.mark.asyncio
async def test_evaluate_multi_output_returns_two_artifacts() -> None:
    adapter = _MockAdapter(
        AgentOutcome(
            success=True,
            returncode=0,
            stdout=json.dumps([
                {"type": "Answer", "data": {"answer": "use map()"}},
                {"type": "Tagline", "data": {"line": "elegant"}},
            ]),
            stderr="",
            session_id="s",
        )
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer, _Tagline])
    result = await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])
    assert len(result.artifacts) == 2
    assert result.artifacts[0].payload["answer"] == "use map()"
    assert result.artifacts[1].payload["line"] == "elegant"


@pytest.mark.asyncio
async def test_evaluate_empty_output_group_returns_empty_result() -> None:
    """Side-effect-only agent: spawn happens but no artifacts produced."""
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout="ok", stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([])
    result = await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])
    assert result.artifacts == []
    assert len(adapter.spawn_calls) == 1  # spawn still happened


# ---------------------------------------------------------------------------
# Session resume
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_uses_stored_session_id_when_present() -> None:
    store = ExternalSessionStore()
    store.set("test-agent", type_registry.name_for(_Question), "session-prior")

    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="session-prior")
    )
    engine = ExternalEngineComponent(adapter=adapter, session_mode="resume", session_store=store)
    agent = _make_agent([_Answer], session_mode="resume")

    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    assert adapter.spawn_calls[0].session_id == "session-prior"
    assert adapter.spawn_calls[0].session_mode == "resume"


@pytest.mark.asyncio
async def test_resume_falls_back_to_new_when_no_stored_session() -> None:
    store = ExternalSessionStore()
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="new-sess")
    )
    engine = ExternalEngineComponent(adapter=adapter, session_mode="resume", session_store=store)
    agent = _make_agent([_Answer], session_mode="resume")

    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    # Spawn called with no session_id (falls back to new mode)
    assert adapter.spawn_calls[0].session_id is None
    assert adapter.spawn_calls[0].session_mode == "new"


@pytest.mark.asyncio
async def test_session_id_stored_after_successful_run() -> None:
    store = ExternalSessionStore()
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="captured-sid")
    )
    engine = ExternalEngineComponent(adapter=adapter, session_store=store)
    agent = _make_agent([_Answer])

    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    assert store.get("test-agent", type_registry.name_for(_Question)) == "captured-sid"


@pytest.mark.asyncio
async def test_subscription_session_mode_overrides_engine_default() -> None:
    """If both engine.session_mode and subscription.session_mode are set, subscription wins."""
    store = ExternalSessionStore()
    store.set("test-agent", type_registry.name_for(_Question), "stored-sid")
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="stored-sid")
    )
    engine = ExternalEngineComponent(adapter=adapter, session_mode="new", session_store=store)
    agent = _make_agent([_Answer], session_mode="resume")

    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    assert adapter.spawn_calls[0].session_id == "stored-sid"


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_adapter_configured_raises() -> None:
    engine = ExternalEngineComponent.__new__(ExternalEngineComponent)
    # Bypass __init__; force adapter=None with minimal init.
    EngineParent = ExternalEngineComponent.__mro__[1]
    EngineParent.__init__(engine, adapter=None, working_dir=".", spawn_timeout=10.0,
                          session_mode=None, additional_env={})
    engine._session_store = ExternalSessionStore()

    agent = _make_agent([_Answer])
    with pytest.raises(ExternalEngineExecutionError, match="no adapter"):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_non_zero_exit_raises_execution_error() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=False, returncode=2, stdout="", stderr="boom", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    with pytest.raises(ExternalEngineExecutionError, match="exited with code 2"):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_invalid_json_raises_execution_error() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout="not json at all", stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    with pytest.raises(ExternalEngineExecutionError, match="non-JSON output"):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_schema_mismatch_raises_execution_error() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"unrelated": "field"}', stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    with pytest.raises(ExternalEngineExecutionError, match="does not match _Answer"):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_empty_output_raises() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout="   ", stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    with pytest.raises(ExternalEngineExecutionError, match="no output"):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_wrong_item_count_raises() -> None:
    adapter = _MockAdapter(
        AgentOutcome(
            success=True,
            returncode=0,
            stdout=json.dumps([{"answer": "a"}, {"answer": "b"}]),
            stderr="",
            session_id="s",
        )
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])  # expects ONE; gets two
    with pytest.raises(ExternalEngineExecutionError, match="returned 2 item"):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_adapter_spawn_error_propagates() -> None:
    adapter = _MockAdapter()
    adapter.set_spawn_error(FileNotFoundError("CLI missing"))
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    with pytest.raises(FileNotFoundError):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])


@pytest.mark.asyncio
async def test_monitor_error_triggers_terminate_then_propagates() -> None:
    adapter = _MockAdapter()
    adapter.set_monitor_error(asyncio.TimeoutError())
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    with pytest.raises(asyncio.TimeoutError):
        await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])
    # Verify cleanup attempted
    assert len(adapter.terminate_calls) == 1


# ---------------------------------------------------------------------------
# Prompt composition
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_includes_input_artifact_payload() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer], description="Be helpful.")
    inputs = _make_inputs({"text": "what is 2+2?", "language": "math"})

    await engine.evaluate(agent, _ctx(), inputs, agent.output_groups[0])

    prompt = adapter.spawn_calls[0].prompt
    assert "Be helpful." in prompt
    assert "what is 2+2?" in prompt
    assert "math" in prompt


@pytest.mark.asyncio
async def test_prompt_includes_output_schema() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    prompt = adapter.spawn_calls[0].prompt
    # The schema for _Answer should include its properties
    assert "answer" in prompt
    assert "confidence" in prompt
    assert "ONLY valid JSON" in prompt


@pytest.mark.asyncio
async def test_prompt_for_empty_output_group_omits_schema_section() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout="ok", stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([], description="Just do the side effect.")
    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    prompt = adapter.spawn_calls[0].prompt
    assert "Expected output" not in prompt
    assert "Just do the side effect" in prompt


# ---------------------------------------------------------------------------
# Session store (async variant)
# ---------------------------------------------------------------------------


class _AsyncStore:
    """Mimics the async signature of SQLiteExternalSessionStore."""

    def __init__(self) -> None:
        self._sessions: dict[tuple[str, str], str] = {}

    async def get(self, agent_name: str, artifact_type: str) -> str | None:
        return self._sessions.get((agent_name, artifact_type))

    async def set(self, agent_name: str, artifact_type: str, session_id: str) -> None:
        self._sessions[(agent_name, artifact_type)] = session_id

    async def clear(self, agent_name: str | None = None) -> None:
        self._sessions.clear()


@pytest.mark.asyncio
async def test_async_session_store_is_awaited() -> None:
    store = _AsyncStore()
    await store.set("test-agent", type_registry.name_for(_Question), "async-stored-sid")

    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="async-stored-sid")
    )
    engine = ExternalEngineComponent(adapter=adapter, session_mode="resume", session_store=store)
    agent = _make_agent([_Answer], session_mode="resume")
    await engine.evaluate(agent, _ctx(), _make_inputs({"text": "?"}), agent.output_groups[0])

    assert adapter.spawn_calls[0].session_id == "async-stored-sid"


# ---------------------------------------------------------------------------
# Engine identity
# ---------------------------------------------------------------------------


def test_external_engine_is_engine_component() -> None:
    from flock.components.agent.base import EngineComponent

    engine = ExternalEngineComponent(adapter=_MockAdapter())
    assert isinstance(engine, EngineComponent)


# ---------------------------------------------------------------------------
# Trace context (Unit 8)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_includes_correlation_id_when_present() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    inputs = _make_inputs({"text": "?"})
    ctx = Context(task_id="t1", correlation_id="trace-corr-abc-123")

    await engine.evaluate(agent, ctx, inputs, agent.output_groups[0])

    prompt = adapter.spawn_calls[0].prompt
    assert "Trace context" in prompt
    assert "trace-corr-abc-123" in prompt


@pytest.mark.asyncio
async def test_prompt_includes_triggering_artifact_id_and_type() -> None:
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    inputs = _make_inputs({"text": "?"})

    await engine.evaluate(agent, _ctx(), inputs, agent.output_groups[0])

    prompt = adapter.spawn_calls[0].prompt
    artifact_id = str(inputs.artifacts[0].id)
    assert artifact_id in prompt
    assert type_registry.name_for(_Question) in prompt


@pytest.mark.asyncio
async def test_prompt_omits_trace_context_when_no_correlation_and_no_artifact_id() -> None:
    """An agent with no inputs and no correlation_id has no trace context."""
    adapter = _MockAdapter(
        AgentOutcome(success=True, returncode=0, stdout='{"answer": "x"}', stderr="", session_id="s")
    )
    engine = ExternalEngineComponent(adapter=adapter)
    agent = _make_agent([_Answer])
    inputs = EvalInputs(artifacts=[])
    ctx = Context(task_id="t1")  # no correlation_id

    await engine.evaluate(agent, ctx, inputs, agent.output_groups[0])

    prompt = adapter.spawn_calls[0].prompt
    assert "Trace context" not in prompt
