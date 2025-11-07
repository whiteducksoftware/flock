"""
Timer Scheduling: Simple Health Monitor

This example demonstrates interval-based scheduling - the core timer pattern.
A health monitor agent runs every 30 seconds to collect system metrics.

KEY CONCEPTS:
- schedule(every=timedelta(...)) for periodic execution
- Timer triggers have no input artifacts (ctx.artifacts = [])
- Access timer metadata: ctx.timer_iteration, ctx.fire_time, ctx.trigger_type
- Agent generates metrics declaratively (LLM-powered)

PATTERN: Interval Scheduling
USE CASE: Regular system monitoring, periodic health checks, heartbeats
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


# ============================================================================
# CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# TYPE REGISTRATION: Define artifact types
# ============================================================================
@flock_type
class HealthStatus(BaseModel):
    """System health metrics collected by the monitor"""

    cpu_percent: float = Field(description="CPU usage percentage (0-100)")
    memory_percent: float = Field(description="Memory usage percentage (0-100)")
    disk_percent: float = Field(description="Disk usage percentage (0-100)")
    timestamp: datetime = Field(description="When the metrics were collected")
    status: str = Field(
        description="Overall health status: healthy, warning, or critical"
    )


# ============================================================================
# AGENT SETUP: Create scheduled health monitor
# ============================================================================
flock = Flock()

# Schedule agent to run every 30 seconds
# This creates a timer trigger that fires at regular intervals
# The agent will generate realistic system health metrics
health_monitor = (
    flock.agent("health_monitor")
    .description(
        "Monitors system health metrics every 30 seconds. "
        "Generate realistic CPU, memory, and disk usage statistics (as percentages). "
        "CPU should vary between 10-90%, memory between 30-80%, disk between 40-70%. "
        "Set status to 'healthy' if all metrics are under 80%, 'warning' if any are 80-90%, "
        "'critical' if any exceed 90%."
    )
    .schedule(every=timedelta(seconds=30))  # Interval-based scheduling
    .publishes(HealthStatus)
)


# ============================================================================
# RUN: Execute the orchestrator
# ============================================================================
async def main_cli():
    """
    CLI mode: Run for a limited time to demonstrate the pattern

    NOTE: Timers run indefinitely by default. For demo purposes,
    we'll run for a specific duration (2 minutes) to show several iterations.
    """
    print("=" * 70)
    print("SIMPLE HEALTH MONITOR - Interval Scheduling Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print("Health monitor fires every 30 seconds")
    print("This demo will run for 2 minutes to show multiple iterations.")
    print("=" * 70)
    print()

    # Use run_until_idle with timeout when using scheduled agents in CLI mode
    # active timer will prevent the idle state from being reached
    await flock.run_until_idle(timeout=120)  # 2 minutes

    print()
    print("=" * 70)
    print("Health monitor demo complete!")
    print("=" * 70)


async def main_dashboard():
    """
    Dashboard mode: Serve with interactive web interface

    The dashboard will show:
    - Timer triggering the health_monitor agent every 30 seconds
    - HealthStatus artifacts being published
    - Agent execution history
    """
    print("Starting Health Monitor with Dashboard...")
    print("Dashboard will be available at: http://localhost:8344")
    print("Timer fires every 30 seconds - watch the agent execute!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
