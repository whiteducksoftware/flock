"""Tests for Phase 4: Engine Fan-Out Contract.

These tests verify that engines can opt-in to fan-out support by implementing
the evaluate_fanout() method, following the same pattern as evaluate_batch().

Phase 4 Requirements (from PLAN.md lines 211-219):
1. EngineComponent.evaluate_fanout() raises NotImplementedError by default
2. Error message includes helpful guidance (like evaluate_batch does)
3. Engine that implements evaluate_fanout() is called correctly
4. Agent.execute() detects fan-out scenario and calls appropriate method
5. Agent.execute() falls back to evaluate() if engine doesn't support fan-out
6. Test error when fan-out requested but engine doesn't support it
7. Mock fan-out-aware engine that returns exactly `count` artifacts
8. Test that group_description is passed to evaluate_fanout()
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field, PrivateAttr

from flock import Flock
from flock.agent import AgentOutput, OutputGroup
from flock.artifacts import Artifact, ArtifactSpec
from flock.components import AgentComponent, EngineComponent
from flock.registry import flock_type
from flock.runtime import Context, EvalInputs, EvalResult
from flock.visibility import PublicVisibility


# Test artifact types
@flock_type(name="TaskArtifact")
class TaskArtifact(BaseModel):
    task_id: int = Field(description="Task identifier")
    description: str = Field(description="Task description")


@flock_type(name="ResultArtifact")
class ResultArtifact(BaseModel):
    result_value: int = Field(description="Result value")


# No-op utility for tests
class NoOpUtility(AgentComponent):
    """Silent utility that does nothing - bypasses default console output."""
    pass


# Mock board for tests
class MockBoard:
    """Mock blackboard that collects published artifacts without side effects."""
    def __init__(self):
        self.published: list[Artifact] = []

    async def publish(self, artifact: Artifact) -> None:
        """Record published artifacts."""
        self.published.append(artifact)

    async def list(self) -> list[Artifact]:
        """Return published artifacts (for context fetching)."""
        return self.published


# ============================================================================
# Test Scenario 1: Base EngineComponent raises NotImplementedError
# ============================================================================


@pytest.mark.asyncio
async def test_base_engine_evaluate_fanout_raises_not_implemented():
    """EngineComponent.evaluate_fanout() should raise NotImplementedError by default."""
    # Arrange
    engine = EngineComponent()
    flock = Flock()

    agent = flock.agent("test").publishes(TaskArtifact)
    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    inputs = EvalInputs(artifacts=[], state={})

    # Create OutputGroup for fan-out
    spec = ArtifactSpec.from_model(TaskArtifact)
    agent_output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=3
    )
    output_group = OutputGroup(
        outputs=[agent_output],
        group_description="Generate 3 tasks"
    )

    # Act & Assert
    with pytest.raises(NotImplementedError) as exc_info:
        await engine.evaluate_fanout(
            agent=agent.agent,
            ctx=ctx,
            inputs=inputs,
            output_group=output_group
        )

    # Error message should be helpful (like evaluate_batch)
    error_msg = str(exc_info.value)
    assert "EngineComponent" in error_msg
    assert "does not support fan-out" in error_msg
    assert "count: 3" in error_msg or "Requested count: 3" in error_msg  # Should show requested count


@pytest.mark.asyncio
async def test_engine_fanout_error_message_includes_helpful_guidance():
    """Error message should include multi-step guidance like evaluate_batch()."""
    # Arrange
    engine = EngineComponent()
    flock = Flock()

    agent = flock.agent("my_agent").publishes(TaskArtifact, fan_out=5)
    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    inputs = EvalInputs(artifacts=[], state={})

    # Create OutputGroup
    spec = ArtifactSpec.from_model(TaskArtifact)
    agent_output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=5
    )
    output_group = OutputGroup(
        outputs=[agent_output],
        group_description=None
    )

    # Act & Assert
    with pytest.raises(NotImplementedError) as exc_info:
        await engine.evaluate_fanout(
            agent=agent.agent,
            ctx=ctx,
            inputs=inputs,
            output_group=output_group
        )

    error_msg = str(exc_info.value)

    # Should include helpful multi-step guidance
    assert "To fix this:" in error_msg
    assert "1." in error_msg  # Multi-step guidance
    assert "2." in error_msg
    assert "3." in error_msg
    assert "Remove fan_out parameter" in error_msg or "remove fan_out" in error_msg
    assert "Implement evaluate_fanout()" in error_msg
    assert "Agent: my_agent" in error_msg
    assert "count: 5" in error_msg or "Requested count: 5" in error_msg


# ============================================================================
# Test Scenario 2: Mock Fan-Out-Aware Engine
# ============================================================================


class MockFanOutEngine(EngineComponent):
    """Mock engine that supports fan-out generation.

    Inspects output_group parameter to know exactly what to produce.
    No shared state, fully thread-safe!
    """

    _call_count: int = PrivateAttr(default=0)
    _fanout_call_count: int = PrivateAttr(default=0)
    _last_output_group: Any = PrivateAttr(default=None)

    def __init__(self):
        super().__init__()
        self._call_count = 0
        self._fanout_call_count = 0
        self._last_output_group = None

    @property
    def call_count(self) -> int:
        """Total evaluate() calls."""
        return self._call_count

    @property
    def fanout_call_count(self) -> int:
        """Total evaluate_fanout() calls."""
        return self._fanout_call_count

    @property
    def last_count(self) -> int | None:
        """Last count requested in evaluate_fanout()."""
        if self._last_output_group and self._last_output_group.outputs:
            return self._last_output_group.outputs[0].count
        return None

    @property
    def last_description(self) -> str | None:
        """Last group_description passed to evaluate_fanout()."""
        if self._last_output_group:
            return self._last_output_group.group_description
        return None

    async def evaluate(self, agent, ctx: Context, inputs: EvalInputs, output_group) -> EvalResult:
        """Standard evaluate - returns single artifact of first expected type.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce
        """
        self._call_count += 1

        # Use output_group to determine what to produce
        if output_group.outputs:
            type_name = output_group.outputs[0].spec.type_name
            if 'Result' in type_name:
                artifact = ResultArtifact(result_value=1)
                return EvalResult.from_objects(artifact, agent=agent)

        # Default to TaskArtifact
        artifact = TaskArtifact(task_id=1, description="Single task")
        return EvalResult.from_objects(artifact, agent=agent)

    async def evaluate_fanout(
        self,
        agent,
        ctx: Context,
        inputs: EvalInputs,
        output_group,  # OutputGroup parameter!
    ) -> EvalResult:
        """Fan-out evaluate - inspects output_group to know what to produce."""
        self._fanout_call_count += 1
        self._last_output_group = output_group

        # Extract info from output_group
        if not output_group.outputs:
            return EvalResult(artifacts=[], state={})

        first_output = output_group.outputs[0]
        count = first_output.count
        type_name = first_output.spec.type_name

        # Generate exactly `count` artifacts of the correct type
        if 'Result' in type_name:
            artifacts = [
                ResultArtifact(result_value=i)
                for i in range(1, count + 1)
            ]
        else:
            artifacts = [
                TaskArtifact(task_id=i, description=f"Task {i}")
                for i in range(1, count + 1)
            ]

        return EvalResult.from_objects(*artifacts, agent=agent)


@pytest.mark.asyncio
async def test_fanout_aware_engine_returns_correct_count():
    """Engine implementing evaluate_fanout() should return exactly `count` artifacts."""
    # Arrange
    mock_engine = MockFanOutEngine()

    # Simulate direct engine call (not through agent yet)
    flock = Flock()
    agent = flock.agent("test").publishes(TaskArtifact, fan_out=5)
    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    inputs = EvalInputs(artifacts=[], state={})

    # Create OutputGroup
    spec = ArtifactSpec.from_model(TaskArtifact)
    agent_output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=5
    )
    output_group = OutputGroup(
        outputs=[agent_output],
        group_description="Generate 5 tasks"
    )

    # Act
    result = await mock_engine.evaluate_fanout(
        agent=agent.agent,
        ctx=ctx,
        inputs=inputs,
        output_group=output_group
    )

    # Assert
    assert len(result.artifacts) == 5, "Should return exactly 5 artifacts"
    assert mock_engine.fanout_call_count == 1
    assert mock_engine.last_count == 5
    assert mock_engine.last_description == "Generate 5 tasks"


@pytest.mark.asyncio
async def test_fanout_engine_receives_group_description():
    """evaluate_fanout() should receive group_description parameter."""
    # Arrange
    mock_engine = MockFanOutEngine()
    flock = Flock()

    agent = flock.agent("test").publishes(TaskArtifact, fan_out=3)
    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    inputs = EvalInputs(artifacts=[], state={})

    custom_description = "Generate high-quality diverse tasks"

    # Create OutputGroup
    spec = ArtifactSpec.from_model(TaskArtifact)
    agent_output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=3
    )
    output_group = OutputGroup(
        outputs=[agent_output],
        group_description=custom_description
    )

    # Act
    await mock_engine.evaluate_fanout(
        agent=agent.agent,
        ctx=ctx,
        inputs=inputs,
        output_group=output_group
    )

    # Assert - group_description should be passed through
    assert mock_engine.last_description == custom_description


# ============================================================================
# Test Scenario 3: Agent.execute() Fan-Out Detection
# ============================================================================


@pytest.mark.asyncio
async def test_agent_detects_fanout_and_calls_evaluate_fanout():
    """Agent.execute() should detect fan-out scenario and call evaluate_fanout()."""
    # Arrange
    flock = Flock()
    mock_engine = MockFanOutEngine()

    agent = (
        flock.agent("fanout_test")
        .consumes(TaskArtifact)
        .publishes(ResultArtifact, fan_out=4, description="Generate 4 results")
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TaskArtifact",
            payload=TaskArtifact(task_id=1, description="Input").model_dump(),
            produced_by="test"
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert - evaluate_fanout() should have been called, not evaluate()
    assert mock_engine.fanout_call_count == 1, "Should call evaluate_fanout()"
    assert mock_engine.call_count == 0, "Should NOT call evaluate()"
    assert mock_engine.last_count == 4
    assert mock_engine.last_description == "Generate 4 results"

    # Should have 4 output artifacts
    assert len(outputs) >= 4, f"Expected 4+ outputs, got {len(outputs)}"


@pytest.mark.asyncio
async def test_agent_without_fanout_calls_standard_evaluate():
    """Agent without fan_out should call standard evaluate(), not evaluate_fanout()."""
    # Arrange
    flock = Flock()
    mock_engine = MockFanOutEngine()

    agent = (
        flock.agent("standard_test")
        .consumes(TaskArtifact)
        .publishes(ResultArtifact)  # No fan_out parameter
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TaskArtifact",
            payload=TaskArtifact(task_id=1, description="Input").model_dump(),
            produced_by="test"
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert - evaluate() should be called, not evaluate_fanout()
    assert mock_engine.call_count == 1, "Should call evaluate()"
    assert mock_engine.fanout_call_count == 0, "Should NOT call evaluate_fanout()"


# ============================================================================
# Test Scenario 4: Engine Doesn't Support Fan-Out
# ============================================================================


class BasicEngine(EngineComponent):
    """Basic engine that doesn't implement evaluate_fanout()."""

    async def evaluate(self, agent, ctx: Context, inputs: EvalInputs, output_group) -> EvalResult:
        """Standard evaluate implementation.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce
        """
        artifact = TaskArtifact(task_id=1, description="Task from basic engine")
        return EvalResult.from_objects(artifact, agent=agent)


