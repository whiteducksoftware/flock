"""Tests for Engine Context Fetching via Provider - Phase 5.

This test suite verifies that engines use the Context Provider security boundary
instead of direct store access (ctx.board.list()).

Phase 5 fixes the vulnerable pattern where engines could:
- Access ALL artifacts via ctx.board.list() (no filtering!)
- Bypass visibility enforcement entirely
- See artifacts they shouldn't have access to

The secure pattern:
- Engine calls ctx.provider (injected by orchestrator)
- Provider enforces visibility filtering
- Engine only sees artifacts it's allowed to see
"""

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, Mock

from flock.components import EngineComponent
from flock.visibility import PublicVisibility, PrivateVisibility, AgentIdentity
from flock.artifacts import Artifact
from flock.context_provider import ContextProvider, ContextRequest, DefaultContextProvider
from flock.store import FilterConfig


class MockContext:
    """Mock Context with provider injected (Phase 7 will add this)."""

    def __init__(self, provider: Any, correlation_id: Any, store: Any):
        self.provider = provider
        self.correlation_id = correlation_id
        self.store = store


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str, labels: set[str] | None = None, tenant_id: str | None = None):
        self.name = name
        self.labels = labels or set()
        self.tenant_id = tenant_id

    @property
    def identity(self) -> AgentIdentity:
        return AgentIdentity(name=self.name, labels=self.labels, tenant_id=self.tenant_id)


class MockStore:
    """Mock blackboard store for testing."""

    def __init__(self, artifacts: list[Artifact]):
        self.artifacts = artifacts

    async def query_artifacts(
        self, filters: FilterConfig | None = None, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Artifact], int]:
        """Mock query that supports full FilterConfig filtering."""
        results = self.artifacts

        if filters:
            # Filter by correlation_id
            if filters.correlation_id:
                results = [a for a in results if str(a.correlation_id) == filters.correlation_id]

            # Filter by type_names
            if filters.type_names:
                results = [a for a in results if a.type in filters.type_names]

            # Filter by tags (artifact must have at least one of the filter tags)
            if filters.tags:
                results = [a for a in results if a.tags and filters.tags.intersection(a.tags)]

            # Filter by produced_by
            if filters.produced_by:
                results = [a for a in results if a.produced_by in filters.produced_by]

        # Apply limit
        if limit > 0:
            results = results[:limit]

        return results, len(results)


