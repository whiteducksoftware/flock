"""
Tests for ScheduleSpec - Timer-Based Scheduling

ScheduleSpec allows agents to be triggered on timer-based schedules:
1. Interval-based (periodic): Every N seconds/minutes/hours
2. Time-based (daily): At specific time each day
3. Datetime-based (one-time): At specific datetime
4. Cron-based (advanced): Cron expression (future)

Test-Driven Development (TDD):
- Tests written FIRST
- Implementation SECOND
- Green tests = working feature
"""

from datetime import datetime, time, timedelta

import pytest

from flock.core.subscription import ScheduleSpec


# ============================================================================
# Phase 1: ScheduleSpec Validation Tests
# ============================================================================


def test_schedule_spec_interval_only():
    """
    GIVEN: ScheduleSpec with only interval specified
    WHEN: Spec is created
    THEN: Valid spec with interval set, other triggers None

    Real-world: Run agent every 30 seconds (periodic health check).
    """
    spec = ScheduleSpec(interval=timedelta(seconds=30))
    assert spec.interval == timedelta(seconds=30)
    assert spec.at is None
    assert spec.cron is None
    assert spec.after is None
    assert spec.max_repeats is None


def test_schedule_spec_time_only():
    """
    GIVEN: ScheduleSpec with only time specified
    WHEN: Spec is created
    THEN: Valid spec with time set, other triggers None

    Real-world: Run agent at 5 PM every day (daily report generation).
    """
    spec = ScheduleSpec(at=time(hour=17, minute=0))
    assert spec.at == time(hour=17, minute=0)
    assert spec.interval is None
    assert spec.cron is None


def test_schedule_spec_datetime_only():
    """
    GIVEN: ScheduleSpec with only datetime specified
    WHEN: Spec is created
    THEN: Valid spec with datetime set, other triggers None

    Real-world: Run agent once at specific datetime (scheduled one-time task).
    """
    dt = datetime(2025, 11, 1, 9, 0)
    spec = ScheduleSpec(at=dt)
    assert spec.at == dt
    assert spec.interval is None
    assert spec.cron is None


def test_schedule_spec_multiple_triggers_raises():
    """
    GIVEN: ScheduleSpec with multiple trigger types specified
    WHEN: Spec is created
    THEN: ValueError raised with message "Exactly one"

    Validation: Cannot specify both interval AND time (ambiguous).
    """
    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec(interval=timedelta(seconds=30), at=time(hour=17))

    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec(interval=timedelta(seconds=30), cron="0 * * * *")

    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec(at=time(hour=17), cron="0 * * * *")

    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec(interval=timedelta(seconds=30), at=time(hour=17), cron="0 * * * *")


def test_schedule_spec_no_triggers_raises():
    """
    GIVEN: ScheduleSpec with no trigger types specified
    WHEN: Spec is created
    THEN: ValueError raised with message "Exactly one"

    Validation: At least one trigger type is required.
    """
    with pytest.raises(ValueError, match="Exactly one"):
        ScheduleSpec()


def test_schedule_spec_with_options():
    """
    GIVEN: ScheduleSpec with interval AND optional after/max_repeats
    WHEN: Spec is created
    THEN: Valid spec with all options set

    Real-world: Wait 10 seconds, then run every 30 seconds, max 5 times.
    """
    spec = ScheduleSpec(
        interval=timedelta(seconds=30),
        after=timedelta(seconds=10),
        max_repeats=5,
    )
    assert spec.interval == timedelta(seconds=30)
    assert spec.after == timedelta(seconds=10)
    assert spec.max_repeats == 5
    assert spec.at is None
    assert spec.cron is None


def test_schedule_spec_cron_only():
    """
    GIVEN: ScheduleSpec with only cron specified
    WHEN: Spec is created
    THEN: Valid spec with cron set, other triggers None

    Real-world: Run agent using cron expression (advanced scheduling).
    """
    spec = ScheduleSpec(cron="0 * * * *")
    assert spec.cron == "0 * * * *"
    assert spec.interval is None
    assert spec.at is None


def test_schedule_spec_with_time_and_after():
    """
    GIVEN: ScheduleSpec with time AND after delay
    WHEN: Spec is created
    THEN: Valid spec with both set

    Real-world: Wait 1 hour, then run at 5 PM daily.
    """
    spec = ScheduleSpec(at=time(hour=17, minute=0), after=timedelta(hours=1))
    assert spec.at == time(hour=17, minute=0)
    assert spec.after == timedelta(hours=1)
    assert spec.interval is None


def test_schedule_spec_after_must_be_non_negative():
    """after must be >= 0 seconds."""
    with pytest.raises(ValueError, match="after must be >= 0"):
        ScheduleSpec(interval=timedelta(seconds=30), after=timedelta(seconds=-1))


def test_schedule_spec_max_repeats_must_be_positive():
    """max_repeats must be > 0 when provided."""
    with pytest.raises(ValueError, match="max_repeats must be > 0"):
        ScheduleSpec(interval=timedelta(seconds=30), max_repeats=0)

def test_schedule_spec_with_datetime_and_max_repeats():
    """
    GIVEN: ScheduleSpec with datetime (should be one-time)
    WHEN: max_repeats > 1 specified
    THEN: Valid spec (validation deferred to runtime)

    Note: max_repeats with datetime doesn't make logical sense,
    but we don't enforce this at the data model level.
    """
    dt = datetime(2025, 11, 1, 9, 0)
    spec = ScheduleSpec(at=dt, max_repeats=5)
    assert spec.at == dt
    assert spec.max_repeats == 5
