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

from datetime import datetime, timedelta

import pytest
from pydantic import BaseModel

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.subscription import JoinSpec
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Publish artifacts with SAME correlation ID
    await orchestrator.publish(SignalA(correlation_id="patient-123", data="xray"))
    await orchestrator.publish(SignalB(correlation_id="patient-123", data="labs"))
    await orchestrator.run_until_idle()

    # Should match!
    assert len(executed) == 1, "Should trigger once for correlated pair"
    assert len(executed[0]["artifacts"]) == 2, "Should receive both artifacts"

    # Verify correlation IDs match
    payloads = executed[0]["payloads"]
    assert all(p["correlation_id"] == "patient-123" for p in payloads), (
        "All correlation IDs should match"
    )

    # Publish artifacts with DIFFERENT correlation IDs
    await orchestrator.publish(SignalA(correlation_id="patient-456", data="xray2"))
    await orchestrator.publish(SignalB(correlation_id="patient-789", data="labs2"))
    await orchestrator.run_until_idle()

    # Should NOT create new matches (different keys)
    assert len(executed) == 1, (
        "Should still only have 1 execution (no cross-correlation)"
    )


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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Publish artifacts for THREE different correlation groups
    # Group 1: stock-AAPL
    await orchestrator.publish(
        SignalA(correlation_id="stock-AAPL", data="volatility-high")
    )
    await orchestrator.publish(
        SignalB(correlation_id="stock-AAPL", data="sentiment-negative")
    )

    # Group 2: stock-MSFT
    await orchestrator.publish(
        SignalA(correlation_id="stock-MSFT", data="volatility-low")
    )
    await orchestrator.publish(
        SignalB(correlation_id="stock-MSFT", data="sentiment-positive")
    )

    # Group 3: stock-TSLA
    await orchestrator.publish(
        SignalA(correlation_id="stock-TSLA", data="volatility-high")
    )
    await orchestrator.publish(
        SignalB(correlation_id="stock-TSLA", data="sentiment-neutral")
    )

    await orchestrator.run_until_idle()

    # Should have 3 independent matches
    assert len(executed) == 3, "Should trigger once per correlation group"

    # Verify each group has matching correlation IDs
    correlation_ids = [
        p["correlation_id"] for group in executed for p in group["payloads"]
    ]
    assert correlation_ids.count("stock-AAPL") == 2, (
        "AAPL group should have 2 artifacts"
    )
    assert correlation_ids.count("stock-MSFT") == 2, (
        "MSFT group should have 2 artifacts"
    )
    assert correlation_ids.count("stock-TSLA") == 2, (
        "TSLA group should have 2 artifacts"
    )


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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Publish only SignalA
    await orchestrator.publish(SignalA(correlation_id="session-abc", data="text-input"))
    await orchestrator.run_until_idle()

    # Should NOT trigger yet
    assert len(executed) == 0, "Should not trigger with only one signal"

    # Publish matching SignalB
    await orchestrator.publish(
        SignalB(correlation_id="session-abc", data="image-upload")
    )
    await orchestrator.run_until_idle()

    # NOW should trigger
    assert len(executed) == 1, "Should trigger after both signals arrive"
    assert len(executed[0]["artifacts"]) == 2, "Should have both artifacts"
    assert all(p["correlation_id"] == "session-abc" for p in executed[0]["payloads"]), (
        "Correlation IDs should match"
    )


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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Publish all three with same key
    await orchestrator.publish(
        SignalA(correlation_id="batch-001", data="temperature-ok")
    )
    await orchestrator.publish(SignalB(correlation_id="batch-001", data="pressure-ok"))
    await orchestrator.publish(SignalC(correlation_id="batch-001", data="viscosity-ok"))
    await orchestrator.run_until_idle()

    # Should trigger once with all three
    assert len(executed) == 1, "Should trigger once for three-way correlation"
    assert len(executed[0]["artifacts"]) == 3, "Should receive all three artifacts"

    # Verify all have same correlation ID
    payloads = executed[0]["payloads"]
    assert all(p["correlation_id"] == "batch-001" for p in payloads), (
        "All correlation IDs should match"
    )

    # Verify all three types present
    types = {
        type(SignalA(**p)).__name__
        if "temperature" in p["data"]
        else type(SignalB(**p)).__name__
        if "pressure" in p["data"]
        else type(SignalC(**p)).__name__
        for p in payloads
    }
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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: A→B (normal order)
    await orchestrator.publish(SignalA(correlation_id="order-1", data="a1"))
    await orchestrator.publish(SignalB(correlation_id="order-1", data="b1"))
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Should trigger for A→B order"

    # Scenario 2: B→A (reversed order)
    await orchestrator.publish(SignalB(correlation_id="order-2", data="b2"))
    await orchestrator.publish(SignalA(correlation_id="order-2", data="a2"))
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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
                within=timedelta(minutes=5),
            ),
        )
        .with_engines(TrackingEngine())
    )

    # Publish with nested correlation key
    await orchestrator.publish(
        NestedSignalA(
            metadata={"request_id": "req-xyz", "source": "api"}, data="request"
        )
    )
    await orchestrator.publish(
        NestedSignalB(
            metadata={"request_id": "req-xyz", "source": "db"}, data="response"
        )
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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
                within=10,  # Count window: next 10 artifacts
            ),
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: Artifacts within 10-message window
    await orchestrator.publish(SignalA(correlation_id="batch-1", data="a1"))
    # Publish 8 unrelated artifacts (noise)
    for i in range(8):
        await orchestrator.publish(SignalA(correlation_id=f"noise-{i}", data="noise"))
    # Publish matching SignalB within window (9th artifact)
    await orchestrator.publish(SignalB(correlation_id="batch-1", data="b1"))
    await orchestrator.run_until_idle()

    # Should correlate (within 10-artifact window)
    assert len(executed) == 1, "Should correlate within 10-artifact window"
    assert executed[0]["payloads"][0]["correlation_id"] == "batch-1"

    # Scenario 2: Artifacts OUTSIDE 10-message window
    await orchestrator.publish(SignalA(correlation_id="batch-2", data="a2"))
    # Publish 11 unrelated artifacts (exceeds window)
    for i in range(11):
        await orchestrator.publish(SignalA(correlation_id=f"noise2-{i}", data="noise"))
    # Publish matching SignalB OUTSIDE window (12th artifact)
    await orchestrator.publish(SignalB(correlation_id="batch-2", data="b2"))
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
        async def evaluate(self, agent, ctx, inputs, output_group):
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
                within=5,  # Tight window: only 5 artifacts
            ),
        )
        .with_engines(TrackingEngine())
    )

    # Interleaved correlation groups
    await orchestrator.publish(SignalA(correlation_id="req-1", data="a1"))
    await orchestrator.publish(SignalA(correlation_id="req-2", data="a2"))
    await orchestrator.publish(
        SignalB(correlation_id="req-1", data="b1")
    )  # req-1 completes (within 5)
    await orchestrator.publish(SignalA(correlation_id="req-3", data="a3"))
    await orchestrator.publish(
        SignalB(correlation_id="req-2", data="b2")
    )  # req-2 completes (within 5)
    await orchestrator.run_until_idle()

    # Should have 2 correlations (req-1 and req-2)
    assert len(executed) == 2, "Should have 2 correlations"
    correlation_ids = {e["correlation_id"] for e in executed}
    assert correlation_ids == {"req-1", "req-2"}


