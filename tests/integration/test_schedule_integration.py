"""Integration tests for Phase 1: Timer Scheduling Infrastructure.

These tests verify that all Phase 1 components work together correctly:
- ScheduleSpec: Schedule specification validation
- TimerTick: System artifact for timer triggers
- AgentBuilder.schedule(): Fluent API for scheduling
- AgentContext timer properties: trigger_type, timer_iteration, fire_time
- Auto-subscription to TimerTick with filtering
- Validation (schedule + batch are mutually exclusive)
"""

from datetime import datetime, time, timedelta

import pytest
from pydantic import BaseModel, Field

from flock import Flock
from flock.core.agent import Agent
from flock.core.subscription import BatchSpec, ScheduleSpec
from flock.models.system_artifacts import TimerTick
from flock.registry import flock_type


# Test artifact types
@flock_type
class HealthStatus(BaseModel):
    """Test artifact for scheduled health checks."""

    cpu: float = Field(description="CPU usage percentage")
    timestamp: datetime = Field(default_factory=datetime.now)


@flock_type
class DailyReport(BaseModel):
    """Test artifact for daily reports."""

    summary: str = Field(description="Report summary")
    count: int = Field(description="Item count")


@flock_type
class MetricData(BaseModel):
    """Test artifact for metrics."""

    value: float = Field(description="Metric value")
    name: str = Field(description="Metric name")


# ============================================================================
# Test 1: Agent creation with schedule_spec
# ============================================================================


def test_agent_with_schedule_spec_created():
    """Verify agent is created with schedule_spec field populated.

    Integration test verifying:
    - AgentBuilder.schedule() creates ScheduleSpec
    - Agent.schedule_spec field is populated correctly
    - ScheduleSpec parameters are preserved
    """
    # Arrange
    flock = Flock()

    # Act - Create agent with interval-based schedule
    agent_builder = (
        flock.agent("health_monitor")
        .schedule(
            every=timedelta(seconds=30), after=timedelta(seconds=5), max_repeats=10
        )
        .publishes(HealthStatus)
    )

    agent = agent_builder.agent

    # Assert - Agent should have schedule_spec
    assert isinstance(agent, Agent)
    assert agent.schedule_spec is not None
    assert isinstance(agent.schedule_spec, ScheduleSpec)

    # Verify schedule parameters
    assert agent.schedule_spec.interval == timedelta(seconds=30)
    assert agent.schedule_spec.after == timedelta(seconds=5)
    assert agent.schedule_spec.max_repeats == 10
    assert agent.schedule_spec.at is None
    assert agent.schedule_spec.cron is None


def test_agent_with_daily_time_schedule():
    """Verify agent created with daily time-based schedule.

    Integration test verifying:
    - AgentBuilder.schedule(at=time(...)) works
    - ScheduleSpec stores time correctly
    """
    # Arrange
    flock = Flock()

    # Act - Create agent with daily schedule at 5 PM
    agent_builder = (
        flock.agent("daily_reporter")
        .schedule(at=time(hour=17, minute=0))
        .publishes(DailyReport)
    )

    agent = agent_builder.agent

    # Assert
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.at == time(hour=17, minute=0)
    assert agent.schedule_spec.interval is None
    assert agent.schedule_spec.cron is None


def test_agent_with_datetime_schedule():
    """Verify agent created with one-time datetime schedule.

    Integration test verifying:
    - AgentBuilder.schedule(at=datetime(...)) works
    - ScheduleSpec stores datetime correctly
    """
    # Arrange
    flock = Flock()
    scheduled_time = datetime(2025, 11, 1, 9, 0, 0)

    # Act - Create agent with one-time schedule
    agent_builder = (
        flock.agent("one_time_task").schedule(at=scheduled_time).publishes(MetricData)
    )

    agent = agent_builder.agent

    # Assert
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.at == scheduled_time
    assert agent.schedule_spec.interval is None


# ============================================================================
# Test 2: Auto-subscription to TimerTick
# ============================================================================


def test_schedule_auto_subscription_works():
    """Verify schedule() auto-subscribes to TimerTick with correct filter.

    Integration test verifying:
    - AgentBuilder.schedule() creates subscription to TimerTick
    - Subscription has filter predicate for timer_name
    - Filter correctly matches agent's own timer
    - Filter correctly rejects other agent's timer
    """
    # Arrange
    flock = Flock()

    # Act - Create scheduled agent
    agent_builder = (
        flock.agent("test_agent")
        .schedule(every=timedelta(seconds=30))
        .publishes(HealthStatus)
    )

    agent = agent_builder.agent

    # Assert - Agent should have subscription to TimerTick
    assert len(agent.subscriptions) == 1
    subscription = agent.subscriptions[0]

    # Verify subscription type
    assert TimerTick in subscription.type_models

    # Verify filter predicate exists
    assert len(subscription.where) == 1
    filter_predicate = subscription.where[0]

    # Test filter with matching timer
    matching_tick = TimerTick(timer_name="test_agent", iteration=0)
    assert filter_predicate(matching_tick) is True

    # Test filter with non-matching timer
    non_matching_tick = TimerTick(timer_name="other_agent", iteration=0)
    assert filter_predicate(non_matching_tick) is False


