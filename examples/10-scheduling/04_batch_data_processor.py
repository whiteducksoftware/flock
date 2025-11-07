"""
Timer Scheduling: Batch Data Processor

Demonstrates a classic batch aggregation pattern driven by a timer. A simulator
publishes DataPoint artifacts frequently; a batch processor runs on a schedule
and aggregates what’s on the blackboard into AggregatedData.

Key concepts
- schedule(every=...) to run aggregation periodically
- Processor uses consumes(..., mode="direct") so it only triggers on its timer
- Context contains previously published DataPoint artifacts
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


USE_DASHBOARD = False


@flock_type
class DataPoint(BaseModel):
    value: float = Field(description="Measured sensor value")
    sensor_id: str = Field(description="Unique sensor identifier")
    timestamp: datetime = Field(description="When measurement was taken")
    unit: str = Field(description="Unit of measurement (celsius, percent, etc)")


@flock_type
class AggregatedData(BaseModel):
    sensor_id: str
    avg_value: float
    min_value: float
    max_value: float
    std_dev: float
    count: int
    period_start: datetime
    period_end: datetime
    unit: str


flock = Flock()

# Sensor simulator — produces realistic points across multiple sensors
sensor_simulator = (
    flock.agent("sensor_simulator")
    .description(
        "Simulate temperature, humidity and pressure sensors. Produce realistic "
        "values, units and timestamps across several sensor_ids."
    )
    .schedule(every=timedelta(seconds=5))
    .publishes(DataPoint)
)

# Batch processor — runs every minute in demo, 10 minutes in production
DEMO_MODE = True
batch_interval = timedelta(minutes=1) if DEMO_MODE else timedelta(minutes=10)

batch_processor = (
    flock.agent("batch_processor")
    .description(
        "Every run, aggregate DataPoint artifacts by sensor_id. Compute count, "
        "min, max, average and standard deviation over the observed period and "
        "publish one AggregatedData per sensor."
    )
    .schedule(every=batch_interval)
    .consumes(DataPoint, mode="direct")
    .publishes(AggregatedData)
)


async def main_cli() -> None:
    print("=" * 70)
    print("BATCH DATA PROCESSOR – Timer-Based Aggregation Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    if DEMO_MODE:
        print("Demo: simulator every 5s; aggregator every 1 min.")
        timeout = 180  # 3 minutes
    else:
        print("Prod: simulator every 5s; aggregator every 10 min.")
        timeout = 1200
    print()
    await flock.run_until_idle(timeout=timeout)
    print("\nDemo complete.")


async def main_dashboard() -> None:
    print("Starting Batch Data Processor with dashboard at http://127.0.0.1:8344 …")
    await flock.serve(dashboard=True)


async def main() -> None:
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())

