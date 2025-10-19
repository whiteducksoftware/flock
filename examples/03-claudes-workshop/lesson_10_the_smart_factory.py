"""
🎓 Lesson 10: The Smart Factory - Combining JoinSpec + BatchSpec

CONCEPT: The ultimate power move! Combine JoinSpec (correlation) with BatchSpec
(batching) to create sophisticated multi-stage processing pipelines. First correlate
related data, THEN batch the correlated groups for efficient bulk processing.

REAL-WORLD USE CASE:
Smart factory with IoT sensors monitors temperature + pressure for each machine.
Need to:
1. Correlate temp + pressure readings from SAME device (JoinSpec)
2. Batch 5 correlated device readings for bulk analysis (BatchSpec)
3. Generate quality control reports for manufacturing efficiency

KEY LEARNING:
- JoinSpec + BatchSpec work together seamlessly
- Flow: Publish → Correlate (JoinSpec) → Batch Groups (BatchSpec) → Process
- BatchSpec batches GROUPS (correlated pairs), not individual artifacts
- Agent receives list of correlation groups, processes them in bulk

WHY THIS MATTERS:
Real-world systems often need BOTH:
- Medical: Correlate patient tests + images, batch 10 patients for radiologist
- Finance: Correlate trades + confirmations, batch 50 for reconciliation
- Logistics: Correlate shipments + manifests, batch 100 for customs processing

PROGRESSION NOTE:
This is THE advanced lesson! You've learned all the building blocks:
- L01-L02: Basic agents and chaining
- L03-L04: Predicates and feedback loops
- L05: Tracing and observability
- L06-L07: Visibility and parallelism
- L08: JoinSpec correlation
- L09: BatchSpec batching
NOW: Combine them for production-grade IoT processing!
"""

import asyncio
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type
from flock.subscription import BatchSpec, JoinSpec


@flock_type
class TemperatureSensor(BaseModel):
    device_id: str  # ⭐ Correlation key
    temperature_c: float = Field(description="Temperature in Celsius")
    timestamp: datetime = Field(default_factory=datetime.now)
    location: str


@flock_type
class PressureSensor(BaseModel):
    device_id: str  # ⭐ Correlation key (same as TemperatureSensor)
    pressure_bar: float = Field(description="Pressure in bars")
    timestamp: datetime = Field(default_factory=datetime.now)
    location: str


@flock_type
class QualityReport(BaseModel):
    batch_id: str
    devices_analyzed: list[str]
    total_readings: int
    anomalies_detected: list[str]
    overall_status: str  # "HEALTHY", "WARNING", "CRITICAL"
    recommendations: list[str]
    analysis_time: str


flock = Flock()

# 🏭 The Smart Factory Agent - Correlates sensors, then batches for analysis!
quality_control = (
    flock.agent("quality_control")
    .description(
        "Smart factory quality control system. Uses JoinSpec to correlate "
        "temperature + pressure readings from same device, then uses BatchSpec "
        "to batch 5 correlated device readings for efficient bulk analysis. "
        "This is the power of combining two Logic Operations features!"
    )
    .consumes(
        TemperatureSensor,
        PressureSensor,
        join=JoinSpec(
            by=lambda x: x.device_id,  # ⭐ Correlate by device ID
            within=timedelta(seconds=30),  # ⭐ Must arrive within 30 seconds
        ),
        batch=BatchSpec(
            size=5,  # ⭐ Batch 5 correlated device readings
            timeout=timedelta(seconds=45),  # ⭐ OR flush after 45 seconds
        ),
    )
    .publishes(QualityReport)
)