def test_schedule_with_additional_consumes():
    """Verify schedule() can be combined with consumes() for context filtering.

    Integration test verifying:
    - Agent can have both TimerTick subscription and other subscriptions
    - Multiple subscriptions coexist correctly
    """
    # Arrange
    flock = Flock()

    # Act - Create agent with schedule + consumes
    agent_builder = (
        flock.agent("context_monitor")
        .schedule(every=timedelta(seconds=60))
        .consumes(MetricData, where=lambda m: m.value > 100.0)
        .publishes(DailyReport)
    )

    agent = agent_builder.agent

    # Assert - Agent should have TWO subscriptions
    assert len(agent.subscriptions) == 2

    # Find TimerTick subscription
    timer_sub = next(
        (sub for sub in agent.subscriptions if TimerTick in sub.type_models), None
    )
    assert timer_sub is not None

    # Find MetricData subscription
    metric_sub = next(
        (sub for sub in agent.subscriptions if MetricData in sub.type_models), None
    )
    assert metric_sub is not None
    assert len(metric_sub.where) == 1  # Has filter predicate


# ============================================================================
# Test 3: Schedule + Batch validation
# ============================================================================


def test_schedule_batch_validation_integrated():
    """Verify batch() THEN schedule() raises ValueError.

    Integration test verifying:
    - AgentBuilder validates schedule + batch are mutually exclusive
    - Error message is clear and helpful
    - Validation happens when schedule() is called after consumes with batch
    """
    # Arrange
    flock = Flock()

    # Act & Assert - batch() THEN schedule() should raise
    with pytest.raises(ValueError, match="mutually exclusive"):
        (
            flock.agent("invalid_agent")
            .consumes(MetricData, batch=BatchSpec(size=10))
            .schedule(every=timedelta(seconds=30))
            .publishes(DailyReport)
        )


def test_batch_with_schedule_validation_comprehensive():
    """Verify schedule + batch validation is comprehensive.

    Integration test verifying:
    - Multiple batch subscriptions also raise error when schedule() called
    - Validation message is consistent
    """
    # Arrange
    flock = Flock()

    # Act & Assert - Multiple batch subscriptions, then schedule
    with pytest.raises(ValueError, match="mutually exclusive"):
        (
            flock.agent("invalid_agent_2")
            .consumes(MetricData, batch=BatchSpec(size=10))
            .consumes(HealthStatus, batch=BatchSpec(size=5))
            .schedule(every=timedelta(seconds=30))
            .publishes(DailyReport)
        )


# ============================================================================
# Test 4: Scheduled agent has timer properties in context
# ============================================================================


def test_scheduled_agent_has_timer_properties():
    """Verify scheduled agents can access timer metadata via context.

    Integration test verifying:
    - Agent can be configured with schedule
    - Context properties (trigger_type, timer_iteration, fire_time) are accessible
    - This is a configuration test, not an execution test
    """
    # Arrange
    flock = Flock()

    # Act - Create scheduled agent that would use context properties
    agent_builder = (
        flock.agent("timer_aware")
        .schedule(every=timedelta(seconds=30))
        .publishes(HealthStatus)
    )

    agent = agent_builder.agent

    # Assert - Agent is configured correctly
    assert agent.schedule_spec is not None
    assert len(agent.subscriptions) == 1

    # Verify subscription to TimerTick (enables timer properties)
    subscription = agent.subscriptions[0]
    assert TimerTick in subscription.type_models

    # Note: Actual context properties are tested in test_agent_context_timer.py
    # This integration test verifies the agent configuration that enables them


# ============================================================================
# Test 5: Multiple scheduled agents
# ============================================================================


