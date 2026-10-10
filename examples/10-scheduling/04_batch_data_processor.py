"""
Timer Scheduling: Batch Data Processor

Demonstrates a classic batch aggregation pattern driven by a timer. A simulator
publishes DataPoint artifacts frequently; a batch processor runs on a schedule
and aggregates what’s on the blackboard into AggregatedData.

Key concepts
- schedule(every=...) to run aggregation periodically
- Processor is triggered by its timer alone
- with_context(FilteredContextProvider(...)) gives it the DataPoint artifacts
  published so far as context
- publishes(..., fan_out=(1, 10)) lets it publish one AggregatedData per sensor
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig
from flock.registry import flock_type, type_registry


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
        "Simulate one reading from one of three sensors: temp-1 (celsius), "
        "humidity-1 (percent) or pressure-1 (hPa). Pick the sensor at random and "
        "produce a realistic value and timestamp."
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
    .with_context(
        FilteredContextProvider(
            FilterConfig(type_names={type_registry.name_for(DataPoint)})
        )
    )
    .publishes(AggregatedData, fan_out=(1, 10))  # one per sensor
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
