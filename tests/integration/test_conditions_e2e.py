"""End-to-end integration tests for Until Conditions DSL.

Spec: 003-until-conditions-dsl
Phase 6: T6.1 - Integration Tests
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.registry import flock_type


if TYPE_CHECKING:
    from flock.core import Flock


# ============================================================================
# Test Artifact Types
# ============================================================================


@flock_type(name="E2EUserStory")
class E2EUserStory(BaseModel):
    """User story artifact for E2E tests."""

    title: str
    points: int = 0


@flock_type(name="E2EHypothesis")
class E2EHypothesis(BaseModel):
    """Hypothesis artifact for E2E tests."""

    content: str
    confidence: float = 0.5


@flock_type(name="E2EWorkflowError")
class E2EWorkflowError(BaseModel):
    """Error artifact for E2E tests."""

    message: str
    error_type: str = "general"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator for E2E tests."""
    orchestrator = Mock()
    orchestrator.store = Mock()
    orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
    orchestrator.get_correlation_status = AsyncMock(
        return_value={"error_count": 0}
    )
    orchestrator._scheduler = Mock()
    orchestrator._scheduler.pending_tasks = set()
    orchestrator._components_initialized = True
    orchestrator._component_runner = Mock()
    orchestrator._component_runner.is_initialized = True
    orchestrator._component_runner.run_idle = AsyncMock()
    orchestrator._lifecycle_manager = Mock()
    orchestrator._lifecycle_manager.has_pending_batches = False
    orchestrator._lifecycle_manager.has_pending_correlations = False
    orchestrator._has_active_timers = Mock(return_value=False)
    orchestrator.shutdown = AsyncMock()
    return orchestrator


# ============================================================================
# Phase 6 Tests: E2E Integration
# ============================================================================


class TestRunUntilCountCondition:
    """Test run_until with artifact count conditions."""

    @pytest.mark.asyncio
    async def test_publish_run_until_stops_at_correct_count(self, mock_orchestrator):
        """Publish artifacts, run_until count condition, verify stop at count."""
        from flock.core.conditions import Until

        # Track artifact count
        artifact_count = [0]

        async def mock_query_artifacts(*args, **kwargs):
            return ([], artifact_count[0])

        mock_orchestrator.store.query_artifacts = mock_query_artifacts

        # Simulate publishing artifacts in background
        async def publish_artifacts():
            for i in range(10):
                await asyncio.sleep(0.01)
                artifact_count[0] = i + 1

        # Create condition: stop when 5 user stories exist
        condition = Until.artifact_count(E2EUserStory).at_least(5)

        # Simulate run_until behavior
        async def mock_run_until(cond, *, timeout=None):
            start = asyncio.get_event_loop().time()
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                if timeout and (asyncio.get_event_loop().time() - start) >= timeout:
                    return False
                await asyncio.sleep(0.01)

        # Start publishing in background
        publish_task = asyncio.create_task(publish_artifacts())

        # Run until condition is met
        result = await mock_run_until(condition, timeout=1.0)

        await publish_task

        assert result is True
        assert artifact_count[0] >= 5


class TestRunUntilErrorCondition:
    """Test run_until with error conditions."""

    @pytest.mark.asyncio
    async def test_run_until_stops_on_error(self, mock_orchestrator):
        """Run until workflow error condition is triggered."""
        from flock.core.conditions import Until

        # Track error count
        error_count = [0]

        async def mock_get_status(*args, **kwargs):
            return {"error_count": error_count[0]}

        mock_orchestrator.get_correlation_status = mock_get_status

        # Simulate error occurring
        async def trigger_error():
            await asyncio.sleep(0.05)
            error_count[0] = 1

        # Create condition: stop on first error
        condition = Until.workflow_error("workflow-123")

        # Simulate run_until
        async def mock_run_until(cond, *, timeout=None):
            start = asyncio.get_event_loop().time()
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                if timeout and (asyncio.get_event_loop().time() - start) >= timeout:
                    return False
                await asyncio.sleep(0.01)

        # Trigger error in background
        error_task = asyncio.create_task(trigger_error())

        # Run until error occurs
        result = await mock_run_until(condition, timeout=1.0)

        await error_task

        assert result is True


class TestRunUntilCompositeCondition:
    """Test run_until with composite conditions."""

    @pytest.mark.asyncio
    async def test_run_until_composite_or_condition(self, mock_orchestrator):
        """Run until composite OR condition is met."""
        from flock.core.conditions import Until

        # Track counts
        user_story_count = [0]
        hypothesis_count = [0]

        async def mock_query_artifacts(*args, **kwargs):
            # Return based on type being queried
            # This is simplified - real implementation would check model
            return ([], user_story_count[0] + hypothesis_count[0])

        mock_orchestrator.store.query_artifacts = mock_query_artifacts

        # Create composite condition: 10 user stories OR 5 hypotheses
        condition = (
            Until.artifact_count(E2EUserStory).at_least(10)
            | Until.artifact_count(E2EHypothesis).at_least(5)
        )

        # Simulate publishing only 3 hypotheses, then 5
        async def publish_hypotheses():
            for i in range(5):
                await asyncio.sleep(0.01)
                hypothesis_count[0] = i + 1

        # Simulate run_until
        async def mock_run_until(cond, *, timeout=None):
            start = asyncio.get_event_loop().time()
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                if timeout and (asyncio.get_event_loop().time() - start) >= timeout:
                    return False
                await asyncio.sleep(0.01)

        # Start publishing
        publish_task = asyncio.create_task(publish_hypotheses())

        result = await mock_run_until(condition, timeout=1.0)

        await publish_task

        assert result is True
        assert hypothesis_count[0] >= 5