def test_multiple_scheduled_agents():
    """Verify multiple agents can be scheduled with different schedules.

    Integration test verifying:
    - Multiple agents can each have schedule_spec
    - Each agent gets its own TimerTick subscription
    - Filters correctly isolate each agent's timer
    """
    # Arrange
    flock = Flock()

    # Act - Create multiple scheduled agents
    agent1_builder = (
        flock.agent("fast_monitor")
        .schedule(every=timedelta(seconds=10))
        .publishes(HealthStatus)
    )

    agent2_builder = (
        flock.agent("slow_monitor")
        .schedule(every=timedelta(minutes=5))
        .publishes(HealthStatus)
    )

    agent3_builder = (
        flock.agent("daily_reporter")
        .schedule(at=time(hour=17, minute=0))
        .publishes(DailyReport)
    )

    agent1 = agent1_builder.agent
    agent2 = agent2_builder.agent
    agent3 = agent3_builder.agent

    # Assert - All agents have schedule_spec
    assert agent1.schedule_spec is not None
    assert agent2.schedule_spec is not None
    assert agent3.schedule_spec is not None

    # Verify different schedule types
    assert agent1.schedule_spec.interval == timedelta(seconds=10)
    assert agent2.schedule_spec.interval == timedelta(minutes=5)
    assert agent3.schedule_spec.at == time(hour=17, minute=0)

    # All should have TimerTick subscriptions
    assert len(agent1.subscriptions) == 1
    assert len(agent2.subscriptions) == 1
    assert len(agent3.subscriptions) == 1

    # Verify filters are agent-specific
    filter1 = agent1.subscriptions[0].where[0]
    filter2 = agent2.subscriptions[0].where[0]
    filter3 = agent3.subscriptions[0].where[0]

    # Test cross-agent isolation
    tick1 = TimerTick(timer_name="fast_monitor", iteration=0)
    tick2 = TimerTick(timer_name="slow_monitor", iteration=0)
    tick3 = TimerTick(timer_name="daily_reporter", iteration=0)

    # Each filter should only match its own timer
    assert filter1(tick1) is True
    assert filter1(tick2) is False
    assert filter1(tick3) is False

    assert filter2(tick1) is False
    assert filter2(tick2) is True
    assert filter2(tick3) is False

    assert filter3(tick1) is False
    assert filter3(tick2) is False
    assert filter3(tick3) is True


# ============================================================================
# Test 6: ScheduleSpec validation integration
# ============================================================================


def test_schedule_spec_validation_via_builder():
    """Verify ScheduleSpec validation works through AgentBuilder.

    Integration test verifying:
    - Invalid schedule parameters raise ValueError
    - Validation happens at schedule() call time
    """
    # Arrange
    flock = Flock()

    # Act & Assert - No schedule parameters should raise
    with pytest.raises(ValueError, match="Exactly one"):
        flock.agent("invalid_no_params").schedule().publishes(HealthStatus)

    # Multiple schedule parameters should raise
    with pytest.raises(ValueError, match="Exactly one"):
        (
            flock.agent("invalid_multiple_params")
            .schedule(every=timedelta(seconds=30), at=time(hour=17))
            .publishes(HealthStatus)
        )


def test_schedule_interval_only():
    """Verify interval-only schedule is valid."""
    # Arrange
    flock = Flock()

    # Act
    agent_builder = (
        flock.agent("interval_agent")
        .schedule(every=timedelta(seconds=30))
        .publishes(HealthStatus)
    )

    # Assert
    assert agent_builder.agent.schedule_spec.interval == timedelta(seconds=30)
    assert agent_builder.agent.schedule_spec.at is None
    assert agent_builder.agent.schedule_spec.cron is None


def test_schedule_time_only():
    """Verify time-only schedule is valid."""
    # Arrange
    flock = Flock()

    # Act
    agent_builder = (
        flock.agent("time_agent").schedule(at=time(hour=12)).publishes(DailyReport)
    )

    # Assert
    assert agent_builder.agent.schedule_spec.at == time(hour=12)
    assert agent_builder.agent.schedule_spec.interval is None
    assert agent_builder.agent.schedule_spec.cron is None


# ============================================================================
# Test 7: Schedule with max_repeats and after
# ============================================================================


def test_schedule_with_options():
    """Verify schedule() with after and max_repeats options.

    Integration test verifying:
    - Optional parameters (after, max_repeats) are stored correctly
    - Options work with different schedule types
    """
    # Arrange
    flock = Flock()

    # Act - Interval with options
    agent1_builder = (
        flock.agent("limited_monitor")
        .schedule(
            every=timedelta(seconds=30), after=timedelta(seconds=10), max_repeats=5
        )
        .publishes(HealthStatus)
    )

    # Act - Daily time with delay
    agent2_builder = (
        flock.agent("delayed_daily")
        .schedule(at=time(hour=17), after=timedelta(minutes=30))
        .publishes(DailyReport)
    )

    agent1 = agent1_builder.agent
    agent2 = agent2_builder.agent

    # Assert - Options are stored
    assert agent1.schedule_spec.after == timedelta(seconds=10)
    assert agent1.schedule_spec.max_repeats == 5

    assert agent2.schedule_spec.after == timedelta(minutes=30)
    assert agent2.schedule_spec.max_repeats is None  # Not specified


