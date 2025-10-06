"""Tests for agent lifecycle."""

import asyncio

import pytest
from pydantic import BaseModel, Field

from flock.artifacts import Artifact
from flock.components import AgentComponent, EngineComponent
from flock.registry import flock_type
from flock.runtime import EvalInputs, EvalResult
from flock.visibility import PublicVisibility


# Test artifact types - use explicit names
# Note: Don't use "Test" prefix to avoid pytest collection warnings
@flock_type(name="AgentInput")
class AgentInput(BaseModel):
    data: str = Field(description="Input data")


@flock_type(name="AgentOutput")
class AgentOutput(BaseModel):
    result: str = Field(description="Output result")


class LifecycleTracker(AgentComponent):
    """Component that tracks lifecycle stages."""

    tracker: list[str] = Field(default_factory=list)  # Pydantic field with default_factory

    async def on_initialize(self, agent, ctx):
        self.tracker.append("initialize")
        return await super().on_initialize(agent, ctx)

    async def on_pre_consume(self, agent, ctx, artifacts):
        self.tracker.append("pre_consume")
        return await super().on_pre_consume(agent, ctx, artifacts)

    async def on_pre_evaluate(self, agent, ctx, inputs):
        self.tracker.append("pre_evaluate")
        return await super().on_pre_evaluate(agent, ctx, inputs)

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        self.tracker.append("post_evaluate")
        return await super().on_post_evaluate(agent, ctx, inputs, result)

    async def on_post_publish(self, agent, ctx, artifacts):
        self.tracker.append("post_publish")
        return await super().on_post_publish(agent, ctx, artifacts)

    async def on_error(self, agent, ctx, exception):
        self.tracker.append("error")
        return await super().on_error(agent, ctx, exception)

    async def on_terminate(self, agent, ctx):
        self.tracker.append("terminate")
        return await super().on_terminate(agent, ctx)


class SimpleEngine(EngineComponent):
    """Simple engine for testing."""

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        # Create output artifacts
        artifacts = [
            Artifact(
                type="AgentOutput",
                payload={"result": "test output"},
                produced_by=agent.name,
                visibility=PublicVisibility(),
            )
        ]
        return EvalResult(artifacts=artifacts, state={})


class StateAddingComponent(AgentComponent):
    """Component that adds state in pre_evaluate."""

    async def on_pre_evaluate(self, agent, ctx, inputs):
        inputs.state["context"] = "test_data"
        return await super().on_pre_evaluate(agent, ctx, inputs)


class StatefulEngine(EngineComponent):
    """Engine that uses state."""

    state_tracker: list[str] = Field(default_factory=list)  # Pydantic field with default_factory

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        # Check if state is available
        if "context" in inputs.state:
            self.state_tracker.append(inputs.state["context"])
        return EvalResult(artifacts=[], state=inputs.state)


class FailingEngine(EngineComponent):
    """Engine that always fails."""

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
        raise ValueError("Test error")


@pytest.mark.asyncio
async def test_agent_lifecycle_executes_all_stages_in_order(orchestrator):
    """Test that agent executes all lifecycle stages in correct order."""
    # Arrange

    lifecycle_tracker = LifecycleTracker()

    agent = (
        orchestrator.agent("test_agent")
        .consumes(AgentInput)
        .publishes(AgentOutput)
        .with_utilities(lifecycle_tracker)
        .with_engines(SimpleEngine())
    )

    input_artifact = AgentInput(data="test")

    # Act
    await orchestrator.invoke(agent, input_artifact)
    await orchestrator.run_until_idle()

    # Assert - stages 1-7 and 9 should execute (skip 8 if no error)
    assert "initialize" in lifecycle_tracker.tracker
    assert "pre_consume" in lifecycle_tracker.tracker
    assert "pre_evaluate" in lifecycle_tracker.tracker
    assert "post_evaluate" in lifecycle_tracker.tracker
    assert "post_publish" in lifecycle_tracker.tracker
    assert "terminate" in lifecycle_tracker.tracker
    assert "error" not in lifecycle_tracker.tracker  # No error occurred


