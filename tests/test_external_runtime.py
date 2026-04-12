"""Tests for ExternalAgentRuntime protocol, models, and ExternalAgentScheduler.

Uses a mock adapter with asyncio.Future-based control to test scheduler
behavior without actual subprocesses.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import aiosqlite

from flock.integrations.external.models import (
    AgentOutcome,
    ExternalSessionStore,
    SQLiteExternalSessionStore,
    SpawnConfig,
    SpawnResult,
)
from flock.storage.sqlite.schema_manager import SQLiteSchemaManager
from flock.integrations.external.runtime import ExternalAgentRuntime
from flock.integrations.external.scheduler import ExternalAgentScheduler
from flock.models.changelog import ChangelogEvent, ChangelogEventType


# ---------------------------------------------------------------------------
# Helpers: fake process and mock adapter
# ---------------------------------------------------------------------------


class FakeProcess:
    """Mimics asyncio.subprocess.Process enough for tests."""

    def __init__(self, pid: int = 42) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def send_signal(self, sig: int) -> None:
        pass

    def kill(self) -> None:
        self.returncode = -9


class MockAdapter:
    """ExternalAgentRuntime implementation controllable via futures.

    Call ``complete(outcome)`` to let monitor() return, or let it hang
    for timeout testing.
    """

    def __init__(self) -> None:
        self.spawn_calls: list[SpawnConfig] = []
        self.terminate_calls: list[SpawnResult] = []
        self._futures: dict[str, asyncio.Future[AgentOutcome]] = {}
        self._counter = 0
        self._spawn_error: Exception | None = None

    def set_spawn_error(self, exc: Exception) -> None:
        """Make the next spawn() raise an exception."""
        self._spawn_error = exc

    async def spawn(self, config: SpawnConfig) -> SpawnResult:
        if self._spawn_error is not None:
            exc = self._spawn_error
            self._spawn_error = None
            raise exc
        self._counter += 1
        session_id = config.session_id or f"sess-{self._counter}"
        result = SpawnResult(
            pid=1000 + self._counter,
            session_id=session_id,
            process=FakeProcess(pid=1000 + self._counter),
        )
        self.spawn_calls.append(config)
        # Create a future that monitor() will await.
        fut: asyncio.Future[AgentOutcome] = asyncio.get_event_loop().create_future()
        self._futures[session_id] = fut
        return result

    async def monitor(self, result: SpawnResult) -> AgentOutcome:
        fut = self._futures.get(result.session_id)
        if fut is None:
            return AgentOutcome(
                success=False, returncode=-1, stdout="", stderr="no future", session_id=result.session_id
            )
        return await fut

    async def terminate(self, result: SpawnResult) -> None:
        self.terminate_calls.append(result)
        # Resolve any pending future so monitor doesn't hang.
        fut = self._futures.pop(result.session_id, None)
        if fut and not fut.done():
            fut.set_result(
                AgentOutcome(
                    success=False,
                    returncode=-1,
                    stdout="",
                    stderr="terminated",
                    session_id=result.session_id,
                )
            )

    def complete(self, session_id: str, outcome: AgentOutcome) -> None:
        """Resolve the future for a given session so monitor() returns."""
        fut = self._futures.get(session_id)
        if fut and not fut.done():
            fut.set_result(outcome)

    def complete_next(self, success: bool = True) -> None:
        """Complete the most recent pending future."""
        for sid, fut in reversed(list(self._futures.items())):
            if not fut.done():
                fut.set_result(
                    AgentOutcome(
                        success=success,
                        returncode=0 if success else 1,
                        stdout="ok" if success else "",
                        stderr="" if success else "crash",
                        session_id=sid,
                    )
                )
                return


# Verify MockAdapter satisfies the protocol at import time.
assert isinstance(MockAdapter(), ExternalAgentRuntime)


# ---------------------------------------------------------------------------
# Helpers: minimal StreamDispatcher stub
# ---------------------------------------------------------------------------


class FakeStreamDispatcher:
    """Minimal StreamDispatcher stub for testing."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, Any] = {}

    async def subscribe(self, filters=None, queue_maxsize: int = 256) -> Any:
        @dataclass
        class _Sub:
            id: str = field(default_factory=lambda: str(uuid4()))
            queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=queue_maxsize))
            filters: Any = None

        sub = _Sub(filters=filters)
        self._subscriptions[sub.id] = sub
        return sub

    async def unsubscribe(self, subscription_id: str) -> None:
        self._subscriptions.pop(subscription_id, None)

    def inject_event(self, event: ChangelogEvent) -> None:
        """Push a serialized event to all subscriber queues."""
        serialized = event.model_dump_json()
        for sub in self._subscriptions.values():
            sub.queue.put_nowait(serialized)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_event(
    artifact_type: str = "BugReport",
    produced_by: str = "scanner",
    payload_summary: dict[str, Any] | None = None,
) -> ChangelogEvent:
    return ChangelogEvent(
        event_type=ChangelogEventType.artifact_published,
        artifact_id=uuid4(),
        artifact_type=artifact_type,
        produced_by=produced_by,
        payload_summary=payload_summary or {"title": "test"},
    )


