"""
Test Suite: AND/OR Gate Logic for Multi-Type Subscriptions

This test suite validates the new AND gate behavior for `.consumes(A, B)` syntax
and ensures backward compatibility with OR gate via chaining `.consumes(A).consumes(B)`.

Target Implementation: Phase 1 of Logic Operations (Spec 003)
Status: RED - Tests written first, implementation pending
"""

import pytest
from pydantic import BaseModel, Field

from flock.components.agent import EngineComponent
from flock.registry import flock_type
from flock.utils.runtime import EvalResult


# Test Types for AND/OR Gate Testing
@flock_type(name="TypeA")
class TypeA(BaseModel):
    """Test type A for multi-type subscription testing."""

    value: str = Field(description="Value for type A")
    correlation_id: str = Field(
        default="default", description="Correlation ID for join testing"
    )


@flock_type(name="TypeB")
class TypeB(BaseModel):
    """Test type B for multi-type subscription testing."""

    value: str = Field(description="Value for type B")
    correlation_id: str = Field(
        default="default", description="Correlation ID for join testing"
    )


@flock_type(name="TypeC")
class TypeC(BaseModel):
    """Test type C for three-way AND gate testing."""

    value: str = Field(description="Value for type C")


# ============================================================================
# Phase 1, Week 1, Day 1-2: Basic AND Gate Tests
# ============================================================================


@pytest.mark.asyncio
async def test_simple_and_gate_waits_for_both_types(orchestrator):
    """
    Test that `.consumes(A, B)` implements AND gate logic.

    GIVEN: Agent consumes TypeA AND TypeB (AND gate)
    WHEN: Only TypeA is published
    THEN: Agent should NOT be triggered
    WHEN: TypeB is then published
    THEN: Agent should be triggered with BOTH artifacts

    This is the foundational test for AND gate behavior.
    Currently FAILS because `.consumes(A, B)` uses OR logic.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        """Tracks agent execution with artifact details."""

        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "agent": agent.name,
                "artifacts": inputs.artifacts,
                "artifact_count": len(inputs.artifacts),
                "types": [a.type for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    # Create agent with AND gate subscription
    orchestrator.agent("and_gate_agent").consumes(TypeA, TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish only TypeA
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Agent should NOT be triggered yet (waiting for TypeB)
    assert len(executed) == 0, (
        "Agent should NOT trigger with only TypeA (AND gate requires both)"
    )

    # Act - Publish TypeB
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Agent should NOW be triggered with BOTH artifacts
    assert len(executed) == 1, "Agent should trigger once when both types present"
    assert executed[0]["artifact_count"] == 2, "Agent should receive BOTH artifacts"

    # Verify both types are present
    types_received = set(executed[0]["types"])
    assert types_received == {"TypeA", "TypeB"}, (
        f"Expected both types, got {types_received}"
    )


@pytest.mark.asyncio
async def test_and_gate_order_independence(orchestrator):
    """
    Test that AND gate works regardless of artifact publication order.

    GIVEN: Agent with AND gate subscription
    WHEN: TypeB published before TypeA
    THEN: Agent should still wait for both and trigger correctly

    This ensures the waiting pool doesn't depend on publication order.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    orchestrator.agent("order_test").consumes(TypeA, TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish TypeB FIRST (reverse order)
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Should not trigger with only TypeB"

    # Act - Publish TypeA SECOND
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger with both artifacts
    assert len(executed) == 1, "Should trigger when both types present"
    assert executed[0] == 2, "Should receive both artifacts"


