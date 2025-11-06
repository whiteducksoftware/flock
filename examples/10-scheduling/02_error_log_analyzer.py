#!/usr/bin/env python3
"""
Error Log Analyzer
Demonstrates scheduled agents with context filtering using proper Flock API.

This example shows:
- Scheduled log collection (every 30 seconds)
- Scheduled error analysis (every 2 minutes for demo)
- Context filtering with where clause
- Timer context access
- Both CLI and dashboard modes
"""

import asyncio
import random
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
class LogEntry(BaseModel):
    """A log message with severity level"""
    level: str = Field(description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    message: str = Field(description="Log message content")
    timestamp: datetime = Field(description="When the log was created")
    source: str = Field(description="Source system/component")

@flock_type
class ErrorReport(BaseModel):
    """Analysis report for ERROR-level logs"""
    error_count: int = Field(description="Number of errors found")
    error_messages: list[str] = Field(description="List of error messages")
    analysis: str = Field(description="Analysis of error patterns")
    report_time: datetime = Field(description="When report was generated")
    iteration: int = Field(description="Timer iteration number")

# ============================================================================
# AGENT SETUP: Create scheduled agents using proper Flock API
# ============================================================================
flock = Flock()

# Agent 1: Log collector - runs every 30 seconds
# This simulates continuous log generation from various systems
log_collector = (
    flock.agent("log_collector")
    .description(
        "Collects and publishes log entries every 30 seconds. "
        "Simulates logs from API servers, databases, and auth services. "
        "Generates mix of DEBUG, INFO, WARNING, and ERROR level logs. "
        "Each log entry should have a realistic message and timestamp."
    )
    .schedule(every=timedelta(seconds=30))
    .publishes(LogEntry)
)

# Agent 2: Error analyzer - runs every 2 minutes (demo timing)
# Uses context filtering to only process ERROR-level logs
error_analyzer = (
    flock.agent("error_analyzer")
    .description(
        "Analyzes ERROR-level logs every 2 minutes. "
        "Generates reports on error patterns and suggests fixes. "
        "Uses context filtering to process only ERROR logs. "
        "For each analysis, count errors by source (api_server, database, auth_service) "
        "and provide recommendations based on error patterns. "
        "Include timer iteration and timestamp in the report."
    )
    .schedule(every=timedelta(minutes=2))  # Demo: every 2 minutes
    .consumes(LogEntry, where=lambda log: log.level == "ERROR")  # Context filter!
    .publishes(ErrorReport)
)

# ============================================================================
# RUN: Execute the orchestrator
# ============================================================================
async def main_cli():
    """
    CLI mode: Run for a limited time to demonstrate the pattern
    
    The demo will run for 6 minutes to show:
    - Log collector firing every 30 seconds (~12 times)
    - Error analyzer firing every 2 minutes (~3 times)
    """
    print("=" * 70)
    print("ERROR LOG ANALYZER - Timer + Context Filtering Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print("Log collector fires every 30 seconds")
    print("Error analyzer fires every 2 minutes (filters ERROR logs only)")
    print("This demo will run for 6 minutes to show multiple iterations.")
    print("=" * 70)
    print()

    # Use run_until_idle with timeout for proper CLI demo mode
    # This initializes timers and runs for specified duration
    await flock.run_until_idle(timeout=360)  # 6 minutes

    print()
    print("=" * 70)
    print("Error log analyzer demo complete!")
    print("=" * 70)


async def main_dashboard():
    """
    Dashboard mode: Serve with interactive web interface
    
    The dashboard will show:
    - Log collector triggering every 30 seconds
    - Error analyzer triggering every 2 minutes  
    - LogEntry artifacts being published
    - ErrorReport artifacts being generated
    - Real-time filtering of ERROR logs
    """
    print("Starting Error Log Analyzer with Dashboard...")
    print("Dashboard will be available at: http://localhost:8344")
    print("Log collector fires every 30 seconds")
    print("Error analyzer fires every 2 minutes - watch the filtering!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
