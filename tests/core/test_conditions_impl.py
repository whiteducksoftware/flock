"""Tests for Concrete Condition Implementations.

Spec: 003-until-conditions-dsl
Phase 2: Concrete Condition Implementations
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type

if TYPE_CHECKING:
    from flock.core import Flock


# ============================================================================
# Test Artifact Types
# ============================================================================


@flock_type(name="CondTestUserStory")
class CondTestUserStory(BaseModel):
    """Test artifact type for condition tests."""

    title: str
    points: int = 0


@flock_type(name="CondTestReview")
class CondTestReview(BaseModel):
    """Test artifact type for condition tests."""

    score: int
    approved: bool = False


# ============================================================================
# Fixtures
# ============================================================================


def _make_artifact(
    type_name: str,
    payload: dict[str, Any],
    produced_by: str = "test-agent",
    correlation_id: str | None = None,
    tags: set[str] | None = None,
) -> Artifact:
    """Helper to create test artifacts."""
    return Artifact(
        id=uuid4(),
        type=type_name,
        payload=payload,
        produced_by=produced_by,
        correlation_id=correlation_id,
        created_at=datetime.now(UTC),
        tags=tags or set(),
        version=1,
        visibility=PublicVisibility(),
    )


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator for condition evaluation."""
    orchestrator = Mock()
    orchestrator.store = Mock()
    orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
    orchestrator.get_correlation_status = AsyncMock(
        return_value={
            "state": "completed",
            "has_pending_work": False,
            "artifact_count": 0,
            "error_count": 0,
        }
    )
    # Mock scheduler for pending tasks check
    orchestrator._scheduler = Mock()
    orchestrator._scheduler.pending_tasks = set()
    return orchestrator


# ============================================================================
# Phase 2 Tests: IdleCondition
# ============================================================================


class TestIdleCondition:
    """Tests for IdleCondition."""

    @pytest.mark.asyncio
    async def test_idle_returns_true_when_no_pending_work(self, mock_orchestrator):
        """IdleCondition returns True when orchestrator is idle."""
        from flock.core.conditions import IdleCondition

        mock_orchestrator._scheduler.pending_tasks = set()

        condition = IdleCondition()
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_idle_returns_false_when_work_pending(self, mock_orchestrator):
        """IdleCondition returns False when scheduler has pending tasks."""
        from flock.core.conditions import IdleCondition

        # Simulate pending task
        mock_task = Mock()
        mock_orchestrator._scheduler.pending_tasks = {mock_task}

        condition = IdleCondition()
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_idle_is_dataclass(self):
        """IdleCondition should be a dataclass."""
        from dataclasses import is_dataclass

        from flock.core.conditions import IdleCondition

        assert is_dataclass(IdleCondition)


# ============================================================================
# Phase 2 Tests: ArtifactCountCondition
# ============================================================================


