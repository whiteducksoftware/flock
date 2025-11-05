"""
Timer Scheduling: Batch Data Processor

This example demonstrates batch aggregation with timer scheduling.
A processor runs every 10 minutes to aggregate accumulated sensor data.

KEY CONCEPTS:
- Timer triggers batch processing of accumulated artifacts
- Group and aggregate data by key (sensor_id)
- Calculate statistics over time windows
- Real-world IoT/monitoring use case

PATTERN: Batch Aggregation with Timer
USE CASE: IoT data processing, metric aggregation, time-window analytics
"""

import asyncio
import random
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
class DataPoint(BaseModel):
    """Raw sensor data point"""

    value: float = Field(description="Measured sensor value")
    sensor_id: str = Field(description="Unique sensor identifier")
    timestamp: datetime = Field(description="When measurement was taken")
    unit: str = Field(description="Unit of measurement (celsius, percent, etc)")


@flock_type
class AggregatedData(BaseModel):
    """Aggregated sensor statistics over time window"""

    sensor_id: str = Field(description="Sensor identifier")
    avg_value: float = Field(description="Average value over time window")
    min_value: float = Field(description="Minimum value over time window")
    max_value: float = Field(description="Maximum value over time window")
    std_dev: float = Field(description="Standard deviation")
    count: int = Field(description="Number of data points aggregated")
    period_start: datetime = Field(description="Start of aggregation window")
    period_end: datetime = Field(description="End of aggregation window")
    unit: str = Field(description="Unit of measurement")


# ============================================================================
# AGENT SETUP: Create sensor simulator and batch processor
# ============================================================================
flock = Flock()

# Agent 1: Simulate sensors publishing data every 5 seconds
# In production, this would be actual sensor data ingestion
sensor_simulator = (
    flock.agent("sensor_simulator")
    .description(
        "Simulates IoT sensors publishing data points. "
        "Generates temperature, humidity, and pressure readings."
    )
    .schedule(every=timedelta(seconds=5))
    .publishes(DataPoint)
)


# Agent 2: Process accumulated data every 10 minutes (demo: 1 minute)
# Aggregates all data points by sensor and calculates statistics
DEMO_MODE = True

if DEMO_MODE:
    batch_interval = timedelta(minutes=1)  # Demo: every 1 minute
else:
    batch_interval = timedelta(minutes=10)  # Production: every 10 minutes

batch_processor = (
    flock.agent("batch_processor")
    .description(
        f"Processes sensor data every {batch_interval.total_seconds() / 60:.0f} minutes. "
        "Aggregates data by sensor and calculates statistics."
    )
    .schedule(every=batch_interval)
    .consumes(DataPoint)
    .publishes(AggregatedData)
)


# ============================================================================
# AGENT IMPLEMENTATIONS
# ============================================================================
@sensor_simulator.implement
async def simulate_sensors(ctx: Context) -> list[DataPoint]:
    """
    Simulate IoT sensors publishing measurements.

    In production, this would:
    - Receive data from actual sensors
    - Validate and normalize readings
    - Publish to blackboard for processing
    """
    # Simulate 5 different sensors
    sensors = [
        {"id": "temp_sensor_01", "type": "temperature", "unit": "celsius"},
        {"id": "temp_sensor_02", "type": "temperature", "unit": "celsius"},
        {"id": "humidity_sensor_01", "type": "humidity", "unit": "percent"},
        {"id": "pressure_sensor_01", "type": "pressure", "unit": "hPa"},
        {"id": "pressure_sensor_02", "type": "pressure", "unit": "hPa"},
    ]

    data_points = []
    now = datetime.now()

    for sensor in sensors:
        # Generate realistic readings based on sensor type
        if sensor["type"] == "temperature":
            value = random.uniform(18.0, 28.0)
        elif sensor["type"] == "humidity":
            value = random.uniform(30.0, 70.0)
        else:  # pressure
            value = random.uniform(980.0, 1020.0)

        data_points.append(
            DataPoint(
                value=round(value, 2),
                sensor_id=sensor["id"],
                timestamp=now,
                unit=sensor["unit"],
            )
        )

    print(f"[Sensor Simulator] Published {len(data_points)} data points")
    return data_points