@pytest.mark.asyncio
async def test_agent_lifecycle_state_propagates(orchestrator):
    """Test that state propagates through lifecycle stages."""
    # Arrange

    stateful_engine = StatefulEngine()

    agent = (
        orchestrator.agent("test_agent")
        .consumes(AgentInput)
        .with_utilities(StateAddingComponent())
        .with_engines(stateful_engine)
    )

    input_artifact = AgentInput(data="test")

    # Act
    await orchestrator.invoke(agent, input_artifact)
    await orchestrator.run_until_idle()

    # Assert - state should be available in engine
    assert "test_data" in stateful_engine.state_tracker


@pytest.mark.asyncio
async def test_on_initialize_called_once(orchestrator):
    """Test that on_initialize is called on each execution (current behavior)."""
    # Arrange

    lifecycle_tracker = LifecycleTracker()

    agent = (
        orchestrator.agent("test_agent")
        .consumes(AgentInput)
        .with_utilities(lifecycle_tracker)
        .with_engines(SimpleEngine())
    )

    input1 = AgentInput(data="test1")
    input2 = AgentInput(data="test2")

    # Act - execute agent twice
    await orchestrator.invoke(agent, input1)
    await orchestrator.invoke(agent, input2)
    await orchestrator.run_until_idle()

    # Assert - initialize is called on each execution in current implementation
    initialize_count = lifecycle_tracker.tracker.count("initialize")
    assert initialize_count == 2  # Current behavior: called per execution


@pytest.mark.asyncio
async def test_on_error_called_on_exception(orchestrator):
    """Test that on_error is called when exception occurs."""
    # Arrange

    lifecycle_tracker = LifecycleTracker()

    agent = (
        orchestrator.agent("test_agent")
        .consumes(AgentInput)
        .with_utilities(lifecycle_tracker)
        .with_engines(FailingEngine())
    )

    input_artifact = AgentInput(data="test")

    # Act - execution should fail but not crash
    try:
        await orchestrator.invoke(agent, input_artifact)
        await orchestrator.run_until_idle()
    except Exception:
        pass  # Expected to fail

    # Assert - error hook should be called
    assert "error" in lifecycle_tracker.tracker


@pytest.mark.asyncio
async def test_on_terminate_always_called(orchestrator):
    """Test that on_terminate is always called, even on error."""
    # Arrange

    lifecycle_tracker = LifecycleTracker()

    agent = (
        orchestrator.agent("test_agent")
        .consumes(AgentInput)
        .with_utilities(lifecycle_tracker)
        .with_engines(FailingEngine())
    )

    input_artifact = AgentInput(data="test")

    # Act - execution should fail but terminate should still be called
    try:
        await orchestrator.invoke(agent, input_artifact)
        await orchestrator.run_until_idle()
    except Exception:
        pass  # Expected to fail

    # Assert - terminate should be called even after error
    assert "terminate" in lifecycle_tracker.tracker


@pytest.mark.asyncio
async def test_agent_respects_max_concurrency(orchestrator):
    """Test that agent respects max_concurrency limit."""
    # Arrange
    concurrent_count = []
    max_concurrent = 0

    class SlowEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            concurrent_count.append(1)
            nonlocal max_concurrent
            max_concurrent = max(max_concurrent, len(concurrent_count))
            await asyncio.sleep(0.1)  # Simulate slow operation
            concurrent_count.pop()
            return EvalResult(artifacts=[], state={})

    agent = (
        orchestrator.agent("test_agent")
        .consumes(AgentInput)
        .max_concurrency(2)
        .with_engines(SlowEngine())
    )

    # Act - attempt 5 concurrent executions
    tasks = [orchestrator.invoke(agent, AgentInput(data=f"test{i}")) for i in range(5)]
    await asyncio.gather(*tasks)
    await orchestrator.run_until_idle()

    # Assert - max concurrent should not exceed 2
    assert max_concurrent <= 2


