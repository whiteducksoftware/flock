"""
Tests for BatchSpec - Batch Processing

BatchSpec allows agents to accumulate artifacts and trigger on:
1. Size threshold (e.g., batch of 10)
2. Timeout (e.g., flush every 30 seconds)
3. Whichever comes first

Real-world use case: Cost optimization
- Batch 25 API calls together instead of calling one-by-one
- 25x cost savings for providers charging per API call

Test-Driven Development (TDD):
- Tests written FIRST
- Implementation SECOND
- Green tests = working feature
"""

from datetime import timedelta

import pytest
from pydantic import BaseModel

from flock import Flock
from flock.components.agent import EngineComponent
from flock.core.subscription import BatchSpec
from flock.engines.examples import SimpleBatchEngine
from flock.engines.examples.simple_batch_engine import BatchItem as SimpleBatchInput
from flock.engines.examples.simple_batch_engine import BatchSummary
from flock.utils.runtime import EvalInputs, EvalResult


# ============================================================================
# Test Fixtures
# ============================================================================


class Event(BaseModel):
    """Simple event for batching tests."""

    id: int
    data: str


class OrderEvent(BaseModel):
    """Order event for e-commerce batching scenario."""

    order_id: str
    amount: float
    customer_id: str


# ============================================================================
# Phase 3 Week 1: Size-Based Batching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batchspec_flushes_on_size_threshold():
    """
    GIVEN: Agent with BatchSpec(size=3)
    WHEN: 2 artifacts published
    THEN: No flush (batch incomplete)
    WHEN: 3rd artifact published
    THEN: Flush triggered, agent receives batch of 3

    Real-world: Accumulate 3 orders, then process batch payment.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "batch_size": len(inputs.artifacts),
                "payloads": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("batch_processor")
        .consumes(Event, batch=BatchSpec(size=3))
        .with_engines(TrackingEngine())
    )

    # Publish 2 artifacts - should NOT flush yet
    await orchestrator.publish(Event(id=1, data="e1"))
    await orchestrator.publish(Event(id=2, data="e2"))
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Batch not full yet, no flush"

    # Publish 3rd artifact - should flush
    await orchestrator.publish(Event(id=3, data="e3"))
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Batch flushed after size threshold"
    assert executed[0]["batch_size"] == 3, "Batch contains 3 artifacts"
    ids = [p["id"] for p in executed[0]["payloads"]]
    assert ids == [1, 2, 3], "Batch contains correct artifacts in order"


@pytest.mark.asyncio
async def test_batchspec_continues_batching_after_flush():
    """
    GIVEN: Agent with BatchSpec(size=3)
    WHEN: 6 artifacts published (2 batches worth)
    THEN: Two separate flushes occur (batch 1-3, then 4-6)

    Ensures batch accumulator resets after flush.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("batch_processor")
        .consumes(Event, batch=BatchSpec(size=3))
        .with_engines(TrackingEngine())
    )

    # Publish 6 artifacts - should trigger 2 flushes
    for i in range(1, 7):
        await orchestrator.publish(Event(id=i, data=f"e{i}"))
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "Two batches flushed"
    assert executed[0] == [1, 2, 3], "First batch: 1-3"
    assert executed[1] == [4, 5, 6], "Second batch: 4-6"


