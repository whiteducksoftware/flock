"""
Real-Time Dashboard Showcase
=============================

This example demonstrates the real-time dashboard feature of Flock Flow.
The dashboard provides live visualization of agent execution, message flow,
and blackboard state through a WebSocket-powered browser interface.

Usage:
    uv run examples/showcase/04_dashboard.py

Features:
    - Real-time graph visualization (Agent View & Blackboard View)
    - Live streaming output from LLM agents
    - Event log with filtering
    - Publish/Invoke controls from dashboard UI
    - Session persistence (positions saved to IndexedDB)

Environment Variables:
    DASHBOARD_DEV=1  - Enable dev mode (hot reload, CORS)
"""

import asyncio

from pydantic import BaseModel, Field

from flock.logging.logging import configure_logging
from flock.orchestrator import Flock
from flock.registry import flock_type


# 1. Define typed artifacts
@flock_type
class Idea(BaseModel):
    topic: str
    genre: str


@flock_type
class Movie(BaseModel):
    title: str = Field(description="Title in CAPS")
    runtime: int = Field(ge=200, le=400)
    synopsis: str


@flock_type
class Tagline(BaseModel):
    line: str


# 2. Create orchestrator
flock = Flock("openai/gpt-4.1")


# 3. Define agents (they auto-connect through the blackboard!)
movie_agent = (
    flock.agent("movie")
    .description("Generate a compelling movie concept.")
    .consumes(Idea)
    .publishes(Movie)
)

tagline_agent = (
    flock.agent("tagline")
    .description("Write a one-sentence marketing tagline.")
    .consumes(Movie)
    .publishes(Tagline)
)


# 4. Run with dashboard enabled!
async def main():
    # Enable INFO-level logging for dashboard components (debug events, websocket, collector)
    configure_logging(
        flock_level="INFO",
        external_level="ERROR",
        specific_levels={
            "dashboard.collector": "INFO",
            "dashboard.websocket": "INFO",
            "dashboard.orchestrator": "INFO",
            "dashboard.agent": "INFO",
        },
    )

    print("=" * 70)
    print("🎬 Movie Pipeline Dashboard is LIVE!")
    print("=" * 70)
    print()
    print("Dashboard URL: http://localhost:8000")
    print("Browser should open automatically...")
    print()
    print("Try this:")
    print("  1. Wait for dashboard to load")
    print("  2. Watch the graph as agents appear")
    print("  3. Use 'Publish Control' to publish an Idea artifact:")
    print('     {"topic": "Space Pirates", "genre": "Sci-Fi Adventure"}')
    print("  4. Watch the agent flow: Idea → Movie → Tagline")
    print("  5. Open EventLog module to see all events")
    print()
    print("Press Ctrl+C to stop...")
    print("=" * 70)
    print()

    # Start dashboard (blocking call - runs until Ctrl+C)
    await flock.serve(dashboard=True)


if __name__ == "__main__":
    asyncio.run(main())