class TestEngineComponent(EngineComponent):
    """Concrete engine component for testing."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        """Minimal implementation for testing."""
        return Mock()


@pytest.mark.asyncio
class TestEngineUsesProvider:
    """Phase 5: Test engines use provider instead of ctx.board.list()."""

    async def test_engine_uses_provider_not_ctx_board(self):
        """SECURITY: Engine must use ctx.provider, NOT ctx.board.list().

        This is the PRIMARY FIX for Vulnerability #1 (READ BYPASS) at the engine level.

        Old (INSECURE):
            all_artifacts = await ctx.board.list()  # Sees EVERYTHING!

        New (SECURE):
            provider = ctx.provider
            context = await provider(request)  # Visibility enforced!
        """
        correlation = uuid4()

        # Create artifacts with different visibility
        public_artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Public task"},
            produced_by="system",
            correlation_id=correlation,
            visibility=PublicVisibility(),
            created_at=datetime.now(timezone.utc),
        )

        private_artifact = Artifact(
            id=uuid4(),
            type="Secret",
            payload={"api_key": "sk-secret123"},
            produced_by="admin",
            correlation_id=correlation,
            visibility=PrivateVisibility(agents={"admin"}),  # Only admin can see
            created_at=datetime.now(timezone.utc),
        )

        store = MockStore([public_artifact, private_artifact])
        agent = MockAgent("untrusted-agent")  # NOT in allowlist

        # Create provider (injected by orchestrator in Phase 7)
        provider = DefaultContextProvider()

        # Create context with provider
        ctx = MockContext(provider=provider, correlation_id=correlation, store=store)

        # Create engine and fetch context (pass agent for visibility checks)
        engine = TestEngineComponent()
        context = await engine.fetch_conversation_context(ctx, agent=agent)

        # SECURITY: Engine should only see public artifact (private filtered by provider)
        assert len(context) == 1
        assert context[0]["type"] == "Task"
        assert context[0]["payload"]["title"] == "Public task"

        # SECURITY: Private artifact must NOT be visible
        assert not any(item["type"] == "Secret" for item in context)

    async def test_engine_respects_visibility_enforcement(self):
        """SECURITY: Engine must respect provider's visibility filtering.

        Even if engine tries to access all artifacts, provider filters them.
        This prevents agents from bypassing security.
        """
        correlation = uuid4()

        # Create private artifact
        secret = Artifact(
            id=uuid4(),
            type="Secret",
            payload={"password": "hunter2"},
            produced_by="admin",
            correlation_id=correlation,
            visibility=PrivateVisibility(agents={"admin"}),
            created_at=datetime.now(timezone.utc),
        )

        store = MockStore([secret])
        untrusted_agent = MockAgent("hacker")  # NOT in allowlist

        provider = DefaultContextProvider()
        ctx = MockContext(provider=provider, correlation_id=correlation, store=store)

        engine = TestEngineComponent()
        context = await engine.fetch_conversation_context(ctx, agent=untrusted_agent)

        # Hacker should see NOTHING
        assert len(context) == 0, "Untrusted agent must NOT see private artifacts"

    async def test_engine_filters_by_correlation_id(self):
        """Engine must only see artifacts from its workflow (correlation_id)."""
        correlation_a = uuid4()
        correlation_b = uuid4()

        # Artifacts from different workflows
        artifact_a = Artifact(
            id=uuid4(),
            type="Task",
            payload={"workflow": "A"},
            produced_by="system",
            correlation_id=correlation_a,
            visibility=PublicVisibility(),
            created_at=datetime.now(timezone.utc),
        )

        artifact_b = Artifact(
            id=uuid4(),
            type="Task",
            payload={"workflow": "B"},
            produced_by="system",
            correlation_id=correlation_b,
            visibility=PublicVisibility(),
            created_at=datetime.now(timezone.utc),
        )

        store = MockStore([artifact_a, artifact_b])
        agent = MockAgent("agent-1")

        provider = DefaultContextProvider()
        ctx = MockContext(provider=provider, correlation_id=correlation_a, store=store)

        engine = TestEngineComponent()
        context = await engine.fetch_conversation_context(ctx, agent=agent)

        # Should only see artifacts from workflow A
        assert len(context) == 1
        assert context[0]["payload"]["workflow"] == "A"

        # Artifact from workflow B must NOT be visible
        assert not any(item["payload"]["workflow"] == "B" for item in context)

    async def test_engine_respects_context_exclude_types(self):
        """Engine must exclude artifact types specified in context_exclude_types."""
        correlation = uuid4()

        task_artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Do something"},
            produced_by="system",
            correlation_id=correlation,
            visibility=PublicVisibility(),
            created_at=datetime.now(timezone.utc),
        )

        log_artifact = Artifact(
            id=uuid4(),
            type="Log",
            payload={"message": "Debug info"},
            produced_by="system",
            correlation_id=correlation,
            visibility=PublicVisibility(),
            created_at=datetime.now(timezone.utc),
        )

        store = MockStore([task_artifact, log_artifact])
        agent = MockAgent("worker")

        provider = DefaultContextProvider()
        ctx = MockContext(provider=provider, correlation_id=correlation, store=store)

        # Create engine that excludes "Log" type
        engine = TestEngineComponent(context_exclude_types={"Log"})
        context = await engine.fetch_conversation_context(ctx, agent=agent)

        # Should only see Task (Log excluded)
        assert len(context) == 1
        assert context[0]["type"] == "Task"
        assert not any(item["type"] == "Log" for item in context)

    async def test_engine_respects_context_max_artifacts(self):
        """Engine must respect context_max_artifacts limit."""
        correlation = uuid4()

        # Create 5 artifacts
        artifacts = [
            Artifact(
                id=uuid4(),
                type="Task",
                payload={"title": f"Task {i}"},
                produced_by="system",
                correlation_id=correlation,
                visibility=PublicVisibility(),
                created_at=datetime(2025, 1, 1, hour=i, tzinfo=timezone.utc),  # Different times for ordering
            )
            for i in range(5)
        ]

        store = MockStore(artifacts)
        agent = MockAgent("worker")

        provider = DefaultContextProvider()
        ctx = MockContext(provider=provider, correlation_id=correlation, store=store)

        # Create engine with max_artifacts=2 (should get last 2)
        engine = TestEngineComponent(context_max_artifacts=2)
        context = await engine.fetch_conversation_context(ctx, agent=agent)

        # Should only return last 2 artifacts (most recent)
        assert len(context) == 2
        assert context[0]["payload"]["title"] == "Task 3"  # Second-to-last
        assert context[1]["payload"]["title"] == "Task 4"  # Last

    async def test_engine_works_with_custom_provider(self):
        """Engine must work with custom provider implementations."""
        from flock.store import FilterConfig
        from flock.context_provider import FilteredContextProvider

        correlation = uuid4()

        # Create artifacts with different tags
        important_artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Critical bug"},
            produced_by="system",
            correlation_id=correlation,
            visibility=PublicVisibility(),
            tags={"important", "bug"},
            created_at=datetime.now(timezone.utc),
        )

        normal_artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Normal task"},
            produced_by="system",
            correlation_id=correlation,
            visibility=PublicVisibility(),
            tags={"feature"},
            created_at=datetime.now(timezone.utc),
        )

        store = MockStore([important_artifact, normal_artifact])
        agent = MockAgent("worker")

        # Use FilteredContextProvider with tag filter
        provider = FilteredContextProvider(FilterConfig(tags={"important"}))
        ctx = MockContext(provider=provider, correlation_id=correlation, store=store)

        engine = TestEngineComponent()
        context = await engine.fetch_conversation_context(ctx, agent=agent)

        # Should only see artifact with "important" tag
        assert len(context) == 1
        assert context[0]["payload"]["title"] == "Critical bug"

    async def test_engine_returns_correct_format(self):
        """Engine must return context in the expected format."""
        correlation = uuid4()

        artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Do something"},
            produced_by="planner",
            correlation_id=correlation,
            visibility=PublicVisibility(),
            created_at=datetime.now(timezone.utc),
        )

        store = MockStore([artifact])
        agent = MockAgent("worker")

        provider = DefaultContextProvider()
        ctx = MockContext(provider=provider, correlation_id=correlation, store=store)

        engine = TestEngineComponent()
        context = await engine.fetch_conversation_context(ctx, agent=agent)

        # Verify format
        assert isinstance(context, list)
        assert len(context) == 1
        assert isinstance(context[0], dict)

        # Verify required fields
        item = context[0]
        assert item["type"] == "Task"
        assert item["payload"] == {"title": "Do something"}
        assert item["produced_by"] == "planner"
        assert "event_number" in item  # Engine adds this field
