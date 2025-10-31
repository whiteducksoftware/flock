"""TimerComponent for managing timer-based agent execution.

This component handles timer-based scheduling for agents with ScheduleSpec.
Creates background tasks that will publish TimerTick artifacts at configured intervals.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, time, timedelta
from typing import TYPE_CHECKING

from flock.components.orchestrator.base import OrchestratorComponent
from flock.models.system_artifacts import TimerTick


if TYPE_CHECKING:
    from flock.core import Flock
    from flock.core.subscription import ScheduleSpec


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
        self._timer_tasks: dict[str, asyncio.Task] = {}

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
        try:
            # Initial delay
            if spec.after:
                await asyncio.sleep(spec.after.total_seconds())

            iteration = 0
            while True:
                # Effective max repeats: implicit one-time for datetime schedules
                effective_max = (
                    1
                    if (hasattr(spec, "at") and isinstance(spec.at, datetime) and spec.max_repeats is None)
                    else spec.max_repeats
                )
                # Check max_repeats
                if effective_max is not None and iteration >= effective_max:
                    break

                # Publish TimerTick
                tick = TimerTick(
                    timer_name=agent_name,
                    fire_time=datetime.now(UTC),
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

                # Wait for next fire (stub for now - Task 2.3)
                await self._wait_for_next_fire(spec)

        except asyncio.CancelledError:
            # Graceful shutdown
            pass

    def _serialize_schedule_spec(self, spec: ScheduleSpec) -> dict:
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
            result["max_repeats"] = spec.max_repeats
        return result

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

    # ────────────────────────────────────────────────────────────────────────────
    # Cron helpers
    # ────────────────────────────────────────────────────────────────────────────
    def _next_cron_fire(self, now_utc: datetime, expr: str) -> datetime:
        """Compute the next datetime (UTC) that matches the given 5-field cron expression.

        Supported syntax: numeric fields with wildcards (*), lists (a,b,c), ranges (a-b), and steps (*/n or a-b/n).
        Fields: minute (0-59), hour (0-23), day of month (1-31), month (1-12), day of week (0-7, where 0 or 7 = Sunday).
        Matching semantics for DOM/DOW follow standard cron: if both are specified (not *), match when either matches (OR).
        """
        fields = expr.split()
        if len(fields) != 5:
            raise ValueError("Cron expression must have 5 fields: 'min hour dom mon dow'")

        minutes = self._parse_cron_field(fields[0], 0, 59)
        hours = self._parse_cron_field(fields[1], 0, 23)
        dom = self._parse_cron_field(fields[2], 1, 31)
        months = self._parse_cron_field(fields[3], 1, 12)
        dow_raw = self._parse_cron_field(fields[4], 0, 7)
        # Remap cron DOW (0 or 7 = Sunday) to Python weekday() (0=Mon..6=Sun)
        dow = set()
        dow_wild = dow_raw is None
        if not dow_wild:
            for d in dow_raw:  # type: ignore[union-attr]
                if d in (0, 7):
                    dow.add(6)
                else:
                    dow.add(d - 1)

        # Start searching at next minute boundary
        dt = now_utc.replace(second=0, microsecond=0) + timedelta(minutes=1)
        attempts = 0
        max_attempts = 366 * 24 * 60  # up to a year of minutes
        while attempts < max_attempts:
            attempts += 1
            if months is not None and dt.month not in months:
                dt += timedelta(minutes=1)
                continue

            minute_ok = (minutes is None) or (dt.minute in minutes)
            hour_ok = (hours is None) or (dt.hour in hours)
            dom_ok = (dom is None) or (dt.day in dom)
            dow_ok = dow_wild or (dt.weekday() in dow)

            # DOM and DOW combine as OR when both specified
            day_ok = (dom is None and dow_wild) or (dom_ok or dow_ok)

            if minute_ok and hour_ok and day_ok:
                return dt

            dt += timedelta(minutes=1)

        # Fallback (should never happen): return next minute to avoid infinite loop
        return now_utc + timedelta(minutes=1)

    def _parse_cron_field(self, field: str, min_v: int, max_v: int) -> set[int] | None:
        """Parse a cron field into a set of integers or None for wildcard (*)."""
        field = field.strip()
        if field == "*":
            return None

        result: set[int] = set()
        parts = field.split(",")
        for part in parts:
            part = part.strip()
            if "/" in part:
                base, step_str = part.split("/", 1)
                step = int(step_str)
                if base == "*":
                    start, end = min_v, max_v
                elif "-" in base:
                    a, b = base.split("-", 1)
                    start, end = int(a), int(b)
                else:
                    # Single value with step → interpret as from that value to max
                    start, end = int(base), max_v
                for v in range(start, end + 1):
                    if v < min_v or v > max_v:
                        continue
                    if (v - start) % step == 0:
                        result.add(v)
                continue

            if "-" in part:
                a, b = part.split("-", 1)
                start, end = int(a), int(b)
                for v in range(start, end + 1):
                    if min_v <= v <= max_v:
                        result.add(v)
                continue

            # Single value
            v = int(part)
            if min_v <= v <= max_v:
                result.add(v)

        return result

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


__all__ = ["TimerComponent"]
