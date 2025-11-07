"""
Cron Schedule Demo (UTC)

Demonstrates cron-based scheduling using Flock timers. For a quick demo we run
every minute; cron expressions are interpreted in UTC.

Key points
- schedule(cron="*/1 * * * *") fires every minute (UTC)
- Use .calls(...) to perform a side-effect (print) after publishing
"""

import asyncio
from datetime import UTC, datetime
from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class Ping(BaseModel):
    message: str = Field(default="cron tick")
    fired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


USE_DASHBOARD = False


def on_ping(p: Ping) -> None:
    print(f"[cron_pinger] {p.message} at {p.fired_at.isoformat()}")


async def main() -> None:
    flock = Flock()

    agent = (
        flock.agent("cron_pinger")
        .description("Publish a Ping on every minute boundary (UTC)")
        .schedule(cron="*/1 * * * *")
        .publishes(Ping)
        .calls(on_ping)
    )

    if USE_DASHBOARD:
        await flock.serve(dashboard=True)
        return

    print("Cron demo running… waiting ~70s to observe at least one tick.")
    await flock.run_until_idle(timeout=70)


if __name__ == "__main__":
    asyncio.run(main())

