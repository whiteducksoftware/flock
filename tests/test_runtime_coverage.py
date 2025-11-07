"""Additional tests for runtime.py to improve coverage."""

from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import MagicMock

import pytest

from flock.core.artifacts import Artifact
from flock.models.system_artifacts import TimerTick
from flock.utils.runtime import Context


class TestRuntimeCoverage:
    """Tests to improve code coverage for runtime.py."""

    def test_timer_iteration_exception_handling(self):
        """Test timer_iteration property exception handling (lines 351-352)."""
        # Create Context with state containing invalid iter value
        ctx = Context(
            artifacts=[],
            task_id="test_task",
            store=MagicMock(),
            agent=MagicMock(),
            trigger_type="timer",
            state={"__timer__": {"iter": "invalid"}},  # Should cause int() to fail
        )
        
        # Should return None on exception
        result = ctx.timer_iteration
        assert result is None

    def test_fire_time_exception_handling(self):
        """Test fire_time property exception handling (lines 377-384)."""
        # Create Context with state containing invalid fire_time string
        ctx = Context(
            artifacts=[],
            task_id="test_task",
            store=MagicMock(),
            agent=MagicMock(),
            trigger_type="timer",
            state={"__timer__": {"fire": "invalid-datetime-string"}},
        )
        
        # Should return None on exception
        result = ctx.fire_time
        assert result is None

    def test_fire_time_string_parsing_from_artifacts(self):
        """Test fire_time string parsing from artifacts (lines 394-398)."""
        # Create TimerTick with proper fields
        tick = TimerTick(
            timer_name="test",
            iteration=0,
            schedule_spec={},
        )
        
        # Create artifact from tick
        tick_artifact = Artifact(
            id=uuid4(),
            type="flock.models.system_artifacts.TimerTick",
            payload=tick.model_dump(),
            produced_by="timer_component",
        )
        
        # Manually set payload with string fire_time (simulating edge case)
        tick_artifact.payload["fire_time"] = "2025-01-01T00:00:00+00:00"
        
        ctx = Context(
            artifacts=[tick_artifact],
            task_id="test_task",
            store=MagicMock(),
            agent=MagicMock(),
            trigger_type="timer",
        )
        
        result = ctx.fire_time
        assert result is not None
        assert isinstance(result, datetime)

    def test_fire_time_returns_fire_time_data_directly(self):
        """Test fire_time returns fire_time_data directly when not datetime/string (line 384)."""
        # Create Context with state containing None fire_time
        ctx = Context(
            artifacts=[],
            task_id="test_task",
            store=MagicMock(),
            agent=MagicMock(),
            trigger_type="timer",
            state={"__timer__": {"fire": None}},
        )
        
        result = ctx.fire_time
        assert result is None

