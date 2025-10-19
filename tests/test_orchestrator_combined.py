"""
Phase 4: Combined Features Tests (JoinSpec + BatchSpec)

This is the FINAL phase - bringing together correlation and batching!

Real-world scenarios:
- Healthcare: Batch correlated diagnostic reports for cost-efficient processing
- Trading: Batch correlated market signals for bulk analysis
- IoT: Batch correlated sensor readings from multiple devices

Test-Driven Development (TDD):
- Tests written FIRST
- Implementation SECOND
- Green tests = release-ready feature set!

Architecture:
    Artifact → Visibility Check → Predicate Check →
    → JoinSpec Correlation (produces correlated pairs) →
    → BatchSpec Accumulator (batches correlated pairs) →
    → Flush on size/timeout →
    → Schedule Agent
"""

from datetime import timedelta

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.subscription import BatchSpec, JoinSpec
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


class BatchAwareEngine(EngineComponent):
    """Helper that routes evaluate_batch to evaluate for batch-aware tests."""

    async def evaluate_batch(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        return await self.evaluate(agent, ctx, inputs, output_group)


# ============================================================================
# Test Fixtures
# ============================================================================


@flock_type
class DiagnosticRequest(BaseModel):
    """Medical diagnostic request (e.g., X-ray order)."""

    patient_id: str
    test_type: str
    priority: str = "normal"


@flock_type
class DiagnosticResult(BaseModel):
    """Medical diagnostic result (e.g., X-ray image + analysis)."""

    patient_id: str
    test_type: str
    findings: str
    priority: str = "normal"  # Add priority field for predicate tests


@flock_type
class MarketSignal(BaseModel):
    """Trading signal with symbol correlation."""

    symbol: str
    signal_type: str  # "volatility" or "sentiment"
    value: float


@flock_type
class SensorReading(BaseModel):
    """IoT sensor reading with device correlation."""

    device_id: str
    sensor_type: str  # "temperature" or "pressure"
    value: float


# ============================================================================
# Phase 4 Week 1: Core Combined Features
# ============================================================================


@pytest.mark.asyncio
async def test_batched_correlated_joins_basic():
    """
    GIVEN: Agent with BOTH JoinSpec (correlate by patient_id) AND BatchSpec (batch of 2)
    WHEN: Publish 2 correlated pairs (4 artifacts total)
    THEN: Correlation completes for each pair, then batch of 2 pairs flushes

    Real-world: Hospital batches correlated diagnostic reports for efficient processing.
    Process 2 complete patient diagnostics at once instead of one-by-one.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "batch_size": len(inputs.artifacts),
                "patient_ids": [a.payload["patient_id"] for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("batch_correlator")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),  # Batch 2 correlated pairs
        )
        .with_engines(TrackingEngine())
    )

    # Publish 2 correlated pairs
    # Pair 1: patient-001
    await orchestrator.publish(
        DiagnosticRequest(patient_id="patient-001", test_type="xray")
    )
    await orchestrator.publish(
        DiagnosticResult(patient_id="patient-001", test_type="xray", findings="normal")
    )

    # After first pair: correlation completes but batch not full yet
    await orchestrator.run_until_idle()
    assert len(executed) == 0, "Batch not full yet (need 2 pairs)"

    # Pair 2: patient-002
    await orchestrator.publish(
        DiagnosticRequest(patient_id="patient-002", test_type="mri")
    )
    await orchestrator.publish(
        DiagnosticResult(patient_id="patient-002", test_type="mri", findings="abnormal")
    )

    # After second pair: batch should flush with 2 correlated pairs
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed with 2 correlated pairs"
    assert executed[0]["batch_size"] == 4, "Batch contains 4 artifacts (2 pairs)"
    assert set(executed[0]["patient_ids"]) == {"patient-001", "patient-002"}, (
        "Both patients in batch"
    )


@pytest.mark.asyncio
async def test_batched_correlation_continues_after_flush():
    """
    GIVEN: Agent with JoinSpec + BatchSpec(size=2)
    WHEN: 4 correlated pairs published (2 batches worth)
    THEN: Two separate batch flushes occur

    Ensures batch accumulator resets after flush and continues accepting correlated pairs.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["symbol"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("multi_batch_correlator")
        .consumes(
            MarketSignal,
            MarketSignal,  # Two signals (volatility + sentiment) per symbol
            join=JoinSpec(by=lambda x: x.symbol, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),  # Batch 2 correlated pairs
        )
        .with_engines(TrackingEngine())
    )

    # Batch 1: AAPL and MSFT
    await orchestrator.publish(
        MarketSignal(symbol="AAPL", signal_type="volatility", value=0.8)
    )
    await orchestrator.publish(
        MarketSignal(symbol="AAPL", signal_type="sentiment", value=0.6)
    )
    await orchestrator.publish(
        MarketSignal(symbol="MSFT", signal_type="volatility", value=0.5)
    )
    await orchestrator.publish(
        MarketSignal(symbol="MSFT", signal_type="sentiment", value=0.7)
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "First batch flushed"
    # Note: batch contains 4 artifacts (2 pairs × 2 signals each)

    # Batch 2: TSLA and GOOGL
    await orchestrator.publish(
        MarketSignal(symbol="TSLA", signal_type="volatility", value=1.2)
    )
    await orchestrator.publish(
        MarketSignal(symbol="TSLA", signal_type="sentiment", value=0.4)
    )
    await orchestrator.publish(
        MarketSignal(symbol="GOOGL", signal_type="volatility", value=0.3)
    )
    await orchestrator.publish(
        MarketSignal(symbol="GOOGL", signal_type="sentiment", value=0.9)
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "Second batch flushed"


@pytest.mark.asyncio
async def test_partial_correlation_waits_in_batch():
    """
    GIVEN: Agent with JoinSpec + BatchSpec(size=2)
    WHEN: Publish Request without matching Result
    THEN: Correlation incomplete, batch doesn't accumulate
    WHEN: Publish matching Result to complete correlation
    THEN: Batch accumulates the correlated pair (but doesn't flush yet if size=2)

    Mental model: Correlation happens FIRST, then batching.
    Incomplete correlations don't enter batch accumulator.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("partial_wait")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),
        )
        .with_engines(TrackingEngine())
    )

    # Publish only Request (no matching Result)
    await orchestrator.publish(
        DiagnosticRequest(patient_id="patient-999", test_type="xray")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "No flush (correlation incomplete)"

    # Publish matching Result - correlation completes
    await orchestrator.publish(
        DiagnosticResult(patient_id="patient-999", test_type="xray", findings="normal")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "No flush yet (batch needs 2 pairs, only have 1)"

    # Publish another complete pair to trigger batch flush
    await orchestrator.publish(
        DiagnosticRequest(patient_id="patient-888", test_type="mri")
    )
    await orchestrator.publish(
        DiagnosticResult(patient_id="patient-888", test_type="mri", findings="normal")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed with 2 pairs"
    assert executed[0] == 4, "Batch contains 4 artifacts"


@pytest.mark.asyncio
async def test_multiple_correlation_groups_batch_independently():
    """
    GIVEN: Agent with JoinSpec + BatchSpec
    WHEN: Multiple correlation keys complete
    THEN: Each correlation feeds into same batch accumulator

    Real-world: IoT system batches sensor readings from multiple devices together.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "batch_size": len(inputs.artifacts),
                "device_ids": list(
                    set(a.payload["device_id"] for a in inputs.artifacts)
                ),
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("multi_device_batch")
        .consumes(
            SensorReading,
            SensorReading,  # Temperature + Pressure per device
            join=JoinSpec(by=lambda x: x.device_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=3),  # Batch 3 correlated device readings
        )
        .with_engines(TrackingEngine())
    )

    # Device 1: temp + pressure
    await orchestrator.publish(
        SensorReading(device_id="device-A", sensor_type="temperature", value=25.0)
    )
    await orchestrator.publish(
        SensorReading(device_id="device-A", sensor_type="pressure", value=101.3)
    )

    # Device 2: temp + pressure
    await orchestrator.publish(
        SensorReading(device_id="device-B", sensor_type="temperature", value=26.5)
    )
    await orchestrator.publish(
        SensorReading(device_id="device-B", sensor_type="pressure", value=100.8)
    )

    await orchestrator.run_until_idle()
    assert len(executed) == 0, "Batch not full yet (need 3 devices)"

    # Device 3: temp + pressure → triggers batch flush
    await orchestrator.publish(
        SensorReading(device_id="device-C", sensor_type="temperature", value=24.0)
    )
    await orchestrator.publish(
        SensorReading(device_id="device-C", sensor_type="pressure", value=102.1)
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed with 3 devices"
    assert executed[0]["batch_size"] == 6, "6 artifacts (3 devices x 2 sensors)"
    assert len(executed[0]["device_ids"]) == 3, "3 different devices"


# ============================================================================
# Phase 4 Week 1: Timeout Integration
# ============================================================================


@pytest.mark.asyncio
async def test_batched_correlation_with_timeout():
    """
    GIVEN: Agent with JoinSpec + BatchSpec(size=5, timeout=100ms)
    WHEN: 2 correlated pairs complete (not enough for size=5)
    THEN: No flush yet
    WHEN: Timeout expires
    THEN: Timeout flush with partial batch of 2 pairs

    Real-world: Don't wait forever for full batch - flush periodically.
    """
    import asyncio

    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("timeout_batch_correlator")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=5, timeout=timedelta(milliseconds=100)),
        )
        .with_engines(TrackingEngine())
    )

    # Publish 2 correlated pairs (not enough for size=5)
    await orchestrator.publish(DiagnosticRequest(patient_id="p1", test_type="xray"))
    await orchestrator.publish(
        DiagnosticResult(patient_id="p1", test_type="xray", findings="ok")
    )
    await orchestrator.publish(DiagnosticRequest(patient_id="p2", test_type="mri"))
    await orchestrator.publish(
        DiagnosticResult(patient_id="p2", test_type="mri", findings="ok")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Batch not full, no immediate flush"

    # Wait for timeout
    await asyncio.sleep(0.15)  # 150ms > 100ms timeout
    await orchestrator._check_batch_timeouts()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Timeout flush triggered"
    assert executed[0] == 4, "Partial batch of 4 artifacts (2 pairs)"


@pytest.mark.asyncio
async def test_batched_correlation_size_or_timeout_whichever_first():
    """
    GIVEN: Agent with JoinSpec + BatchSpec(size=3, timeout=200ms)
    WHEN: 2 correlated pairs + timeout → timeout wins
    WHEN: 3 correlated pairs quickly → size wins
    THEN: Both triggers work independently
    """
    import asyncio

    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("hybrid_batch_correlator")
        .consumes(
            MarketSignal,
            MarketSignal,
            join=JoinSpec(by=lambda x: x.symbol, within=timedelta(minutes=5)),
            batch=BatchSpec(size=3, timeout=timedelta(milliseconds=200)),
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: Timeout wins (2 pairs, wait for timeout)
    await orchestrator.publish(
        MarketSignal(symbol="AAPL", signal_type="volatility", value=0.8)
    )
    await orchestrator.publish(
        MarketSignal(symbol="AAPL", signal_type="sentiment", value=0.6)
    )
    await orchestrator.publish(
        MarketSignal(symbol="MSFT", signal_type="volatility", value=0.5)
    )
    await orchestrator.publish(
        MarketSignal(symbol="MSFT", signal_type="sentiment", value=0.7)
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "No flush yet"

    await asyncio.sleep(0.25)  # 250ms > 200ms
    await orchestrator._check_batch_timeouts()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Timeout flush"
    assert executed[0] == 4, "Partial batch (2 pairs)"

    # Scenario 2: Size wins (3 pairs published quickly)
    for i in range(3):
        await orchestrator.publish(
            MarketSignal(symbol=f"SYM{i}", signal_type="volatility", value=0.5)
        )
        await orchestrator.publish(
            MarketSignal(symbol=f"SYM{i}", signal_type="sentiment", value=0.5)
        )
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "Size flush (before timeout)"
    assert executed[1] == 6, "Full batch (3 pairs)"


@pytest.mark.asyncio
async def test_batched_correlation_shutdown_flushes_partial():
    """
    GIVEN: Agent with JoinSpec + BatchSpec
    WHEN: Partial batch in accumulator
    THEN: Shutdown flushes partial batch (zero data loss)

    Critical: Users expect no data loss even with combined features.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("shutdown_test")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=5),
        )
        .with_engines(TrackingEngine())
    )

    # Publish 2 correlated pairs (partial batch)
    await orchestrator.publish(DiagnosticRequest(patient_id="p1", test_type="xray"))
    await orchestrator.publish(
        DiagnosticResult(patient_id="p1", test_type="xray", findings="ok")
    )
    await orchestrator.publish(DiagnosticRequest(patient_id="p2", test_type="mri"))
    await orchestrator.publish(
        DiagnosticResult(patient_id="p2", test_type="mri", findings="ok")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Partial batch waiting"

    # Simulate shutdown
    await orchestrator._flush_all_batches()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Shutdown flushed partial batch"
    assert executed[0] == 4, "All 4 artifacts delivered (2 pairs)"


# ============================================================================
# Phase 4 Week 2: Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batched_correlation_with_visibility():
    """
    GIVEN: Agent with JoinSpec + BatchSpec + visibility restrictions
    WHEN: Some artifacts visible, some not
    THEN: Only visible artifacts participate in correlation AND batching

    Mental model: Visibility → Correlation → Batching (in sequence)
    """
    from flock.core.visibility import PrivateVisibility, PublicVisibility

    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["patient_id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("visibility_batch_correlator")
        .labels("hospital_a")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),
        )
        .with_engines(TrackingEngine())
    )

    # Pair 1: Both public → should correlate and batch
    await orchestrator.publish(
        DiagnosticRequest(patient_id="p1", test_type="xray"),
        visibility=PublicVisibility(),
    )
    await orchestrator.publish(
        DiagnosticResult(patient_id="p1", test_type="xray", findings="ok"),
        visibility=PublicVisibility(),
    )

    # Pair 2: Request private (hospital_b), Result public → NO correlation (Request filtered)
    await orchestrator.publish(
        DiagnosticRequest(patient_id="p2", test_type="mri"),
        visibility=PrivateVisibility(labels={"hospital_b"}),
    )
    await orchestrator.publish(
        DiagnosticResult(patient_id="p2", test_type="mri", findings="ok"),
        visibility=PublicVisibility(),
    )

    # Pair 3: Both public → should correlate, complete batch with pair 1
    await orchestrator.publish(
        DiagnosticRequest(patient_id="p3", test_type="ct"),
        visibility=PublicVisibility(),
    )
    await orchestrator.publish(
        DiagnosticResult(patient_id="p3", test_type="ct", findings="ok"),
        visibility=PublicVisibility(),
    )

    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed with visible pairs only"
    assert set(executed[0]) == {"p1", "p3"}, (
        "Only visible pairs batched (p2 filtered out)"
    )


@pytest.mark.asyncio
async def test_batched_correlation_with_where_predicate():
    """
    GIVEN: Agent with JoinSpec + BatchSpec + where predicate
    WHEN: Some artifacts pass predicate, some don't
    THEN: Only passing artifacts participate in correlation AND batching

    Mental model: Predicate → Correlation → Batching (in sequence)
    Predicate is "bouncer at the door" before correlation.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["patient_id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    # Predicate: Only accept "high" priority diagnostics
    def predicate(payload):
        return payload.priority == "high"

    agent = (
        orchestrator.agent("predicate_batch_correlator")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            where=predicate,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),
        )
        .with_engines(TrackingEngine())
    )

    # Pair 1: Both high priority → should correlate and batch
    await orchestrator.publish(
        DiagnosticRequest(patient_id="p1", test_type="xray", priority="high")
    )
    await orchestrator.publish(
        DiagnosticResult(
            patient_id="p1", test_type="xray", findings="ok", priority="high"
        )
    )

    # Pair 2: Request high, Result normal → NO correlation (Result rejected)
    await orchestrator.publish(
        DiagnosticRequest(patient_id="p2", test_type="mri", priority="high")
    )
    await orchestrator.publish(
        DiagnosticResult(
            patient_id="p2", test_type="mri", findings="ok", priority="normal"
        )
    )

    await orchestrator.run_until_idle()
    assert len(executed) == 0, "Batch not full yet (only 1 pair passed predicate)"

    # Pair 3: Both high priority → completes batch with pair 1
    await orchestrator.publish(
        DiagnosticRequest(patient_id="p3", test_type="ct", priority="high")
    )
    await orchestrator.publish(
        DiagnosticResult(
            patient_id="p3", test_type="ct", findings="ok", priority="high"
        )
    )

    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed with high priority pairs only"
    assert set(executed[0]) == {"p1", "p3"}, "Only high priority pairs batched"


@pytest.mark.asyncio
async def test_batched_correlation_state_isolation_per_agent():
    """
    GIVEN: TWO agents with same JoinSpec + BatchSpec
    WHEN: Correlated pairs published
    THEN: Each agent maintains independent correlation AND batch state

    Real-world: Multiple microservices independently batch-processing correlated events.
    """
    orchestrator = Flock()
    executed_agent1 = []
    executed_agent2 = []

    class TrackingEngine1(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed_agent1.append({
                "agent": agent.name,
                "batch_size": len(inputs.artifacts),
            })
            return EvalResult(artifacts=[])

    class TrackingEngine2(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed_agent2.append({
                "agent": agent.name,
                "batch_size": len(inputs.artifacts),
            })
            return EvalResult(artifacts=[])

    # Agent 1: Batch size 2
    agent1 = (
        orchestrator.agent("agent1")
        .consumes(
            MarketSignal,
            MarketSignal,
            join=JoinSpec(by=lambda x: x.symbol, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),
        )
        .with_engines(TrackingEngine1())
    )

    # Agent 2: Batch size 3 (independent state)
    agent2 = (
        orchestrator.agent("agent2")
        .consumes(
            MarketSignal,
            MarketSignal,
            join=JoinSpec(by=lambda x: x.symbol, within=timedelta(minutes=5)),
            batch=BatchSpec(size=3),
        )
        .with_engines(TrackingEngine2())
    )

    # Publish 3 correlated pairs
    for i in range(3):
        await orchestrator.publish(
            MarketSignal(symbol=f"STOCK{i}", signal_type="volatility", value=0.5)
        )
        await orchestrator.publish(
            MarketSignal(symbol=f"STOCK{i}", signal_type="sentiment", value=0.5)
        )
    await orchestrator.run_until_idle()

    # Agent 1: Should flush once (batch size 2, got 3 pairs → flush 2, wait 1)
    assert len(executed_agent1) == 1, "Agent1 flushed once"
    assert executed_agent1[0]["batch_size"] == 4, "Agent1 batch: 4 artifacts (2 pairs)"

    # Agent 2: Should flush once (batch size 3, got 3 pairs → flush 3)
    assert len(executed_agent2) == 1, "Agent2 flushed once"
    assert executed_agent2[0]["batch_size"] == 6, "Agent2 batch: 6 artifacts (3 pairs)"


@pytest.mark.asyncio
async def test_batched_correlation_performance():
    """
    GIVEN: Agent with JoinSpec + BatchSpec
    WHEN: Multiple correlated pairs batched rapidly
    THEN: Combined overhead <100ms total

    Performance target: Correlation + batching should be fast.
    """
    import time

    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("performance_test")
        .consumes(
            SensorReading,
            SensorReading,
            join=JoinSpec(by=lambda x: x.device_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=10),  # Batch 10 correlated pairs
        )
        .with_engines(TrackingEngine())
    )

    # Publish 10 correlated pairs (20 artifacts)
    start = time.time()
    for i in range(10):
        await orchestrator.publish(
            SensorReading(
                device_id=f"device-{i}", sensor_type="temperature", value=25.0
            )
        )
        await orchestrator.publish(
            SensorReading(device_id=f"device-{i}", sensor_type="pressure", value=101.0)
        )
    await orchestrator.run_until_idle()
    end = time.time()

    # Verify batch flushed
    assert len(executed) == 1, "Batch flushed once"
    assert executed[0] == 20, "20 artifacts (10 correlated pairs)"

    # Performance check
    elapsed_ms = (end - start) * 1000
    print(f"\nCombined performance: {elapsed_ms:.2f}ms for 10 correlated pairs batched")
    assert elapsed_ms < 1000, f"Performance target: <1000ms (got {elapsed_ms:.2f}ms)"


# ============================================================================
# Phase 4 Week 2: Advanced Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test_three_way_correlation_with_batching():
    """
    GIVEN: Agent with THREE-WAY JoinSpec + BatchSpec
    WHEN: Multiple three-way correlations complete
    THEN: Batch accumulates three-way correlated groups

    Real-world: Manufacturing correlates 3 sensor types per batch, then batches groups.
    """

    @flock_type
    class TempSensor(BaseModel):
        batch_id: str
        value: float

    @flock_type
    class PressureSensor(BaseModel):
        batch_id: str
        value: float

    @flock_type
    class ViscositySensor(BaseModel):
        batch_id: str
        value: float

    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "batch_size": len(inputs.artifacts),
                "batch_ids": list({a.payload["batch_id"] for a in inputs.artifacts}),
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("three_way_batch")
        .consumes(
            TempSensor,
            PressureSensor,
            ViscositySensor,
            join=JoinSpec(by=lambda x: x.batch_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=2),  # Batch 2 three-way correlations
        )
        .with_engines(TrackingEngine())
    )

    # Correlation 1: batch-A (3 sensors)
    await orchestrator.publish(TempSensor(batch_id="batch-A", value=25.0))
    await orchestrator.publish(PressureSensor(batch_id="batch-A", value=101.0))
    await orchestrator.publish(ViscositySensor(batch_id="batch-A", value=50.0))

    await orchestrator.run_until_idle()
    assert len(executed) == 0, "Batch not full yet (need 2 correlations)"

    # Correlation 2: batch-B (3 sensors) → triggers batch flush
    await orchestrator.publish(TempSensor(batch_id="batch-B", value=26.0))
    await orchestrator.publish(PressureSensor(batch_id="batch-B", value=102.0))
    await orchestrator.publish(ViscositySensor(batch_id="batch-B", value=51.0))

    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed with 2 three-way correlations"
    assert executed[0]["batch_size"] == 6, "6 artifacts (2 batches x 3 sensors)"
    assert set(executed[0]["batch_ids"]) == {"batch-A", "batch-B"}, (
        "Both batches present"
    )


@pytest.mark.asyncio
async def test_batched_correlation_with_mixed_completion_rates():
    """
    GIVEN: Agent with JoinSpec + BatchSpec
    WHEN: Some correlations complete quickly, others slowly
    THEN: Batch accumulates completed correlations, waits for incomplete ones

    Edge case: Correlation completion rate varies - batch should handle gracefully.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(BatchAwareEngine):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["patient_id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("mixed_rate_batch")
        .consumes(
            DiagnosticRequest,
            DiagnosticResult,
            join=JoinSpec(by=lambda x: x.patient_id, within=timedelta(minutes=5)),
            batch=BatchSpec(size=3),
        )
        .with_engines(TrackingEngine())
    )

    # Fast correlation: p1 completes immediately
    await orchestrator.publish(DiagnosticRequest(patient_id="p1", test_type="xray"))
    await orchestrator.publish(
        DiagnosticResult(patient_id="p1", test_type="xray", findings="ok")
    )

    # Slow correlation: p2 only has Request (Result delayed)
    await orchestrator.publish(DiagnosticRequest(patient_id="p2", test_type="mri"))

    # Fast correlation: p3 completes immediately
    await orchestrator.publish(DiagnosticRequest(patient_id="p3", test_type="ct"))
    await orchestrator.publish(
        DiagnosticResult(patient_id="p3", test_type="ct", findings="ok")
    )

    await orchestrator.run_until_idle()
    assert len(executed) == 0, (
        "Batch not full (only 2 correlations complete, p2 waiting)"
    )

    # Complete p2 correlation → batch should flush with all 3
    await orchestrator.publish(
        DiagnosticResult(patient_id="p2", test_type="mri", findings="ok")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed after p2 completed"
    assert set(executed[0]) == {"p1", "p2", "p3"}, "All 3 patients in batch"


# ============================================================================
# Phase 4: Documentation Task Marker
# ============================================================================

# TODO (Phase 4 Completion): Update documentation
# 1. Add combined features section to docs/guides/agents.md
# 2. Create example: examples/01-cli/13_combined_features.py (healthcare scenario)
# 3. Update README.md with JoinSpec + BatchSpec usage
# 4. Add troubleshooting guide for combined features
# 5. Document predicate behavior across all features in one place
# 6. Create migration guide for users upgrading from v0.5