def _make_external_agent(
    name: str = "reviewer",
    adapter_name: str = "mock",
    session_mode: str | None = "new",
    timeout: float = 5.0,
    consumes_types: list[str] | None = None,
) -> Any:
    """Create a mock Agent with agent_kind='external' and proper subscriptions."""
    from flock.core.agent import Agent
    from flock.core.subscription import Subscription
    from flock.registry import type_registry
    from pydantic import BaseModel

    # Dynamic type creation for subscription, registered with explicit names
    types = consumes_types or ["BugReport"]
    type_models = []
    for type_name in types:
        model = type(type_name, (BaseModel,), {"__annotations__": {"data": str}, "data": "test"})
        # Register with the exact name so it matches event.artifact_type
        type_registry.register(model, name=type_name)
        type_models.append(model)

    mock_orch = MagicMock()
    mock_orch.model = "test-model"
    agent = Agent(name, orchestrator=mock_orch)
    agent.agent_kind = "external"
    agent.adapter_name = adapter_name
    agent.working_dir = "/tmp/test"
    agent.spawn_timeout = timeout

    for model in type_models:
        sub = Subscription(agent_name=name, types=[model])
        if session_mode:
            sub.session_mode = session_mode
        agent.subscriptions.append(sub)

    return agent


def _make_mock_orchestrator(
    agents: list[Any] | None = None,
) -> Any:
    """Create a mock Flock with registered agents."""
    mock = MagicMock()
    mock.agents = agents or []
    return mock


# ---------------------------------------------------------------------------
# Model unit tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_spawn_config_defaults(self) -> None:
        cfg = SpawnConfig(prompt="hello", working_dir=Path("/tmp"))
        assert cfg.session_id is None
        assert cfg.session_mode == "new"
        assert cfg.timeout == 1800.0

    def test_spawn_result_fields(self) -> None:
        proc = FakeProcess(pid=99)
        r = SpawnResult(pid=99, session_id="s1", process=proc)
        assert r.pid == 99
        assert r.session_id == "s1"

    def test_agent_outcome_success(self) -> None:
        o = AgentOutcome(success=True, returncode=0, stdout="ok", stderr="", session_id="s1")
        assert o.success is True

    def test_agent_outcome_failure(self) -> None:
        o = AgentOutcome(success=False, returncode=1, stdout="", stderr="oops", session_id="s1")
        assert o.success is False
        assert o.returncode == 1


