"""
Cron Schedule Demo (UTC)

This example demonstrates cron-based scheduling using Flock's timer system.

- Cron expressions are evaluated in UTC
- Supported syntax: `*`, lists (","), ranges ("-"), steps ("/")
- Sunday may be written as 0 or 7

To see it in action quickly, we use an "every minute" schedule and run
for just long enough to observe one or two firings in CLI demo mode.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from pydantic import BaseModel, Field

from flock import Flock
from flock.core.artifacts import flock_type
from flock.core.agent import AgentContext


@flock_type
class Ping(BaseModel):
    message: str = Field(default="cron tick")
    fired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


DEMO_MODE = True  # CLI demo: run briefly and exit
USE_DASHBOARD = False


async def main() -> None:
    flock = Flock()

    # Every minute (UTC) at second 0
    agent = (
        flock.agent("cron_pinger")
        .description("Publishes a Ping on every minute boundary (UTC)")
        .schedule(cron="0 * * * *")
        .publishes(Ping)
    )

    async def on_ping(p: Ping) -> None:
        print(f"[cron_pinger] {p.message} at {p.fired_at.isoformat()}")

    flock.subscribe(Ping, on_ping)

    if USE_DASHBOARD:
        # Dashboard mode: block indefinitely
        await flock.serve(dashboard=True)
        return

    if DEMO_MODE:
        # CLI demo: run briefly to observe cron behavior
        print("Cron demo running... waiting for next minute boundary (UTC)")
        
        # Start the orchestrator in background
        serve_task = asyncio.create_task(flock.serve())
        
        # Sleep until a bit after the next minute boundary so at least one tick fires
        now = datetime.now(UTC)
        next_minute = (now.replace(second=0, microsecond=0) + timedelta(minutes=1))
        sleep_for = (next_minute - now).total_seconds() + 5.0  # buffer
        
        try:
            await asyncio.sleep(max(6.0, sleep_for))
        except KeyboardInterrupt:
            print("\nStopping cron demo...")
        finally:
            serve_task.cancel()
            try:
                await serve_task
            except asyncio.CancelledError:
                pass
        return

    # Default: serve in CLI mode (blocking)
    await flock.serve()


if __name__ == "__main__":
    asyncio.run(main())