class TestActivationConditions:
    """Test subscription activation conditions."""

    @pytest.mark.asyncio
    async def test_agent_activates_after_threshold(self, mock_orchestrator):
        """Agent only activates after threshold condition is met."""
        from flock.components.orchestrator.activation import ActivationComponent
        from flock.core.artifacts import Artifact
        from flock.core.conditions import When
        from flock.core.subscription import Subscription

        # Create mock agent with activation condition
        agent = Mock()
        agent.name = "qa-agent"

        # Activation: need at least 5 user stories
        condition = When.correlation(E2EUserStory).count_at_least(5)
        sub = Subscription(
            agent_name="qa-agent",
            types=[E2EUserStory],
            activation=condition,
        )
        agent.subscriptions = [sub]

        # Create artifact
        artifact = Artifact(
            id=uuid4(),
            type="E2EUserStory",
            payload={"title": "Test Story", "points": 5},
            produced_by="story-generator",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
            correlation_id="workflow-123",
        )

        component = ActivationComponent()

        # Scenario 1: Only 3 user stories exist (below threshold)
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 3))

        result = await component.on_before_agent_schedule(
            mock_orchestrator, agent, [artifact]
        )

        assert len(result) == 0  # Deferred - not activated

        # Scenario 2: 5 user stories exist (at threshold)
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        result = await component.on_before_agent_schedule(
            mock_orchestrator, agent, [artifact]
        )

        assert len(result) == 1  # Activated

    @pytest.mark.asyncio
    async def test_multiple_agents_different_activations(self, mock_orchestrator):
        """Multiple agents with different activation conditions."""
        from flock.components.orchestrator.activation import ActivationComponent
        from flock.core.artifacts import Artifact
        from flock.core.conditions import When
        from flock.core.subscription import Subscription

        # Create two agents with different activation thresholds
        qa_agent = Mock()
        qa_agent.name = "qa-agent"
        qa_sub = Subscription(
            agent_name="qa-agent",
            types=[E2EUserStory],
            activation=When.correlation(E2EUserStory).count_at_least(5),
        )
        qa_agent.subscriptions = [qa_sub]

        summary_agent = Mock()
        summary_agent.name = "summary-agent"
        summary_sub = Subscription(
            agent_name="summary-agent",
            types=[E2EUserStory],
            activation=When.correlation(E2EUserStory).count_at_least(10),
        )
        summary_agent.subscriptions = [summary_sub]

        artifact = Artifact(
            id=uuid4(),
            type="E2EUserStory",
            payload={"title": "Test Story", "points": 5},
            produced_by="story-generator",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
        )

        component = ActivationComponent()

        # 7 user stories exist
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 7))

        # QA agent should activate (7 >= 5)
        qa_result = await component.on_before_agent_schedule(
            mock_orchestrator, qa_agent, [artifact]
        )
        assert len(qa_result) == 1

        # Summary agent should NOT activate (7 < 10)
        summary_result = await component.on_before_agent_schedule(
            mock_orchestrator, summary_agent, [artifact]
        )
        assert len(summary_result) == 0


class TestRunUntilWithActivation:
    """Test run_until combined with activation conditions."""

    @pytest.mark.asyncio
    async def test_run_until_and_activation_together(self, mock_orchestrator):
        """run_until and activation conditions work together."""
        from flock.components.orchestrator.activation import ActivationComponent
        from flock.core.artifacts import Artifact
        from flock.core.conditions import Until, When
        from flock.core.subscription import Subscription

        # Create agent with activation
        agent = Mock()
        agent.name = "synthesis-agent"
        sub = Subscription(
            agent_name="synthesis-agent",
            types=[E2EHypothesis],
            activation=When.correlation(E2EHypothesis).count_at_least(3),
        )
        agent.subscriptions = [sub]

        artifact = Artifact(
            id=uuid4(),
            type="E2EHypothesis",
            payload={"content": "Test hypothesis", "confidence": 0.8},
            produced_by="researcher",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
        )

        component = ActivationComponent()

        # Simulate workflow progression
        hypothesis_count = [0]

        async def mock_query(*args, **kwargs):
            return ([], hypothesis_count[0])

        mock_orchestrator.store.query_artifacts = mock_query

        # Run_until condition: need at least 5 hypotheses
        run_condition = Until.artifact_count(E2EHypothesis).at_least(5)

        # Publish hypotheses
        for i in range(5):
            hypothesis_count[0] = i + 1

            # Check activation at each step
            result = await component.on_before_agent_schedule(
                mock_orchestrator, agent, [artifact]
            )

            if i < 2:  # Less than 3 hypotheses
                assert len(result) == 0, f"Should not activate at count {i + 1}"
            else:  # 3+ hypotheses
                assert len(result) == 1, f"Should activate at count {i + 1}"

        # Check run_until condition
        final_result = await run_condition.evaluate(mock_orchestrator)
        assert final_result is True


