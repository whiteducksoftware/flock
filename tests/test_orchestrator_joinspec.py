"""
Test suite for JoinSpec - Correlated AND gates with time windows.

Phase 2 Week 1: Correlation Engine Tests
- Day 1-2: Basic correlation by key
- Day 3-5: CorrelationEngine implementation

Following TDD: Tests written FIRST, implementation SECOND.

Real-world scenarios:
- Healthcare: Correlate X-ray + Lab results by patient_id
- Trading: Correlate volatility + sentiment by stock symbol
- Multi-modal AI: Correlate text + image by session_id
"""

import pytest
from datetime import datetime, timedelta
from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.subscription import JoinSpec
from flock.registry import flock_type
from flock.components import EngineComponent
from flock.runtime import EvalResult


# Test artifact types with correlation support
@flock_type
class SignalA(BaseModel):
    """First signal type for correlation tests."""
    correlation_id: str
    data: str
    timestamp: datetime | None = None


@flock_type
class SignalB(BaseModel):
    """Second signal type for correlation tests."""
    correlation_id: str
    data: str
    timestamp: datetime | None = None


@flock_type
class SignalC(BaseModel):
    """Third signal type for three-way correlation tests."""
    correlation_id: str
    data: str
    timestamp: datetime | None = None


# Note: TrackingEngine is defined inline in each test to avoid Pydantic field issues
# Each test creates its own TrackingEngine class


# ============================================================================
# Phase 2 Week 1 Day 1-2: Basic Correlation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_joinspec_correlates_artifacts_by_same_key():
    """
    GIVEN: Agent with JoinSpec correlation by correlation_id
    WHEN: Two artifacts with SAME correlation key are published
    THEN: Agent should be triggered with the correlated pair
    WHEN: Two artifacts with DIFFERENT keys are published
    THEN: No cross-correlation (artifacts wait independently)

    Real-world: Healthcare diagnostic system correlating X-ray + Lab results by patient ID.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("correlator")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=timedelta(minutes=5)
            )
        )
        .with_engines(TrackingEngine())
    )

    # Publish artifacts with SAME correlation ID
    await orchestrator.publish({"type": "SignalA", "correlation_id": "patient-123", "data": "xray"})
    await orchestrator.publish({"type": "SignalB", "correlation_id": "patient-123", "data": "labs"})
    await orchestrator.run_until_idle()

    # Should match!
    assert len(executed) == 1, "Should trigger once for correlated pair"
    assert len(executed[0]["artifacts"]) == 2, "Should receive both artifacts"

    # Verify correlation IDs match
    payloads = executed[0]["payloads"]
    assert all(p["correlation_id"] == "patient-123" for p in payloads), "All correlation IDs should match"

    # Publish artifacts with DIFFERENT correlation IDs
    await orchestrator.publish({"type": "SignalA", "correlation_id": "patient-456", "data": "xray2"})
    await orchestrator.publish({"type": "SignalB", "correlation_id": "patient-789", "data": "labs2"})
    await orchestrator.run_until_idle()

    # Should NOT create new matches (different keys)
    assert len(executed) == 1, "Should still only have 1 execution (no cross-correlation)"


@pytest.mark.asyncio
async def test_joinspec_multiple_correlation_keys_independent():
    """
    GIVEN: Agent with JoinSpec correlation
    WHEN: Multiple correlation keys are active simultaneously
    THEN: Each correlation group should trigger independently

    Real-world: Trading system processing multiple stocks in parallel.
    Each stock symbol has its own volatility + sentiment correlation.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("multi_correlator")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=timedelta(minutes=5)
            )
        )
        .with_engines(TrackingEngine())
    )

    # Publish artifacts for THREE different correlation groups
    # Group 1: stock-AAPL
    await orchestrator.publish(SignalA(correlation_id="stock-AAPL", data="volatility-high").model_dump())
    await orchestrator.publish(SignalB(correlation_id="stock-AAPL", data="sentiment-negative").model_dump())

    # Group 2: stock-MSFT
    await orchestrator.publish(SignalA(correlation_id="stock-MSFT", data="volatility-low").model_dump())
    await orchestrator.publish(SignalB(correlation_id="stock-MSFT", data="sentiment-positive").model_dump())

    # Group 3: stock-TSLA
    await orchestrator.publish(SignalA(correlation_id="stock-TSLA", data="volatility-high").model_dump())
    await orchestrator.publish(SignalB(correlation_id="stock-TSLA", data="sentiment-neutral").model_dump())

    await orchestrator.run_until_idle()

    # Should have 3 independent matches
    assert len(executed) == 3, "Should trigger once per correlation group"

    # Verify each group has matching correlation IDs
    correlation_ids = [p["correlation_id"] for exec in executed for p in exec["payloads"]]
    assert correlation_ids.count("stock-AAPL") == 2, "AAPL group should have 2 artifacts"
    assert correlation_ids.count("stock-MSFT") == 2, "MSFT group should have 2 artifacts"
    assert correlation_ids.count("stock-TSLA") == 2, "TSLA group should have 2 artifacts"