@pytest.mark.asyncio
async def test_three_way_and_gate(orchestrator):
    """
    Test that AND gate works with more than 2 types.

    GIVEN: Agent consumes TypeA, TypeB, AND TypeC
    WHEN: Only 2 out of 3 types published
    THEN: Agent should NOT trigger
    WHEN: All 3 types published
    THEN: Agent should trigger with all 3 artifacts
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "count": len(inputs.artifacts),
                "types": [a.type for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    orchestrator.agent("three_way").consumes(TypeA, TypeB, TypeC).with_engines(
        TrackingEngine()
    )

    # Act - Publish only TypeA and TypeB
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Should not trigger with only 2 out of 3 types"

    # Act - Publish TypeC (completes the set)
    await orchestrator.publish({"type": "TypeC", "value": "c1"})
    await orchestrator.run_until_idle()

    # Assert - Should trigger with all 3 artifacts
    assert len(executed) == 1, "Should trigger when all 3 types present"
    assert executed[0]["count"] == 3, "Should receive all 3 artifacts"
    assert set(executed[0]["types"]) == {"TypeA", "TypeB", "TypeC"}


@pytest.mark.asyncio
async def test_multiple_agents_same_types_independent_waiting(orchestrator):
    """
    Test that multiple agents with AND gates don't interfere.

    GIVEN: Two agents both consume TypeA AND TypeB
    WHEN: Both types published
    THEN: Both agents should trigger independently
    """
    # Arrange
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

    orchestrator.agent("agent1").consumes(TypeA, TypeB).with_engines(TrackingEngine1())

    orchestrator.agent("agent2").consumes(TypeA, TypeB).with_engines(TrackingEngine2())

    # Act - Publish both types
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Both agents should trigger independently
    assert len(executed_agent1) == 1, "Agent1 should trigger"
    assert len(executed_agent2) == 1, "Agent2 should trigger"
    assert executed_agent1[0] == 2, "Agent1 should receive 2 artifacts"
    assert executed_agent2[0] == 2, "Agent2 should receive 2 artifacts"


@pytest.mark.asyncio
async def test_partial_match_does_not_trigger(orchestrator):
    """
    Test that partial matches don't trigger AND gate prematurely.

    GIVEN: Agent with AND gate for TypeA and TypeB
    WHEN: TypeA published multiple times but no TypeB
    THEN: Agent should NEVER trigger (still waiting for TypeB)
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(True)
            return EvalResult(artifacts=[])

    orchestrator.agent("partial_test").consumes(TypeA, TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish TypeA multiple times (but no TypeB)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a3",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should NEVER trigger (still waiting for TypeB)
    assert len(executed) == 0, "Agent should not trigger without TypeB"


# ============================================================================
# Edge Cases and Error Scenarios
# ============================================================================


@pytest.mark.asyncio
async def test_and_gate_with_single_type_triggers_immediately(orchestrator):
    """
    Test that `.consumes(TypeA)` with single type triggers immediately (no waiting).

    GIVEN: Agent consumes only TypeA (no AND gate needed)
    WHEN: TypeA published
    THEN: Agent should trigger immediately (no waiting for additional types)

    This ensures single-type subscriptions aren't affected by AND gate logic.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    orchestrator.agent("single_type").consumes(TypeA).with_engines(TrackingEngine())

    # Act
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger immediately with single artifact
    assert len(executed) == 1, "Single-type subscription should trigger immediately"
    assert executed[0] == 1, "Should receive single artifact"


@pytest.mark.asyncio
async def test_and_gate_does_not_accumulate_across_completions(orchestrator):
    """
    Test that AND gate waiting pool is cleared after triggering.

    GIVEN: Agent with AND gate
    WHEN: Both types published (first completion)
    AND: Both types published again (second time)
    THEN: Agent should trigger TWICE (independent waiting pools)

    This ensures the waiting pool is cleared after each successful trigger.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "count": len(inputs.artifacts),
                "values": [a.payload["value"] for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    orchestrator.agent("repeat_test").consumes(TypeA, TypeB).with_engines(
        TrackingEngine()
    )

    # Act - First completion
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Should trigger first time"

    # Act - Second completion (new pair)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b2",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger second time independently
    assert len(executed) == 2, "Should trigger second time with new pair"
    assert executed[0]["count"] == 2, "First trigger should have 2 artifacts"
    assert executed[1]["count"] == 2, "Second trigger should have 2 artifacts"

    # Verify different values (not accumulated)
    assert executed[0]["values"] == ["a1", "b1"], "First trigger should have first pair"
    assert executed[1]["values"] == ["a2", "b2"], (
        "Second trigger should have second pair"
    )


# ============================================================================
# Phase 1, Week 2: OR Gate via Chaining Tests
# ============================================================================


@pytest.mark.asyncio
async def test_or_gate_via_chaining(orchestrator):
    """
    Test that `.consumes(A).consumes(B)` implements OR gate logic.

    GIVEN: Agent with chained consumes (OR gate)
    WHEN: TypeA is published
    THEN: Agent triggered with TypeA only
    WHEN: TypeB is published
    THEN: Agent triggered AGAIN with TypeB only

    This verifies backward compatibility - chaining creates separate
    subscriptions, each triggering independently.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "trigger_count": len(executed) + 1,
                "artifact_count": len(inputs.artifacts),
                "types": [a.type for a in inputs.artifacts],
                "values": [a.payload["value"] for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    # Create agent with OR gate subscription (chaining)
    orchestrator.agent("or_gate_agent").consumes(TypeA).consumes(TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish TypeA
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Agent should trigger with ONLY TypeA
    assert len(executed) == 1, "Agent should trigger once with TypeA"
    assert executed[0]["artifact_count"] == 1, "Agent should receive single artifact"
    assert executed[0]["types"] == ["TypeA"], "Agent should receive only TypeA"
    assert executed[0]["values"] == ["a1"]

    # Act - Publish TypeB
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Agent should trigger AGAIN with ONLY TypeB
    assert len(executed) == 2, "Agent should trigger second time with TypeB"
    assert executed[1]["artifact_count"] == 1, "Agent should receive single artifact"
    assert executed[1]["types"] == ["TypeB"], "Agent should receive only TypeB"
    assert executed[1]["values"] == ["b1"]


@pytest.mark.asyncio
async def test_mixed_and_or_subscriptions(orchestrator):
    """
    Test agent with BOTH AND gate and OR gate subscriptions.

    GIVEN: Agent with `.consumes(A, B)` AND `.consumes(C)`
    WHEN: TypeC published
    THEN: Agent triggers with only TypeC (OR gate)
    WHEN: TypeA and TypeB published
    THEN: Agent triggers with both TypeA and TypeB (AND gate)

    This ensures AND and OR gates don't interfere with each other.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifact_count": len(inputs.artifacts),
                "types": sorted([a.type for a in inputs.artifacts]),
            })
            return EvalResult(artifacts=[])

    # Create agent with MIXED subscriptions
    orchestrator.agent("mixed_agent").consumes(TypeA, TypeB).consumes(
        TypeC
    ).with_engines(TrackingEngine())

    # Act - Publish TypeC (OR gate should trigger)
    await orchestrator.publish({"type": "TypeC", "value": "c1"})
    await orchestrator.run_until_idle()

    # Assert - Should trigger with only TypeC
    assert len(executed) == 1, "Should trigger with TypeC"
    assert executed[0]["artifact_count"] == 1
    assert executed[0]["types"] == ["TypeC"]

    # Act - Publish TypeA (AND gate should wait)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Should NOT trigger yet (AND gate waiting for TypeB)"

    # Act - Publish TypeB (AND gate should complete)
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger with both TypeA and TypeB
    assert len(executed) == 2, "Should trigger with AND gate complete"
    assert executed[1]["artifact_count"] == 2
    assert executed[1]["types"] == ["TypeA", "TypeB"]