@pytest.mark.asyncio
async def test_error_when_fanout_requested_but_engine_unsupported():
    """Agent with fan_out should raise clear error if engine doesn't support it."""
    # Arrange
    flock = Flock()
    basic_engine = BasicEngine()

    agent = (
        flock.agent("needs_fanout")
        .consumes(TaskArtifact)
        .publishes(ResultArtifact, fan_out=3)  # Requires fan-out
        .with_engines(basic_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TaskArtifact",
            payload=TaskArtifact(task_id=1, description="Input").model_dump(),
            produced_by="test"
        )
    ]

    # Act & Assert - Should raise helpful error
    with pytest.raises((NotImplementedError, ValueError)) as exc_info:
        await agent.agent.execute(ctx, input_artifacts)

    error_msg = str(exc_info.value)

    # Error should mention engine doesn't support fan-out
    assert any(term in error_msg for term in [
        "fan-out", "fan_out", "BasicEngine", "does not support"
    ])


# ============================================================================
# Test Scenario 5: Multiple Groups with Mixed Fan-Out
# ============================================================================


@pytest.mark.asyncio
async def test_mixed_fanout_and_standard_groups():
    """Agent with both fan-out and standard groups should call appropriate methods."""
    # Arrange
    flock = Flock()
    mock_engine = MockFanOutEngine()

    agent = (
        flock.agent("mixed")
        .consumes(TaskArtifact)
        .publishes(TaskArtifact, fan_out=3)  # Group 1: fan-out
        .publishes(ResultArtifact)           # Group 2: standard
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TaskArtifact",
            payload=TaskArtifact(task_id=1, description="Input").model_dump(),
            produced_by="test"
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert
    # Group 1 should call evaluate_fanout()
    assert mock_engine.fanout_call_count >= 1, "Should call evaluate_fanout() for group 1"

    # Group 2 should call evaluate()
    assert mock_engine.call_count >= 1, "Should call evaluate() for group 2"


# ============================================================================
# Test Scenario 6: Fan-Out with Single Type Validation
# ============================================================================


@pytest.mark.asyncio
async def test_fanout_only_for_single_type_groups():
    """Fan-out should only apply to groups with a single type repeated."""
    # Arrange
    flock = Flock()
    mock_engine = MockFanOutEngine()

    # This should use fan-out (single type, count > 1)
    agent1 = (
        flock.agent("single_type")
        .consumes(TaskArtifact)
        .publishes(ResultArtifact, fan_out=3)
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TaskArtifact",
            payload=TaskArtifact(task_id=1, description="Input").model_dump(),
            produced_by="test"
        )
    ]

    # Act
    await agent1.agent.execute(ctx, input_artifacts)

    # Assert - Should use evaluate_fanout() for single type
    assert mock_engine.fanout_call_count > 0, "Single type with fan_out should use evaluate_fanout()"