class TestExternalSessionStore:
    def test_get_set(self) -> None:
        store = ExternalSessionStore()
        assert store.get("a", "BugReport") is None
        store.set("a", "BugReport", "sess-1")
        assert store.get("a", "BugReport") == "sess-1"

    def test_clear_all(self) -> None:
        store = ExternalSessionStore()
        store.set("a", "X", "s1")
        store.set("b", "Y", "s2")
        store.clear()
        assert len(store) == 0

    def test_clear_by_agent(self) -> None:
        store = ExternalSessionStore()
        store.set("a", "X", "s1")
        store.set("a", "Y", "s2")
        store.set("b", "Z", "s3")
        store.clear("a")
        assert len(store) == 1
        assert store.get("b", "Z") == "s3"

    def test_repr(self) -> None:
        store = ExternalSessionStore()
        store.set("a", "X", "s1")
        assert "1 sessions" in repr(store)


class TestSQLiteExternalSessionStore:
    """Tests for the SQLite-backed session store."""

    @pytest.fixture
    async def sqlite_store(self, tmp_path: Path) -> SQLiteExternalSessionStore:
        """Create a SQLiteExternalSessionStore with a temporary database."""
        db_path = tmp_path / "test_sessions.db"
        conn = await aiosqlite.connect(str(db_path))
        schema_mgr = SQLiteSchemaManager()
        await schema_mgr.apply_schema(conn)
        store = SQLiteExternalSessionStore(conn)
        yield store  # type: ignore[misc]
        await conn.close()

    @pytest.mark.asyncio
    async def test_get_set(self, sqlite_store: SQLiteExternalSessionStore) -> None:
        assert await sqlite_store.get("a", "BugReport") is None
        await sqlite_store.set("a", "BugReport", "sess-1")
        assert await sqlite_store.get("a", "BugReport") == "sess-1"

    @pytest.mark.asyncio
    async def test_upsert_overwrites(
        self, sqlite_store: SQLiteExternalSessionStore
    ) -> None:
        await sqlite_store.set("a", "BugReport", "sess-1")
        await sqlite_store.set("a", "BugReport", "sess-2")
        assert await sqlite_store.get("a", "BugReport") == "sess-2"

    @pytest.mark.asyncio
    async def test_clear_all(self, sqlite_store: SQLiteExternalSessionStore) -> None:
        await sqlite_store.set("a", "X", "s1")
        await sqlite_store.set("b", "Y", "s2")
        await sqlite_store.clear()
        assert await sqlite_store.count() == 0

    @pytest.mark.asyncio
    async def test_clear_by_agent(
        self, sqlite_store: SQLiteExternalSessionStore
    ) -> None:
        await sqlite_store.set("a", "X", "s1")
        await sqlite_store.set("a", "Y", "s2")
        await sqlite_store.set("b", "Z", "s3")
        await sqlite_store.clear("a")
        assert await sqlite_store.count() == 1
        assert await sqlite_store.get("b", "Z") == "s3"

    @pytest.mark.asyncio
    async def test_persistence_across_reconnect(self, tmp_path: Path) -> None:
        """Sessions survive closing and reopening the database."""
        db_path = tmp_path / "persist.db"
        schema_mgr = SQLiteSchemaManager()

        # First connection: write a session
        conn1 = await aiosqlite.connect(str(db_path))
        await schema_mgr.apply_schema(conn1)
        store1 = SQLiteExternalSessionStore(conn1)
        await store1.set("agent-a", "PRDiff", "session-42")
        await conn1.close()

        # Second connection: read it back
        conn2 = await aiosqlite.connect(str(db_path))
        await schema_mgr.apply_schema(conn2)
        store2 = SQLiteExternalSessionStore(conn2)
        assert await store2.get("agent-a", "PRDiff") == "session-42"
        await conn2.close()

    @pytest.mark.asyncio
    async def test_repr(self, sqlite_store: SQLiteExternalSessionStore) -> None:
        assert "SQLiteExternalSessionStore" in repr(sqlite_store)


class TestRuntimeProtocol:
    def test_mock_adapter_satisfies_protocol(self) -> None:
        adapter = MockAdapter()
        assert isinstance(adapter, ExternalAgentRuntime)


# ---------------------------------------------------------------------------
# Scheduler integration tests
# ---------------------------------------------------------------------------


