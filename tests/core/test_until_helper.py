"""Tests for Until Helper (Builder Pattern).

Spec: 003-until-conditions-dsl
Phase 3: Until Helper
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from flock.registry import flock_type


# ============================================================================
# Test Artifact Types
# ============================================================================


@flock_type(name="UntilTestUserStory")
class UntilTestUserStory(BaseModel):
    """Test artifact type for Until helper tests."""

    title: str
    points: int = 0


@flock_type(name="UntilTestHypothesis")
class UntilTestHypothesis(BaseModel):
    """Test artifact type for Until helper tests."""

    content: str
    confidence: float = 0.5


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator for condition evaluation."""
    orchestrator = Mock()
    orchestrator.store = Mock()
    orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
    orchestrator.get_correlation_status = AsyncMock(
        return_value={"error_count": 0}
    )
    orchestrator._scheduler = Mock()
    orchestrator._scheduler.pending_tasks = set()
    return orchestrator


# ============================================================================
# Phase 3 Tests: Until Helper
# ============================================================================


class TestUntilIdle:
    """Test Until.idle() and Until.no_pending_work()."""

    def test_idle_returns_idle_condition(self):
        """Until.idle() returns IdleCondition."""
        from flock.core.conditions import IdleCondition, Until

        condition = Until.idle()

        assert isinstance(condition, IdleCondition)

    def test_no_pending_work_returns_idle_condition(self):
        """Until.no_pending_work() returns IdleCondition (alias)."""
        from flock.core.conditions import IdleCondition, Until

        condition = Until.no_pending_work()

        assert isinstance(condition, IdleCondition)

    @pytest.mark.asyncio
    async def test_idle_evaluates_correctly(self, mock_orchestrator):
        """Until.idle() condition evaluates correctly."""
        from flock.core.conditions import Until

        mock_orchestrator._scheduler.pending_tasks = set()

        condition = Until.idle()
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestUntilArtifactCount:
    """Test Until.artifact_count() builder."""

    def test_artifact_count_returns_artifact_count_condition(self):
        """Until.artifact_count(Model) returns ArtifactCountCondition."""
        from flock.core.conditions import ArtifactCountCondition, Until

        condition = Until.artifact_count(UntilTestUserStory)

        assert isinstance(condition, ArtifactCountCondition)
        assert condition.model is UntilTestUserStory

    def test_artifact_count_with_correlation_id(self):
        """Until.artifact_count with correlation_id passes filter."""
        from flock.core.conditions import Until

        condition = Until.artifact_count(
            UntilTestUserStory, correlation_id="workflow-123"
        )

        assert condition.correlation_id == "workflow-123"

    def test_artifact_count_with_tags(self):
        """Until.artifact_count with tags passes filter."""
        from flock.core.conditions import Until

        condition = Until.artifact_count(
            UntilTestUserStory, tags={"important", "reviewed"}
        )

        assert condition.tags == {"important", "reviewed"}

    def test_artifact_count_with_produced_by(self):
        """Until.artifact_count with produced_by passes filter."""
        from flock.core.conditions import Until

        condition = Until.artifact_count(
            UntilTestUserStory, produced_by="story-writer"
        )

        assert condition.produced_by == "story-writer"

    def test_artifact_count_chaining_at_least(self):
        """Until.artifact_count().at_least(5) chains correctly."""
        from flock.core.conditions import Until

        condition = Until.artifact_count(UntilTestUserStory).at_least(5)

        assert condition.min_count == 5

    def test_artifact_count_chaining_at_most(self):
        """Until.artifact_count().at_most(10) chains correctly."""
        from flock.core.conditions import Until

        condition = Until.artifact_count(UntilTestUserStory).at_most(10)

        assert condition.max_count == 10

    def test_artifact_count_chaining_exactly(self):
        """Until.artifact_count().exactly(5) chains correctly."""
        from flock.core.conditions import Until

        condition = Until.artifact_count(UntilTestUserStory).exactly(5)

        assert condition.exact_count == 5

    @pytest.mark.asyncio
    async def test_artifact_count_evaluates_correctly(self, mock_orchestrator):
        """Until.artifact_count().at_least() evaluates correctly."""
        from flock.core.conditions import Until

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        condition = Until.artifact_count(UntilTestUserStory).at_least(5)
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestUntilExists:
    """Test Until.exists() builder."""

    def test_exists_returns_exists_condition(self):
        """Until.exists(Model) returns ExistsCondition."""
        from flock.core.conditions import ExistsCondition, Until

        condition = Until.exists(UntilTestUserStory)

        assert isinstance(condition, ExistsCondition)
        assert condition.model is UntilTestUserStory

    def test_exists_with_correlation_id(self):
        """Until.exists with correlation_id passes filter."""
        from flock.core.conditions import Until

        condition = Until.exists(
            UntilTestUserStory, correlation_id="workflow-abc"
        )

        assert condition.correlation_id == "workflow-abc"

    def test_exists_with_tags(self):
        """Until.exists with tags passes filter."""
        from flock.core.conditions import Until

        condition = Until.exists(
            UntilTestUserStory, tags={"verified"}
        )

        assert condition.tags == {"verified"}

    @pytest.mark.asyncio
    async def test_exists_evaluates_correctly(self, mock_orchestrator):
        """Until.exists() evaluates correctly."""
        from flock.core.conditions import Until

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 1))

        condition = Until.exists(UntilTestUserStory)
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestUntilNone:
    """Test Until.none() builder."""

    def test_none_returns_not_condition(self):
        """Until.none(Model) returns NotCondition wrapping ExistsCondition."""
        from flock.core.conditions import ExistsCondition, NotCondition, Until

        condition = Until.none(UntilTestUserStory)

        assert isinstance(condition, NotCondition)
        assert isinstance(condition.condition, ExistsCondition)
        assert condition.condition.model is UntilTestUserStory

    def test_none_with_correlation_id(self):
        """Until.none with correlation_id passes filter."""
        from flock.core.conditions import ExistsCondition, Until

        condition = Until.none(
            UntilTestUserStory, correlation_id="workflow-xyz"
        )

        inner = condition.condition
        assert isinstance(inner, ExistsCondition)
        assert inner.correlation_id == "workflow-xyz"

    @pytest.mark.asyncio
    async def test_none_evaluates_correctly_no_artifacts(self, mock_orchestrator):
        """Until.none() returns True when no artifacts exist."""
        from flock.core.conditions import Until

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        condition = Until.none(UntilTestUserStory)
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_none_evaluates_correctly_with_artifacts(self, mock_orchestrator):
        """Until.none() returns False when artifacts exist."""
        from flock.core.conditions import Until

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 1))

        condition = Until.none(UntilTestUserStory)
        result = await condition.evaluate(mock_orchestrator)

        assert result is False