# ============================================================================
# Test Scenario 7: Contract Validation
# ============================================================================


class StrictFanOutEngine(EngineComponent):
    """Engine that validates contract - must return exactly `count` artifacts."""

    async def evaluate(self, agent, ctx: Context, inputs: EvalInputs, output_group) -> EvalResult:
        """Standard evaluate implementation.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce
        """
        artifact = TaskArtifact(task_id=1, description="Task")
        return EvalResult.from_objects(artifact, agent=agent)

    async def evaluate_fanout(
        self,
        agent,
        ctx: Context,
        inputs: EvalInputs,
        output_group,
    ) -> EvalResult:
        """Strict implementation that validates count.

        Args:
            agent: Agent instance
            ctx: Execution context
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce
        """
        # Extract count from output_group
        if not output_group.outputs:
            return EvalResult(artifacts=[], state={})

        count = output_group.outputs[0].count

        # Generate exactly `count` artifacts (contract fulfilled)
        artifacts = [
            TaskArtifact(task_id=i, description=f"Task {i}")
            for i in range(count)
        ]

        result = EvalResult.from_objects(*artifacts, agent=agent)

        # Self-validation (optional - framework should also validate)
        if len(result.artifacts) != count:
            raise ValueError(
                f"Contract violation: expected {count} artifacts, "
                f"generated {len(result.artifacts)}"
            )

        return result