@pytest.mark.asyncio
async def test_joinspec_partial_correlation_waits():
    """
    GIVEN: Agent with JoinSpec requiring SignalA + SignalB
    WHEN: Only SignalA is published (missing SignalB)
    THEN: No trigger (waiting for matching SignalB)
    WHEN: SignalB with same key is published
    THEN: Trigger with correlated pair

    Real-world: Multi-modal AI waiting for both text input and image upload for same session.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("partial_correlator")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=timedelta(minutes=5)
            )
        )
        .with_engines(TrackingEngine())
    )

    # Publish only SignalA
    await orchestrator.publish(SignalA(correlation_id="session-abc", data="text-input").model_dump())
    await orchestrator.run_until_idle()

    # Should NOT trigger yet
    assert len(executed) == 0, "Should not trigger with only one signal"

    # Publish matching SignalB
    await orchestrator.publish(SignalB(correlation_id="session-abc", data="image-upload").model_dump())
    await orchestrator.run_until_idle()

    # NOW should trigger
    assert len(executed) == 1, "Should trigger after both signals arrive"
    assert len(executed[0]["artifacts"]) == 2, "Should have both artifacts"
    assert all(p["correlation_id"] == "session-abc" for p in executed[0]["payloads"]), "Correlation IDs should match"


@pytest.mark.asyncio
async def test_joinspec_three_way_correlation():
    """
    GIVEN: Agent with JoinSpec requiring THREE types (A + B + C)
    WHEN: All three artifacts with same key are published
    THEN: Agent triggers with all three correlated artifacts

    Real-world: Manufacturing quality control correlating measurements from 3 different sensors.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("three_way_correlator")
        .consumes(
            SignalA,
            SignalB,
            SignalC,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=timedelta(minutes=5)
            )
        )
        .with_engines(TrackingEngine())
    )

    # Publish all three with same key
    await orchestrator.publish(SignalA(correlation_id="batch-001", data="temperature-ok").model_dump())
    await orchestrator.publish(SignalB(correlation_id="batch-001", data="pressure-ok").model_dump())
    await orchestrator.publish(SignalC(correlation_id="batch-001", data="viscosity-ok").model_dump())
    await orchestrator.run_until_idle()

    # Should trigger once with all three
    assert len(executed) == 1, "Should trigger once for three-way correlation"
    assert len(executed[0]["artifacts"]) == 3, "Should receive all three artifacts"

    # Verify all have same correlation ID
    payloads = executed[0]["payloads"]
    assert all(p["correlation_id"] == "batch-001" for p in payloads), "All correlation IDs should match"

    # Verify all three types present
    types = {type(SignalA(**p)).__name__ if "temperature" in p["data"] else
             type(SignalB(**p)).__name__ if "pressure" in p["data"] else
             type(SignalC(**p)).__name__
             for p in payloads}
    assert len(types) == 3, "Should have all three signal types"


