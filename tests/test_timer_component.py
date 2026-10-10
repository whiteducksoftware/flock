"""Tests for TimerComponent lifecycle hooks and structure."""

import asyncio
import gc
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from flock.components.orchestrator.scheduling import timer as timer_module
from flock.components.orchestrator.scheduling.timer import TimerComponent
from flock.core.subscription import ScheduleSpec
from flock.models.system_artifacts import TimerTick


@pytest.fixture(autouse=True)
async def no_leaked_timer_loops():
    """Fail a test that leaves TimerComponent loops running or crashed.

    A leaked loop fires against a mocked orchestrator; its exception surfaces
    later as "Task exception was never retrieved" in unrelated tests.
    """
    loop = asyncio.get_running_loop()
    errors: list[dict] = []
    previous = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: errors.append(context))
    yield
    leaked = [
        task
        for task in asyncio.all_tasks()
        if not task.done() and task.get_coro().__qualname__.endswith("_timer_loop")
    ]
    for task in leaked:
        task.cancel()
    await asyncio.sleep(0)
    gc.collect()
    loop.set_exception_handler(previous)
    assert not leaked, "test left TimerComponent loops running; call on_shutdown()"
    assert not errors, f"background task failed: {errors[0].get('exception')!r}"


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

    def test_timer_component_timer_states_initialized(self):
        """Test TimerComponent initializes _timer_states dict."""
        from flock.components.orchestrator.scheduling.timer import TimerState

        component = TimerComponent()

        assert hasattr(component, "_timer_states")
        assert isinstance(component._timer_states, dict)
        assert len(component._timer_states) == 0

    def test_timer_component_has_get_timer_state_method(self):
        """Test TimerComponent has get_timer_state method."""
        component = TimerComponent()

        assert hasattr(component, "get_timer_state")
        assert callable(component.get_timer_state)


