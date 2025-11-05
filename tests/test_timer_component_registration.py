"""Tests for TimerComponent registration in orchestrator.

This test module verifies that TimerComponent is properly registered
in the orchestrator when agents with schedule_spec are present.

Part of Flock v0.6.0 timer integration - Task 2.4
"""

from datetime import timedelta

import pytest
from pydantic import BaseModel

from flock.components.orchestrator.scheduling.timer import TimerComponent
from flock.core import Flock
from flock.core.subscription import ScheduleSpec


class DummyInput(BaseModel):
    """Test input for scheduled agents."""

    value: str


class DummyOutput(BaseModel):
    """Test output for scheduled agents."""

    result: str


class TestTimerComponentAutoRegistration:
    """Tests for automatic TimerComponent registration."""

    @pytest.mark.asyncio
    async def test_timer_component_auto_registered_with_scheduled_agents(self):
        """Test TimerComponent is automatically registered when agents have schedule_spec.

        Given: An orchestrator with an agent that has a schedule_spec
        When: The orchestrator initializes components
        Then: TimerComponent should be registered in the components list
        """
        # Arrange
        orchestrator = Flock()

        # Create an agent with schedule_spec
        agent = (
            orchestrator.agent("scheduled_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(seconds=30))
        )

        # Act - Initialize components (would normally happen on first publish/run)
        await orchestrator._run_initialize()

        # Assert - TimerComponent should be in components list
        timer_components = [
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        ]

        assert len(timer_components) == 1, "TimerComponent should be registered"
        assert timer_components[0].name == "timer"
        assert timer_components[0].priority == 5

        # Verify timer task was created for the scheduled agent
        assert "scheduled_agent" in timer_components[0]._timer_tasks

        # Cleanup
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_timer_component_not_registered_without_scheduled_agents(self):
        """Test TimerComponent is NOT registered when no agents have schedule_spec.

        Given: An orchestrator with only regular (non-scheduled) agents
        When: The orchestrator initializes components
        Then: TimerComponent should NOT be registered in the components list
        """
        # Arrange
        orchestrator = Flock()

        # Create a regular agent WITHOUT schedule_spec
        agent = (
            orchestrator.agent("regular_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
        )

        # Act - Initialize components
        await orchestrator._run_initialize()

        # Assert - TimerComponent should NOT be in components list
        timer_components = [
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        ]

        assert len(timer_components) == 0, (
            "TimerComponent should NOT be registered without scheduled agents"
        )

        # Cleanup
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_timer_component_requires_publishes_for_scheduled_agents(self):
        """Scheduled agents must declare .publishes(); otherwise init raises ValueError."""
        orchestrator = Flock()

        # Schedule an agent without publishes()
        orchestrator.agent("invalid_scheduled").schedule(
            ScheduleSpec(interval=timedelta(minutes=5))
        )

        with pytest.raises(ValueError, match="must declare .publishes\(\)"):
            await orchestrator._run_initialize()

    @pytest.mark.asyncio
    async def test_timer_component_registered_with_multiple_scheduled_agents(self):
        """Test TimerComponent handles multiple scheduled agents.

        Given: An orchestrator with multiple agents that have schedule_spec
        When: The orchestrator initializes components
        Then: TimerComponent should create timer tasks for all scheduled agents
        """
        # Arrange
        orchestrator = Flock()

        # Create multiple agents with schedule_spec
        agent1 = (
            orchestrator.agent("timer_agent_1")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(seconds=30))
        )

        agent2 = (
            orchestrator.agent("timer_agent_2")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(minutes=5))
        )

        # Act - Initialize components
        await orchestrator._run_initialize()

        # Assert - TimerComponent should be registered
        timer_components = [
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        ]

        assert len(timer_components) == 1

        # Both agents should have timer tasks
        timer_component = timer_components[0]
        assert "timer_agent_1" in timer_component._timer_tasks
        assert "timer_agent_2" in timer_component._timer_tasks
        assert len(timer_component._timer_tasks) == 2

        # Cleanup
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_timer_component_priority_order(self):
        """Test TimerComponent priority (5) places it correctly in execution order.

        Given: An orchestrator with TimerComponent and other components
        When: Components are sorted by priority
        Then: TimerComponent (priority 5) should run before collection (priority 100)
              but after circuit breaker (priority 10) and deduplication (priority 20)
        """
        # Arrange
        orchestrator = Flock()

        # Create a scheduled agent to trigger TimerComponent registration
        agent = (
            orchestrator.agent("scheduled_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(seconds=30))
        )

        # Act - Initialize components
        await orchestrator._run_initialize()

        # Assert - Verify priority ordering
        component_names_and_priorities = [
            (c.name, c.priority) for c in orchestrator._components
        ]

        # Find positions of key components
        timer_pos = next(
            i
            for i, (name, _) in enumerate(component_names_and_priorities)
            if name == "timer"
        )
        circuit_breaker_pos = next(
            i
            for i, (name, _) in enumerate(component_names_and_priorities)
            if name == "circuit_breaker"
        )
        dedup_pos = next(
            i
            for i, (name, _) in enumerate(component_names_and_priorities)
            if name == "deduplication"
        )
        builtin_pos = next(
            i
            for i, (name, _) in enumerate(component_names_and_priorities)
            if name == "builtin_collection"
        )

        # Verify timer (priority 5) runs BEFORE circuit breaker (10), dedup (20), and builtin (100)
        assert timer_pos < circuit_breaker_pos, (
            "Timer should run before circuit breaker"
        )
        assert timer_pos < dedup_pos, "Timer should run before deduplication"
        assert timer_pos < builtin_pos, "Timer should run before builtin collection"

        # Verify priorities are as expected
        assert orchestrator._components[timer_pos].priority == 5
        assert orchestrator._components[circuit_breaker_pos].priority == 10
        assert orchestrator._components[dedup_pos].priority == 20
        assert orchestrator._components[builtin_pos].priority == 100

        # Cleanup
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_timer_component_mixed_agents(self):
        """Test TimerComponent registration with mixed scheduled and non-scheduled agents.

        Given: An orchestrator with both scheduled and non-scheduled agents
        When: The orchestrator initializes components
        Then: TimerComponent should be registered and create tasks only for scheduled agents
        """
        # Arrange
        orchestrator = Flock()

        # Create a scheduled agent
        scheduled_agent = (
            orchestrator.agent("scheduled_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(seconds=30))
        )

        # Create a regular agent (no schedule)
        regular_agent = (
            orchestrator.agent("regular_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
        )

        # Act - Initialize components
        await orchestrator._run_initialize()

        # Assert - TimerComponent should be registered
        timer_components = [
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        ]

        assert len(timer_components) == 1

        # Only scheduled_agent should have a timer task
        timer_component = timer_components[0]
        assert "scheduled_agent" in timer_component._timer_tasks
        assert "regular_agent" not in timer_component._timer_tasks
        assert len(timer_component._timer_tasks) == 1

        # Cleanup
        await orchestrator.shutdown()

    @pytest.mark.asyncio
    async def test_timer_component_initialization_idempotent(self):
        """Test TimerComponent initialization is idempotent (can be called multiple times).

        Given: An orchestrator with a scheduled agent
        When: _run_initialize is called multiple times
        Then: TimerComponent should only be initialized once
        """
        # Arrange
        orchestrator = Flock()

        agent = (
            orchestrator.agent("scheduled_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(seconds=30))
        )

        # Act - Initialize components multiple times
        await orchestrator._run_initialize()
        timer_component = next(
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        )
        initial_task_count = len(timer_component._timer_tasks)

        await orchestrator._run_initialize()  # Second call
        await orchestrator._run_initialize()  # Third call

        # Assert - Should still have only one timer task
        timer_components = [
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        ]

        assert len(timer_components) == 1
        assert len(timer_components[0]._timer_tasks) == initial_task_count

        # Cleanup
        await orchestrator.shutdown()


class TestTimerComponentIntegration:
    """Integration tests for TimerComponent with orchestrator lifecycle."""

    @pytest.mark.asyncio
    async def test_timer_component_shutdown_cleanup(self):
        """Test TimerComponent properly cleans up on shutdown.

        Given: An orchestrator with a scheduled agent and running timer tasks
        When: The orchestrator shuts down
        Then: All timer tasks should be cancelled and cleaned up
        """
        # Arrange
        orchestrator = Flock()

        agent = (
            orchestrator.agent("scheduled_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
            .schedule(every=timedelta(seconds=30))
        )

        # Act - Initialize and then shutdown
        await orchestrator._run_initialize()

        # Get timer component and verify tasks exist
        timer_component = next(
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        )

        assert len(timer_component._timer_tasks) > 0

        # Shutdown
        await orchestrator.shutdown()

        # Assert - All tasks should be done (cancelled or completed)
        for task in timer_component._timer_tasks.values():
            assert task.done(), "Timer tasks should be cancelled on shutdown"

    @pytest.mark.asyncio
    async def test_timer_component_no_registration_creates_no_tasks(self):
        """Test that without scheduled agents, no timer tasks are created.

        Given: An orchestrator with no scheduled agents
        When: The orchestrator runs through its lifecycle
        Then: No timer tasks should be created
        """
        # Arrange
        orchestrator = Flock()

        # Create only regular agents
        agent = (
            orchestrator.agent("regular_agent")
            .consumes(DummyInput)
            .publishes(DummyOutput)
        )

        # Act
        await orchestrator._run_initialize()

        # Assert - No TimerComponent should exist
        timer_components = [
            c for c in orchestrator._components if isinstance(c, TimerComponent)
        ]

        assert len(timer_components) == 0

        # Cleanup
        await orchestrator.shutdown()
