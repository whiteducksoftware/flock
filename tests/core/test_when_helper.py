"""Tests for When Helper (Subscription Activation Conditions).

Spec: 003-until-conditions-dsl
Phase 5: When Helper & Subscription Activation
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.registry import flock_type


if TYPE_CHECKING:
    from flock.core import Flock


# ============================================================================
# Test Artifact Types
# ============================================================================


@flock_type(name="WhenTestInput")
class WhenTestInput(BaseModel):
    """Test artifact type for When helper tests."""

    value: str


@flock_type(name="WhenTestHypothesis")
class WhenTestHypothesis(BaseModel):
    """Test artifact type for When helper tests."""

    content: str
    confidence: float = 0.5


@flock_type(name="WhenTestUserStory")
class WhenTestUserStory(BaseModel):
    """Test artifact type for When helper tests."""

    title: str
    points: int = 0


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
# Phase 5 Tests: When Helper
# ============================================================================


class TestWhenCorrelation:
    """Test When.correlation() builder."""

    def test_correlation_returns_builder(self):
        """When.correlation(Model) returns CorrelationConditionBuilder."""
        from flock.core.conditions import CorrelationConditionBuilder, When

        builder = When.correlation(WhenTestUserStory)

        assert isinstance(builder, CorrelationConditionBuilder)
        assert builder.model is WhenTestUserStory

    def test_correlation_stores_model(self):
        """When.correlation stores the model for condition building."""
        from flock.core.conditions import When

        builder = When.correlation(WhenTestHypothesis)

        assert builder.model is WhenTestHypothesis


class TestCorrelationBuilderCountAtLeast:
    """Test CorrelationConditionBuilder.count_at_least()."""

    def test_count_at_least_returns_artifact_count_condition(self):
        """count_at_least(N) returns ArtifactCountCondition with min_count."""
        from flock.core.conditions import ArtifactCountCondition, When

        condition = When.correlation(WhenTestUserStory).count_at_least(5)

        assert isinstance(condition, ArtifactCountCondition)
        assert condition.min_count == 5
        assert condition.model is WhenTestUserStory

    def test_count_at_least_with_different_values(self):
        """count_at_least works with various threshold values."""
        from flock.core.conditions import When

        cond_1 = When.correlation(WhenTestUserStory).count_at_least(1)
        cond_10 = When.correlation(WhenTestUserStory).count_at_least(10)
        cond_100 = When.correlation(WhenTestUserStory).count_at_least(100)

        assert cond_1.min_count == 1
        assert cond_10.min_count == 10
        assert cond_100.min_count == 100

    @pytest.mark.asyncio
    async def test_count_at_least_evaluates_correctly_true(self, mock_orchestrator):
        """count_at_least returns True when count meets threshold."""
        from flock.core.conditions import When

        # Mock: 5 artifacts exist
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        condition = When.correlation(WhenTestUserStory).count_at_least(5)
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_count_at_least_evaluates_correctly_false(self, mock_orchestrator):
        """count_at_least returns False when count below threshold."""
        from flock.core.conditions import When

        # Mock: 3 artifacts exist (below 5 threshold)
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))

        condition = When.correlation(WhenTestUserStory).count_at_least(5)
        result = await condition.evaluate(mock_orchestrator)

        assert result is False


class TestCorrelationBuilderAnyField:
    """Test CorrelationConditionBuilder.any_field()."""

    def test_any_field_returns_field_predicate_condition(self):
        """any_field() returns FieldPredicateCondition."""
        from flock.core.conditions import FieldPredicateCondition, When

        condition = When.correlation(WhenTestHypothesis).any_field(
            field="confidence",
            predicate=lambda v: v >= 0.9,
        )

        assert isinstance(condition, FieldPredicateCondition)
        assert condition.model is WhenTestHypothesis
        assert condition.field == "confidence"

    def test_any_field_stores_predicate(self):
        """any_field stores the predicate function."""
        from flock.core.conditions import When

        predicate_fn = lambda v: v >= 0.9
        condition = When.correlation(WhenTestHypothesis).any_field(
            field="confidence",
            predicate=predicate_fn,
        )

        assert condition.predicate is predicate_fn

    @pytest.mark.asyncio
    async def test_any_field_evaluates_correctly_true(self, mock_orchestrator):
        """any_field returns True when any artifact matches predicate."""
        from flock.core.conditions import When
        from flock.core.artifacts import Artifact

        # Create an artifact with high confidence
        artifact = Artifact(
            id=uuid4(),
            type="WhenTestHypothesis",
            payload={"content": "test", "confidence": 0.95},
            produced_by="test-agent",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
        )
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=([artifact], 1)
        )

        condition = When.correlation(WhenTestHypothesis).any_field(
            field="confidence",
            predicate=lambda v: v is not None and v >= 0.9,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_any_field_evaluates_correctly_false(self, mock_orchestrator):
        """any_field returns False when no artifacts match predicate."""
        from flock.core.conditions import When
        from flock.core.artifacts import Artifact

        # Create an artifact with low confidence
        artifact = Artifact(
            id=uuid4(),
            type="WhenTestHypothesis",
            payload={"content": "test", "confidence": 0.5},
            produced_by="test-agent",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
        )
        mock_orchestrator.store.query_artifacts = AsyncMock(
            return_value=([artifact], 1)
        )

        condition = When.correlation(WhenTestHypothesis).any_field(
            field="confidence",
            predicate=lambda v: v is not None and v >= 0.9,
        )
        result = await condition.evaluate(mock_orchestrator)

        assert result is False


class TestCorrelationBuilderCountExactly:
    """Test CorrelationConditionBuilder.count_exactly()."""

    def test_count_exactly_returns_artifact_count_condition(self):
        """count_exactly(N) returns ArtifactCountCondition with exact_count."""
        from flock.core.conditions import ArtifactCountCondition, When

        condition = When.correlation(WhenTestUserStory).count_exactly(3)

        assert isinstance(condition, ArtifactCountCondition)
        assert condition.exact_count == 3
        assert condition.model is WhenTestUserStory


class TestCorrelationBuilderCountAtMost:
    """Test CorrelationConditionBuilder.count_at_most()."""

    def test_count_at_most_returns_artifact_count_condition(self):
        """count_at_most(N) returns ArtifactCountCondition with max_count."""
        from flock.core.conditions import ArtifactCountCondition, When

        condition = When.correlation(WhenTestUserStory).count_at_most(10)

        assert isinstance(condition, ArtifactCountCondition)
        assert condition.max_count == 10
        assert condition.model is WhenTestUserStory


class TestCorrelationBuilderExists:
    """Test CorrelationConditionBuilder.exists()."""

    def test_exists_returns_exists_condition(self):
        """exists() returns ExistsCondition."""
        from flock.core.conditions import ExistsCondition, When

        condition = When.correlation(WhenTestUserStory).exists()

        assert isinstance(condition, ExistsCondition)
        assert condition.model is WhenTestUserStory

    @pytest.mark.asyncio
    async def test_exists_evaluates_correctly(self, mock_orchestrator):
        """exists() returns True when any artifact exists."""
        from flock.core.conditions import When

        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 1))

        condition = When.correlation(WhenTestUserStory).exists()
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestWhenExported:
    """Test When class is exported."""

    def test_when_exported(self):
        """When should be exported from conditions module."""
        from flock.core.conditions import When

        assert When is not None

    def test_correlation_condition_builder_exported(self):
        """CorrelationConditionBuilder should be exported from conditions module."""
        from flock.core.conditions import CorrelationConditionBuilder

        assert CorrelationConditionBuilder is not None


class TestWhenComposition:
    """Test condition composition with When helper."""

    @pytest.mark.asyncio
    async def test_when_condition_with_or(self, mock_orchestrator):
        """When conditions can be combined with OR."""
        from flock.core.conditions import OrCondition, When

        condition = (
            When.correlation(WhenTestUserStory).count_at_least(5)
            | When.correlation(WhenTestHypothesis).count_at_least(3)
        )

        assert isinstance(condition, OrCondition)

        # Test: first condition met (5 user stories)
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))
        result = await condition.evaluate(mock_orchestrator)
        assert result is True

    @pytest.mark.asyncio
    async def test_when_condition_with_and(self, mock_orchestrator):
        """When conditions can be combined with AND."""
        from flock.core.conditions import AndCondition, When

        condition = (
            When.correlation(WhenTestUserStory).count_at_least(5)
            & When.correlation(WhenTestHypothesis).count_at_least(3)
        )

        assert isinstance(condition, AndCondition)

    @pytest.mark.asyncio
    async def test_when_condition_with_not(self, mock_orchestrator):
        """When conditions can be negated."""
        from flock.core.conditions import NotCondition, When

        condition = ~When.correlation(WhenTestUserStory).exists()

        assert isinstance(condition, NotCondition)

        # No artifacts exist
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
        result = await condition.evaluate(mock_orchestrator)
        assert result is True


class TestWhenWithCorrelationId:
    """Test When helper with correlation_id context binding."""

    def test_builder_can_set_correlation_id(self):
        """CorrelationConditionBuilder can set correlation_id."""
        from flock.core.conditions import When

        builder = When.correlation(WhenTestUserStory)
        # The correlation_id is typically bound later by ActivationComponent
        # but the builder should allow creating conditions that use it

        condition = builder.count_at_least(5)
        # The condition should work without correlation_id for now
        assert condition.correlation_id is None

    def test_condition_accepts_correlation_id(self):
        """Conditions created via When helper accept correlation_id."""
        from flock.core.conditions import When

        # When used in activation context, correlation_id is bound
        # This tests that the underlying conditions support it
        condition = When.correlation(WhenTestUserStory).count_at_least(5)

        # Verify it's an ArtifactCountCondition that supports correlation_id
        assert hasattr(condition, "correlation_id")
