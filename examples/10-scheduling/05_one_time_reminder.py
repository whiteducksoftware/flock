"""
Timer Scheduling: One-Time Reminder

Demonstrates datetime-based scheduling that fires exactly once at a specific
time — perfect for reminders and delayed tasks.

Key concepts
- schedule(at=datetime(...)) for one-time execution; a datetime without a
  timezone is read as UTC, so use timezone-aware datetimes
- max_repeats=1 is implicit with datetime schedules
- with_context(...) gives the reminder the published meeting as context
- Use a quick demo time (now + 30s) so you can observe it locally
"""

import asyncio
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig
from flock.registry import flock_type, type_registry


USE_DASHBOARD = False


@flock_type
class MeetingSchedule(BaseModel):
    meeting_id: str
    title: str
    scheduled_time: datetime
    participants: list[str]
    location: str


@flock_type
class Reminder(BaseModel):
    meeting_id: str
    message: str
    reminder_time: datetime
    minutes_before: int
    iteration: int


flock = Flock()

# Demo: schedule reminder for 30 seconds from now
DEMO_MODE = True
reminder_time = (
    datetime.now(UTC) + timedelta(seconds=30)
    if DEMO_MODE
    else datetime(2026, 11, 2, 8, 55, tzinfo=UTC)
)

print(f"\n[Setup] Current time:  {datetime.now(UTC).strftime('%H:%M:%S')} UTC")
print(f"[Setup] Reminder for: {reminder_time.strftime('%H:%M:%S')} UTC\n")

# Publisher runs once to create a meeting
meeting_publisher = (
    flock.agent("meeting_publisher")
    .description(
        "Publish a single upcoming meeting with realistic title, time, attendees "
        "and location."
    )
    .schedule(every=timedelta(seconds=1), max_repeats=1)
    .publishes(MeetingSchedule)
)


# Reminder fires once at the scheduled datetime
def print_reminder(rem: Reminder) -> None:
    print("\n🔔 Meeting Reminder")
    print(f"Title: (see meeting)")
    print(f"When:  {rem.reminder_time.strftime('%H:%M:%S')}")
    print(f"Msg:   {rem.message}")


meeting_reminder = (
    flock.agent("meeting_reminder")
    .description(
        f"At {reminder_time.strftime('%H:%M:%S')} UTC, send a friendly reminder for the "
        "next meeting in the context. Include minutes-before and a helpful message."
    )
    .schedule(at=reminder_time)
    .with_context(
        FilteredContextProvider(
            FilterConfig(type_names={type_registry.name_for(MeetingSchedule)})
        )
    )
    .publishes(Reminder)
    .calls(print_reminder)
)


async def main_cli() -> None:
    print("=" * 70)
    print("ONE-TIME REMINDER – Datetime Scheduling Demo")
    print("=" * 70)
    print("Waiting ~45s so the reminder can fire in demo mode…")
    timeout = 45 if DEMO_MODE else 3600
    await flock.run_until_idle(timeout=timeout)
    print("\nDemo complete.")


async def main_dashboard() -> None:
    print("Starting One-Time Reminder with dashboard at http://127.0.0.1:8344 …")
    await flock.serve(dashboard=True)


async def main() -> None:
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