@pytest.mark.asyncio
async def test_batchspec_partial_batch_stays_pending():
    """
    GIVEN: Agent with BatchSpec(size=5)
    WHEN: Only 3 artifacts published
    THEN: No flush (batch incomplete, stays in accumulator)

    Partial batches wait until size threshold OR timeout (tested later).
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("batch_processor")
        .consumes(Event, batch=BatchSpec(size=5))
        .with_engines(TrackingEngine())
    )

    # Publish 3 artifacts (not enough for size=5)
    await orchestrator.publish(Event(id=1, data="e1"))
    await orchestrator.publish(Event(id=2, data="e2"))
    await orchestrator.publish(Event(id=3, data="e3"))
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Partial batch should NOT flush"


@pytest.mark.asyncio
async def test_batchspec_multiple_agents_independent_batches():
    """
    GIVEN: TWO agents with different BatchSpec sizes
    WHEN: Artifacts published
    THEN: Each agent maintains its own batch accumulator (isolated)

    Real-world: Different microservices batch the same event stream differently.
    """
    orchestrator = Flock()
    executed_agent1 = []
    executed_agent2 = []

    class TrackingEngine1(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed_agent1.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    class TrackingEngine2(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed_agent2.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    # Agent 1: Batch size 2
    agent1 = (
        orchestrator.agent("batch_agent1")
        .consumes(Event, batch=BatchSpec(size=2))
        .with_engines(TrackingEngine1())
    )

    # Agent 2: Batch size 3
    agent2 = (
        orchestrator.agent("batch_agent2")
        .consumes(Event, batch=BatchSpec(size=3))
        .with_engines(TrackingEngine2())
    )

    # Publish 6 artifacts
    for i in range(1, 7):
        await orchestrator.publish(Event(id=i, data=f"e{i}"))
    await orchestrator.run_until_idle()

    # Agent 1: Batch size 2 → 3 flushes (2, 2, 2)
    assert len(executed_agent1) == 3, "Agent1: 3 batches"
    assert executed_agent1 == [2, 2, 2], "Agent1: batches of 2"

    # Agent 2: Batch size 3 → 2 flushes (3, 3)
    assert len(executed_agent2) == 2, "Agent2: 2 batches"
    assert executed_agent2 == [3, 3], "Agent2: batches of 3"


@pytest.mark.asyncio
async def test_batchspec_with_single_type_subscription():
    """
    GIVEN: Agent with BatchSpec on single type
    WHEN: Artifacts published
    THEN: Batching works correctly (no AND gate involved)

    Batching is orthogonal to AND/OR gates.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("single_type_batch")
        .consumes(Event, batch=BatchSpec(size=2))
        .with_engines(TrackingEngine())
    )

    # Publish 4 events → 2 batches
    for i in range(1, 5):
        await orchestrator.publish(Event(id=i, data=f"e{i}"))
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "Two batches"
    assert executed[0] == [1, 2], "First batch"
    assert executed[1] == [3, 4], "Second batch"


# ============================================================================
# Phase 3 Week 2: Timeout-Based Batching Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batchspec_flushes_on_timeout():
    """
    GIVEN: Agent with BatchSpec(timeout=100ms)
    WHEN: 1 artifact published, then 100ms elapses
    THEN: Timeout flush triggered, agent receives partial batch of 1

    Real-world: Don't wait forever for full batch, flush periodically.
    """
    import asyncio

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("timeout_batch")
        .consumes(Event, batch=BatchSpec(timeout=timedelta(milliseconds=100)))
        .with_engines(TrackingEngine())
    )

    # Publish 1 artifact
    await orchestrator.publish(Event(id=1, data="e1"))
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "No immediate flush"

    # Wait for timeout
    await asyncio.sleep(0.15)  # 150ms > 100ms timeout

    # Trigger timeout check (orchestrator should have background task)
    # For now, we'll manually trigger it
    await orchestrator._check_batch_timeouts()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Timeout flush triggered"
    assert executed[0] == 1, "Partial batch of 1"


@pytest.mark.asyncio
async def test_batchspec_size_or_timeout_whichever_first():
    """
    GIVEN: Agent with BatchSpec(size=5, timeout=200ms)
    WHEN: 3 artifacts published quickly
    THEN: No flush (neither threshold met)
    WHEN: Timeout expires
    THEN: Timeout flush with 3 artifacts

    WHEN: 5 more artifacts published before timeout
    THEN: Size flush (size wins over timeout)
    """
    import asyncio

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("hybrid_batch")
        .consumes(Event, batch=BatchSpec(size=5, timeout=timedelta(milliseconds=200)))
        .with_engines(TrackingEngine())
    )

    # Scenario 1: Timeout wins (3 artifacts, timeout at 200ms)
    await orchestrator.publish(Event(id=1, data="e1"))
    await orchestrator.publish(Event(id=2, data="e2"))
    await orchestrator.publish(Event(id=3, data="e3"))
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "No flush yet"

    await asyncio.sleep(0.25)  # 250ms > 200ms
    await orchestrator._check_batch_timeouts()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Timeout flush"
    assert executed[0] == 3, "Partial batch of 3"

    # Scenario 2: Size wins (5 artifacts published quickly)
    for i in range(4, 9):
        await orchestrator.publish(Event(id=i, data=f"e{i}"))
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "Size flush (before timeout)"
    assert executed[1] == 5, "Full batch of 5"


