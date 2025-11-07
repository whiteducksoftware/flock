"""TimerComponent for managing timer-based agent execution.

This component handles timer-based scheduling for agents with ScheduleSpec.
Creates background tasks that will publish TimerTick artifacts at configured intervals.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING, Any

from croniter import croniter

from flock.components.orchestrator.base import OrchestratorComponent
from flock.models.system_artifacts import TimerTick


if TYPE_CHECKING:
    from flock.core import Flock
    from flock.core.subscription import ScheduleSpec


@dataclass
class TimerState:
    """Timer state for a scheduled agent."""

    iteration: int = 0
    last_fire_time: datetime | None = None
    next_fire_time: datetime | None = None
    is_active: bool = True
    is_completed: bool = False
    is_stopped: bool = False


class TimerComponent(OrchestratorComponent):
    """Manages timer-based agent execution.

    This component:
    1. Starts background tasks for each scheduled agent during initialization
    2. Will publish TimerTick artifacts at configured intervals (future task)
    3. Handles graceful shutdown and task cancellation

    Priority: 5 (runs before collection component at 100)

    Attributes:
        name: Component name ("timer")
        priority: Execution priority (5)
        _timer_tasks: Dictionary mapping agent names to their timer tasks

    Examples:
        >>> # Component is automatically initialized by orchestrator
        >>> component = TimerComponent()
        >>> await component.on_initialize(orchestrator)
        >>> # Background tasks created for scheduled agents
        >>> await component.on_shutdown(orchestrator)
        >>> # All tasks gracefully cancelled
    """

    name: str = "timer"
    priority: int = 5  # Run before collection component (100)

    def __init__(self, **kwargs):
        """Initialize TimerComponent with empty task dictionary.

        Args:
            **kwargs: Additional arguments passed to OrchestratorComponent
        """
        super().__init__(**kwargs)
        self._timer_tasks: dict[str, asyncio.Task[None]] = {}
        self._timer_states: dict[str, TimerState] = {}

    async def on_initialize(self, orchestrator: Flock) -> None:
        """Start timer tasks for all scheduled agents.

        Iterates through all agents in the orchestrator and creates a background
        task for each agent that has a schedule_spec defined.

        Args:
            orchestrator: Flock orchestrator instance

        Examples:
            >>> # Called automatically during orchestrator startup
            >>> await component.on_initialize(orchestrator)
            >>> # Tasks created for agents with schedule_spec
        """
        for agent in orchestrator.agents:
            # Check if agent has schedule_spec attribute and it's not None
            if hasattr(agent, "schedule_spec") and agent.schedule_spec:
                # CRITICAL FIX: Skip if timer task already exists for this agent
                if agent.name in self._timer_tasks:
                    # Check if existing task is still running
                    existing_task = self._timer_tasks[agent.name]
                    if not existing_task.done():
                        # Task already exists and is running, skip to prevent duplicates
                        continue
                    # Task exists but is done, remove it before creating new one
                    del self._timer_tasks[agent.name]

                # Initialize timer state
                self._timer_states[agent.name] = TimerState()
                # Calculate initial next fire time
                self._timer_states[
                    agent.name
                ].next_fire_time = self._calculate_next_fire_time(agent.schedule_spec)
                # Create background task for this scheduled agent
                task = asyncio.create_task(
                    self._timer_loop(orchestrator, agent.name, agent.schedule_spec)
                )
                self._timer_tasks[agent.name] = task

    async def _timer_loop(
        self, orchestrator: Flock, agent_name: str, spec: ScheduleSpec
    ) -> None:
        """Background task that publishes TimerTick artifacts on schedule.

        Handles:
        - Initial delay (spec.after)
        - Max repeats limit (spec.max_repeats)
        - Publishing TimerTick artifacts via orchestrator
        - Graceful cancellation during shutdown
        - Iteration counter incrementing

        Args:
            orchestrator: Flock instance to publish to
            agent_name: Name of agent being scheduled
            spec: Schedule specification with interval/at/cron and options

        Note:
            Implementation of wait-for-next-fire logic is deferred to Task 2.3
        """
        # Effective max repeats: implicit one-time for datetime schedules
        effective_max = (
            1
            if (
                hasattr(spec, "at")
                and isinstance(spec.at, datetime)
                and spec.max_repeats is None
            )
            else spec.max_repeats
        )
        is_one_time = (
            hasattr(spec, "at")
            and isinstance(spec.at, datetime)
            and spec.max_repeats is None
        )

        try:
            # Initial delay
            if spec.after:
                await asyncio.sleep(spec.after.total_seconds())

            iteration = 0
            while True:
                # Check max_repeats
                if effective_max is not None and iteration >= effective_max:
                    if agent_name in self._timer_states:
                        self._timer_states[agent_name].is_stopped = True
                        self._timer_states[agent_name].is_active = False
                        self._timer_states[agent_name].next_fire_time = None
                    break

                # CRITICAL FIX #1: Wait BEFORE publishing for non-interval schedules
                # This prevents immediate fire on startup for datetime/cron schedules
                # For interval schedules, we publish immediately then wait
                # For non-interval schedules (datetime/cron), we wait first then publish
                if not spec.interval:
                    # Wait for scheduled time before publishing
                    await self._wait_for_next_fire(spec)

                # Update timer state
                fire_time = datetime.now(UTC)
                if agent_name in self._timer_states:
                    self._timer_states[agent_name].iteration = iteration
                    self._timer_states[agent_name].last_fire_time = fire_time

                # Publish TimerTick
                tick = TimerTick(
                    timer_name=agent_name,
                    fire_time=fire_time,
                    iteration=iteration,
                    schedule_spec=self._serialize_schedule_spec(spec),
                )
                await orchestrator.publish(
                    tick,
                    # correlation_id must be None or let orchestrator generate it
                    # Don't use custom string as it must be a valid UUID
                    tags={"system", "timer"},
                )

                # Increment iteration
                iteration += 1

                # Calculate next fire time based on actual fire_time (not current time after publish)
                # This prevents drift accumulation from publish execution time
                if agent_name in self._timer_states:
                    self._timer_states[
                        agent_name
                    ].next_fire_time = self._calculate_next_fire_time(
                        spec, base_time=fire_time
                    )

                # Wait for next fire (for interval schedules, wait after publish)
                # For non-interval schedules, we already waited before publish
                if spec.interval:
                    await self._wait_for_next_fire(spec)

        except asyncio.CancelledError:
            # Graceful shutdown
            if agent_name in self._timer_states:
                self._timer_states[agent_name].is_active = False
        except Exception as e:
            # CRITICAL FIX #3: Handle unexpected exceptions and mark timer as inactive
            # This prevents run_until_idle() from spinning forever waiting for crashed timers
            from flock.logging.logging import get_logger

            logger = get_logger(__name__)
            logger.error(
                f"Timer loop crashed for agent '{agent_name}': {e}",
                exc_info=True,
            )
            if agent_name in self._timer_states:
                self._timer_states[agent_name].is_active = False
                self._timer_states[agent_name].is_stopped = True
            # Remove task from dictionary since it's crashed
            if agent_name in self._timer_tasks:
                del self._timer_tasks[agent_name]
            raise  # Re-raise for visibility
        finally:
            # Mark as completed if one-time schedule
            if is_one_time and agent_name in self._timer_states:
                self._timer_states[agent_name].is_completed = True
                self._timer_states[agent_name].is_active = False
                self._timer_states[agent_name].next_fire_time = None

    def _serialize_schedule_spec(self, spec: ScheduleSpec) -> dict[str, Any]:
        """Convert ScheduleSpec to dict for TimerTick.

        Args:
            spec: Schedule specification to serialize

        Returns:
            Dictionary representation of schedule spec
        """
        result = {}
        if spec.interval:
            result["interval"] = str(spec.interval)
        if spec.at:
            result["at"] = str(spec.at)
        if spec.cron:
            result["cron"] = spec.cron
        if spec.after:
            result["after"] = str(spec.after)
        if spec.max_repeats:
            # FIX #4: Keep max_repeats as integer for type consistency
            result["max_repeats"] = spec.max_repeats
        return result

    def _calculate_next_fire_time(
        self, spec: ScheduleSpec, base_time: datetime | None = None
    ) -> datetime | None:
        """Calculate the next fire time for a schedule spec.

        Args:
            spec: Schedule specification
            base_time: Base time to calculate from (defaults to current time).
                For interval schedules, should be the actual fire_time to prevent drift.

        Returns:
            Next fire datetime in UTC, or None if cannot be calculated
        """
        now = base_time if base_time is not None else datetime.now(UTC)

        if spec.interval:
            # Next fire is base_time + interval
            # Using base_time (actual fire_time) prevents drift from publish execution time
            return now + spec.interval

        if spec.at:
            if isinstance(spec.at, time):
                # Daily scheduling: calculate next occurrence
                target = now.replace(
                    hour=spec.at.hour,
                    minute=spec.at.minute,
                    second=spec.at.second if spec.at.second else 0,
                    microsecond=0,
                )
                if target <= now:
                    # Time passed today, schedule for tomorrow
                    target += timedelta(days=1)
                return target

            if isinstance(spec.at, datetime):
                # One-time scheduling
                target = spec.at if spec.at.tzinfo else spec.at.replace(tzinfo=UTC)
                return target if target > now else None

        elif spec.cron:
            # Cron scheduling
            return self._next_cron_fire(now, spec.cron)

        return None

    async def _wait_for_next_fire(self, spec: ScheduleSpec) -> None:
        """Calculate and wait until next timer fire.

        Supports three scheduling modes:
        1. Interval: Simple periodic sleep
        2. Time (time object): Daily scheduling at specific time
        3. Datetime (datetime object): One-time scheduling at specific datetime

        Args:
            spec: Schedule specification

        Raises:
            NotImplementedError: If cron scheduling is specified (not yet supported)

        Examples:
            >>> # Interval mode
            >>> spec = ScheduleSpec(interval=timedelta(seconds=30))
            >>> await component._wait_for_next_fire(spec)
            >>> # Sleeps for 30 seconds

            >>> # Time mode (daily at 5 PM)
            >>> spec = ScheduleSpec(at=time(hour=17, minute=0))
            >>> await component._wait_for_next_fire(spec)
            >>> # Waits until next 5 PM (today or tomorrow)

            >>> # Datetime mode (one-time)
            >>> spec = ScheduleSpec(at=datetime(2025, 11, 1, 9, 0, tzinfo=UTC))
            >>> await component._wait_for_next_fire(spec)
            >>> # Waits until specific datetime
        """
        if spec.interval:
            # Simple interval-based sleep
            await asyncio.sleep(spec.interval.total_seconds())

        elif spec.at:
            if isinstance(spec.at, time):
                # Daily scheduling: calculate seconds until next occurrence
                now = datetime.now(UTC)
                target = now.replace(
                    hour=spec.at.hour,
                    minute=spec.at.minute,
                    second=spec.at.second if spec.at.second else 0,
                    microsecond=0,
                )
                if target <= now:
                    # Time passed today, schedule for tomorrow
                    target += timedelta(days=1)
                seconds_until = (target - now).total_seconds()
                await asyncio.sleep(seconds_until)

            elif isinstance(spec.at, datetime):
                # One-time scheduling: wait until specific datetime
                now = datetime.now(UTC)
                # Handle timezone-naive datetime (assume UTC)
                target = spec.at if spec.at.tzinfo else spec.at.replace(tzinfo=UTC)
                seconds_until = (target - now).total_seconds()
                if seconds_until > 0:
                    await asyncio.sleep(seconds_until)
                # After firing once, this should not be called again (max_repeats=1 implicit)

        elif spec.cron:
            # Cron scheduling (UTC): compute next fire and sleep until then
            now = datetime.now(UTC)
            next_fire = self._next_cron_fire(now, spec.cron)
            seconds_until = max(0.0, (next_fire - now).total_seconds())
            if seconds_until > 0:
                await asyncio.sleep(seconds_until)
            # After firing once, this should not be called again (max_repeats=1 implicit)

    # ────────────────────────────────────────────────────────────────────────────
    # Cron helpers
    # ────────────────────────────────────────────────────────────────────────────
    def _next_cron_fire(self, now_utc: datetime, expr: str) -> datetime:
        """Compute the next datetime (UTC) that matches the given cron expression.

        Uses croniter library for robust cron parsing and scheduling.

        Args:
            now_utc: Current datetime in UTC
            expr: Cron expression (5-field format)

        Returns:
            Next fire datetime in UTC
        """
        try:
            cron = croniter(expr, now_utc)
            return cron.get_next(datetime)
        except Exception:
            # Fallback to next minute if cron parsing fails
            return now_utc + timedelta(minutes=1)

    async def on_shutdown(self, orchestrator: Flock) -> None:
        """Cancel all timer tasks during shutdown.

        Cancels all running timer tasks and waits for them to complete
        their cancellation gracefully. Handles both running and already
        completed tasks.

        Args:
            orchestrator: Flock orchestrator instance

        Examples:
            >>> # Called automatically during orchestrator shutdown
            >>> await component.on_shutdown(orchestrator)
            >>> # All timer tasks cancelled and cleaned up
        """
        # Cancel all timer tasks
        for task in self._timer_tasks.values():
            if not task.done():
                task.cancel()

        # Wait for all tasks to complete cancellation
        if self._timer_tasks:
            await asyncio.gather(*self._timer_tasks.values(), return_exceptions=True)

    def get_timer_state(self, agent_name: str) -> TimerState | None:
        """Get timer state for an agent.

        Args:
            agent_name: Name of the agent

        Returns:
            TimerState if agent has a timer, None otherwise
        """
        return self._timer_states.get(agent_name)


__all__ = ["TimerComponent", "TimerState"]