class TestExternalAgentScheduler:
    """Integration tests for the scheduler using mock adapter."""

    async def _make_scheduler(
        self,
        adapter: MockAdapter | None = None,
        agents: list[Any] | None = None,
    ) -> tuple[ExternalAgentScheduler, FakeStreamDispatcher, MockAdapter]:
        adapter = adapter or MockAdapter()
        dispatcher = FakeStreamDispatcher()
        agent_list = agents or [_make_external_agent()]
        orchestrator = _make_mock_orchestrator(agent_list)
        scheduler = ExternalAgentScheduler()
        scheduler.configure(
            stream_dispatcher=dispatcher,
            adapters={"mock": adapter},
        )
        await scheduler.on_initialize(orchestrator)
        return scheduler, dispatcher, adapter

    @pytest.mark.asyncio
    async def test_happy_path_spawn(self) -> None:
        """Changelog event matching subscription triggers spawn with correct config."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            event = _make_event()
            dispatcher.inject_event(event)

            # Give the listener + worker time to process.
            await asyncio.sleep(0.1)

            assert len(adapter.spawn_calls) == 1
            cfg = adapter.spawn_calls[0]
            assert cfg.working_dir == Path("/tmp/test")
            assert cfg.session_mode == "new"
            assert cfg.session_id is None

            # Complete the spawn so worker finishes.
            adapter.complete_next(success=True)
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_session_mode_new_has_no_session_id(self) -> None:
        """Session mode 'new' passes session_id=None in SpawnConfig."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)
            assert adapter.spawn_calls[0].session_id is None
            adapter.complete_next()
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_session_mode_resume_with_stored_session(self) -> None:
        """Resume mode with an existing stored session passes the session_id."""
        agent = _make_external_agent(session_mode="resume")
        scheduler, dispatcher, adapter = await self._make_scheduler(
            agents=[agent]
        )
        try:
            # Pre-seed the session store.
            scheduler.session_store.set("reviewer", "BugReport", "saved-session")

            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)

            assert len(adapter.spawn_calls) == 1
            assert adapter.spawn_calls[0].session_id == "saved-session"
            assert adapter.spawn_calls[0].session_mode == "resume"

            adapter.complete_next()
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_session_mode_resume_fallback_to_new(self) -> None:
        """Resume mode with no stored session falls back to 'new' and logs warning."""
        agent = _make_external_agent(session_mode="resume")
        scheduler, dispatcher, adapter = await self._make_scheduler(
            agents=[agent]
        )
        try:
            # Don't seed session store — should fall back.
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)

            assert len(adapter.spawn_calls) == 1
            assert adapter.spawn_calls[0].session_id is None
            assert adapter.spawn_calls[0].session_mode == "new"

            adapter.complete_next()
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_serial_queue_one_at_a_time(self) -> None:
        """Events for the same agent are processed serially (second waits)."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            # Inject two events rapidly.
            dispatcher.inject_event(_make_event())
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)

            # Only one spawn should have happened (second is queued).
            assert len(adapter.spawn_calls) == 1

            # Complete first — second should then start.
            adapter.complete_next(success=True)
            await asyncio.sleep(0.15)

            assert len(adapter.spawn_calls) == 2

            adapter.complete_next(success=True)
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_two_events_same_agent_second_waits(self) -> None:
        """Explicit edge case: second event for same agent queues behind first."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)
            assert len(adapter.spawn_calls) == 1

            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)
            # Still only 1 spawn because first hasn't completed.
            assert len(adapter.spawn_calls) == 1

            adapter.complete_next()
            await asyncio.sleep(0.15)
            assert len(adapter.spawn_calls) == 2

            adapter.complete_next()
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_timeout_triggers_terminate(self) -> None:
        """Agent exceeding timeout gets terminated."""
        agent = _make_external_agent(timeout=0.3)
        scheduler, dispatcher, adapter = await self._make_scheduler(
            agents=[agent]
        )
        try:
            dispatcher.inject_event(_make_event())
            # Don't complete — let it time out.
            await asyncio.sleep(0.6)

            assert len(adapter.terminate_calls) == 1
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_spawn_exception_logged_queue_continues(self) -> None:
        """When adapter.spawn() raises, error is logged and queue continues."""
        adapter = MockAdapter()
        adapter.set_spawn_error(RuntimeError("boom"))
        scheduler, dispatcher, _ = await self._make_scheduler(adapter=adapter)
        try:
            # First event: spawn will raise.
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)
            assert len(adapter.spawn_calls) == 0  # spawn failed before recording

            # Second event: spawn should work normally.
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)
            assert len(adapter.spawn_calls) == 1

            adapter.complete_next()
            await asyncio.sleep(0.05)
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_agent_crash_produces_failure_outcome(self) -> None:
        """Non-zero exit code → AgentOutcome with success=False."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)

            # Complete with failure.
            adapter.complete_next(success=False)
            await asyncio.sleep(0.1)

            # The scheduler should have logged the failure but continued.
            # Verify the session store was still updated (session_id from the outcome).
            # The session_id from MockAdapter is "sess-N".
            assert scheduler.session_store.get("reviewer", "BugReport") is not None
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_no_dispatcher_skips_gracefully(self) -> None:
        """Scheduler with no dispatcher configured doesn't crash."""
        scheduler = ExternalAgentScheduler()
        # Don't call configure — no dispatcher.
        orchestrator = _make_mock_orchestrator([])
        await scheduler.on_initialize(orchestrator)
        await scheduler.on_shutdown(orchestrator)

    @pytest.mark.asyncio
    async def test_no_external_agents_skips(self) -> None:
        """Scheduler with no external agents does nothing on init."""
        dispatcher = FakeStreamDispatcher()
        scheduler = ExternalAgentScheduler()
        scheduler.configure(
            stream_dispatcher=dispatcher,
            adapters={"mock": MockAdapter()},
        )
        # No external agents registered on the orchestrator
        orchestrator = _make_mock_orchestrator([])
        await scheduler.on_initialize(orchestrator)
        await scheduler.on_shutdown(orchestrator)

    @pytest.mark.asyncio
    async def test_event_type_not_matching_skipped(self) -> None:
        """Events whose artifact_type doesn't match subscribed_types are ignored."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            # Send an event with a type the agent doesn't subscribe to.
            event = _make_event(artifact_type="UnrelatedType")
            dispatcher.inject_event(event)
            await asyncio.sleep(0.1)

            assert len(adapter.spawn_calls) == 0
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_session_persisted_after_success(self) -> None:
        """Successful outcome stores session_id for future resume."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        try:
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.1)
            adapter.complete_next(success=True)
            await asyncio.sleep(0.1)

            stored = scheduler.session_store.get("reviewer", "BugReport")
            assert stored is not None
            assert stored.startswith("sess-")
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up(self) -> None:
        """Shutdown cancels workers and clears state."""
        scheduler, dispatcher, adapter = await self._make_scheduler()
        dispatcher.inject_event(_make_event())
        await asyncio.sleep(0.1)
        # Don't complete — simulate in-progress work.
        await scheduler.on_shutdown(None)  # type: ignore[arg-type]
        # After shutdown, no workers should remain.
        assert len(scheduler._workers) == 0

    @pytest.mark.asyncio
    async def test_missing_adapter_returns_error_outcome(self) -> None:
        """Agent referencing a non-existent adapter is skipped at init."""
        agent = _make_external_agent(adapter_name="nonexistent")
        # The scheduler skips agents with unregistered adapters at init
        dispatcher = FakeStreamDispatcher()
        orchestrator = _make_mock_orchestrator([agent])
        adapter = MockAdapter()
        scheduler = ExternalAgentScheduler()
        scheduler.configure(
            stream_dispatcher=dispatcher,
            adapters={"mock": adapter},
        )
        await scheduler.on_initialize(orchestrator)
        try:
            dispatcher.inject_event(_make_event())
            await asyncio.sleep(0.15)
            # spawn should not have been called on the mock adapter.
            assert len(adapter.spawn_calls) == 0
        finally:
            await scheduler.on_shutdown(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Subscription session_mode field test
# ---------------------------------------------------------------------------


class TestSubscriptionSessionMode:
    def test_default_none(self) -> None:
        from flock.core.subscription import Subscription
        from pydantic import BaseModel

        class Dummy(BaseModel):
            x: int = 1

        sub = Subscription(types=[Dummy])
        assert sub.session_mode is None

    def test_set_to_resume(self) -> None:
        from flock.core.subscription import Subscription
        from pydantic import BaseModel

        class Dummy(BaseModel):
            x: int = 1

        sub = Subscription(types=[Dummy])
        sub.session_mode = "resume"
        assert sub.session_mode == "resume"


# ---------------------------------------------------------------------------
# Agent agent_kind field test
# ---------------------------------------------------------------------------


class TestAgentKindField:
    def test_default_internal(self) -> None:
        """Agent defaults to agent_kind='internal'."""
        from unittest.mock import MagicMock
        from flock.core.agent import Agent

        mock_orch = MagicMock()
        agent = Agent("test-agent", orchestrator=mock_orch)
        assert agent.agent_kind == "internal"

    def test_set_external(self) -> None:
        from unittest.mock import MagicMock
        from flock.core.agent import Agent

        mock_orch = MagicMock()
        agent = Agent("test-agent", orchestrator=mock_orch)
        agent.agent_kind = "external"
        assert agent.agent_kind == "external"


class TestAgentBuilderExternalAPI:
    """Test the fluent builder API for external agents."""

    def test_kind_adapter_chain(self) -> None:
        from unittest.mock import MagicMock
        from flock.core.agent import AgentBuilder

        mock_orch = MagicMock()
        mock_orch.model = "test"
        mock_orch.no_output = False
        mock_orch.register_agent = MagicMock()

        builder = AgentBuilder(mock_orch, "reviewer")
        result = builder.kind("external").adapter("claude_code")
        assert result is builder  # fluent
        assert builder.agent.agent_kind == "external"
        assert builder.agent.adapter_name == "claude_code"

    def test_working_dir_and_timeout(self) -> None:
        from unittest.mock import MagicMock
        from flock.core.agent import AgentBuilder

        mock_orch = MagicMock()
        mock_orch.model = "test"
        mock_orch.no_output = False
        mock_orch.register_agent = MagicMock()

        builder = AgentBuilder(mock_orch, "reviewer")
        builder.kind("external").adapter("claude_code").working_dir("/repos/flock").spawn_timeout(60.0)
        assert builder.agent.working_dir == "/repos/flock"
        assert builder.agent.spawn_timeout == 60.0

    def test_session_mode_propagates_to_subscriptions(self) -> None:
        from unittest.mock import MagicMock
        from pydantic import BaseModel
        from flock.core.agent import AgentBuilder

        class TestType(BaseModel):
            x: int = 1

        mock_orch = MagicMock()
        mock_orch.model = "test"
        mock_orch.no_output = False
        mock_orch.register_agent = MagicMock()

        builder = AgentBuilder(mock_orch, "reviewer")
        builder.kind("external").adapter("claude_code").consumes(TestType).session_mode("resume")
        assert builder.agent.subscriptions[0].session_mode == "resume"

    def test_session_mode_before_consumes(self) -> None:
        """session_mode set before consumes is propagated to later subscriptions."""
        from unittest.mock import MagicMock
        from pydantic import BaseModel
        from flock.core.agent import AgentBuilder

        class TestType2(BaseModel):
            x: int = 1

        mock_orch = MagicMock()
        mock_orch.model = "test"
        mock_orch.no_output = False
        mock_orch.register_agent = MagicMock()

        builder = AgentBuilder(mock_orch, "reviewer")
        builder.kind("external").adapter("claude_code").session_mode("resume").consumes(TestType2)
        assert builder.agent.subscriptions[0].session_mode == "resume"