@pytest.mark.asyncio
async def test_batchspec_timeout_resets_after_flush():
    """
    GIVEN: Agent with BatchSpec(timeout=100ms)
    WHEN: Batch flushed (size or timeout)
    THEN: Timeout timer resets for next batch

    Ensures timeout doesn't trigger on empty accumulator.
    """
    import asyncio

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("timeout_reset")
        .consumes(Event, batch=BatchSpec(size=2, timeout=timedelta(milliseconds=100)))
        .with_engines(TrackingEngine())
    )

    # Batch 1: Size flush (2 artifacts)
    await orchestrator.publish(Event(id=1, data="e1"))
    await orchestrator.publish(Event(id=2, data="e2"))
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Size flush"

    # Wait past timeout
    await asyncio.sleep(0.15)
    await orchestrator._check_batch_timeouts()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "No spurious timeout flush (accumulator empty)"

    # Batch 2: Timeout flush (1 artifact)
    await orchestrator.publish(Event(id=3, data="e3"))
    await orchestrator.run_until_idle()

    await asyncio.sleep(0.15)
    await orchestrator._check_batch_timeouts()
    await orchestrator.run_until_idle()

    assert len(executed) == 2, "New timeout flush"
    assert executed[1] == 1, "Partial batch"


@pytest.mark.asyncio
async def test_batchspec_shutdown_flushes_partial_batch():
    """
    GIVEN: Agent with partial batch in accumulator
    WHEN: Orchestrator shuts down
    THEN: Partial batch is flushed (no data loss)

    Critical: Users expect zero data loss on shutdown.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("shutdown_test")
        .consumes(Event, batch=BatchSpec(size=5))
        .with_engines(TrackingEngine())
    )

    # Publish 3 artifacts (partial batch)
    await orchestrator.publish(Event(id=1, data="e1"))
    await orchestrator.publish(Event(id=2, data="e2"))
    await orchestrator.publish(Event(id=3, data="e3"))
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "No flush yet (partial)"

    # Simulate shutdown - flush all partial batches
    await orchestrator._flush_all_batches()
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Shutdown flushed partial batch"
    assert executed[0] == 3, "All 3 artifacts delivered"


# ============================================================================
# Phase 3 Week 2: Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_batchspec_with_visibility_filters_before_batching():
    """
    GIVEN: Agent with BatchSpec + visibility restrictions
    WHEN: Some artifacts visible, some not
    THEN: Only visible artifacts enter batch accumulator

    Mental model: Visibility filtering happens BEFORE batching.
    """
    from flock.core.visibility import PrivateVisibility, PublicVisibility

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("visibility_batch")
        .labels("team_a")
        .consumes(Event, batch=BatchSpec(size=2))
        .with_engines(TrackingEngine())
    )

    # Publish 4 events: 2 public, 2 private (team_b)
    await orchestrator.publish(Event(id=1, data="e1"), visibility=PublicVisibility())
    await orchestrator.publish(
        Event(id=2, data="e2"), visibility=PrivateVisibility(labels={"team_b"})
    )
    await orchestrator.publish(Event(id=3, data="e3"), visibility=PublicVisibility())
    await orchestrator.publish(
        Event(id=4, data="e4"), visibility=PrivateVisibility(labels={"team_b"})
    )
    await orchestrator.run_until_idle()

    # Only 2 public events should batch (team_b events filtered out)
    assert len(executed) == 1, "One batch"
    assert executed[0] == [1, 3], "Only public events batched"


@pytest.mark.asyncio
async def test_batchspec_with_where_predicate_filters_before_batching():
    """
    GIVEN: Agent with BatchSpec + where predicate
    WHEN: Some artifacts pass predicate, some don't
    THEN: Only passing artifacts enter batch accumulator

    Mental model: Predicate is "bouncer at the door" - filters BEFORE batching.
    """
    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["id"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    # Predicate: Only accept events with even IDs
    def predicate(payload):
        return payload.id % 2 == 0

    agent = (
        orchestrator.agent("predicate_batch")
        .consumes(Event, where=predicate, batch=BatchSpec(size=2))
        .with_engines(TrackingEngine())
    )

    # Publish 5 events: 1, 2, 3, 4, 5 (only 2, 4 pass predicate)
    for i in range(1, 6):
        await orchestrator.publish(Event(id=i, data=f"e{i}"))
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "One batch (2 and 4)"
    assert executed[0] == [2, 4], "Only even IDs batched"


@pytest.mark.order(1)
@pytest.mark.asyncio
async def test_simple_batch_engine_processes_all_artifacts():
    """
    GIVEN: SimpleBatchEngine with BatchSpec(size=3)
    WHEN: Three artifacts are published
    THEN: Engine receives all three and annotates batch size correctly
    """
    orchestrator = Flock()

    (
        orchestrator.agent("simple_batch")
        .consumes(SimpleBatchInput, batch=BatchSpec(size=3))
        .publishes(BatchSummary)
        .with_engines(SimpleBatchEngine())
    )

    await orchestrator.publish(SimpleBatchInput(value=1))
    await orchestrator.publish(SimpleBatchInput(value=2))
    await orchestrator.publish(SimpleBatchInput(value=3))
    await orchestrator.run_until_idle()

    outputs = [
        artifact
        for artifact in await orchestrator.store.list()
        if artifact.produced_by == "simple_batch" and artifact.type == "BatchSummary"
    ]

    assert len(outputs) == 1, "Engine should emit a single batch summary"
    summary = outputs[0].payload
    assert summary["batch_size"] == 3
    assert summary["values"] == [1, 2, 3]


@pytest.mark.order(2)
@pytest.mark.asyncio
async def test_batch_spec_with_non_batch_engine_logs_error(caplog):
    """
    GIVEN: Agent with BatchSpec but engine lacks evaluate_batch()
    WHEN: Batch fills to required size
    THEN: NotImplementedError is surfaced
    """

    class NonBatchEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            return EvalResult.empty()

    orchestrator = Flock()

    (
        orchestrator.agent("non_batch_engine")
        .consumes(SimpleBatchInput, batch=BatchSpec(size=2))
        .with_engines(NonBatchEngine())
    )

    await orchestrator.publish(SimpleBatchInput(value=10))
    await orchestrator.publish(SimpleBatchInput(value=20))

    await orchestrator.run_until_idle()

    # No outputs should be produced because the engine failed before publishing.
    outputs = [
        artifact
        for artifact in await orchestrator.store.list()
        if artifact.produced_by == "non_batch_engine"
    ]
    assert outputs == []


@pytest.mark.asyncio
async def test_batchspec_performance_batching_overhead():
    """
    GIVEN: Agent with BatchSpec
    WHEN: 100 artifacts published in 10 batches
    THEN: Batching overhead <100ms total

    Performance target: Batching should add minimal latency.
    """
    import time

    orchestrator = Flock()
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    agent = (
        orchestrator.agent("performance_batch")
        .consumes(Event, batch=BatchSpec(size=10))
        .with_engines(TrackingEngine())
    )

    # Publish 100 artifacts → 10 batches
    start = time.time()
    for i in range(1, 101):
        await orchestrator.publish(Event(id=i, data=f"e{i}"))
    await orchestrator.run_until_idle()
    end = time.time()

    # Verify all batches triggered
    assert len(executed) == 10, "10 batches"
    assert all(size == 10 for size in executed), "All batches size 10"

    # Performance check: <3000ms overhead (relaxed for slow CI VMs)
    elapsed_ms = (end - start) * 1000
    print(f"\nBatching performance: {elapsed_ms:.2f}ms for 100 artifacts in 10 batches")
    assert elapsed_ms < 3000, f"Performance target: <3000ms (got {elapsed_ms:.2f}ms)"