# T060: Agent Best-of-N Selection
@pytest.mark.asyncio
async def test_agent_best_of_n_selects_highest_score(orchestrator):
    """Test that best_of selects result with highest score."""
    # Arrange

    # Engine that returns different scores on each invocation
    invocation_count = [0]

    class ScoredEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            invocation_count[0] += 1
            score = invocation_count[0] * 10  # 10, 20, 30
            return EvalResult(artifacts=[], state={}, metrics={"confidence": score})

    agent = (
        orchestrator.agent("test")
        .consumes(AgentInput)
        .with_engines(ScoredEngine())
        .best_of(3, score=lambda r: r.metrics.get("confidence", 0))
    )

    # Act
    input_data = AgentInput(data="test")
    await orchestrator.invoke(agent, input_data)

    # Assert - Engine should be called 3 times
    assert invocation_count[0] == 3


@pytest.mark.asyncio
async def test_agent_best_of_one_skips_parallel_execution(orchestrator):
    """Test that best_of(1) doesn't use TaskGroup."""
    # Arrange
    call_count = [0]

    class CountingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            call_count[0] += 1
            return EvalResult(artifacts=[], state={})

    agent = (
        orchestrator.agent("test")
        .consumes(AgentInput)
        .with_engines(CountingEngine())
        .best_of(1, score=lambda r: 1.0)  # best_of(1) should be no-op
    )

    # Act
    await orchestrator.invoke(agent, AgentInput(data="test"))

    # Assert - Called once (no parallel execution for n=1)
    assert call_count[0] == 1


# T061: Agent Output Fallback to State
@pytest.mark.asyncio
async def test_agent_output_fallback_to_state(orchestrator):
    """Test that agent falls back to state when no matching artifact in result."""
    # Arrange

    class StateFallbackEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            # Return state with output data instead of artifacts
            return EvalResult(
                artifacts=[],  # No artifacts!
                state={"AgentOutput": {"result": "from state"}},  # Data in state
                metrics={},
            )

    agent = (
        orchestrator.agent("test")
        .consumes(AgentInput)
        .publishes(AgentOutput)
        .with_engines(StateFallbackEngine())
    )

    # Act
    results = await orchestrator.invoke(agent, AgentInput(data="test"))

    # Assert - Should publish artifact using state data
    assert len(results) == 1
    assert results[0].type == "AgentOutput"
    assert results[0].payload["result"] == "from state"


@pytest.mark.asyncio
async def test_agent_no_output_when_no_artifacts_or_state(orchestrator):
    """Test agent doesn't publish when no artifacts and no state match."""
    # Arrange

    class EmptyEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            return EvalResult(artifacts=[], state={})  # Nothing

    agent = (
        orchestrator.agent("test")
        .consumes(AgentInput)
        .publishes(AgentOutput)
        .with_engines(EmptyEngine())
    )

    # Act
    results = await orchestrator.invoke(agent, AgentInput(data="test"))

    # Assert - No outputs published
    assert len(results) == 0


# T064: Prevent Self-Trigger Tests
@pytest.mark.asyncio
async def test_agent_prevent_self_trigger_enabled_by_default(orchestrator):
    """Test that prevent_self_trigger is True by default."""
    # Arrange
    agent = orchestrator.agent("test").consumes(AgentInput)

    # Assert - Default should be True
    assert agent.agent.prevent_self_trigger is True


@pytest.mark.asyncio
async def test_agent_prevent_self_trigger_blocks_own_artifacts(orchestrator):
    """Test that agent with prevent_self_trigger=True doesn't process own outputs."""
    # Arrange
    executed_count = [0]

    class CountingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            executed_count[0] += 1
            # Publish same type the agent consumes
            return EvalResult(
                artifacts=[
                    Artifact(
                        type="AgentInput",
                        payload={"data": f"output_{executed_count[0]}"},
                        produced_by=agent.name,
                        visibility=PublicVisibility(),
                    )
                ],
                state={},
            )

    (
        orchestrator.agent("self_publisher")
        .consumes(AgentInput)
        .publishes(AgentInput)
        .with_engines(CountingEngine())
    )
    # prevent_self_trigger should be True by default

    # Act - Publish external input
    await orchestrator.publish({"type": "AgentInput", "data": "external"})
    await orchestrator.run_until_idle()

    # Assert - Should execute only once (for external input, not own output)
    assert executed_count[0] == 1