@pytest.mark.asyncio
async def test_engine_fulfills_fanout_contract():
    """Engine that implements evaluate_fanout() should fulfill count contract."""
    # Arrange
    flock = Flock()
    strict_engine = StrictFanOutEngine()

    agent = (
        flock.agent("strict_test")
        .consumes(TaskArtifact)
        .publishes(TaskArtifact, fan_out=7)
        .with_engines(strict_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TaskArtifact",
            payload=TaskArtifact(task_id=1, description="Input").model_dump(),
            produced_by="test"
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert - Should generate exactly 7 artifacts (contract fulfilled)
    task_outputs = [a for a in outputs if a.type == "TaskArtifact"]
    assert len(task_outputs) == 7, f"Expected 7 artifacts, got {len(task_outputs)}"


# ============================================================================
# Test Scenario 8: Error Message Clarity
# ============================================================================


@pytest.mark.asyncio
async def test_error_message_includes_agent_and_engine_names():
    """Error message should include both agent and engine names for debugging."""
    # Arrange
    basic_engine = BasicEngine()
    flock = Flock()

    agent = flock.agent("my_special_agent").publishes(TaskArtifact, fan_out=5)
    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    inputs = EvalInputs(artifacts=[], state={})

    # Create OutputGroup
    spec = ArtifactSpec.from_model(TaskArtifact)
    agent_output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=5
    )
    output_group = OutputGroup(
        outputs=[agent_output],
        group_description=None
    )

    # Act & Assert
    with pytest.raises(NotImplementedError) as exc_info:
        await basic_engine.evaluate_fanout(
            agent=agent.agent,
            ctx=ctx,
            inputs=inputs,
            output_group=output_group
        )

    error_msg = str(exc_info.value)

    # Should include agent name for debugging
    assert "my_special_agent" in error_msg or "Agent:" in error_msg

    # Should include engine class name
    assert "BasicEngine" in error_msg