class TestUntilAnyField:
    """Test Until.any_field() builder."""

    def test_any_field_returns_field_predicate_condition(self):
        """Until.any_field returns FieldPredicateCondition."""
        from flock.core.conditions import FieldPredicateCondition, Until

        condition = Until.any_field(
            UntilTestHypothesis,
            field="confidence",
            predicate=lambda v: v >= 0.9,
        )

        assert isinstance(condition, FieldPredicateCondition)
        assert condition.model is UntilTestHypothesis
        assert condition.field == "confidence"

    def test_any_field_with_correlation_id(self):
        """Until.any_field with correlation_id passes filter."""
        from flock.core.conditions import Until

        condition = Until.any_field(
            UntilTestHypothesis,
            field="confidence",
            predicate=lambda v: v >= 0.9,
            correlation_id="workflow-test",
        )

        assert condition.correlation_id == "workflow-test"

    @pytest.mark.asyncio
    async def test_any_field_evaluates_correctly(self, mock_orchestrator):
        """Until.any_field() evaluates predicate correctly."""
        from flock.core.conditions import Until
        from flock.core.artifacts import Artifact
        from datetime import UTC, datetime
        from uuid import uuid4

        artifact = Artifact(
            id=uuid4(),
            type="UntilTestHypothesis",
            payload={"content": "test", "confidence": 0.95},
            produced_by="test-agent",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
        )
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=([artifact], 1)
        )

        condition = Until.any_field(
            UntilTestHypothesis,
            field="confidence",
            predicate=lambda v: v is not None and v >= 0.9,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestUntilWorkflowError:
    """Test Until.workflow_error() builder."""

    def test_workflow_error_returns_workflow_error_condition(self):
        """Until.workflow_error(cid) returns WorkflowErrorCondition."""
        from flock.core.conditions import Until, WorkflowErrorCondition

        condition = Until.workflow_error("workflow-123")

        assert isinstance(condition, WorkflowErrorCondition)
        assert condition.correlation_id == "workflow-123"

    @pytest.mark.asyncio
    async def test_workflow_error_evaluates_correctly(self, mock_orchestrator):
        """Until.workflow_error() evaluates correctly."""
        from flock.core.conditions import Until

        mock_orchestrator.get_correlation_status = AsyncMock(
            return_value={"error_count": 2}
        )

        condition = Until.workflow_error("workflow-123")
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestUntilComposition:
    """Test complex condition composition with Until helper."""

    @pytest.mark.asyncio
    async def test_complex_composition_or(self, mock_orchestrator):
        """Test: Until.artifact_count().at_least(5) | Until.workflow_error()."""
        from flock.core.conditions import OrCondition, Until

        condition = (
            Until.artifact_count(UntilTestUserStory).at_least(5)
            | Until.workflow_error("workflow-123")
        )

        assert isinstance(condition, OrCondition)

        # Scenario: error exists (should return True via OR)
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))
        mock_orchestrator.get_correlation_status = AsyncMock(
            return_value={"error_count": 1}
        )

        result = await condition.evaluate(mock_orchestrator)
        assert result is True

    @pytest.mark.asyncio
    async def test_complex_composition_and(self, mock_orchestrator):
        """Test: Until.artifact_count().at_least(5) & Until.idle()."""
        from flock.core.conditions import AndCondition, Until

        condition = (
            Until.artifact_count(UntilTestUserStory).at_least(5)
            & Until.idle()
        )

        assert isinstance(condition, AndCondition)

        # Scenario: 5+ artifacts AND idle
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))
        mock_orchestrator._scheduler.pending_tasks = set()

        result = await condition.evaluate(mock_orchestrator)
        assert result is True

    @pytest.mark.asyncio
    async def test_complex_composition_not(self, mock_orchestrator):
        """Test: ~Until.exists(Model) (same as Until.none())."""
        from flock.core.conditions import NotCondition, Until

        condition = ~Until.exists(UntilTestUserStory)

        assert isinstance(condition, NotCondition)

        # No artifacts exist
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        result = await condition.evaluate(mock_orchestrator)
        assert result is True


class TestUntilExported:
    """Test Until class is exported."""

    def test_until_exported(self):
        """Until should be exported from conditions module."""
        from flock.core.conditions import Until

        assert Until is not None
