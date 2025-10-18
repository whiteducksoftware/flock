"""
Combined Features: JoinSpec + BatchSpec for IoT Sensor Processing

Real-world scenario: Smart factory monitors temperature and pressure sensors
from multiple machines. System correlates readings from same machine (JoinSpec),
then batches 5 correlated readings together for bulk analysis (BatchSpec).

This combines:
- JoinSpec: Correlate temp + pressure by device_id
- BatchSpec: Batch 5 correlated pairs for efficient processing
"""

import asyncio
from datetime import timedelta

from pydantic import BaseModel, Field

from flock import Flock
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
        "readings from same device, then batches 5 devices for bulk analysis"
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


async def simulate_device_readings(
    flock: Flock, device_id: str, location: str, temp: float, pressure: float
):
    """Simulate sensor readings from one device"""
    timestamp = f"2025-10-13 14:{30 + int(device_id[-1]) * 2}:00"

    # Publish temperature reading
    await flock.publish(
        TemperatureSensor(
            device_id=device_id,
            temperature_c=temp,
            timestamp=timestamp,
            location=location,
        )
    )

    # Publish pressure reading (correlated with temperature)
    await flock.publish(
        PressureSensor(
            device_id=device_id,
            pressure_bar=pressure,
            timestamp=timestamp,
            location=location,
        )
    )


async def main():
    print("🏭 Smart Factory IoT Sensor Processing")
    print("=" * 60)
    print("📡 Combined JoinSpec + BatchSpec for efficient monitoring\n")

    print("⚙️  Configuration:")
    print("   🔗 JoinSpec:  Correlate temp + pressure by device_id")
    print("   📦 BatchSpec: Batch 5 correlated pairs together")
    print("   ⏱️  Timeout:   45 seconds for partial batches\n")

    # Simulate readings from 5 devices (will trigger size threshold)
    print("=" * 60)
    print("📊 SCENARIO 1: Batch 5 Correlated Device Readings")
    print("=" * 60)
    print("📡 Receiving sensor data from factory floor...\n")

    devices = [
        ("DEVICE-001", "Assembly Line A", 72.5, 1.2),
        ("DEVICE-002", "Assembly Line A", 75.0, 1.3),
        ("DEVICE-003", "Assembly Line B", 68.0, 1.1),
        ("DEVICE-004", "Assembly Line B", 73.5, 1.25),
        ("DEVICE-005", "Quality Control", 70.0, 1.15),
    ]

    for device_id, location, temp, pressure in devices:
        print(f"   🌡️  {device_id} ({location}):")
        print(f"      Temperature: {temp}°C, Pressure: {pressure} bar")
        await simulate_device_readings(flock, device_id, location, temp, pressure)
        await asyncio.sleep(0.1)  # Small delay between devices

    print("\n⚡ Processing correlations and batching...")
    await flock.run_until_idle()

    # Add 2 more devices (partial batch - will wait for timeout)
    print("\n" + "=" * 60)
    print("📊 SCENARIO 2: Partial Batch (2 devices)")
    print("=" * 60)
    print("📡 Two more devices reporting...\n")

    additional_devices = [
        ("DEVICE-006", "Packaging", 69.0, 1.18),
        ("DEVICE-007", "Packaging", 71.5, 1.22),
    ]

    for device_id, location, temp, pressure in additional_devices:
        print(f"   🌡️  {device_id} ({location}):")
        print(f"      Temperature: {temp}°C, Pressure: {pressure} bar")
        await simulate_device_readings(flock, device_id, location, temp, pressure)
        await asyncio.sleep(0.1)

    print("\n⏳ Only 2 devices (not enough for batch size 5)...")
    print("   Waiting for 45-second timeout or more devices...\n")

    # Simulate timeout
    await asyncio.sleep(2)
    print("   ⏰ Timeout triggered! Flushing partial batch...")
    await flock._check_batch_timeouts()
    await flock.run_until_idle()

    # Retrieve quality analysis reports
    analyses = await flock.store.get_by_type(QualityAnalysis)

    print("\n" + "=" * 60)
    print("📋 QUALITY ANALYSIS REPORTS:")
    print("=" * 60)

    for i, analysis in enumerate(analyses, 1):
        print(f"\n🔬 Analysis Batch #{i} ({analysis.batch_id}):")
        print(f"   Devices Analyzed: {', '.join(analysis.devices_analyzed)}")
        print(f"   Total Readings:   {analysis.total_readings} sensors")
        print(f"   Status:           {analysis.overall_status}")

        if analysis.anomalies_detected:
            print(f"   ⚠️  Anomalies:      {', '.join(analysis.anomalies_detected)}")
        else:
            print("   ✅ No Anomalies")

        if analysis.recommendations:
            print("   💡 Recommendations:")
            for rec in analysis.recommendations:
                print(f"      • {rec}")

    print("\n" + "=" * 60)
    print(f"✅ Analyzed {len(analyses)} batches")
    print(f"🔗 Total Correlated Devices: {len(devices) + len(additional_devices)}")
    print("\n💡 KEY FEATURES COMBINED:")
    print("   1️⃣  JoinSpec: Correlates temp + pressure by device")
    print("   2️⃣  BatchSpec: Batches 5 correlations for bulk analysis")
    print("   3️⃣  Efficient: Processes multiple devices together!")


if __name__ == "__main__":
    asyncio.run(main())
