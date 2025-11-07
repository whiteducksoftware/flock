"""Tests for TimerTick system artifact following strict TDD.

TimerTick is an internal artifact published by timer component to trigger scheduled agents.
Must be immutable (frozen=True) and follow existing system artifact patterns.
"""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from flock.models.system_artifacts import TimerTick
from flock.registry import type_registry


def test_timer_tick_creation():
    """Test basic instantiation with all fields."""
    # Arrange
    timer_name = "test_timer"
    fire_time = datetime(2025, 10, 30, 12, 0, 0, tzinfo=UTC)
    iteration = 5
    schedule_spec = {"cron": "0 12 * * *", "timezone": "UTC"}

    # Act
    tick = TimerTick(
        timer_name=timer_name,
        fire_time=fire_time,
        iteration=iteration,
        schedule_spec=schedule_spec,
    )

    # Assert
    assert tick.timer_name == timer_name
    assert tick.fire_time == fire_time
    assert tick.iteration == iteration
    assert tick.schedule_spec == schedule_spec


def test_timer_tick_creation_with_defaults():
    """Test instantiation with default values for optional fields."""
    # Arrange
    timer_name = "minimal_timer"

    # Act
    tick = TimerTick(timer_name=timer_name)

    # Assert
    assert tick.timer_name == timer_name
    assert isinstance(tick.fire_time, datetime)
    assert tick.iteration == 0
    assert tick.schedule_spec == {}


def test_timer_tick_immutable():
    """Verify frozen=True prevents modification."""
    # Arrange
    tick = TimerTick(
        timer_name="test_timer",
        fire_time=datetime(2025, 10, 30, 12, 0, 0, tzinfo=UTC),
        iteration=1,
        schedule_spec={"cron": "0 12 * * *"},
    )

    # Act & Assert - Attempting to modify should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        tick.timer_name = "modified_timer"

    # Verify it's a frozen instance error
    error_str = str(exc_info.value).lower()
    assert (
        "frozen" in error_str
        or "immutable" in error_str
        or "instance is frozen" in error_str
    )


def test_timer_tick_immutable_all_fields():
    """Verify all fields are immutable."""
    # Arrange
    tick = TimerTick(timer_name="test_timer")

    # Act & Assert - Test each field
    with pytest.raises(ValidationError):
        tick.fire_time = datetime.now(tz=UTC)

    with pytest.raises(ValidationError):
        tick.iteration = 99

    with pytest.raises(ValidationError):
        tick.schedule_spec = {"new": "value"}


def test_timer_tick_serialization():
    """Test JSON round-trip (model_dump/model_validate)."""
    # Arrange
    original_tick = TimerTick(
        timer_name="serialization_test",
        fire_time=datetime(2025, 10, 30, 15, 30, 0, tzinfo=UTC),
        iteration=3,
        schedule_spec={"cron": "30 15 * * *", "timezone": "America/New_York"},
    )

    # Act - Serialize to dict
    dumped = original_tick.model_dump()

    # Assert - Verify dumped structure
    assert dumped["timer_name"] == "serialization_test"
    assert isinstance(dumped["fire_time"], datetime)
    assert dumped["iteration"] == 3
    assert dumped["schedule_spec"]["cron"] == "30 15 * * *"

    # Act - Deserialize back to model
    restored_tick = TimerTick.model_validate(dumped)

    # Assert - Verify restored model matches original
    assert restored_tick.timer_name == original_tick.timer_name
    assert restored_tick.fire_time == original_tick.fire_time
    assert restored_tick.iteration == original_tick.iteration
    assert restored_tick.schedule_spec == original_tick.schedule_spec


def test_timer_tick_json_serialization():
    """Test JSON string round-trip (model_dump_json/model_validate_json)."""
    # Arrange
    original_tick = TimerTick(
        timer_name="json_test",
        fire_time=datetime(2025, 10, 30, 10, 0, 0, tzinfo=UTC),
        iteration=10,
        schedule_spec={"interval": 60},
    )

    # Act - Serialize to JSON string
    json_str = original_tick.model_dump_json()

    # Assert - Verify JSON string is valid
    assert isinstance(json_str, str)
    assert "json_test" in json_str

    # Act - Deserialize from JSON string
    restored_tick = TimerTick.model_validate_json(json_str)

    # Assert - Verify restored model matches original
    assert restored_tick.timer_name == original_tick.timer_name
    assert restored_tick.fire_time == original_tick.fire_time
    assert restored_tick.iteration == original_tick.iteration
    assert restored_tick.schedule_spec == original_tick.schedule_spec


def test_timer_tick_registered_as_flock_type():
    """Verify @flock_type registration."""
    # Act - Check if TimerTick is registered in the registry using simple name
    registered_type = type_registry.resolve_name("TimerTick")

    # Assert - Verify registration with simple name resolves to full name
    assert registered_type is not None, (
        "TimerTick should be registered with @flock_type"
    )
    assert registered_type == "flock.models.system_artifacts.TimerTick"

    # Act - Resolve the class using the full name
    resolved_class = type_registry.resolve(registered_type)

    # Assert - Verify resolved class is TimerTick
    assert resolved_class == TimerTick, "Registered type should be TimerTick class"


def test_timer_tick_required_fields():
    """Test that timer_name is required."""
    # Act & Assert - Missing required field should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        TimerTick()

    # Verify the error is about the missing timer_name field
    error_str = str(exc_info.value).lower()
    assert "timer_name" in error_str or "field required" in error_str


def test_timer_tick_fire_time_type():
    """Test that fire_time must be a datetime."""
    # Act & Assert - Invalid type should raise ValidationError
    with pytest.raises(ValidationError):
        TimerTick(
            timer_name="test_timer",
            fire_time="not-a-datetime",
        )


def test_timer_tick_iteration_type():
    """Test that iteration must be an integer."""
    # Act & Assert - Invalid type should raise ValidationError
    with pytest.raises(ValidationError):
        TimerTick(
            timer_name="test_timer",
            iteration="not-an-int",
        )


def test_timer_tick_schedule_spec_type():
    """Test that schedule_spec must be a dict."""
    # Act & Assert - Invalid type should raise ValidationError
    with pytest.raises(ValidationError):
        TimerTick(
            timer_name="test_timer",
            schedule_spec="not-a-dict",
        )


def test_timer_tick_equality():
    """Test that two TimerTick instances with same data are equal."""
    # Arrange
    fire_time = datetime(2025, 10, 30, 12, 0, 0, tzinfo=UTC)
    tick1 = TimerTick(
        timer_name="test_timer",
        fire_time=fire_time,
        iteration=1,
        schedule_spec={"cron": "0 12 * * *"},
    )
    tick2 = TimerTick(
        timer_name="test_timer",
        fire_time=fire_time,
        iteration=1,
        schedule_spec={"cron": "0 12 * * *"},
    )

    # Assert
    assert tick1 == tick2


def test_timer_tick_inequality():
    """Test that two TimerTick instances with different data are not equal."""
    # Arrange
    tick1 = TimerTick(timer_name="timer1", iteration=1)
    tick2 = TimerTick(timer_name="timer2", iteration=2)

    # Assert
    assert tick1 != tick2