@pytest.mark.asyncio
async def test_joinspec_order_independence():
    """
    GIVEN: Agent with JoinSpec correlation
    WHEN: Artifacts arrive in different orders
    THEN: Correlation should work regardless of arrival order

    Scenario 1: A→B (normal order)
    Scenario 2: B→A (reversed order)
    Both should trigger successfully.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("order_test")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=timedelta(minutes=5)
            )
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: A→B (normal order)
    await orchestrator.publish(SignalA(correlation_id="order-1", data="a1").model_dump())
    await orchestrator.publish(SignalB(correlation_id="order-1", data="b1").model_dump())
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Should trigger for A→B order"

    # Scenario 2: B→A (reversed order)
    await orchestrator.publish(SignalB(correlation_id="order-2", data="b2").model_dump())
    await orchestrator.publish(SignalA(correlation_id="order-2", data="a2").model_dump())
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "Should trigger for B→A order too"


@pytest.mark.asyncio
async def test_joinspec_key_extraction_with_nested_fields():
    """
    GIVEN: JoinSpec with lambda extracting nested field
    WHEN: Artifacts have nested correlation keys
    THEN: Correlation should work with extracted nested values

    Real-world: API events with nested payload.metadata.request_id structure.
    """
    @flock_type
    class NestedSignalA(BaseModel):
        metadata: dict
        data: str

    @flock_type
    class NestedSignalB(BaseModel):
        metadata: dict
        data: str

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("nested_correlator")
        .consumes(
            NestedSignalA,
            NestedSignalB,
            join=JoinSpec(
                by=lambda x: x.metadata["request_id"],  # Extract nested field
                within=timedelta(minutes=5)
            )
        )
        .with_engines(TrackingEngine())
    )

    # Publish with nested correlation key
    await orchestrator.publish(
        NestedSignalA(metadata={"request_id": "req-xyz", "source": "api"}, data="request").model_dump()
    )
    await orchestrator.publish(
        NestedSignalB(metadata={"request_id": "req-xyz", "source": "db"}, data="response").model_dump()
    )
    await orchestrator.run_until_idle()

    # Should correlate by nested request_id
    assert len(executed) == 1, "Should correlate by nested field"
    assert len(executed[0]["artifacts"]) == 2, "Should have both artifacts"


# ============================================================================
# Phase 2 Week 1 Day 3-5: These will be added after CorrelationEngine implementation
# ============================================================================

@pytest.mark.asyncio
async def test_joinspec_count_based_window():
    """
    GIVEN: JoinSpec with count-based window (within=10 means "within next 10 artifacts")
    WHEN: Correlated artifacts published within 10-artifact window
    THEN: Correlation succeeds
    WHEN: Correlated artifacts published OUTSIDE 10-artifact window
    THEN: No correlation (expired)

    Real-world: Stream processing with message-count windows instead of time windows.
    Useful when time is less relevant than message ordering/throughput.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("count_window_test")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=10  # Count window: next 10 artifacts
            )
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: Artifacts within 10-message window
    await orchestrator.publish({"type": "SignalA", "correlation_id": "batch-1", "data": "a1"})
    # Publish 8 unrelated artifacts (noise)
    for i in range(8):
        await orchestrator.publish({"type": "SignalA", "correlation_id": f"noise-{i}", "data": "noise"})
    # Publish matching SignalB within window (9th artifact)
    await orchestrator.publish({"type": "SignalB", "correlation_id": "batch-1", "data": "b1"})
    await orchestrator.run_until_idle()

    # Should correlate (within 10-artifact window)
    assert len(executed) == 1, "Should correlate within 10-artifact window"
    assert executed[0]["payloads"][0]["correlation_id"] == "batch-1"

    # Scenario 2: Artifacts OUTSIDE 10-message window
    await orchestrator.publish({"type": "SignalA", "correlation_id": "batch-2", "data": "a2"})
    # Publish 11 unrelated artifacts (exceeds window)
    for i in range(11):
        await orchestrator.publish({"type": "SignalA", "correlation_id": f"noise2-{i}", "data": "noise"})
    # Publish matching SignalB OUTSIDE window (12th artifact)
    await orchestrator.publish({"type": "SignalB", "correlation_id": "batch-2", "data": "b2"})
    await orchestrator.run_until_idle()

    # Should NOT correlate (outside 10-artifact window)
    assert len(executed) == 1, "Should still only have 1 execution (batch-2 expired)"


@pytest.mark.asyncio
async def test_joinspec_count_window_with_multiple_correlations():
    """
    GIVEN: JoinSpec with count window
    WHEN: Multiple correlation groups compete for space in window
    THEN: Each group tracks its own position in global artifact stream

    Real-world: High-throughput system where multiple requests overlap.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs):
            executed.append({
                "correlation_id": inputs.artifacts[0].payload["correlation_id"],
                "artifact_count": len(inputs.artifacts),
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("multi_count_window")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=5  # Tight window: only 5 artifacts
            )
        )
        .with_engines(TrackingEngine())
    )

    # Interleaved correlation groups
    await orchestrator.publish({"type": "SignalA", "correlation_id": "req-1", "data": "a1"})
    await orchestrator.publish({"type": "SignalA", "correlation_id": "req-2", "data": "a2"})
    await orchestrator.publish({"type": "SignalB", "correlation_id": "req-1", "data": "b1"})  # req-1 completes (within 5)
    await orchestrator.publish({"type": "SignalA", "correlation_id": "req-3", "data": "a3"})
    await orchestrator.publish({"type": "SignalB", "correlation_id": "req-2", "data": "b2"})  # req-2 completes (within 5)
    await orchestrator.run_until_idle()

    # Should have 2 correlations (req-1 and req-2)
    assert len(executed) == 2, "Should have 2 correlations"
    correlation_ids = {e["correlation_id"] for e in executed}
    assert correlation_ids == {"req-1", "req-2"}


# TODO: Add edge case tests after basic implementation works:
# - test_joinspec_correlation_state_isolation_per_agent
# - test_joinspec_handles_duplicate_correlation_keys
# - test_joinspec_key_extraction_errors_reject_artifact
# - test_joinspec_with_where_predicate_filters_before_correlation
# - test_joinspec_with_visibility_controls
