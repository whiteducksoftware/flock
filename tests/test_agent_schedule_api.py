"""Tests for AgentBuilder.schedule() method.

Tests the fluent API for timer-based agent scheduling following TDD approach.

Requirements:
- schedule() creates ScheduleSpec with interval/at/cron parameters
- Auto-subscribes to TimerTick filtered by agent name
- Returns self for method chaining
- Validates mutual exclusivity with batch processing
- Integrates seamlessly with existing builder pattern
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import pytest
from pydantic import BaseModel, Field

from flock import Flock
from flock.core.subscription import ScheduleSpec
from flock.models.system_artifacts import TimerTick
from flock.registry import flock_type


# Test artifact types
@flock_type(name="MockArtifact")
class MockArtifact(BaseModel):
    value: int = Field(description="Test value")


@flock_type(name="Result")
class Result(BaseModel):
    output: str = Field(description="Test output")


# ============================================================================
# Test 1: Basic interval scheduling
# ============================================================================


def test_agent_builder_schedule_with_interval():
    """AgentBuilder.schedule() with interval creates ScheduleSpec with interval."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act
    agent_builder = (
        flock.agent("health_check")
        .schedule(every=timedelta(seconds=30))
        .publishes(Result)
    )

    # Assert - Access underlying Agent via .agent property
    agent = agent_builder.agent
    assert hasattr(agent, "schedule_spec")
    assert agent.schedule_spec is not None
    assert isinstance(agent.schedule_spec, ScheduleSpec)
    assert agent.schedule_spec.interval == timedelta(seconds=30)
    assert agent.schedule_spec.at is None
    assert agent.schedule_spec.cron is None


# ============================================================================
# Test 2: Time-based scheduling (daily)
# ============================================================================


def test_agent_builder_schedule_with_time():
    """AgentBuilder.schedule() with time creates daily schedule."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act
    agent_builder = (
        flock.agent("daily_report")
        .schedule(at=time(hour=17, minute=0))
        .publishes(Result)
    )

    # Assert
    agent = agent_builder.agent
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.at == time(hour=17, minute=0)
    assert agent.schedule_spec.interval is None
    assert agent.schedule_spec.cron is None


# ============================================================================
# Test 3: Datetime-based scheduling (one-time)
# ============================================================================


def test_agent_builder_schedule_with_datetime():
    """AgentBuilder.schedule() with datetime creates one-time schedule."""
    # Arrange
    flock = Flock("openai/gpt-4")
    target_time = datetime(2025, 11, 1, 9, 0)

    # Act
    agent_builder = (
        flock.agent("one_time_task").schedule(at=target_time).publishes(Result)
    )

    # Assert
    agent = agent_builder.agent
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.at == target_time
    assert agent.schedule_spec.interval is None
    assert agent.schedule_spec.cron is None


# ============================================================================
# Test 4: Auto-subscribes to TimerTick with filter
# ============================================================================


def test_schedule_auto_subscribes_to_timer_tick():
    """AgentBuilder.schedule() auto-subscribes to TimerTick filtered by timer_name."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act
    agent_builder = (
        flock.agent("scheduled_agent")
        .schedule(every=timedelta(seconds=30))
        .publishes(Result)
    )

    # Assert - Verify subscription exists
    agent = agent_builder.agent
    assert len(agent.subscriptions) == 1

    subscription = agent.subscriptions[0]
    assert TimerTick in subscription.type_models
    assert len(subscription.type_models) == 1

    # Verify filter predicate exists
    assert subscription.where is not None
    assert len(subscription.where) == 1
    predicate = subscription.where[0]

    # Test predicate filters by timer_name
    matching_tick = TimerTick(timer_name="scheduled_agent", iteration=0)
    non_matching_tick = TimerTick(timer_name="other_agent", iteration=0)

    assert predicate(matching_tick) is True
    assert predicate(non_matching_tick) is False


# ============================================================================
# Test 5: Mutual exclusivity with batch processing
# ============================================================================


def test_schedule_with_batch_raises_error():
    """AgentBuilder raises error when schedule() is added after batch."""
    from flock.core.subscription import BatchSpec

    # Arrange
    flock = Flock("openai/gpt-4")

    # Act & Assert - Should raise ValueError when adding schedule after batch
    with pytest.raises(ValueError, match="mutually exclusive"):
        agent_builder = (
            flock.agent("invalid_agent")
            .consumes(MockArtifact, batch=BatchSpec(size=10))
            .schedule(every=timedelta(seconds=30))
            .publishes(Result)
        )


# ============================================================================
# Test 6: Fluent API chaining
# ============================================================================


def test_schedule_returns_self_for_chaining():
    """AgentBuilder.schedule() returns self for method chaining."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act - Chain multiple builder methods
    agent_builder = flock.agent("chained_agent")
    result = agent_builder.schedule(every=timedelta(seconds=60))

    # Assert - schedule() returns AgentBuilder instance
    assert result is agent_builder
    assert result.agent.schedule_spec is not None

    # Verify chaining continues to work (description returns self)
    after_description = result.description("A scheduled agent with chaining")
    assert after_description is agent_builder
    assert after_description.agent.description == "A scheduled agent with chaining"

    # publishes() returns PublishBuilder (different type for conditional publishing)
    # but underlying agent should still have the configuration
    final_builder = after_description.publishes(Result)
    assert final_builder.agent.description == "A scheduled agent with chaining"
    assert final_builder.agent.schedule_spec is not None


# ============================================================================
# Test 7: Schedule with after parameter
# ============================================================================


def test_agent_builder_schedule_with_after():
    """AgentBuilder.schedule() with after parameter sets initial delay."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act
    agent_builder = (
        flock.agent("delayed_agent")
        .schedule(every=timedelta(seconds=30), after=timedelta(seconds=10))
        .publishes(Result)
    )

    # Assert
    agent = agent_builder.agent
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.interval == timedelta(seconds=30)
    assert agent.schedule_spec.after == timedelta(seconds=10)


# ============================================================================
# Test 8: Schedule with max_repeats parameter
# ============================================================================


def test_agent_builder_schedule_with_max_repeats():
    """AgentBuilder.schedule() with max_repeats limits execution count."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act
    agent_builder = (
        flock.agent("limited_agent")
        .schedule(every=timedelta(seconds=5), max_repeats=10)
        .publishes(Result)
    )

    # Assert
    agent = agent_builder.agent
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.interval == timedelta(seconds=5)
    assert agent.schedule_spec.max_repeats == 10


# ============================================================================
# Test 9: Schedule integration with existing builder methods
# ============================================================================


def test_schedule_integrates_with_existing_builder_methods():
    """AgentBuilder.schedule() works alongside description() and publishes()."""
    # Arrange
    flock = Flock("openai/gpt-4")

    # Act - Use multiple builder methods together
    agent_builder = (
        flock.agent("integrated_agent")
        .description("Performs health checks every 30 seconds")
        .schedule(every=timedelta(seconds=30))
        .publishes(Result)
    )

    # Assert - All configuration should be present
    agent = agent_builder.agent
    assert agent.name == "integrated_agent"
    assert agent.description == "Performs health checks every 30 seconds"
    assert agent.schedule_spec is not None
    assert agent.schedule_spec.interval == timedelta(seconds=30)
    assert len(agent.output_groups) == 1  # publishes() created output group
    assert len(agent.subscriptions) == 1  # schedule() created subscription
