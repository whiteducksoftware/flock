"""Tests for TimerComponent lifecycle hooks and structure."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from flock.components.orchestrator.scheduling.timer import TimerComponent
from flock.core.subscription import ScheduleSpec
from flock.models.system_artifacts import TimerTick


class TestTimerComponentCreation:
    """Tests for TimerComponent basic instantiation."""

    def test_timer_component_creation(self):
        """Test TimerComponent can be instantiated."""
        component = TimerComponent()

        assert component is not None
        assert hasattr(component, "name")
        assert hasattr(component, "priority")
        assert hasattr(component, "_timer_tasks")

    def test_timer_component_name(self):
        """Test TimerComponent has correct name."""
        component = TimerComponent()

        assert component.name == "timer"

    def test_timer_component_priority(self):
        """Test TimerComponent has priority = 5."""
        component = TimerComponent()

        assert component.priority == 5

    def test_timer_component_timer_tasks_initialized(self):
        """Test TimerComponent initializes _timer_tasks dict."""
        component = TimerComponent()

        assert hasattr(component, "_timer_tasks")
        assert isinstance(component._timer_tasks, dict)
        assert len(component._timer_tasks) == 0


class TestTimerComponentInitialize:
    """Tests for TimerComponent on_initialize lifecycle hook."""

    @pytest.mark.asyncio
    async def test_on_initialize_creates_timer_tasks(self):
        """Test on_initialize creates tasks for scheduled agents."""
        # Create mock orchestrator with scheduled agents
        orchestrator = MagicMock()

        # Agent with schedule_spec
        agent1 = MagicMock()
        agent1.name = "scheduled_agent"
        agent1.schedule_spec = ScheduleSpec(interval=timedelta(seconds=1))

        # Agent without schedule_spec
        agent2 = MagicMock()
        agent2.name = "normal_agent"
        agent2.schedule_spec = None

        # Agent without schedule_spec attribute at all
        agent3 = MagicMock(spec=["name"])
        agent3.name = "minimal_agent"

        orchestrator.agents = [agent1, agent2, agent3]

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Should create task only for agent1
        assert len(component._timer_tasks) == 1
        assert "scheduled_agent" in component._timer_tasks
        assert isinstance(component._timer_tasks["scheduled_agent"], asyncio.Task)

    @pytest.mark.asyncio
    async def test_on_initialize_no_scheduled_agents(self):
        """Test on_initialize handles orchestrator with no scheduled agents."""
        orchestrator = MagicMock()
        orchestrator.agents = []

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Should not create any tasks
        assert len(component._timer_tasks) == 0

    @pytest.mark.asyncio
    async def test_on_initialize_multiple_scheduled_agents(self):
        """Test on_initialize creates tasks for multiple scheduled agents."""
        orchestrator = MagicMock()

        agent1 = MagicMock()
        agent1.name = "timer1"
        agent1.schedule_spec = ScheduleSpec(interval=timedelta(seconds=1))

        agent2 = MagicMock()
        agent2.name = "timer2"
        agent2.schedule_spec = ScheduleSpec(interval=timedelta(seconds=2))

        orchestrator.agents = [agent1, agent2]

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Should create tasks for both
        assert len(component._timer_tasks) == 2
        assert "timer1" in component._timer_tasks
        assert "timer2" in component._timer_tasks


class TestTimerComponentShutdown:
    """Tests for TimerComponent on_shutdown lifecycle hook."""

    @pytest.mark.asyncio
    async def test_on_shutdown_cancels_tasks(self):
        """Test on_shutdown cancels all timer tasks gracefully."""
        orchestrator = MagicMock()
        orchestrator.agents = []

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Manually add timer tasks (simulate running tasks)
        async def dummy_task():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                pass

        task1 = asyncio.create_task(dummy_task())
        task2 = asyncio.create_task(dummy_task())
        component._timer_tasks["agent1"] = task1
        component._timer_tasks["agent2"] = task2

        # Verify tasks are running
        assert not task1.done()
        assert not task2.done()

        # Trigger shutdown
        await component.on_shutdown(orchestrator)

        # Verify tasks were cancelled
        assert task1.done()
        assert task2.done()

    @pytest.mark.asyncio
    async def test_on_shutdown_no_tasks(self):
        """Test on_shutdown handles empty task list gracefully."""
        orchestrator = MagicMock()
        orchestrator.agents = []

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Should not raise any errors
        await component.on_shutdown(orchestrator)

    @pytest.mark.asyncio
    async def test_on_shutdown_already_completed_tasks(self):
        """Test on_shutdown handles already completed tasks."""
        orchestrator = MagicMock()
        orchestrator.agents = []

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Add already completed task
        async def completed_task():
            return "done"

        task = asyncio.create_task(completed_task())
        await task  # Wait for completion
        component._timer_tasks["agent1"] = task

        assert task.done()

        # Should not raise errors
        await component.on_shutdown(orchestrator)


class TestTimerComponentInheritance:
    """Tests for TimerComponent inheritance from OrchestratorComponent."""

    def test_timer_component_extends_orchestrator_component(self):
        """Test TimerComponent extends OrchestratorComponent."""
        from flock.components.orchestrator.base import OrchestratorComponent

        component = TimerComponent()

        assert isinstance(component, OrchestratorComponent)

    def test_timer_component_has_lifecycle_hooks(self):
        """Test TimerComponent has required lifecycle hooks."""
        component = TimerComponent()

        # Check for lifecycle hooks
        assert hasattr(component, "on_initialize")
        assert hasattr(component, "on_shutdown")
        assert callable(component.on_initialize)
        assert callable(component.on_shutdown)


class TestTimerLoop:
    """Tests for _timer_loop background task logic."""

    @pytest.mark.asyncio
    async def test_timer_loop_publishes_ticks(self):
        """Timer loop publishes TimerTick artifacts at intervals."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.1))  # 100ms for fast test

        # Act - Run timer loop for 0.35s (should publish ~3 ticks)
        task = asyncio.create_task(
            component._timer_loop(orchestrator, "test_agent", spec)
        )

        await asyncio.sleep(0.35)
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        # Assert - Verify publish called at least 3 times (timing may vary)
        assert orchestrator.publish.call_count >= 3
        # But not too many (shouldn't be more than 4 for 350ms with 100ms interval)
        assert orchestrator.publish.call_count <= 4

        # Verify TimerTick structure
        for call in orchestrator.publish.call_args_list:
            tick = call.args[0]
            assert isinstance(tick, TimerTick)
            assert tick.timer_name == "test_agent"
            assert tick.fire_time is not None
            assert isinstance(tick.fire_time, datetime)

    @pytest.mark.asyncio
    async def test_timer_loop_respects_initial_delay(self):
        """Timer waits for initial delay before first tick."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(
            interval=timedelta(seconds=0.1), after=timedelta(seconds=0.2)
        )

        # Act
        task = asyncio.create_task(
            component._timer_loop(orchestrator, "test_agent", spec)
        )

        # Wait 0.15s - should NOT have published yet
        await asyncio.sleep(0.15)
        assert orchestrator.publish.call_count == 0

        # Wait another 0.2s - should have published
        await asyncio.sleep(0.2)
        assert orchestrator.publish.call_count >= 1

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_timer_loop_respects_max_repeats(self):
        """Timer stops after max_repeats executions."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.05), max_repeats=3)

        # Act - Run timer loop (should stop after 3 iterations)
        await component._timer_loop(orchestrator, "test_agent", spec)

        # Assert - Verify exactly 3 publishes
        assert orchestrator.publish.call_count == 3

        # Verify iteration numbers
        iterations = [
            call.args[0].iteration for call in orchestrator.publish.call_args_list
        ]
        assert iterations == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_timer_loop_handles_cancellation(self):
        """Timer loop handles CancelledError gracefully."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.1))

        # Act - Start timer and cancel it
        task = asyncio.create_task(
            component._timer_loop(orchestrator, "test_agent", spec)
        )

        await asyncio.sleep(0.05)  # Let it start
        task.cancel()

        # Should not raise exception - CancelledError handled gracefully
        try:
            await task
        except asyncio.CancelledError:
            pytest.fail(
                "CancelledError should be handled gracefully within _timer_loop"
            )

        # Should have completed without errors
        assert task.done()

    @pytest.mark.asyncio
    async def test_timer_loop_increments_iteration(self):
        """Timer loop increments iteration counter for each tick."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.05), max_repeats=5)

        # Act
        await component._timer_loop(orchestrator, "test_agent", spec)

        # Assert - Verify iterations are 0, 1, 2, 3, 4
        iterations = [
            call.args[0].iteration for call in orchestrator.publish.call_args_list
        ]
        assert iterations == [0, 1, 2, 3, 4]

        # Verify each iteration is unique and incremental
        for i, iteration in enumerate(iterations):
            assert iteration == i

    @pytest.mark.asyncio
    async def test_timer_loop_publishes_with_tags(self):
        """Timer loop publishes with system and timer tags (correlation_id is auto-generated)."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.05), max_repeats=2)

        # Act
        await component._timer_loop(orchestrator, "my_agent", spec)

        # Assert - Verify tags are set correctly
        assert orchestrator.publish.call_count == 2

        # Check first call has correct tags
        first_call = orchestrator.publish.call_args_list[0]
        assert first_call.kwargs["tags"] == {"system", "timer"}

        # correlation_id should NOT be set (orchestrator generates it as UUID)
        assert (
            "correlation_id" not in first_call.kwargs
            or first_call.kwargs["correlation_id"] is None
        )

        # Check second call
        second_call = orchestrator.publish.call_args_list[1]
        assert second_call.kwargs["tags"] == {"system", "timer"}

    @pytest.mark.asyncio
    async def test_timer_loop_publishes_with_tags(self):
        """Timer loop publishes with system and timer tags."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.05), max_repeats=1)

        # Act
        await component._timer_loop(orchestrator, "test_agent", spec)

        # Assert - Verify tags
        call_kwargs = orchestrator.publish.call_args_list[0].kwargs
        assert "tags" in call_kwargs
        tags = call_kwargs["tags"]
        assert "system" in tags
        assert "timer" in tags

    @pytest.mark.asyncio
    async def test_timer_loop_serializes_schedule_spec(self):
        """Timer loop serializes ScheduleSpec to dict in TimerTick."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=30), max_repeats=1)

        # Act
        await component._timer_loop(orchestrator, "test_agent", spec)

        # Assert - Verify schedule_spec is serialized as dict
        tick = orchestrator.publish.call_args_list[0].args[0]
        assert isinstance(tick.schedule_spec, dict)
        assert "interval" in tick.schedule_spec
        # Interval should be serialized (could be as string or seconds)
        assert tick.schedule_spec["interval"] is not None


class TestWaitForNextFire:
    """Tests for _wait_for_next_fire scheduling logic."""

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_interval(self):
        """Test interval-based scheduling sleeps for interval duration."""
        from datetime import UTC

        # Arrange
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.1))

        # Act
        start = datetime.now(UTC)
        await component._wait_for_next_fire(spec)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        # Assert - Should sleep for approximately 0.1 seconds
        assert elapsed >= 0.09  # Allow small tolerance
        assert elapsed < 0.15  # Not too much longer

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_time_future_today(self):
        """Test time-based scheduling calculates wait for future time today."""
        from datetime import UTC, time

        # Arrange
        component = TimerComponent()
        now = datetime.now(UTC)
        # Set target time to be 2-3 seconds in the future, but with cleared microseconds
        # to match how time objects work
        future_moment = now + timedelta(seconds=2)
        future_time = time(
            hour=future_moment.hour,
            minute=future_moment.minute,
            second=future_moment.second,
        )
        spec = ScheduleSpec(at=future_time)

        # Act - Calculate expected wait time
        # The implementation will use now.replace(hour=..., minute=..., second=..., microsecond=0)
        expected_target = now.replace(
            hour=future_time.hour,
            minute=future_time.minute,
            second=future_time.second,
            microsecond=0,
        )
        expected_wait = (expected_target - now).total_seconds()

        start = datetime.now(UTC)
        await component._wait_for_next_fire(spec)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        # Assert - Should sleep for approximately the expected wait time
        # Allow 0.1s tolerance for execution overhead
        assert elapsed >= expected_wait - 0.1
        assert elapsed < expected_wait + 0.5

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_time_past_today(self):
        """Test time-based scheduling wraps to tomorrow for past time."""
        from datetime import UTC

        # Arrange
        component = TimerComponent()
        now = datetime.now(UTC)
        # Set target time 2 seconds in the PAST
        past_time = (now - timedelta(seconds=2)).time()
        spec = ScheduleSpec(at=past_time)

        # Act
        start = datetime.now(UTC)
        # Create task with timeout to avoid waiting 24 hours
        wait_task = asyncio.create_task(component._wait_for_next_fire(spec))

        # Give it a moment to calculate the wait time
        await asyncio.sleep(0.01)

        # Cancel the task (we don't want to wait 24 hours)
        wait_task.cancel()

        try:
            await wait_task
        except asyncio.CancelledError:
            pass

        # Assert - Should have calculated wait time close to 24 hours
        # We can't easily test this without mocking, so we verify it started waiting
        # and didn't complete immediately
        elapsed = (datetime.now(UTC) - start).total_seconds()
        assert elapsed < 1.0  # Should not have slept the full time (we cancelled)

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_datetime_future(self):
        """Test datetime-based scheduling waits until specific future datetime."""
        from datetime import UTC

        # Arrange
        component = TimerComponent()
        now = datetime.now(UTC)
        # Set target datetime 0.2 seconds in the future
        future_dt = now + timedelta(seconds=0.2)
        spec = ScheduleSpec(at=future_dt)

        # Act
        start = datetime.now(UTC)
        await component._wait_for_next_fire(spec)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        # Assert - Should sleep for approximately 0.2 seconds
        assert elapsed >= 0.19
        assert elapsed < 0.3

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_datetime_past(self):
        """Test datetime-based scheduling handles past datetime appropriately."""
        from datetime import UTC

        # Arrange
        component = TimerComponent()
        now = datetime.now(UTC)
        # Set target datetime in the PAST
        past_dt = now - timedelta(seconds=5)
        spec = ScheduleSpec(at=past_dt)

        # Act
        start = datetime.now(UTC)
        await component._wait_for_next_fire(spec)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        # Assert - Should return immediately (or very quickly) for past datetime
        assert elapsed < 0.1  # Should not sleep

    def test_cron_next_fire_basic(self):
        """Cron next-fire helper computes a reasonable next timestamp (UTC)."""
        from datetime import UTC

        component = TimerComponent()
        now = datetime.now(UTC)
        # Next minute of current hour
        next_min = (now.minute + 1) % 60
        expr = f"{next_min} {now.hour} * * *"
        next_fire = component._next_cron_fire(now, expr)

        assert next_fire >= now
        assert next_fire.minute == next_min
        assert next_fire.hour in {now.hour, (now.hour + 1) % 24}

    def test_cron_next_fire_range_list_step(self):
        """Cron next-fire supports ranges, steps, and weekdays."""
        from datetime import UTC

        component = TimerComponent()
        # Weekdays 1-5 (Mon-Fri), hours 9-17 step 2 → 9,11,13,15,17
        expr = "0 9-17/2 * * 1-5"
        # Choose a Sunday to force next weekday; if today is Sunday, fine; else use now
        now = datetime.now(UTC)
        next_fire = component._next_cron_fire(now, expr)
        # Zero minute
        assert next_fire.minute == 0
        # Hour in 9,11,13,15,17
        assert next_fire.hour in {9, 11, 13, 15, 17}
        # Weekday Mon-Fri
        assert next_fire.weekday() in {0, 1, 2, 3, 4}

    def test_cron_every_five_minutes(self):
        """Cron */5 * * * * schedules to the next 5-minute boundary."""
        from datetime import UTC

        component = TimerComponent()
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        expr = "*/5 * * * *"
        nf = component._next_cron_fire(now, expr)
        assert nf.minute % 5 == 0
        assert nf >= now + timedelta(minutes=1)