@batch_processor.implement
async def process_batch(ctx: Context) -> list[AggregatedData]:
    """
    Aggregate sensor data by sensor_id and calculate statistics.

    Batch Processing Pattern:
    - Timer fires at regular intervals (every 10 minutes)
    - Collects ALL data points from blackboard
    - Groups by sensor_id
    - Calculates aggregate statistics for each sensor
    - Publishes aggregated results
    """
    assert ctx.trigger_type == "timer"
    assert ctx.artifacts == []

    # Get all data points from blackboard
    all_data_points = ctx.get_artifacts(DataPoint)

    print()
    print("=" * 70)
    print(f"[Batch Processor] Timer fired - Iteration {ctx.timer_iteration}")
    print(f"[Batch Processor] Processing {len(all_data_points)} data points")
    print("=" * 70)

    if not all_data_points:
        print("No data points to process")
        return []

    # Group by sensor_id
    by_sensor: dict[str, list[DataPoint]] = {}
    for point in all_data_points:
        if point.sensor_id not in by_sensor:
            by_sensor[point.sensor_id] = []
        by_sensor[point.sensor_id].append(point)

    print(f"Grouped into {len(by_sensor)} unique sensors")

    # Aggregate each sensor
    results = []
    for sensor_id, points in by_sensor.items():
        values = [p.value for p in points]

        # Calculate statistics
        avg_value = sum(values) / len(values)
        min_value = min(values)
        max_value = max(values)

        # Calculate standard deviation
        variance = sum((x - avg_value) ** 2 for x in values) / len(values)
        std_dev = variance**0.5

        # Time window
        timestamps = [p.timestamp for p in points]
        period_start = min(timestamps)
        period_end = max(timestamps)

        aggregated = AggregatedData(
            sensor_id=sensor_id,
            avg_value=round(avg_value, 2),
            min_value=round(min_value, 2),
            max_value=round(max_value, 2),
            std_dev=round(std_dev, 2),
            count=len(points),
            period_start=period_start,
            period_end=period_end,
            unit=points[0].unit,
        )

        results.append(aggregated)

        # Log summary
        print(f"\n{sensor_id}:")
        print(f"  Count: {aggregated.count}")
        print(f"  Average: {aggregated.avg_value} {aggregated.unit}")
        print(f"  Range: {aggregated.min_value} - {aggregated.max_value}")
        print(f"  Std Dev: {aggregated.std_dev}")

    print(f"\nPublished {len(results)} aggregated reports")
    return results


# ============================================================================
# RUN: Execute the orchestrator
# ============================================================================
async def main_cli():
    """
    CLI mode: Demonstrate batch data processing with timers

    Flow:
    1. sensor_simulator runs every 5s, publishes raw DataPoints
    2. batch_processor runs every 1 minute (demo) or 10 minutes (prod)
    3. Aggregates accumulated data by sensor_id
    4. Demo runs for 3 minutes to show 3 batch cycles
    """
    print("=" * 70)
    print("BATCH DATA PROCESSOR - Timer-Based Aggregation Demo")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print()

    if DEMO_MODE:
        print("DEMO MODE:")
        print("  - Sensor Simulator: every 5 seconds")
        print("  - Batch Processor: every 1 minute")
        print()
        print("In production, use every=timedelta(minutes=10)")
        print("Demo runs for 3 minutes to show multiple batch cycles.")
    else:
        print("PRODUCTION MODE:")
        print("  - Sensor Simulator: every 5 seconds")
        print("  - Batch Processor: every 10 minutes")

    print("=" * 70)
    print()

    # Start orchestrator
    serve_task = asyncio.create_task(flock.serve())

    try:
        await asyncio.sleep(180)  # 3 minutes
    except KeyboardInterrupt:
        print("\n\nStopping batch processor...")
    finally:
        serve_task.cancel()
        try:
            await serve_task
        except asyncio.CancelledError:
            pass

    print()
    print("=" * 70)
    print("Batch processing demo complete!")
    print("=" * 70)


async def main_dashboard():
    """
    Dashboard mode: Visualize batch processing

    The dashboard will show:
    - sensor_simulator publishing DataPoint artifacts frequently
    - DataPoints accumulating on blackboard
    - batch_processor firing periodically
    - AggregatedData artifacts with statistics
    """
    print("Starting Batch Data Processor with Dashboard...")
    print("Dashboard will be available at: http://localhost:8344")
    print()
    if DEMO_MODE:
        print("DEMO MODE: Batch every 1 minute")
    else:
        print("PRODUCTION MODE: Batch every 10 minutes")
    print()
    print("Watch how data points accumulate and get aggregated!")
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