class TestTimerComponentInitialize:
    """Tests for TimerComponent on_initialize lifecycle hook."""

    @pytest.mark.asyncio
    async def test_on_initialize_creates_timer_tasks(self):
        """Test on_initialize creates tasks for scheduled agents."""
        # Create mock orchestrator with scheduled agents
        orchestrator = MagicMock()
        orchestrator.publish = AsyncMock()

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

        # Should initialize timer state for agent1
        assert len(component._timer_states) == 1
        assert "scheduled_agent" in component._timer_states
        timer_state = component._timer_states["scheduled_agent"]
        assert timer_state.iteration == 0
        assert timer_state.is_active is True
        assert timer_state.is_completed is False
        assert timer_state.is_stopped is False
        assert timer_state.next_fire_time is not None

        await component.on_shutdown(orchestrator)

    @pytest.mark.asyncio
    async def test_on_initialize_initializes_timer_states(self):
        """Test on_initialize initializes timer states for scheduled agents."""
        orchestrator = MagicMock()
        orchestrator.publish = AsyncMock()

        agent1 = MagicMock()
        agent1.name = "agent1"
        agent1.schedule_spec = ScheduleSpec(interval=timedelta(seconds=30))

        agent2 = MagicMock()
        agent2.name = "agent2"
        agent2.schedule_spec = ScheduleSpec(interval=timedelta(seconds=60))

        orchestrator.agents = [agent1, agent2]

        component = TimerComponent()
        await component.on_initialize(orchestrator)

        # Should have timer states for both agents
        assert len(component._timer_states) == 2
        assert "agent1" in component._timer_states
        assert "agent2" in component._timer_states

        # Verify initial state
        state1 = component._timer_states["agent1"]
        assert state1.iteration == 0
        assert state1.last_fire_time is None
        assert state1.next_fire_time is not None
        assert state1.is_active is True

        state2 = component._timer_states["agent2"]
        assert state2.iteration == 0
        assert state2.is_active is True

        await component.on_shutdown(orchestrator)

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
        orchestrator.publish = AsyncMock()

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

        await component.on_shutdown(orchestrator)


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
                await asyncio.sleep(0.1)  # Short wait for test
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

        # Initialize timer state
        from flock.components.orchestrator.scheduling.timer import TimerState

        component._timer_states["test_agent"] = TimerState()

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

        # Verify timer state was updated
        timer_state = component._timer_states["test_agent"]
        assert timer_state.iteration == 4  # Last iteration before stopping
        assert timer_state.last_fire_time is not None
        assert timer_state.is_stopped is True
        assert timer_state.is_active is False

    @pytest.mark.asyncio
    async def test_timer_loop_updates_timer_state(self):
        """Timer loop updates timer state with each fire."""
        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=0.05), max_repeats=3)

        # Initialize timer state
        from flock.components.orchestrator.scheduling.timer import TimerState

        component._timer_states["test_agent"] = TimerState()

        # Act
        await component._timer_loop(orchestrator, "test_agent", spec)

        # Assert - Verify state updates
        timer_state = component._timer_states["test_agent"]
        assert timer_state.iteration == 2  # 0, 1, 2 = 3 iterations
        assert timer_state.last_fire_time is not None
        assert timer_state.is_stopped is True
        assert timer_state.is_active is False
        assert timer_state.next_fire_time is None  # Stopped, no next fire

    @pytest.mark.asyncio
    async def test_timer_loop_one_time_schedule_completes(self):
        """Timer loop marks one-time datetime schedules as completed."""
        from datetime import UTC

        # Arrange
        orchestrator = AsyncMock()
        component = TimerComponent()
        future_dt = datetime.now(UTC) + timedelta(seconds=0.1)
        spec = ScheduleSpec(at=future_dt)  # One-time schedule

        # Initialize timer state
        from flock.components.orchestrator.scheduling.timer import TimerState

        component._timer_states["one_time_agent"] = TimerState()

        # Act
        await component._timer_loop(orchestrator, "one_time_agent", spec)

        # Assert - Should publish once and mark as completed
        assert orchestrator.publish.call_count == 1
        timer_state = component._timer_states["one_time_agent"]
        assert timer_state.iteration == 0
        assert timer_state.is_completed is True
        assert timer_state.is_active is False
        assert timer_state.next_fire_time is None

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
    """Tests for _wait_for_next_fire scheduling logic.

    The tests check the wait the component asks for, not the elapsed wall
    time: a busy event loop or a wall clock that steps (VM time sync, NTP)
    would make elapsed-time bounds flaky.
    """

    @pytest.fixture
    def sleeps(self, monkeypatch) -> list[float]:
        """Record the timer's sleeps instead of waiting."""
        recorded: list[float] = []

        async def record(seconds: float) -> None:
            recorded.append(seconds)

        monkeypatch.setattr(timer_module.asyncio, "sleep", record)
        return recorded

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_interval(self, sleeps):
        """Interval scheduling sleeps for the interval."""
        component = TimerComponent()

        await component._wait_for_next_fire(
            ScheduleSpec(interval=timedelta(seconds=0.1))
        )

        assert sleeps == [0.1]

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_time_future_today(self, sleeps):
        """A time of day later today waits until then."""
        from datetime import UTC, time

        component = TimerComponent()
        # 30 s ahead, whole seconds like a time-of-day schedule; at midnight
        # the target rolls over to tomorrow, still 29-30 s away
        target = datetime.now(UTC) + timedelta(seconds=30)
        spec = ScheduleSpec(
            at=time(hour=target.hour, minute=target.minute, second=target.second)
        )

        await component._wait_for_next_fire(spec)

        (wait,) = sleeps
        assert 28.0 < wait <= 30.0

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_time_past_today(self, sleeps):
        """A time of day that has passed today waits until tomorrow."""
        from datetime import UTC

        component = TimerComponent()
        past_time = (datetime.now(UTC) - timedelta(seconds=30)).time()

        await component._wait_for_next_fire(ScheduleSpec(at=past_time))

        (wait,) = sleeps
        day = timedelta(days=1).total_seconds()
        assert day - 32.0 < wait <= day - 29.0

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_datetime_future(self, sleeps):
        """A future datetime waits until then."""
        from datetime import UTC

        component = TimerComponent()
        spec = ScheduleSpec(at=datetime.now(UTC) + timedelta(seconds=30))

        await component._wait_for_next_fire(spec)

        (wait,) = sleeps
        assert 28.0 < wait <= 30.0

    @pytest.mark.asyncio
    async def test_wait_for_next_fire_datetime_past(self, sleeps):
        """A datetime in the past does not wait."""
        from datetime import UTC

        component = TimerComponent()
        spec = ScheduleSpec(at=datetime.now(UTC) - timedelta(seconds=5))

        await component._wait_for_next_fire(spec)

        assert sleeps == []

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
        """Cron next-fire supports ranges, steps, and weekdays.

        Tests cron expressions with ranges (9-17), steps (/2), and weekday constraints (1-5).
        Verifies that hour/minute constraints are correctly applied.
        """
        from datetime import UTC

        component = TimerComponent()
        # Hours 9-17 step 2 → 9,11,13,15,17, weekday constraint 1-5 (Mon-Fri)
        expr = "0 9-17/2 * * 1-5"
        # Set to Sunday at 8:00 AM
        now = datetime(2025, 11, 2, 8, 0, 0, tzinfo=UTC)  # Sunday Nov 2, 2025 at 8 AM
        assert now.weekday() == 6, "Test setup: now should be Sunday"

        next_fire = component._next_cron_fire(now, expr)
        # Verify it's in the future
        assert next_fire > now, f"Next fire {next_fire} should be after now {now}"
        # Zero minute
        assert next_fire.minute == 0, f"Expected minute 0, got {next_fire.minute}"
        # Hour in 9,11,13,15,17 (step 2 from range 9-17)
        assert next_fire.hour in {9, 11, 13, 15, 17}, (
            f"Expected hour in {{9,11,13,15,17}}, got {next_fire.hour}"
        )
        # Verify it advances time correctly (should be at least 1 hour later since we're at 8 AM)
        assert next_fire.hour >= 9, f"Expected hour >= 9, got {next_fire.hour}"

    def test_cron_every_five_minutes(self):
        """Cron */5 * * * * schedules to the next 5-minute boundary."""
        from datetime import UTC

        component = TimerComponent()
        now = datetime.now(UTC).replace(second=0, microsecond=0)
        expr = "*/5 * * * *"
        nf = component._next_cron_fire(now, expr)
        assert nf.minute % 5 == 0
        assert nf >= now + timedelta(minutes=1)


