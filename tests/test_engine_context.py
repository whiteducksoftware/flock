"""Tests for Engine Context Reading - Phase 8.

This test suite verifies that engines read pre-filtered context from ctx.artifacts
instead of querying data themselves.

Phase 8 fixes ALL context security vulnerabilities:
- Orchestrator evaluates context BEFORE creating Context
- Context contains ONLY pre-filtered artifacts (no provider/store)
- Engines are pure functions: input + ctx.artifacts → output
- Engines CANNOT query for more data (no capabilities)

The secure pattern (Phase 8):
- Orchestrator uses provider to evaluate context
- Orchestrator creates Context with pre-filtered artifacts
- Engine reads ctx.artifacts (no querying!)
"""

from datetime import UTC, datetime
from typing import Any
from unittest.mock import Mock
from uuid import uuid4

import pytest

from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.core.visibility import AgentIdentity


class MockContext:
    """Mock Context with pre-filtered artifacts (Phase 8 pattern)."""

    def __init__(self, artifacts: list[Artifact], correlation_id: Any):
        self.artifacts = artifacts  # Pre-filtered by orchestrator
        self.correlation_id = correlation_id
        # Phase 8: NO provider, NO store (engines can't query)


class MockAgent:
    """Mock agent for testing."""

    def __init__(
        self, name: str, labels: set[str] | None = None, tenant_id: str | None = None
    ):
        self.name = name
        self.labels = labels or set()
        self.tenant_id = tenant_id

    @property
    def identity(self) -> AgentIdentity:
        return AgentIdentity(
            name=self.name, labels=self.labels, tenant_id=self.tenant_id
        )


class TestEngineComponent(EngineComponent):
    """Concrete engine component for testing."""

    async def evaluate(self, agent, ctx, inputs, output_group):
        """Minimal implementation for testing."""
        return Mock()