async def main():
    """
    📖 LEARNING SCENARIO:

    Phase 1: CORRELATION
    - Publish temp + pressure readings for 5 devices
    - JoinSpec correlates them by device_id
    - Creates 5 correlation groups

    Phase 2: BATCHING
    - BatchSpec accumulates correlation groups
    - When 5 groups collected → FLUSH!
    - Agent processes all 5 devices together

    Phase 3: TIMEOUT HANDLING
    - Publish 2 more devices (partial batch)
    - Timeout triggers after 45 seconds
    - Partial batch flushes automatically

    💡 KEY INSIGHT: BatchSpec counts GROUPS, not individual artifacts!
       BatchSpec(size=5) with JoinSpec means "batch 5 correlated pairs"
    """

    print("🎯 LESSON 10: The Smart Factory - JoinSpec + BatchSpec")
    print("=" * 60)
    print("🏭 IoT Sensor Monitoring & Quality Control")
    print()
    print("🔬 MULTI-STAGE PROCESSING:")
    print("   1️⃣  JoinSpec:  Correlate temp + pressure by device_id")
    print("   2️⃣  BatchSpec: Batch 5 correlated pairs")
    print("   3️⃣  Agent:     Bulk quality analysis\n")

    print("⚙️  CONFIGURATION:")
    print("   🔗 JoinSpec:  Correlate by device_id within 30 seconds")
    print("   📦 BatchSpec: Batch 5 correlation groups OR 45-second timeout")
    print("   ⚡ Result:    Efficient bulk processing!\n")

    # Phase 1: Publish correlated sensors for 5 devices (FULL BATCH)
    print("=" * 60)
    print("📊 PHASE 1: Full Batch (5 Devices)")
    print("=" * 60)
    print("📡 Publishing sensor readings from factory floor...\n")

    devices_batch_1 = [
        ("DEVICE-001", "Assembly Line A", 72.5, 1.2),
        ("DEVICE-002", "Assembly Line A", 75.0, 1.3),
        ("DEVICE-003", "Assembly Line B", 68.0, 1.1),
        ("DEVICE-004", "Assembly Line B", 73.5, 1.25),
        ("DEVICE-005", "Quality Control", 70.0, 1.15),
    ]

    for device_id, location, temp, pressure in devices_batch_1:
        # Publish temperature reading
        await flock.publish(
            TemperatureSensor(
                device_id=device_id,
                temperature_c=temp,
                location=location,
            )
        )

        # Publish pressure reading (will correlate with temperature)
        await flock.publish(
            PressureSensor(
                device_id=device_id,
                pressure_bar=pressure,
                location=location,
            )
        )

        print(f"   🌡️  {device_id} ({location}): {temp}°C, {pressure} bar")
        await asyncio.sleep(0.1)  # Small delay for effect

    print("\n   🔗 Correlating sensors by device_id...")
    print("   📦 Accumulating batches (need 5 devices)...")
    print("   ⚡ Size threshold reached (5 correlated pairs)!")
    print("   🔄 Flushing batch for analysis...\n")

    await flock.run_until_idle()

    # Check first quality report
    reports = await flock.store.get_by_type(QualityReport)

    if reports:
        report = reports[0]
        print(f"✅ Quality Report #{1}:")
        print(f"   Batch ID: {report.batch_id}")
        print(f"   Devices: {', '.join(report.devices_analyzed)}")
        print(f"   Total Readings: {report.total_readings}")
        print(f"   Status: {report.overall_status}")
        if report.anomalies_detected:
            print(f"   ⚠️  Anomalies: {', '.join(report.anomalies_detected)}")
        else:
            print("   ✅ No Anomalies Detected")

        if report.recommendations:
            print("   💡 Recommendations:")
            for rec in report.recommendations:
                print(f"      • {rec}")

    # Phase 2: Publish partial batch (timeout trigger)
    print("\n" + "=" * 60)
    print("📊 PHASE 2: Partial Batch (2 Devices)")
    print("=" * 60)
    print("📡 Two more devices reporting...\n")

    devices_batch_2 = [
        ("DEVICE-006", "Packaging", 69.0, 1.18),
        ("DEVICE-007", "Packaging", 71.5, 1.22),
    ]

    for device_id, location, temp, pressure in devices_batch_2:
        await flock.publish(
            TemperatureSensor(
                device_id=device_id,
                temperature_c=temp,
                location=location,
            )
        )

        await flock.publish(
            PressureSensor(
                device_id=device_id,
                pressure_bar=pressure,
                location=location,
            )
        )

        print(f"   🌡️  {device_id} ({location}): {temp}°C, {pressure} bar")
        await asyncio.sleep(0.1)

    print("\n   🔗 Correlating sensors by device_id...")
    print("   ⏳ Only 2 devices (not enough for batch size=5)...")
    print("   ⌛ Waiting for 45-second timeout to flush partial batch...")
    print("   (Simulating timeout with manual trigger)\n")

    # Simulate timeout
    await asyncio.sleep(1)
    print("   ⏰ Timeout triggered! Flushing partial batch...")

    await flock._check_batch_timeouts()
    await flock.run_until_idle()

    # Check second quality report
    reports = await flock.store.get_by_type(QualityReport)

    if len(reports) >= 2:
        report = reports[1]
        print(f"\n✅ Quality Report #{2}:")
        print(f"   Batch ID: {report.batch_id}")
        print(f"   Devices: {', '.join(report.devices_analyzed)}")
        print(f"   Total Readings: {report.total_readings}")
        print(f"   Status: {report.overall_status}")
        if report.anomalies_detected:
            print(f"   ⚠️  Anomalies: {', '.join(report.anomalies_detected)}")
        else:
            print("   ✅ No Anomalies Detected")

    # Final Analysis
    print("\n" + "=" * 60)
    print("📊 FINAL ANALYSIS")
    print("=" * 60)

    total_devices = len(devices_batch_1) + len(devices_batch_2)
    total_sensors = total_devices * 2  # temp + pressure per device

    print(f"   Total Devices Monitored: {total_devices}")
    print(f"   Total Sensor Readings: {total_sensors}")
    print(f"   Quality Reports Generated: {len(reports)}")
    print()
    print("   💡 KEY INSIGHTS:")
    print("   1️⃣  JoinSpec correlated temp + pressure by device_id")
    print("   2️⃣  BatchSpec batched 5 correlation GROUPS (not individual sensors)")
    print("   3️⃣  Report #1 flushed on SIZE (5 devices)")
    print("   4️⃣  Report #2 flushed on TIMEOUT (2 devices)")
    print("   5️⃣  Agent received LISTS of correlated pairs for bulk processing")
    print()
    print("🎓 LESSON COMPLETE!")
    print()
    print("🔬 EXPERIMENTS TO TRY:")
    print("   1. Add predicate `where=` to filter high-temp devices only")
    print("   2. Change batch size to 10 and see how timeout handles partials")
    print("   3. Add third sensor type (e.g., VibrationSensor) to correlation")
    print("   4. Use visibility to separate production vs QA environments")
    print("   5. Chain another agent to process QualityReport anomalies")
    print()
    print("🏆 WORKSHOP MASTERY ACHIEVED!")
    print()
    print("   You've now learned:")
    print("   ✅ Single agents and type contracts (L01)")
    print("   ✅ Multi-agent chaining via blackboard (L02)")
    print("   ✅ Conditional consumption with predicates (L03)")
    print("   ✅ Feedback loops and iteration (L04)")
    print("   ✅ Distributed tracing and debugging (L05)")
    print("   ✅ Visibility controls and security (L06)")
    print("   ✅ Parallel agent execution (L07)")
    print("   ✅ Data correlation with JoinSpec (L08)")
    print("   ✅ Efficient batching with BatchSpec (L09)")
    print("   ✅ Combined features for advanced workflows (L10)")
    print()
    print("   🎯 You're ready to build production-grade multi-agent systems!")
    print("   🚀 Go forth and orchestrate with confidence!")


if __name__ == "__main__":
    asyncio.run(main())
