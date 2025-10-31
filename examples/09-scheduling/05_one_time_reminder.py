"""
Timer Scheduling: One-Time Reminder

This example demonstrates datetime-based scheduling for one-time execution.
A reminder fires once at a specific datetime to send a notification.

KEY CONCEPTS:
- schedule(at=datetime(...)) for one-time execution
- Executes exactly once at the specified datetime
- max_repeats=1 is implicit for datetime scheduling
- Useful for reminders, scheduled tasks, future actions

PATTERN: DateTime-Based One-Time Scheduling
USE CASE: Reminders, scheduled notifications, future task execution, delays
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.utils.runtime import Context


# ============================================================================
# CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# TYPE REGISTRATION: Define artifact types
# ============================================================================
@flock_type
class MeetingSchedule(BaseModel):
    """Meeting information stored on blackboard"""

    meeting_id: str = Field(description="Unique meeting identifier")
    title: str = Field(description="Meeting title")
    scheduled_time: datetime = Field(description="When meeting is scheduled")
    participants: list[str] = Field(description="List of participant names")
    location: str = Field(description="Meeting location or video link")


@flock_type
class Reminder(BaseModel):
    """Reminder notification sent to participants"""

    meeting_id: str = Field(description="Related meeting identifier")
    message: str = Field(description="Reminder message")
    reminder_time: datetime = Field(description="When reminder was sent")
    minutes_before: int = Field(description="How many minutes before meeting")
    iteration: int = Field(description="Timer iteration (should be 0 for one-time)")


# ============================================================================
# AGENT SETUP: Create meeting scheduler and reminder agent
# ============================================================================
flock = Flock("openai/gpt-4o-mini")

# For demo purposes, we'll schedule reminders shortly in the future
# In production, you would schedule at actual meeting times
DEMO_MODE = True

if DEMO_MODE:
    # Demo: schedule reminder 30 seconds from now
    reminder_time = datetime.now() + timedelta(seconds=30)
    print(f"\n[Setup] Scheduling reminder for: {reminder_time.strftime('%H:%M:%S')}")
    print(f"[Setup] Current time: {datetime.now().strftime('%H:%M:%S')}")
    print("[Setup] Reminder will fire in 30 seconds\n")
else:
    # Production: schedule for specific datetime
    # Example: November 1, 2025 at 8:55 AM
    reminder_time = datetime(2025, 11, 1, 8, 55)


# Agent 1: Publish meeting information (runs once at startup)
# In production, this would be triggered by user creating a meeting
meeting_publisher = (
    flock.agent("meeting_publisher")
    .description("Publishes meeting information when meetings are scheduled")
    .schedule(every=timedelta(seconds=1), max_repeats=1)  # Run once at startup
    .publishes(MeetingSchedule)
)


# Agent 2: Send reminder at specific time
# This agent runs ONCE at the scheduled datetime
meeting_reminder = (
    flock.agent("meeting_reminder")
    .description(
        f"Sends meeting reminder at {reminder_time.strftime('%H:%M:%S')}. "
        "Executes once at the specified datetime."
    )
    .schedule(at=reminder_time)  # One-time execution
    .consumes(MeetingSchedule)
    .publishes(Reminder)
)


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================
@meeting_publisher.implement
async def publish_meeting(ctx: Context) -> MeetingSchedule:
    """
    Publish meeting information.

    In production, this would be triggered by:
    - User creating meeting in calendar
    - API endpoint receiving meeting request
    - Integration with scheduling system
    """
    print("[Meeting Publisher] Publishing meeting information...")

    meeting_time = datetime.now() + timedelta(minutes=5)

    meeting = MeetingSchedule(
        meeting_id="MTG_001",
        title="Team Standup",
        scheduled_time=meeting_time,
        participants=["Alice", "Bob", "Carol", "David"],
        location="https://meet.example.com/standup",
    )

    print(
        f"[Meeting Publisher] Meeting scheduled for: {meeting_time.strftime('%H:%M:%S')}"
    )
    return meeting


@meeting_reminder.implement
async def send_reminder(ctx: Context) -> Reminder:
    """
    Send meeting reminder at scheduled time.

    One-Time DateTime Scheduling:
    - ctx.trigger_type = "timer"
    - ctx.timer_iteration = 0 (always 0 for one-time)
    - ctx.fire_time = scheduled datetime
    - Executes exactly once
    - max_repeats=1 is implicit
    """
    assert ctx.trigger_type == "timer"
    assert ctx.timer_iteration == 0  # Always 0 for one-time execution

    print()
    print("=" * 70)
    print("[Meeting Reminder] REMINDER TRIGGERED!")
    print(f"[Meeting Reminder] Current time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"[Meeting Reminder] Scheduled for: {ctx.fire_time.strftime('%H:%M:%S')}")
    print("=" * 70)

    # Get meeting information from blackboard
    meetings = ctx.get_artifacts(MeetingSchedule)

    if not meetings:
        print("[Meeting Reminder] WARNING: No meeting found on blackboard")
        return Reminder(
            meeting_id="UNKNOWN",
            message="Meeting reminder triggered but no meeting found",
            reminder_time=datetime.now(),
            minutes_before=5,
            iteration=ctx.timer_iteration,
        )

    meeting = meetings[0]

    # Calculate time until meeting
    time_until = meeting.scheduled_time - datetime.now()
    minutes_before = int(time_until.total_seconds() / 60)

    # Create reminder message
    message = f"""
