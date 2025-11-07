"""Tests for AgentContext (Context) timer metadata properties following strict TDD.

These tests verify that Context class provides properties to access timer metadata
when triggered by TimerTick artifacts, following the design specification.
"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.models.system_artifacts import TimerTick
from flock.utils.runtime import Context


class MockArtifact(BaseModel):
    """Mock artifact for testing non-timer triggers."""

    message: str = "test"


def test_agent_context_trigger_type_timer():
    """AgentContext.trigger_type returns 'timer' for TimerTick artifacts.

    When Context contains a single TimerTick artifact, trigger_type should
    return "timer" to indicate timer-based execution.
    """
    # Arrange
    tick = TimerTick(timer_name="test_agent", iteration=5)
    tick_artifact = Artifact(
        id=uuid4(),
        type="flock.models.system_artifacts.TimerTick",
        payload=tick.model_dump(),
        produced_by="timer_component",
    )
    ctx = Context(
        artifacts=[tick_artifact],
        task_id="task_123",
    )

    # Act & Assert
    assert ctx.trigger_type == "timer"


def test_agent_context_trigger_type_artifact():
    """AgentContext.trigger_type returns 'artifact' for normal artifacts.

    When Context contains non-TimerTick artifacts, trigger_type should
    return "artifact" to indicate normal artifact-based execution.
    """
    # Arrange
    mock_artifact = Artifact(
        id=uuid4(),
        type="MockArtifact",
        payload={"message": "test"},
        produced_by="some_agent",
    )
    ctx = Context(
        artifacts=[mock_artifact],
        task_id="task_456",
    )

    # Act & Assert
    assert ctx.trigger_type == "artifact"


def test_agent_context_trigger_type_empty_artifacts():
    """AgentContext.trigger_type returns 'artifact' for empty artifact list.

    When Context has no artifacts, trigger_type should default to "artifact".
    """
    # Arrange
    ctx = Context(
        artifacts=[],
        task_id="task_789",
    )

    # Act & Assert
    assert ctx.trigger_type == "artifact"


def test_agent_context_trigger_type_multiple_artifacts():
    """AgentContext.trigger_type returns 'artifact' for multiple artifacts.

    When Context contains multiple artifacts, trigger_type should return
    "artifact" even if one is TimerTick, since timer execution always
    provides exactly one TimerTick artifact.
    """
    # Arrange
    tick = TimerTick(timer_name="test_agent", iteration=5)
    tick_artifact = Artifact(
        id=uuid4(),
        type="flock.models.system_artifacts.TimerTick",
        payload=tick.model_dump(),
        produced_by="timer_component",
    )
    other_artifact = Artifact(
        id=uuid4(),
        type="MockArtifact",
        payload={"message": "test"},
        produced_by="some_agent",
    )
    ctx = Context(
        artifacts=[tick_artifact, other_artifact],
        task_id="task_multi",
    )

    # Act & Assert
    assert ctx.trigger_type == "artifact"


def test_agent_context_timer_iteration():
    """AgentContext.timer_iteration returns iteration count from TimerTick.

    When triggered by a timer, timer_iteration should return the iteration
    number from the TimerTick artifact's payload.
    """
    # Arrange
    tick = TimerTick(timer_name="test_agent", iteration=42)
    tick_artifact = Artifact(
        id=uuid4(),
        type="flock.models.system_artifacts.TimerTick",
        payload=tick.model_dump(),
        produced_by="timer_component",
    )
    ctx = Context(
        artifacts=[tick_artifact],
        task_id="task_iter",
    )

    # Act & Assert
    assert ctx.timer_iteration == 42


def test_agent_context_timer_iteration_none():
    """AgentContext.timer_iteration returns None for non-timer triggers.

    When not triggered by a timer, timer_iteration should return None.
    """
    # Arrange
    mock_artifact = Artifact(
        id=uuid4(),
        type="MockArtifact",
        payload={"message": "test"},
        produced_by="some_agent",
    )
    ctx = Context(
        artifacts=[mock_artifact],
        task_id="task_no_timer",
    )

    # Act & Assert
    assert ctx.timer_iteration is None


def test_agent_context_timer_iteration_empty_artifacts():
    """AgentContext.timer_iteration returns None for empty artifacts.

    When Context has no artifacts, timer_iteration should return None.
    """
    # Arrange
    ctx = Context(
        artifacts=[],
        task_id="task_empty",
    )

    # Act & Assert
    assert ctx.timer_iteration is None


def test_agent_context_fire_time():
    """AgentContext.fire_time returns fire_time datetime from TimerTick.

    When triggered by a timer, fire_time should return the datetime when
    the timer fired, extracted from the TimerTick artifact's payload.
    """
    # Arrange
    fire_time = datetime(2025, 10, 30, 12, 0, 0)
    tick = TimerTick(timer_name="test_agent", iteration=5, fire_time=fire_time)
    tick_artifact = Artifact(
        id=uuid4(),
        type="flock.models.system_artifacts.TimerTick",
        payload=tick.model_dump(),
        produced_by="timer_component",
    )
    ctx = Context(
        artifacts=[tick_artifact],
        task_id="task_fire",
    )

    # Act & Assert
    assert ctx.fire_time == fire_time


def test_agent_context_fire_time_none():
    """AgentContext.fire_time returns None for non-timer triggers.

    When not triggered by a timer, fire_time should return None.
    """
    # Arrange
    mock_artifact = Artifact(
        id=uuid4(),
        type="MockArtifact",
        payload={"message": "test"},
        produced_by="some_agent",
    )
    ctx = Context(
        artifacts=[mock_artifact],
        task_id="task_no_fire",
    )

    # Act & Assert
    assert ctx.fire_time is None


def test_agent_context_fire_time_empty_artifacts():
    """AgentContext.fire_time returns None for empty artifacts.

    When Context has no artifacts, fire_time should return None.
    """
    # Arrange
    ctx = Context(
        artifacts=[],
        task_id="task_empty_fire",
    )

    # Act & Assert
    assert ctx.fire_time is None


def test_agent_context_timer_iteration_with_zero():
    """AgentContext.timer_iteration correctly returns 0 for first iteration.

    Verify that iteration=0 (first timer fire) is properly returned,
    not confused with None or falsy values.
    """
    # Arrange
    tick = TimerTick(timer_name="test_agent", iteration=0)
    tick_artifact = Artifact(
        id=uuid4(),
        type="flock.models.system_artifacts.TimerTick",
        payload=tick.model_dump(),
        produced_by="timer_component",
    )
    ctx = Context(
        artifacts=[tick_artifact],
        task_id="task_zero_iter",
    )

    # Act & Assert
    assert ctx.timer_iteration == 0
    assert ctx.timer_iteration is not None


def test_agent_context_all_timer_properties_together():
    """Test all timer properties work correctly together.

    Comprehensive test verifying trigger_type, timer_iteration, and fire_time
    all return expected values for a timer-triggered context.
    """
    # Arrange
    fire_time = datetime(2025, 10, 30, 15, 30, 45)
    tick = TimerTick(
        timer_name="scheduler_agent",
        iteration=10,
        fire_time=fire_time,
    )
    tick_artifact = Artifact(
        id=uuid4(),
        type="flock.models.system_artifacts.TimerTick",
        payload=tick.model_dump(),
        produced_by="timer_component",
    )
    ctx = Context(
        artifacts=[tick_artifact],
        task_id="task_comprehensive",
    )

    # Act & Assert - All properties should work
    assert ctx.trigger_type == "timer"
    assert ctx.timer_iteration == 10
    assert ctx.fire_time == fire_time


def test_agent_context_all_properties_for_artifact_trigger():
    """Test all timer properties return appropriate values for artifact triggers.

    Comprehensive test verifying trigger_type, timer_iteration, and fire_time
    all return appropriate values for a normal artifact-triggered context.
    """
    # Arrange
    mock_artifact = Artifact(
        id=uuid4(),
        type="MockArtifact",
        payload={"message": "regular execution"},
        produced_by="regular_agent",
    )
    ctx = Context(
        artifacts=[mock_artifact],
        task_id="task_artifact_comprehensive",
    )

    # Act & Assert - All properties should indicate non-timer trigger
    assert ctx.trigger_type == "artifact"
    assert ctx.timer_iteration is None
    assert ctx.fire_time is None