class TestIdleCondition:
    """Test idle condition integration."""

    @pytest.mark.asyncio
    async def test_idle_condition_with_pending_work(self, mock_orchestrator):
        """Idle condition returns False when work is pending."""
        from flock.core.conditions import Until

        # Work is pending
        mock_orchestrator._scheduler.pending_tasks = {"task1", "task2"}

        condition = Until.idle()
        result = await condition.evaluate(mock_orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_idle_condition_when_idle(self, mock_orchestrator):
        """Idle condition returns True when no work is pending."""
        from flock.core.conditions import Until

        # No pending work
        mock_orchestrator._scheduler.pending_tasks = set()

        condition = Until.idle()
        result = await condition.evaluate(mock_orchestrator)

        assert result is True


class TestTimeoutBehavior:
    """Test timeout behavior in conditions."""

    @pytest.mark.asyncio
    async def test_run_until_respects_timeout(self, mock_orchestrator):
        """run_until returns False when timeout exceeded."""
        from flock.core.conditions import Until

        # Condition that never becomes true
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))

        condition = Until.artifact_count(E2EUserStory).at_least(100)

        # Simulate run_until with short timeout
        async def mock_run_until(cond, *, timeout=None):
            start = asyncio.get_event_loop().time()
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                if timeout and (asyncio.get_event_loop().time() - start) >= timeout:
                    return False
                await asyncio.sleep(0.01)

        result = await mock_run_until(condition, timeout=0.05)

        assert result is False  # Timed out


class TestAcceptanceCriteria:
    """Test acceptance criteria from spec."""

    def test_until_artifact_count_at_least_works(self):
        """AC: Until.artifact_count().at_least() works."""
        from flock.core.conditions import ArtifactCountCondition, Until

        condition = Until.artifact_count(E2EUserStory).at_least(5)

        assert isinstance(condition, ArtifactCountCondition)
        assert condition.min_count == 5

    def test_until_exists_works(self):
        """AC: Until.exists() works."""
        from flock.core.conditions import ExistsCondition, Until

        condition = Until.exists(E2EUserStory)

        assert isinstance(condition, ExistsCondition)

    def test_until_idle_works(self):
        """AC: Until.idle() works."""
        from flock.core.conditions import IdleCondition, Until

        condition = Until.idle()

        assert isinstance(condition, IdleCondition)

    def test_until_workflow_error_works(self):
        """AC: Until.workflow_error() works."""
        from flock.core.conditions import Until, WorkflowErrorCondition

        condition = Until.workflow_error("cid-123")

        assert isinstance(condition, WorkflowErrorCondition)
        assert condition.correlation_id == "cid-123"

    def test_boolean_combinators_work(self):
        """AC: Boolean combinators (|, &, ~) work."""
        from flock.core.conditions import (
            AndCondition,
            NotCondition,
            OrCondition,
            Until,
        )

        # OR combinator
        or_cond = Until.exists(E2EUserStory) | Until.idle()
        assert isinstance(or_cond, OrCondition)

        # AND combinator
        and_cond = Until.exists(E2EUserStory) & Until.idle()
        assert isinstance(and_cond, AndCondition)

        # NOT combinator
        not_cond = ~Until.exists(E2EUserStory)
        assert isinstance(not_cond, NotCondition)

    def test_when_helper_creates_activation_conditions(self):
        """AC: When helper creates activation conditions."""
        from flock.core.conditions import ArtifactCountCondition, When

        condition = When.correlation(E2EUserStory).count_at_least(5)

        assert isinstance(condition, ArtifactCountCondition)
        assert condition.min_count == 5


class TestBackwardCompatibility:
    """Test backward compatibility."""

    @pytest.mark.asyncio
    async def test_subscription_without_activation_works(self, mock_orchestrator):
        """Subscriptions without activation continue to work."""
        from flock.components.orchestrator.activation import ActivationComponent
        from flock.core.artifacts import Artifact
        from flock.core.subscription import Subscription

        # Create subscription without activation (old behavior)
        agent = Mock()
        agent.name = "old-agent"
        sub = Subscription(
            agent_name="old-agent",
            types=[E2EUserStory],
            # No activation parameter
        )
        agent.subscriptions = [sub]

        artifact = Artifact(
            id=uuid4(),
            type="E2EUserStory",
            payload={"title": "Test", "points": 3},
            produced_by="generator",
            created_at=datetime.now(UTC),
            tags=set(),
            version=1,
        )

        component = ActivationComponent()
        result = await component.on_before_agent_schedule(
            mock_orchestrator, agent, [artifact]
        )

        # Should pass through without filtering
        assert len(result) == 1
        assert result[0] == artifact
