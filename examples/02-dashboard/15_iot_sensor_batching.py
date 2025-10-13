"""
Combined Features: JoinSpec + BatchSpec for IoT Sensor Processing (Dashboard)

Real-world scenario: Smart factory monitors temperature and pressure sensors
from multiple machines. System correlates readings from same machine (JoinSpec),
then batches 5 correlated readings together for bulk analysis (BatchSpec).

This combines:
- JoinSpec: Correlate temp + pressure by device_id
- BatchSpec: Batch 5 correlated pairs for efficient processing

📊 Dashboard Features:
- Visualize sensor readings arriving
- Watch correlation matching (temp + pressure per device)
- See batch accumulation (5 devices)
- Monitor quality analysis reports
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.subscription import BatchSpec, JoinSpec


@flock_type
class TemperatureSensor(BaseModel):
    device_id: str
    temperature_c: float = Field(description="Temperature in Celsius")
    timestamp: str
    location: str


@flock_type
class PressureSensor(BaseModel):
    device_id: str
    pressure_bar: float = Field(description="Pressure in bars")
    timestamp: str
    location: str


@flock_type
class QualityAnalysis(BaseModel):
    batch_id: str
    devices_analyzed: list[str]
    total_readings: int
    anomalies_detected: list[str]
    overall_status: str
    recommendations: list[str]


flock = Flock()

# Quality analyzer: Correlate sensors by device, then batch for analysis
quality_analyzer = (
    flock.agent("quality_analyzer")
    .description(
        "Manufacturing quality control system that correlates temperature + pressure "
        "readings from same device (JoinSpec), then batches 5 devices for bulk "
        "analysis (BatchSpec). Combines two powerful features for efficient IoT processing!"
    )
    .consumes(
        TemperatureSensor,
        PressureSensor,
        join=JoinSpec(
            by=lambda x: x.device_id,  # Correlate by device ID
            within=timedelta(seconds=30),  # Readings within 30 seconds
        ),
        batch=BatchSpec(
            size=5,  # Batch 5 correlated device readings
            timeout=timedelta(seconds=45),  # OR flush every 45 seconds
        ),
    )
    .publishes(QualityAnalysis)
)

# Start dashboard and publish sensor readings!
# Try publishing temp + pressure for same device_id to see correlation
# Publish 5 devices to trigger batch flush
# Or wait 45 seconds for timeout-based flush
asyncio.run(flock.serve(dashboard=True), debug=True)