# ============================================================================
# Test 8: TimerTick artifact structure
# ============================================================================


def test_timer_tick_artifact_structure():
    """Verify TimerTick artifact has correct structure.

    Integration test verifying:
    - TimerTick can be instantiated
    - All required fields are present
    - Fields have correct types
    - TimerTick is immutable (frozen)
    """
    # Arrange
    fire_time = datetime(2025, 10, 30, 12, 0, 0)
    schedule_dict = {"interval": 30, "after": None}

    # Act
    tick = TimerTick(
        timer_name="test_agent",
        fire_time=fire_time,
        iteration=42,
        schedule_spec=schedule_dict,
    )

    # Assert - All fields present
    assert tick.timer_name == "test_agent"
    assert tick.fire_time == fire_time
    assert tick.iteration == 42
    assert tick.schedule_spec == schedule_dict

    # Verify immutability
    with pytest.raises(Exception):  # Pydantic raises ValidationError for frozen models
        tick.iteration = 43


def test_timer_tick_default_values():
    """Verify TimerTick default values work correctly."""
    # Arrange & Act
    tick = TimerTick(timer_name="test_agent")

    # Assert - Defaults are applied
    assert tick.timer_name == "test_agent"
    assert isinstance(tick.fire_time, datetime)
    assert tick.iteration == 0
    assert tick.schedule_spec == {}


# ============================================================================
# Test 9: Agent builder method chaining
# ============================================================================


def test_schedule_method_chaining():
    """Verify schedule() supports fluent method chaining.

    Integration test verifying:
    - schedule() returns AgentBuilder
    - Can chain with publishes()
    - Can chain with consumes()
    - Can chain with other builder methods
    """
    # Arrange
    flock = Flock()

    # Act - Complex chaining
    agent_builder = (
        flock.agent("chained_agent")
        .description("Test agent for method chaining")
        .schedule(every=timedelta(seconds=30))
        .consumes(MetricData, where=lambda m: m.value > 0)
        .publishes(HealthStatus)
        .publishes(DailyReport)
    )

    agent = agent_builder.agent

    # Assert - All configurations applied
    assert agent.name == "chained_agent"
    assert agent.description == "Test agent for method chaining"
    assert agent.schedule_spec is not None
    assert len(agent.subscriptions) == 2  # TimerTick + MetricData
    assert len(agent.output_groups) == 2  # Two publishes() calls


# ============================================================================
# Test 10: Integration with orchestrator agent registration
# ============================================================================


def test_scheduled_agent_registered_with_orchestrator():
    """Verify scheduled agents are properly registered with orchestrator.

    Integration test verifying:
    - Scheduled agent can be retrieved from orchestrator
    - Agent maintains schedule_spec after registration
    - Orchestrator knows about the agent
    """
    # Arrange
    flock = Flock()

    # Act - Create and register scheduled agent
    agent_builder = (
        flock.agent("registered_agent")
        .schedule(every=timedelta(seconds=30))
        .publishes(HealthStatus)
    )

    # Retrieve from orchestrator
    retrieved_agent = flock.get_agent("registered_agent")

    # Assert - Agent is registered correctly
    assert retrieved_agent is not None
    assert retrieved_agent.name == "registered_agent"
    assert retrieved_agent.schedule_spec is not None
    assert retrieved_agent.schedule_spec.interval == timedelta(seconds=30)

    # Verify it's the same agent instance
    assert retrieved_agent is agent_builder.agent


def test_multiple_agents_with_orchestrator():
    """Verify multiple scheduled agents work with orchestrator."""
    # Arrange
    flock = Flock()

    # Act - Create multiple scheduled agents
    (
        flock.agent("agent_1")
        .schedule(every=timedelta(seconds=10))
        .publishes(HealthStatus)
    )

    (flock.agent("agent_2").schedule(every=timedelta(minutes=1)).publishes(MetricData))

    (flock.agent("agent_3").schedule(at=time(hour=9, minute=0)).publishes(DailyReport))

    # Assert - All agents registered
    assert flock.get_agent("agent_1") is not None
    assert flock.get_agent("agent_2") is not None
    assert flock.get_agent("agent_3") is not None

    # Verify schedule specs preserved
    assert flock.get_agent("agent_1").schedule_spec.interval == timedelta(seconds=10)
    assert flock.get_agent("agent_2").schedule_spec.interval == timedelta(minutes=1)
    assert flock.get_agent("agent_3").schedule_spec.at == time(hour=9, minute=0)