# ============================================================================
# Phase 2 Week 2-3: Integration & Performance Tests
# ============================================================================


@pytest.mark.asyncio
async def test_joinspec_with_visibility_controls():
    """
    GIVEN: Agent with JoinSpec + visibility restrictions
    WHEN: Some artifacts are visible, some are not
    THEN: Only visible artifacts participate in correlation

    Real-world: Multi-tenant system where each tenant's data is isolated.
    """
    from flock.core.visibility import PrivateVisibility, PublicVisibility

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("visibility_correlator")
        .labels("team_a")  # Agent has label "team_a"
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: Both artifacts PUBLIC → should correlate
    await orchestrator.publish(
        SignalA(correlation_id="pub-1", data="a1"), visibility=PublicVisibility()
    )
    await orchestrator.publish(
        SignalB(correlation_id="pub-1", data="b1"), visibility=PublicVisibility()
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Public artifacts should correlate"

    # Scenario 2: SignalA private (for team_b), SignalB public → should NOT correlate
    await orchestrator.publish(
        SignalA(correlation_id="mixed-1", data="a2"),
        visibility=PrivateVisibility(labels={"team_b"}),  # Not visible to team_a
    )
    await orchestrator.publish(
        SignalB(correlation_id="mixed-1", data="b2"), visibility=PublicVisibility()
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, (
        "Mixed visibility should NOT correlate (SignalA filtered out)"
    )


@pytest.mark.asyncio
async def test_joinspec_with_where_predicate_filters_before_correlation():
    """
    GIVEN: Agent with JoinSpec + where predicate
    WHEN: Artifacts match type but fail predicate
    THEN: Filtered artifacts do NOT enter correlation pool

    Mental model: Predicate is "bouncer at the door" - filters BEFORE correlation.

    Real-world: Healthcare system only correlates "completed" lab results,
    ignores "pending" ones even if they match the correlation key.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifacts": inputs.artifacts,
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    # Predicate: Only accept SignalB with data starting with "completed"
    def predicate(payload):
        # Apply predicate to SignalB only (SignalA always passes)
        if hasattr(payload, "data") and isinstance(payload, SignalB):
            return payload.data.startswith("completed")
        return True  # SignalA always passes

    agent = (
        orchestrator.agent("predicate_correlator")
        .consumes(
            SignalA,
            SignalB,
            where=predicate,
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Scenario 1: SignalB with "pending" status → REJECTED by predicate
    await orchestrator.publish(SignalA(correlation_id="lab-1", data="xray"))
    await orchestrator.publish(SignalB(correlation_id="lab-1", data="pending"))
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "SignalB rejected by predicate, no correlation"

    # Scenario 2: SignalB with "completed" status → ACCEPTED by predicate
    await orchestrator.publish(
        SignalB(correlation_id="lab-1", data="completed-results")
    )
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "SignalB accepted, correlation completes"
    assert len(executed[0]["artifacts"]) == 2, "Both artifacts present"


@pytest.mark.asyncio
async def test_joinspec_correlation_state_isolation_per_agent():
    """
    GIVEN: TWO agents with same JoinSpec correlation
    WHEN: Artifacts published match both agents
    THEN: Each agent maintains its own correlation state (isolated pools)

    Real-world: Multiple microservices independently correlating the same event stream.
    """
    orchestrator = Flock()
    executed_agent1 = []
    executed_agent2 = []

    class TrackingEngine1(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed_agent1.append({
                "agent": agent.name,
                "correlation_id": inputs.artifacts[0].payload["correlation_id"],
            })
            return EvalResult(artifacts=[])

    class TrackingEngine2(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed_agent2.append({
                "agent": agent.name,
                "correlation_id": inputs.artifacts[0].payload["correlation_id"],
            })
            return EvalResult(artifacts=[])

    # Agent 1: Correlates SignalA + SignalB
    agent1 = (
        orchestrator.agent("agent1")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine1())
    )

    # Agent 2: Also correlates SignalA + SignalB (independent state)
    agent2 = (
        orchestrator.agent("agent2")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine2())
    )

    # Publish correlated pair
    await orchestrator.publish(SignalA(correlation_id="shared-1", data="a"))
    await orchestrator.publish(SignalB(correlation_id="shared-1", data="b"))
    await orchestrator.run_until_idle()

    # BOTH agents should trigger independently
    assert len(executed_agent1) == 1, "Agent1 should correlate"
    assert len(executed_agent2) == 1, "Agent2 should correlate"
    assert executed_agent1[0]["agent"] == "agent1"
    assert executed_agent2[0]["agent"] == "agent2"
    assert executed_agent1[0]["correlation_id"] == "shared-1"
    assert executed_agent2[0]["correlation_id"] == "shared-1"


@pytest.mark.asyncio
async def test_joinspec_performance_correlation_overhead():
    """
    GIVEN: Agent with JoinSpec correlation
    WHEN: Multiple correlated pairs published rapidly
    THEN: Correlation overhead should be <50ms total

    Performance target: Correlation should add minimal latency.
    """
    import time

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("performance_test")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(minutes=5)),
        )
        .with_engines(TrackingEngine())
    )

    # Publish 10 correlated pairs rapidly
    start = time.time()
    for i in range(10):
        await orchestrator.publish(SignalA(correlation_id=f"perf-{i}", data=f"a{i}"))
        await orchestrator.publish(SignalB(correlation_id=f"perf-{i}", data=f"b{i}"))
    await orchestrator.run_until_idle()
    end = time.time()

    # Verify all correlations triggered
    assert len(executed) == 10, "All 10 pairs should correlate"

    # Performance check: <2000ms overhead (accounting for CI environment variability)
    elapsed_ms = (end - start) * 1000
    print(
        f"\nCorrelation performance: {elapsed_ms:.2f}ms for 10 pairs ({elapsed_ms / 10:.2f}ms per pair)"
    )
    assert elapsed_ms < 2000, (
        f"Performance target: <2000ms total (got {elapsed_ms:.2f}ms)"
    )


@pytest.mark.asyncio
async def test_joinspec_time_based_expiry_discards_partial_correlation():
    """
    GIVEN: Agent with JoinSpec with time-based window (1 second)
    WHEN: Only 1 of 2 required types arrives, then timeout expires
    THEN: Partial correlation is DISCARDED (not flushed), agent never runs

    This test verifies:
    1. Background cleanup task starts for time-based correlations
    2. Expired partial correlations are discarded (not flushed like batches)
    3. Agent does NOT run with incomplete data
    """
    import asyncio

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifacts": len(inputs.artifacts),
                "types": [a.type for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("time_expiry_test")
        .consumes(
            SignalA,
            SignalB,
            join=JoinSpec(
                by=lambda x: x.correlation_id,
                within=timedelta(seconds=1.0),  # 1 second time window
            ),
        )
        .with_engines(TrackingEngine())
    )

    # Publish ONLY SignalA (missing SignalB)
    await orchestrator.publish(SignalA(correlation_id="incomplete-1", data="a"))
    await orchestrator.run_until_idle()

    # Verify agent hasn't run yet (partial correlation waiting)
    assert len(executed) == 0, "Agent should not run with partial correlation"

    # Wait for timeout to expire (1.0s + margin)
    await asyncio.sleep(1.2)
    await orchestrator.run_until_idle()

    # Verify agent STILL hasn't run (partial correlation discarded)
    assert len(executed) == 0, (
        "Agent should not run - partial correlation discarded after timeout"
    )

    # Now publish a complete pair with SAME correlation_id (should start fresh)
    await orchestrator.publish(SignalA(correlation_id="incomplete-1", data="a2"))
    await orchestrator.publish(SignalB(correlation_id="incomplete-1", data="b2"))
    await orchestrator.run_until_idle()

    # Now agent should run (new complete correlation)
    assert len(executed) == 1, "Agent should run with complete correlation"
    assert executed[0]["artifacts"] == 2, "Should have both artifacts"


@pytest.mark.asyncio
async def test_joinspec_time_expiry_vs_batch_timeout_behavior():
    """
    COMPARISON TEST: JoinSpec expiry vs BatchSpec timeout behavior

    GIVEN: Two agents - one with JoinSpec (correlation), one with BatchSpec (batching)
    WHEN: Both receive partial data and timeout expires
    THEN:
    - JoinSpec: DISCARDS partial correlation (agent never runs)
    - BatchSpec: FLUSHES partial batch (agent runs with partial data)

    This test documents the fundamental difference in timeout behavior.
    """
    import asyncio

    from flock.core.subscription import BatchSpec

    orchestrator = Flock()
    correlation_executed = []
    batch_executed = []
    batch_count = 0

    class CorrelationEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            correlation_executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    class BatchEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            nonlocal batch_count
            batch_count += 1
            batch_executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

        async def evaluate_batch(self, agent, ctx, inputs, output_group):
            nonlocal batch_count
            batch_count += 1
            batch_executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    # Agent 1: JoinSpec correlation (requires A+B, 1s timeout)
    orchestrator.agent("correlation_agent").consumes(
        SignalA,
        SignalB,
        join=JoinSpec(by=lambda x: x.correlation_id, within=timedelta(seconds=1.0)),
    ).with_engines(CorrelationEngine())

    # Agent 2: BatchSpec batching (batches SignalC, 1s timeout)
    orchestrator.agent("batch_agent").consumes(
        SignalC, batch=BatchSpec(size=10, timeout=timedelta(seconds=1.0))
    ).with_engines(BatchEngine())

    # Publish partial data for both
    await orchestrator.publish(
        SignalA(correlation_id="test", data="a")
    )  # Only A, missing B
    await orchestrator.publish(SignalC(correlation_id="test", data="c1"))  # Only 1 item
    await orchestrator.run_until_idle()

    # Both waiting
    assert len(correlation_executed) == 0, "Correlation waiting for SignalB"
    assert len(batch_executed) == 0, "Batch waiting for more items or timeout"

    # Wait for timeout (1.5s to be safe)
    await asyncio.sleep(3.5)
    await orchestrator.run_until_idle()

    # DIFFERENT BEHAVIORS:
    assert len(correlation_executed) == 0, (
        "JoinSpec: partial correlation DISCARDED (agent never runs)"
    )
    assert batch_count == 1
    assert len(batch_executed) == 1, "BatchSpec: partial batch FLUSHED (agent runs)"
    assert batch_executed[0] == 1, "BatchSpec: agent received 1 item from partial flush"