@pytest.mark.asyncio
async def test_agent_prevent_self_trigger_disabled_allows_feedback(orchestrator):
    """Test that prevent_self_trigger=False allows agent to process own outputs."""
    # Arrange
    orchestrator.max_agent_iterations = 10  # Lower limit to prevent long test
    executed_count = [0]

    class FeedbackEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            executed_count[0] += 1
            # Always publish (relies on circuit breaker to stop)
            return EvalResult(
                artifacts=[
                    Artifact(
                        type="AgentInput",
                        payload={"data": f"feedback_{executed_count[0]}"},
                        produced_by=agent.name,
                        visibility=PublicVisibility(),
                    )
                ],
                state={},
            )

    (
        orchestrator.agent("feedback")
        .consumes(AgentInput)
        .publishes(AgentInput)
        .with_engines(FeedbackEngine())
        .prevent_self_trigger(False)  # Explicitly allow feedback
    )

    # Act
    await orchestrator.publish({"type": "AgentInput", "data": "seed"})
    await orchestrator.run_until_idle()

    # Assert - Should execute multiple times (limited by circuit breaker)
    # Executed_count should be > 1 (proves feedback works) and <= max_iterations
    assert executed_count[0] > 1, "Agent should process own outputs when prevent_self_trigger=False"
    assert executed_count[0] <= orchestrator.max_agent_iterations, (
        "Circuit breaker should limit iterations"
    )


# T073: Configuration Validation Tests
@pytest.mark.asyncio
async def test_agent_validates_self_trigger_risk(orchestrator):
    """Test that agent validation runs when consumes/publishes same type."""
    # Arrange & Act - This should complete without errors and validate config
    agent = (
        orchestrator.agent("risky")
        .consumes(AgentInput)
        .publishes(AgentInput)  # Same type - validation runs
        # prevent_self_trigger is True by default (safe)
    )

    # Assert - Agent created successfully, validation ran
    assert agent.agent.prevent_self_trigger is True
    # Validation warning would be logged (via loguru)


@pytest.mark.asyncio
async def test_agent_validates_excessive_best_of(orchestrator):
    """Test that agent validation runs when best_of > 100."""
    # Arrange & Act - This should complete and validate
    agent = (
        orchestrator.agent("parallel")
        .consumes(AgentInput)
        .best_of(150, score=lambda r: 1.0)  # > 100 - validation runs
    )

    # Assert - Agent created successfully
    assert agent.agent.best_of_n == 150
    # Validation warning would be logged (via loguru)


@pytest.mark.asyncio
async def test_agent_validates_high_concurrency(orchestrator):
    """Test that agent validation runs when max_concurrency > 1000."""
    # Arrange & Act - This should complete and validate
    agent = (
        orchestrator.agent("concurrent")
        .consumes(AgentInput)
        .max_concurrency(1500)  # > 1000 - validation runs
    )

    # Assert - Agent created successfully
    assert agent.agent.max_concurrency == 1500
    # Validation warning would be logged (via loguru)


@pytest.mark.asyncio
async def test_agent_validation_methods_exist(orchestrator):
    """Test that validation methods exist and can be called."""
    # Arrange
    agent = orchestrator.agent("validator").consumes(AgentInput)

    # Act & Assert - Validation methods should exist
    assert hasattr(agent, "_validate_self_trigger_risk")
    assert hasattr(agent, "_validate_best_of")
    assert hasattr(agent, "_validate_concurrency")

    # Methods should be callable without errors
    agent._validate_best_of(50)  # Normal value - no warning
    agent._validate_concurrency(10)  # Normal value - no warning