🔔 Meeting Reminder

Title: {meeting.title}
Time: {meeting.scheduled_time.strftime("%I:%M %p")}
Location: {meeting.location}
Participants: {", ".join(meeting.participants)}

The meeting starts in {minutes_before} minutes!
"""

    print(message)

    return Reminder(
        meeting_id=meeting.meeting_id,
        message=message.strip(),
        reminder_time=datetime.now(),
        minutes_before=minutes_before,
        iteration=ctx.timer_iteration,
    )


# ============================================================================
# RUN: Execute the orchestrator
# ============================================================================
async def main_cli():
    """
    CLI mode: Demonstrate one-time datetime scheduling

    Flow:
    1. meeting_publisher runs once to publish meeting info
    2. meeting_reminder scheduled for specific datetime
    3. When datetime arrives, reminder fires ONCE
    4. Demo waits long enough to see the reminder fire
    """
    print("=" * 70)
    print("ONE-TIME REMINDER - DateTime-Based Scheduling Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print()

    if DEMO_MODE:
        print("DEMO MODE:")
        print(f"  - Reminder scheduled for: {reminder_time.strftime('%H:%M:%S')}")
        print("  - Will fire in approximately 30 seconds")
        print()
        print("In production, use: .schedule(at=datetime(2025, 11, 1, 8, 55))")
    else:
        print("PRODUCTION MODE:")
        print(
            f"  - Reminder scheduled for: {reminder_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    print()
    print("Key Points:")
    print("  - Executes exactly ONCE at specified datetime")
    print("  - max_repeats=1 is implicit for datetime scheduling")
    print("  - timer_iteration will always be 0")
    print("=" * 70)
    print()

    # Start orchestrator
    serve_task = asyncio.create_task(flock.serve())

    try:
        # Wait long enough for reminder to fire (45 seconds in demo mode)
        if DEMO_MODE:
            print("Waiting for reminder to fire...")
            await asyncio.sleep(45)
        else:
            # In production, would run indefinitely
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        print("\n\nStopping reminder system...")
    finally:
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

    print()
    print("=" * 70)
    print("One-time reminder demo complete!")
    print("=" * 70)


async def main_dashboard():
    """
    Dashboard mode: Visualize one-time scheduling

    The dashboard will show:
    - meeting_publisher running once at startup
    - MeetingSchedule artifact on blackboard
    - meeting_reminder waiting for scheduled time
    - Reminder artifact when datetime arrives
    """
    print("Starting One-Time Reminder with Dashboard...")
    print("Dashboard will be available at: http://localhost:8344")
    print()
    if DEMO_MODE:
        print(f"Reminder scheduled for: {reminder_time.strftime('%H:%M:%S')}")
        print("Watch the timer fire at the scheduled time!")
    else:
        print(f"Reminder scheduled for: {reminder_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