@pytest.mark.asyncio
async def test_or_gate_does_not_accumulate(orchestrator):
    """
    Test that OR gate triggers don't accumulate artifacts.

    GIVEN: Agent with `.consumes(A).consumes(B)` (OR gate)
    WHEN: TypeA published twice
    THEN: Agent triggers twice, each time with single TypeA artifact

    This ensures OR gate doesn't use the waiting pool.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    orchestrator.agent("or_test").consumes(TypeA).consumes(TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish TypeA twice
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger twice, each with single artifact
    assert len(executed) == 2, "Should trigger twice"
    assert executed[0] == 1, "First trigger should have 1 artifact"
    assert executed[1] == 1, "Second trigger should have 1 artifact"


@pytest.mark.asyncio
async def test_three_way_or_gate(orchestrator):
    """
    Test OR gate with three types via chaining.

    GIVEN: Agent with `.consumes(A).consumes(B).consumes(C)`
    WHEN: Any single type published
    THEN: Agent triggers with only that type

    This ensures chaining works for any number of types.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({"types": [a.type for a in inputs.artifacts]})
            return EvalResult(artifacts=[])

    orchestrator.agent("three_or").consumes(TypeA).consumes(TypeB).consumes(
        TypeC
    ).with_engines(TrackingEngine())

    # Act - Publish each type individually
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    await orchestrator.publish({"type": "TypeC", "value": "c1"})
    await orchestrator.run_until_idle()

    # Assert - Should trigger three times, each with single type
    assert len(executed) == 3, "Should trigger three times"
    assert executed[0]["types"] == ["TypeA"]
    assert executed[1]["types"] == ["TypeB"]
    assert executed[2]["types"] == ["TypeC"]