class TestTimerStateTracking:
    """Tests for TimerComponent timer state tracking functionality."""

    def test_get_timer_state_returns_none_for_unknown_agent(self):
        """Test get_timer_state returns None for agent without timer."""
        component = TimerComponent()

        result = component.get_timer_state("unknown_agent")

        assert result is None

    def test_get_timer_state_returns_state_for_registered_agent(self):
        """Test get_timer_state returns TimerState for registered agent."""
        from flock.components.orchestrator.scheduling.timer import TimerState
        from datetime import UTC

        component = TimerComponent()
        timer_state = TimerState(
            iteration=5,
            last_fire_time=datetime.now(UTC),
            next_fire_time=datetime.now(UTC) + timedelta(seconds=30),
            is_active=True,
        )
        component._timer_states["test_agent"] = timer_state

        result = component.get_timer_state("test_agent")

        assert result is not None
        assert result.iteration == 5
        assert result.is_active is True
        assert result.last_fire_time is not None
        assert result.next_fire_time is not None

    def test_calculate_next_fire_time_interval(self):
        """Test _calculate_next_fire_time for interval-based schedules."""
        from datetime import UTC

        component = TimerComponent()
        spec = ScheduleSpec(interval=timedelta(seconds=30))

        next_fire = component._calculate_next_fire_time(spec)

        assert next_fire is not None
        assert isinstance(next_fire, datetime)
        # Should be approximately 30 seconds in the future
        now = datetime.now(UTC)
        diff = (next_fire - now).total_seconds()
        assert 29 <= diff <= 31

    def test_calculate_next_fire_time_time(self):
        """Test _calculate_next_fire_time for time-based schedules."""
        from datetime import UTC, time

        component = TimerComponent()
        # Set target time to be soon in the future
        now = datetime.now(UTC)
        future_time = time(
            hour=now.hour,
            minute=now.minute,
            second=(now.second + 5) % 60,
        )
        spec = ScheduleSpec(at=future_time)

        next_fire = component._calculate_next_fire_time(spec)

        assert next_fire is not None
        assert isinstance(next_fire, datetime)
        assert next_fire.hour == future_time.hour
        assert next_fire.minute == future_time.minute

    def test_calculate_next_fire_time_datetime(self):
        """Test _calculate_next_fire_time for datetime-based schedules."""
        from datetime import UTC

        component = TimerComponent()
        future_dt = datetime.now(UTC) + timedelta(seconds=60)
        spec = ScheduleSpec(at=future_dt)

        next_fire = component._calculate_next_fire_time(spec)

        assert next_fire is not None
        assert next_fire == future_dt

    def test_calculate_next_fire_time_cron(self):
        """Test _calculate_next_fire_time for cron-based schedules."""
        from datetime import UTC

        component = TimerComponent()
        spec = ScheduleSpec(cron="0 * * * *")  # Every hour

        next_fire = component._calculate_next_fire_time(spec)

        assert next_fire is not None
        assert isinstance(next_fire, datetime)
        assert next_fire.minute == 0  # Should be on the hour