class TestArtifactCountCondition:
    """Tests for ArtifactCountCondition."""

    @pytest.mark.asyncio
    async def test_at_least_with_fewer_artifacts(self, mock_orchestrator):
        """at_least(5) with 3 artifacts returns False."""
        from flock.core.conditions import ArtifactCountCondition

        # Mock store returns 3 artifacts
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, min_count=5
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_at_least_with_exact_count(self, mock_orchestrator):
        """at_least(5) with 5 artifacts returns True."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, min_count=5
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_at_least_with_more_artifacts(self, mock_orchestrator):
        """at_least(5) with 7 artifacts returns True."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 7))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, min_count=5
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_at_most_boundary_exact(self, mock_orchestrator):
        """at_most(3) with 3 artifacts returns True."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, max_count=3
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_at_most_boundary_over(self, mock_orchestrator):
        """at_most(3) with 4 artifacts returns False."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 4))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, max_count=3
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_at_most_boundary_under(self, mock_orchestrator):
        """at_most(3) with 2 artifacts returns True."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 2))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, max_count=3
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_exactly_match(self, mock_orchestrator):
        """exactly(5) with 5 artifacts returns True."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, exact_count=5
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_exactly_no_match(self, mock_orchestrator):
        """exactly(5) with 4 artifacts returns False."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 4))

        condition = ArtifactCountCondition(
            model=CondTestUserStory, exact_count=5
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_with_correlation_id_filter(self, mock_orchestrator):
        """ArtifactCountCondition passes correlation_id to filter."""
        from flock.core.conditions import ArtifactCountCondition
        from flock.core.store import FilterConfig

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        condition = ArtifactCountCondition(
            model=CondTestUserStory,
            correlation_id="workflow-123",
            min_count=5,
        )
        await condition.evaluate(mock_orchestrator)

        # Verify filter config was passed correctly
        call_args = mock_orchestrator.store.query_artifacts.call_args
        filters = call_args[0][0]
        assert filters.correlation_id == "workflow-123"

    @pytest.mark.asyncio
    async def test_with_tags_filter(self, mock_orchestrator):
        """ArtifactCountCondition passes tags to filter."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))

        condition = ArtifactCountCondition(
            model=CondTestUserStory,
            tags={"important", "reviewed"},
            min_count=3,
        )
        await condition.evaluate(mock_orchestrator)

        call_args = mock_orchestrator.store.query_artifacts.call_args
        filters = call_args[0][0]
        assert filters.tags == {"important", "reviewed"}

    @pytest.mark.asyncio
    async def test_with_produced_by_filter(self, mock_orchestrator):
        """ArtifactCountCondition passes produced_by to filter."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 2))

        condition = ArtifactCountCondition(
            model=CondTestUserStory,
            produced_by="story-writer",
            min_count=2,
        )
        await condition.evaluate(mock_orchestrator)

        call_args = mock_orchestrator.store.query_artifacts.call_args
        filters = call_args[0][0]
        assert filters.produced_by == {"story-writer"}

    @pytest.mark.asyncio
    async def test_at_least_builder_method(self, mock_orchestrator):
        """at_least() builder method creates correct condition."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        base = ArtifactCountCondition(model=CondTestUserStory)
        condition = base.at_least(5)

        assert condition.min_count == 5
        result = await condition.evaluate(mock_orchestrator)
        assert result is True

    @pytest.mark.asyncio
    async def test_at_most_builder_method(self, mock_orchestrator):
        """at_most() builder method creates correct condition."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))

        base = ArtifactCountCondition(model=CondTestUserStory)
        condition = base.at_most(5)

        assert condition.max_count == 5
        result = await condition.evaluate(mock_orchestrator)
        assert result is True

    @pytest.mark.asyncio
    async def test_exactly_builder_method(self, mock_orchestrator):
        """exactly() builder method creates correct condition."""
        from flock.core.conditions import ArtifactCountCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        base = ArtifactCountCondition(model=CondTestUserStory)
        condition = base.exactly(5)

        assert condition.exact_count == 5
        result = await condition.evaluate(mock_orchestrator)
        assert result is True


# ============================================================================
# Phase 2 Tests: ExistsCondition
# ============================================================================


class TestExistsCondition:
    """Tests for ExistsCondition."""

    @pytest.mark.asyncio
    async def test_exists_returns_true_when_artifact_exists(self, mock_orchestrator):
        """ExistsCondition returns True when matching artifact exists."""
        from flock.core.conditions import ExistsCondition

        artifact = _make_artifact("CondTestUserStory", {"title": "Test", "points": 5})
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=([artifact], 1)
        )

        condition = ExistsCondition(model=CondTestUserStory)
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_exists_returns_false_when_no_artifacts(self, mock_orchestrator):
        """ExistsCondition returns False when no matching artifacts."""
        from flock.core.conditions import ExistsCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        condition = ExistsCondition(model=CondTestUserStory)
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_exists_with_correlation_id(self, mock_orchestrator):
        """ExistsCondition passes correlation_id filter."""
        from flock.core.conditions import ExistsCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 1))

        condition = ExistsCondition(
            model=CondTestUserStory, correlation_id="workflow-abc"
        )
        await condition.evaluate(mock_orchestrator)

        call_args = mock_orchestrator.store.query_artifacts.call_args
        filters = call_args[0][0]
        assert filters.correlation_id == "workflow-abc"

    @pytest.mark.asyncio
    async def test_exists_with_tags(self, mock_orchestrator):
        """ExistsCondition passes tags filter."""
        from flock.core.conditions import ExistsCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 1))

        condition = ExistsCondition(
            model=CondTestUserStory, tags={"verified"}
        )
        await condition.evaluate(mock_orchestrator)

        call_args = mock_orchestrator.store.query_artifacts.call_args
        filters = call_args[0][0]
        assert filters.tags == {"verified"}

    @pytest.mark.asyncio
    async def test_exists_uses_limit_1(self, mock_orchestrator):
        """ExistsCondition should use limit=1 for efficiency."""
        from flock.core.conditions import ExistsCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        condition = ExistsCondition(model=CondTestUserStory)
        await condition.evaluate(mock_orchestrator)

        call_args = mock_orchestrator.store.query_artifacts.call_args
        assert call_args.kwargs.get("limit") == 1


# ============================================================================
# Phase 2 Tests: FieldPredicateCondition
# ============================================================================


class TestFieldPredicateCondition:
    """Tests for FieldPredicateCondition."""

    @pytest.mark.asyncio
    async def test_field_predicate_matching_value(self, mock_orchestrator):
        """FieldPredicateCondition returns True when predicate matches."""
        from flock.core.conditions import FieldPredicateCondition

        artifacts = [
            _make_artifact("CondTestReview", {"score": 75, "approved": False}),
            _make_artifact("CondTestReview", {"score": 95, "approved": True}),
        ]
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=(artifacts, 2)
        )

        # Predicate: score >= 90
        condition = FieldPredicateCondition(
            model=CondTestReview,
            field="score",
            predicate=lambda v: v is not None and v >= 90,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_field_predicate_no_matching_value(self, mock_orchestrator):
        """FieldPredicateCondition returns False when no predicate matches."""
        from flock.core.conditions import FieldPredicateCondition

        artifacts = [
            _make_artifact("CondTestReview", {"score": 75, "approved": False}),
            _make_artifact("CondTestReview", {"score": 80, "approved": False}),
        ]
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=(artifacts, 2)
        )

        # Predicate: score >= 90
        condition = FieldPredicateCondition(
            model=CondTestReview,
            field="score",
            predicate=lambda v: v is not None and v >= 90,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_field_predicate_with_none_field_value(self, mock_orchestrator):
        """FieldPredicateCondition handles None field values gracefully."""
        from flock.core.conditions import FieldPredicateCondition

        artifacts = [
            _make_artifact("CondTestReview", {"score": None, "approved": False}),
        ]
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=(artifacts, 1)
        )

        # Predicate checks for non-None high score
        condition = FieldPredicateCondition(
            model=CondTestReview,
            field="score",
            predicate=lambda v: v is not None and v >= 90,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_field_predicate_missing_field(self, mock_orchestrator):
        """FieldPredicateCondition handles missing field gracefully."""
        from flock.core.conditions import FieldPredicateCondition

        # Artifact without the 'score' field in payload
        artifacts = [
            _make_artifact("CondTestReview", {"approved": True}),
        ]
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=(artifacts, 1)
        )

        condition = FieldPredicateCondition(
            model=CondTestReview,
            field="score",
            predicate=lambda v: v is not None and v >= 90,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_field_predicate_with_correlation_id(self, mock_orchestrator):
        """FieldPredicateCondition passes correlation_id filter."""
        from flock.core.conditions import FieldPredicateCondition

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        condition = FieldPredicateCondition(
            model=CondTestReview,
            field="approved",
            predicate=lambda v: v is True,
            correlation_id="workflow-xyz",
        )
        await condition.evaluate(mock_orchestrator)

        call_args = mock_orchestrator.store.query_artifacts.call_args
        filters = call_args[0][0]
        assert filters.correlation_id == "workflow-xyz"

    @pytest.mark.asyncio
    async def test_field_predicate_boolean_field(self, mock_orchestrator):
        """FieldPredicateCondition works with boolean fields."""
        from flock.core.conditions import FieldPredicateCondition

        artifacts = [
            _make_artifact("CondTestReview", {"score": 85, "approved": True}),
        ]
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=(artifacts, 1)
        )

        condition = FieldPredicateCondition(
            model=CondTestReview,
            field="approved",
            predicate=lambda v: v is True,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


# ============================================================================
# Phase 2 Tests: WorkflowErrorCondition
# ============================================================================


class TestWorkflowErrorCondition:
    """Tests for WorkflowErrorCondition."""

    @pytest.mark.asyncio
    async def test_workflow_error_with_errors_present(self, mock_orchestrator):
        """WorkflowErrorCondition returns True when errors exist."""
        from flock.core.conditions import WorkflowErrorCondition

        mock_orchestrator.get_correlation_status = AsyncMock(
            return_value={
                "state": "failed",
                "has_pending_work": False,
                "artifact_count": 3,
                "error_count": 2,
            }
        )

        condition = WorkflowErrorCondition(correlation_id="workflow-123")
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_workflow_error_with_no_errors(self, mock_orchestrator):
        """WorkflowErrorCondition returns False when no errors."""
        from flock.core.conditions import WorkflowErrorCondition

        mock_orchestrator.get_correlation_status = AsyncMock(
            return_value={
                "state": "completed",
                "has_pending_work": False,
                "artifact_count": 5,
                "error_count": 0,
            }
        )

        condition = WorkflowErrorCondition(correlation_id="workflow-123")
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_workflow_error_passes_correlation_id(self, mock_orchestrator):
        """WorkflowErrorCondition uses correct correlation_id."""
        from flock.core.conditions import WorkflowErrorCondition

        mock_orchestrator.get_correlation_status = AsyncMock(
            return_value={"error_count": 0}
        )

        condition = WorkflowErrorCondition(correlation_id="my-workflow")
        await condition.evaluate(mock_orchestrator)

        mock_orchestrator.get_correlation_status.assert_called_once_with("my-workflow")


# ============================================================================
# Phase 2 Tests: Module Exports
# ============================================================================


class TestConcreteConditionExports:
    """Test module exports for concrete conditions."""

    def test_idle_condition_exported(self):
        """IdleCondition should be exported."""
        from flock.core.conditions import IdleCondition

        assert IdleCondition is not None

    def test_artifact_count_condition_exported(self):
        """ArtifactCountCondition should be exported."""
        from flock.core.conditions import ArtifactCountCondition

        assert ArtifactCountCondition is not None

    def test_exists_condition_exported(self):
        """ExistsCondition should be exported."""
        from flock.core.conditions import ExistsCondition

        assert ExistsCondition is not None

    def test_field_predicate_condition_exported(self):
        """FieldPredicateCondition should be exported."""
        from flock.core.conditions import FieldPredicateCondition

        assert FieldPredicateCondition is not None

    def test_workflow_error_condition_exported(self):
        """WorkflowErrorCondition should be exported."""
        from flock.core.conditions import WorkflowErrorCondition

        assert WorkflowErrorCondition is not None