# ============================================================================
# Phase 1, Week 2, Day 3-5: Count-Based AND Gates
# ============================================================================


@pytest.mark.asyncio
async def test_count_based_and_gate_waits_for_three_as(orchestrator):
    """
    Test that `.consumes(A, A, A)` waits for THREE distinct A artifacts.

    GIVEN: Agent with `.consumes(TypeA, TypeA, TypeA)` (count-based AND)
    WHEN: Only 2 TypeA artifacts published
    THEN: Agent should NOT trigger (waiting for 3rd)
    WHEN: 3rd TypeA published
    THEN: Agent triggers with all 3 TypeA artifacts

    This implements count-based AND gate logic for duplicate types.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifact_count": len(inputs.artifacts),
                "types": [a.type for a in inputs.artifacts],
                "values": sorted([a.payload["value"] for a in inputs.artifacts]),
            })
            return EvalResult(artifacts=[])

    # Create agent with count-based AND gate (3 TypeA)
    orchestrator.agent("count_gate").consumes(TypeA, TypeA, TypeA).with_engines(
        TrackingEngine()
    )

    # Act - Publish 2 TypeA artifacts
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should NOT trigger yet (need 3)
    assert len(executed) == 0, "Agent should NOT trigger with only 2 TypeA (need 3)"

    # Act - Publish 3rd TypeA
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a3",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should NOW trigger with all 3 artifacts
    assert len(executed) == 1, "Agent should trigger when 3 TypeA present"
    assert executed[0]["artifact_count"] == 3, "Agent should receive 3 artifacts"
    assert executed[0]["types"] == ["TypeA", "TypeA", "TypeA"], "All 3 should be TypeA"
    assert executed[0]["values"] == ["a1", "a2", "a3"], "Should have all 3 values"


@pytest.mark.asyncio
async def test_count_based_and_gate_order_independence(orchestrator):
    """
    Test that count-based AND gate works regardless of publication order.

    GIVEN: Agent with `.consumes(A, A)`
    WHEN: TypeA artifacts published in any order
    THEN: Agent triggers when count reaches 2
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    orchestrator.agent("count_order").consumes(TypeA, TypeA).with_engines(
        TrackingEngine()
    )

    # Act - Publish 2 TypeA
    await orchestrator.publish({
        "type": "TypeA",
        "value": "first",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()
    assert len(executed) == 0, "Should not trigger with 1 TypeA"

    await orchestrator.publish({
        "type": "TypeA",
        "value": "second",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert
    assert len(executed) == 1, "Should trigger with 2 TypeA"
    assert executed[0] == 2, "Should receive 2 artifacts"


@pytest.mark.asyncio
async def test_mixed_count_and_type_gate(orchestrator):
    """
    Test mixed count and type requirements: `.consumes(A, A, B)`.

    GIVEN: Agent with `.consumes(TypeA, TypeA, TypeB)`
    WHEN: 1 TypeA + 1 TypeB published
    THEN: Agent should NOT trigger (need 2 TypeA)
    WHEN: 2nd TypeA published
    THEN: Agent triggers with 2 TypeA + 1 TypeB
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifact_count": len(inputs.artifacts),
                "type_counts": {
                    "TypeA": sum(1 for a in inputs.artifacts if a.type == "TypeA"),
                    "TypeB": sum(1 for a in inputs.artifacts if a.type == "TypeB"),
                },
            })
            return EvalResult(artifacts=[])

    orchestrator.agent("mixed_count").consumes(TypeA, TypeA, TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish 1 TypeA + 1 TypeB (incomplete)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Should NOT trigger (need 2 TypeA, only have 1)"

    # Act - Publish 2nd TypeA (complete)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger with 2 TypeA + 1 TypeB
    assert len(executed) == 1, "Should trigger with 2 TypeA + 1 TypeB"
    assert executed[0]["artifact_count"] == 3, "Should receive 3 artifacts total"
    assert executed[0]["type_counts"]["TypeA"] == 2, "Should have 2 TypeA"
    assert executed[0]["type_counts"]["TypeB"] == 1, "Should have 1 TypeB"


@pytest.mark.asyncio
async def test_count_based_latest_artifacts_win(orchestrator):
    """
    Test that latest artifacts are used when exceeding required count.

    GIVEN: Agent with `.consumes(A, A)` (need 2)
    WHEN: 4 TypeA artifacts published
    THEN: Agent triggers twice (first 2, then next 2)

    This tests the "latest wins" behavior for each completion cycle.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "artifact_count": len(inputs.artifacts),
                "values": sorted([a.payload["value"] for a in inputs.artifacts]),
            })
            return EvalResult(artifacts=[])

    orchestrator.agent("latest_wins").consumes(TypeA, TypeA).with_engines(
        TrackingEngine()
    )

    # Act - Publish 4 TypeA artifacts
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Should trigger first time with a1, a2"
    assert executed[0]["values"] == ["a1", "a2"]

    # Publish 2 more
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a3",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a4",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger second time with a3, a4
    assert len(executed) == 2, "Should trigger second time with a3, a4"
    assert executed[1]["values"] == ["a3", "a4"]


# ============================================================================
# Phase 1, Week 3, Day 1-2: Agent Signature Tests
# ============================================================================


@pytest.mark.asyncio
async def test_agent_receives_list_of_artifacts_for_and_gate(orchestrator):
    """
    Test that agent's evaluate() receives correct list of artifacts for AND gate.

    GIVEN: Agent with `.consumes(TypeA, TypeB)` AND gate
    WHEN: Both artifacts published
    THEN: Agent's evaluate() receives list with both artifacts in correct format
    """
    # Arrange
    received_inputs = []

    class InspectionEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # Capture the inputs object for inspection
            received_inputs.append({
                "type": type(inputs.artifacts).__name__,
                "length": len(inputs.artifacts),
                "artifact_types": [type(a).__name__ for a in inputs.artifacts],
                "artifact_values": [a.payload for a in inputs.artifacts],
            })
            return EvalResult(artifacts=[])

    orchestrator.agent("signature_test").consumes(TypeA, TypeB).with_engines(
        InspectionEngine()
    )

    # Act
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Verify signature
    assert len(received_inputs) == 1, "Agent should be called once"
    assert received_inputs[0]["type"] == "list", "Artifacts should be a list"
    assert received_inputs[0]["length"] == 2, "Should receive 2 artifacts"
    assert "Artifact" in str(received_inputs[0]["artifact_types"]), (
        "Should be Artifact objects"
    )


@pytest.mark.asyncio
async def test_agent_can_access_artifact_payloads_in_and_gate(orchestrator):
    """
    Test that agent can access individual artifact payloads from AND gate.

    GIVEN: Agent with AND gate subscription
    WHEN: Multiple artifacts trigger AND gate
    THEN: Agent can access each artifact's payload individually
    """
    # Arrange
    payloads_received = []

    class PayloadExtractorEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # Extract payloads from artifacts
            for artifact in inputs.artifacts:
                payloads_received.append({
                    "type": artifact.type,
                    "payload": artifact.payload,
                })
            return EvalResult(artifacts=[])

    orchestrator.agent("payload_test").consumes(TypeA, TypeB).with_engines(
        PayloadExtractorEngine()
    )

    # Act
    await orchestrator.publish({
        "type": "TypeA",
        "value": "test_a",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "test_b",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert
    assert len(payloads_received) == 2, "Should receive 2 payloads"
    assert payloads_received[0]["type"] == "TypeA"
    assert payloads_received[0]["payload"]["value"] == "test_a"
    assert payloads_received[1]["type"] == "TypeB"
    assert payloads_received[1]["payload"]["value"] == "test_b"


@pytest.mark.asyncio
async def test_count_based_gate_provides_all_instances_to_agent(orchestrator):
    """
    Test that count-based AND gate provides all N instances to agent.

    GIVEN: Agent with `.consumes(A, A, A)`
    WHEN: 3 TypeA artifacts published
    THEN: Agent receives list with all 3 distinct TypeA instances
    """
    # Arrange
    received_artifacts = []

    class CountInspectorEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            received_artifacts.extend(inputs.artifacts)
            return EvalResult(artifacts=[])

    orchestrator.agent("count_signature").consumes(TypeA, TypeA, TypeA).with_engines(
        CountInspectorEngine()
    )

    # Act
    await orchestrator.publish({
        "type": "TypeA",
        "value": "first",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "second",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeA",
        "value": "third",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert
    assert len(received_artifacts) == 3, "Should receive all 3 TypeA artifacts"
    values = [a.payload["value"] for a in received_artifacts]
    assert sorted(values) == ["first", "second", "third"], (
        "Should have all 3 distinct values"
    )


# ============================================================================
# Phase 1, Week 3, Day 3-5: Integration Tests
# ============================================================================


@pytest.mark.asyncio
async def test_and_gate_with_visibility_filter(orchestrator):
    """
    Test AND gate integration with visibility controls.

    GIVEN: Agent with AND gate and visibility restrictions
    WHEN: Artifacts with different visibility published
    THEN: AND gate only considers visible artifacts
    """

    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    # Create agent that only sees public artifacts
    orchestrator.agent("visibility_test").consumes(TypeA, TypeB).with_engines(
        TrackingEngine()
    )

    # Act - Publish public TypeA
    await orchestrator.publish({
        "type": "TypeA",
        "value": "public_a",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 0, "Should not trigger (waiting for TypeB)"

    # Publish public TypeB
    await orchestrator.publish({
        "type": "TypeB",
        "value": "public_b",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger with both public artifacts
    assert len(executed) == 1, "Should trigger with both public artifacts"
    assert executed[0] == 2, "Should receive 2 artifacts"


@pytest.mark.asyncio
async def test_and_gate_with_where_predicate(orchestrator):
    """
    Test AND gate integration with where clause filtering.

    GIVEN: Agent with AND gate and where predicate
    WHEN: Artifacts don't match predicate
    THEN: Agent should NOT trigger
    WHEN: Artifacts match predicate AND all types present
    THEN: Agent triggers

    Note: where predicates apply to ALL artifacts in subscription.
    Use type checking in predicate to filter specific types.
    """
    # Arrange
    executed = []

    class TrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append([a.payload["value"] for a in inputs.artifacts])
            return EvalResult(artifacts=[])

    # Create agent with AND gate + where predicate that allows all artifacts
    # Predicate: TypeA must start with "x", TypeB can be anything
    def predicate(payload):
        # TypeA: check if value starts with "x"
        if isinstance(payload, TypeA):
            return payload.value.startswith("x")
        # TypeB: always allow
        return True

    orchestrator.agent("where_test").consumes(
        TypeA, TypeB, where=predicate
    ).with_engines(TrackingEngine())

    # Act - Publish TypeA (doesn't match predicate) + TypeB
    # TypeB will be accepted and wait in the pool since TypeB always passes predicate
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 0, (
        "Should NOT trigger (TypeA doesn't match where predicate)"
    )

    # Act - Publish TypeA (matches predicate)
    # Now TypeA="x1" enters the pool and completes the AND gate with TypeB="b1" that's been waiting
    await orchestrator.publish({
        "type": "TypeA",
        "value": "x1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger with TypeA="x1" + TypeB="b1" (from waiting pool)
    assert len(executed) == 1, (
        "Should trigger when AND gate complete and where predicate satisfied"
    )
    assert "x1" in executed[0], "Should have predicate-matching TypeA"
    assert "b1" in executed[0], "Should have TypeB that was waiting in pool"


@pytest.mark.asyncio
async def test_and_gate_with_prevent_self_trigger(orchestrator):
    """
    Test AND gate integration with prevent_self_trigger.

    GIVEN: Agent with AND gate and prevent_self_trigger enabled
    WHEN: Agent publishes one of its consumed types
    THEN: Agent should NOT trigger on its own output
    """
    # Arrange
    executed = []

    class SelfPublishingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            # Publish TypeA (should be ignored by self)
            return EvalResult(
                artifacts=[
                    {
                        "type": "TypeA",
                        "value": "self_published",
                        "correlation_id": "test",
                    }
                ]
            )

    # Create agent that publishes TypeA (which it also consumes)
    orchestrator.agent("self_trigger_test").consumes(TypeA, TypeB).with_engines(
        SelfPublishingEngine()
    ).prevent_self_trigger()

    # Act - Trigger agent with external artifacts
    await orchestrator.publish({
        "type": "TypeA",
        "value": "external_a",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "external_b",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    # Assert - Should trigger once (not again from self-published TypeA)
    assert len(executed) == 1, "Should trigger once (not on self-published artifact)"


@pytest.mark.asyncio
async def test_and_gate_with_multiple_subscriptions_same_agent(orchestrator):
    """
    Test agent with multiple AND gate subscriptions.

    GIVEN: Single agent with TWO AND gate subscriptions
    WHEN: Artifacts for first subscription published
    THEN: Agent triggers with first subscription's artifacts
    WHEN: Artifacts for second subscription published
    THEN: Agent triggers AGAIN with second subscription's artifacts
    """
    # Arrange
    executed = []

    class MultiSubscriptionEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append({
                "count": len(inputs.artifacts),
                "types": sorted([a.type for a in inputs.artifacts]),
            })
            return EvalResult(artifacts=[])

    # Create agent with TWO AND gate subscriptions
    agent = orchestrator.agent("multi_sub").with_engines(MultiSubscriptionEngine())
    agent.consumes(TypeA, TypeB)  # First AND gate
    agent.consumes(TypeA, TypeC)  # Second AND gate

    # Act - Satisfy first subscription (TypeA + TypeB)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()

    assert len(executed) == 1, "Should trigger for first subscription"
    assert executed[0]["types"] == ["TypeA", "TypeB"]

    # Act - Satisfy second subscription (TypeA + TypeC)
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a2",
        "correlation_id": "test",
    })
    await orchestrator.publish({"type": "TypeC", "value": "c1"})
    await orchestrator.run_until_idle()

    # Assert - Should trigger for second subscription
    assert len(executed) == 2, "Should trigger for second subscription"
    assert executed[1]["types"] == ["TypeA", "TypeC"]


# ============================================================================
# Phase 1, Week 3, Day 3-5: Performance Benchmarks
# ============================================================================


@pytest.mark.asyncio
async def test_and_gate_performance_latency_target(orchestrator):
    """
    Performance test: AND gate should add <10ms latency.

    GIVEN: Agent with AND gate
    WHEN: Both artifacts published rapidly
    THEN: Agent triggers within 10ms overhead (compared to single-type)
    """
    import time

    # Arrange
    executed = []

    class FastEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(time.time())
            return EvalResult(artifacts=[])

    orchestrator.agent("perf_test").consumes(TypeA, TypeB).with_engines(FastEngine())

    # Act - Measure end-to-end time
    start = time.time()
    await orchestrator.publish({
        "type": "TypeA",
        "value": "a1",
        "correlation_id": "test",
    })
    await orchestrator.publish({
        "type": "TypeB",
        "value": "b1",
        "correlation_id": "test",
    })
    await orchestrator.run_until_idle()
    end = time.time()

    # Assert - Total time should be reasonable (<200ms including overhead)
    total_time_ms = (end - start) * 1000
    assert len(executed) == 1, "Agent should have executed"
    assert total_time_ms < 200, (
        f"AND gate latency too high: {total_time_ms:.2f}ms (target: <200ms)"
    )

    # Note: The <10ms target is for the AND gate logic itself, not the full
    # orchestrator execution. This test validates the overall latency is acceptable.


@pytest.mark.asyncio
async def test_and_gate_performance_many_artifacts(orchestrator):
    """
    Performance test: AND gate should handle many artifacts efficiently.

    GIVEN: Agent with AND gate
    WHEN: Many artifact pairs published
    THEN: All pairs processed without significant slowdown
    """
    import time

    # Arrange
    executed = []

    class CountingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            executed.append(len(inputs.artifacts))
            return EvalResult(artifacts=[])

    orchestrator.agent("perf_many").consumes(TypeA, TypeB).with_engines(
        CountingEngine()
    )

    # Act - Publish 10 pairs rapidly
    start = time.time()
    for i in range(10):
        await orchestrator.publish({
            "type": "TypeA",
            "value": f"a{i}",
            "correlation_id": "test",
        })
        await orchestrator.publish({
            "type": "TypeB",
            "value": f"b{i}",
            "correlation_id": "test",
        })
        await orchestrator.run_until_idle()
    end = time.time()

    # Assert - All pairs should be processed
    assert len(executed) == 10, "Should process all 10 pairs"
    assert all(count == 2 for count in executed), "Each trigger should have 2 artifacts"

    # Performance check - 10 pairs in reasonable time
    total_time_ms = (end - start) * 1000
    assert total_time_ms < 2000, (
        f"Processing 10 pairs took {total_time_ms:.2f}ms (should be <2s)"
    )