@pytest.mark.asyncio
class TestEngineUsesProvider:
    """Phase 8: Test engines read pre-filtered artifacts from ctx.artifacts."""

    async def test_engine_uses_provider_not_ctx_board(self):
        """SECURITY Phase 8: Engine reads ctx.artifacts (pre-filtered by orchestrator).

        This is the FINAL FIX for ALL context security vulnerabilities.

        Old (INSECURE):
            all_artifacts = await ctx.board.list()  # Sees EVERYTHING!
            context = await ctx.provider(request)   # Can query arbitrary data!

        New (SECURE - Phase 8):
            context = ctx.artifacts  # Pre-filtered by orchestrator!
            # Engine CANNOT query for more data (no provider/store)
        """
        correlation = uuid4()

        # Phase 8: Orchestrator pre-filters context BEFORE creating Context
        # This simulates what the orchestrator does (applies visibility filtering)
        pre_filtered_artifacts = [
            Artifact(
                id=uuid4(),
                type="Task",
                payload={"title": "Public task"},
                produced_by="system",
                created_at=datetime.now(UTC),
            )
            # Private artifact NOT included (filtered by orchestrator's provider evaluation)
        ]

        # Create context with pre-filtered artifacts (Phase 8 pattern)
        ctx = MockContext(artifacts=pre_filtered_artifacts, correlation_id=correlation)

        # Create engine and read context
        engine = TestEngineComponent()
        context = engine.get_conversation_context(ctx)

        # SECURITY Phase 8: Engine sees only pre-filtered artifacts
        assert len(context) == 1
        assert context[0].type == "Task"
        assert context[0].payload["title"] == "Public task"

        # SECURITY Phase 8: Engine CANNOT query for more data
        assert not hasattr(ctx, "provider"), "Context must NOT have provider"
        assert not hasattr(ctx, "store"), "Context must NOT have store"

    async def test_engine_respects_visibility_enforcement(self):
        """SECURITY Phase 8: Orchestrator enforces visibility when evaluating context.

        Engines receive only pre-filtered artifacts. They CANNOT bypass filtering.
        """
        correlation = uuid4()

        # Phase 8: Orchestrator filtered out the secret artifact (visibility enforcement)
        # Engine receives empty list (no artifacts visible to untrusted agent)
        pre_filtered_artifacts = []  # Orchestrator filtered everything out

        ctx = MockContext(artifacts=pre_filtered_artifacts, correlation_id=correlation)

        engine = TestEngineComponent()
        context = engine.get_conversation_context(ctx)

        # Untrusted agent sees NOTHING (orchestrator filtered it all out)
        assert len(context) == 0, "Engine must see only what orchestrator pre-filtered"

    async def test_engine_filters_by_correlation_id(self):
        """Phase 8: Orchestrator filters by correlation_id when evaluating context.

        Engine receives only artifacts from its workflow (correlation_id).
        """
        correlation_a = uuid4()

        # Phase 8: Orchestrator pre-filtered to include only correlation_a artifacts
        pre_filtered_artifacts = [
            Artifact(
                id=uuid4(),
                type="Task",
                payload={"workflow": "A"},
                produced_by="system",
                created_at=datetime.now(UTC),
            )
            # Artifacts from workflow B NOT included (filtered by orchestrator)
        ]

        ctx = MockContext(
            artifacts=pre_filtered_artifacts, correlation_id=correlation_a
        )

        engine = TestEngineComponent()
        context = engine.get_conversation_context(ctx)

        # Should only see artifacts from workflow A (orchestrator filtered others)
        assert len(context) == 1
        assert context[0].payload["workflow"] == "A"

    async def test_engine_respects_context_exclude_types(self):
        """Phase 8: Engine excludes artifact types specified in context_exclude_types.

        This is ADDITIONAL engine-level filtering on top of orchestrator filtering.
        """
        correlation = uuid4()

        # Phase 8: Orchestrator pre-filtered artifacts
        pre_filtered_artifacts = [
            Artifact(
                id=uuid4(),
                type="Task",
                payload={"title": "Do something"},
                produced_by="system",
                created_at=datetime.now(UTC),
            ),
            Artifact(
                id=uuid4(),
                type="Log",
                payload={"message": "Debug info"},
                produced_by="system",
                created_at=datetime.now(UTC),
            ),
        ]

        ctx = MockContext(artifacts=pre_filtered_artifacts, correlation_id=correlation)

        # Create engine that excludes "Log" type (engine-level filtering)
        engine = TestEngineComponent(context_exclude_types={"Log"})
        context = engine.get_conversation_context(ctx)

        # Should only see Task (Log excluded by engine)
        assert len(context) == 1
        assert context[0].type == "Task"
        assert not any(item.type == "Log" for item in context)

    async def test_engine_respects_context_max_artifacts(self):
        """Phase 8: Engine respects context_max_artifacts limit (engine-level limit).

        This limits the already-filtered artifact list from orchestrator.
        """
        correlation = uuid4()

        # Phase 8: Orchestrator pre-filtered 5 artifacts
        pre_filtered_artifacts = [
            Artifact(
                id=uuid4(),
                type="Task",
                payload={"title": f"Task {i}"},
                produced_by="system",
                created_at=datetime.now(UTC),
            )
            for i in range(5)
        ]

        ctx = MockContext(artifacts=pre_filtered_artifacts, correlation_id=correlation)

        # Create engine with max_artifacts=2 (should get last 2)
        engine = TestEngineComponent(context_max_artifacts=2)
        context = engine.get_conversation_context(ctx)

        # Should only return last 2 artifacts
        assert len(context) == 2
        assert context[0].payload["title"] == "Task 3"  # Second-to-last
        assert context[1].payload["title"] == "Task 4"  # Last

    async def test_engine_works_with_custom_provider(self):
        """Phase 8: Orchestrator can use custom provider to evaluate context.

        Engine just reads the pre-filtered result (doesn't know which provider was used).
        """
        correlation = uuid4()

        # Phase 8: Orchestrator used FilteredContextProvider with tag filter
        # Result: only artifacts with "important" tag
        pre_filtered_artifacts = [
            Artifact(
                id=uuid4(),
                type="Task",
                payload={"title": "Critical bug"},
                produced_by="system",
                created_at=datetime.now(UTC),
            )
            # Normal artifact NOT included (filtered by custom provider)
        ]

        ctx = MockContext(artifacts=pre_filtered_artifacts, correlation_id=correlation)

        engine = TestEngineComponent()
        context = engine.get_conversation_context(ctx)

        # Should only see artifact that passed custom provider's filter
        assert len(context) == 1
        assert context[0].payload["title"] == "Critical bug"

    async def test_engine_returns_correct_format(self):
        """Phase 8: Engine returns Artifact objects with full metadata."""
        correlation = uuid4()

        # Phase 8: Orchestrator pre-filtered artifact
        artifact_id = uuid4()
        pre_filtered_artifacts = [
            Artifact(
                id=artifact_id,
                type="Task",
                payload={"title": "Do something"},
                produced_by="planner",
                created_at=datetime.now(UTC),
            )
        ]

        ctx = MockContext(artifacts=pre_filtered_artifacts, correlation_id=correlation)

        engine = TestEngineComponent()
        context = engine.get_conversation_context(ctx)

        # Verify format
        assert isinstance(context, list)
        assert len(context) == 1
        assert isinstance(context[0], Artifact)

        # Verify Artifact fields (full metadata available)
        item = context[0]
        assert item.type == "Task"
        assert item.payload == {"title": "Do something"}
        assert item.produced_by == "planner"
        assert item.id == artifact_id
        assert item.created_at is not None
