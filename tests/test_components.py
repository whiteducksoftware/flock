"""Tests for component system."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from flock.components.agent import AgentComponent, AgentComponentConfig, EngineComponent
from flock.core import Flock, OutputGroup
from flock.core.artifacts import Artifact
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


# Test artifact types
@flock_type(name="ComponentInput")
class ComponentInput(BaseModel):
    data: str = Field(description="Input data")


@flock_type(name="ComponentOutput")
class ComponentOutput(BaseModel):
    result: str = Field(description="Output result")


class OrderTracker(AgentComponent):
    """Component that tracks execution order."""

    order: list[str] = Field(default_factory=list)
    label: str = Field(default="")

    async def on_pre_evaluate(self, agent, ctx, inputs):
        self.order.append(f"pre_evaluate_{self.label}")
        return await super().on_pre_evaluate(agent, ctx, inputs)


class SimpleTestEngine(EngineComponent):
    """Simple engine for testing."""

    async def evaluate(
        self, agent, ctx, inputs: EvalInputs, output_group
    ) -> EvalResult:
        return EvalResult(artifacts=[], state={})


@pytest.mark.asyncio
async def test_components_execute_in_registration_order():
    """Test that component hooks execute in registration order."""
    # Arrange
    orchestrator = Flock()

    shared_order = []

    class ComponentA(AgentComponent):
        async def on_pre_evaluate(self, agent, ctx, inputs):
            shared_order.append("A")
            return await super().on_pre_evaluate(agent, ctx, inputs)

    class ComponentB(AgentComponent):
        async def on_pre_evaluate(self, agent, ctx, inputs):
            shared_order.append("B")
            return await super().on_pre_evaluate(agent, ctx, inputs)

    class ComponentC(AgentComponent):
        async def on_pre_evaluate(self, agent, ctx, inputs):
            shared_order.append("C")
            return await super().on_pre_evaluate(agent, ctx, inputs)

    agent = (
        orchestrator.agent("test_agent")
        .consumes(ComponentInput)
        .with_utilities(ComponentA(), ComponentB(), ComponentC())
        .with_engines(SimpleTestEngine())
    )

    input_artifact = ComponentInput(data="test")

    # Act
    await orchestrator.invoke(agent, input_artifact, publish_outputs=False)

    # Assert - components should execute in order A -> B -> C
    assert shared_order == ["A", "B", "C"]


@pytest.mark.asyncio
async def test_component_priority_controls_execution_order():
    """Test that component priority overrides registration order."""
    orchestrator = Flock()

    execution_order = []

    class LateComponent(AgentComponent):
        priority: int = 50

        async def on_pre_evaluate(self, agent, ctx, inputs):
            execution_order.append("late")
            return await super().on_pre_evaluate(agent, ctx, inputs)

    class DefaultComponent(AgentComponent):
        priority: int = 0

        async def on_pre_evaluate(self, agent, ctx, inputs):
            execution_order.append("default")
            return await super().on_pre_evaluate(agent, ctx, inputs)

    class EarlyComponent(AgentComponent):
        priority: int = -10

        async def on_pre_evaluate(self, agent, ctx, inputs):
            execution_order.append("early")
            return await super().on_pre_evaluate(agent, ctx, inputs)

    agent = (
        orchestrator.agent("priority_agent")
        .consumes(ComponentInput)
        .with_utilities(LateComponent(), DefaultComponent(), EarlyComponent())
        .with_engines(SimpleTestEngine())
    )

    await orchestrator.invoke(agent, ComponentInput(data="test"), publish_outputs=False)

    assert execution_order == ["early", "default", "late"]


@pytest.mark.asyncio
async def test_component_adds_state_in_pre_evaluate():
    """Test that component can add state in pre_evaluate."""
    # Arrange
    orchestrator = Flock()

    state_captured = {}

    class StateAddingComponent(AgentComponent):
        async def on_pre_evaluate(self, agent, ctx, inputs):
            inputs.state["context"] = "added_data"
            inputs.state["counter"] = 42
            return await super().on_pre_evaluate(agent, ctx, inputs)

    class StateCapturingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            state_captured.update(inputs.state)
            return EvalResult(artifacts=[], state=inputs.state)

    agent = (
        orchestrator.agent("test_agent")
        .consumes(ComponentInput)
        .with_utilities(StateAddingComponent())
        .with_engines(StateCapturingEngine())
    )

    input_artifact = ComponentInput(data="test")

    # Act
    await orchestrator.invoke(agent, input_artifact)
    await orchestrator.run_until_idle()

    # Assert - state should be available in engine
    assert state_captured.get("context") == "added_data"
    assert state_captured.get("counter") == 42


@pytest.mark.asyncio
async def test_metrics_component_adds_metrics():
    """Test that metrics component adds metrics to result."""
    # Arrange
    orchestrator = Flock()

    metrics_result = {}

    class MetricsComponent(AgentComponent):
        async def on_post_evaluate(self, agent, ctx, inputs, result):
            result.metrics["latency_ms"] = 100
            result.metrics["tokens"] = 42
            result.metrics["confidence"] = 0.95
            # Store metrics for test verification
            metrics_result.update(result.metrics)
            return await super().on_post_evaluate(agent, ctx, inputs, result)

    class MetricsCapturingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            return EvalResult(artifacts=[], state={})

    agent = (
        orchestrator.agent("test_agent")
        .consumes(ComponentInput)
        .with_utilities(MetricsComponent())
        .with_engines(MetricsCapturingEngine())
    )

    input_artifact = ComponentInput(data="test")

    # Act
    await orchestrator.invoke(agent, input_artifact)
    await orchestrator.run_until_idle()

    # Assert - metrics should be added
    assert metrics_result.get("latency_ms") == 100
    assert metrics_result.get("tokens") == 42
    assert metrics_result.get("confidence") == 0.95


@pytest.mark.asyncio
async def test_component_on_error_hook_called():
    """Test that component's on_error hook is called on exception."""
    # Arrange
    orchestrator = Flock()

    error_caught = []

    class ErrorHandlingComponent(AgentComponent):
        async def on_error(self, agent, ctx, exception):
            error_caught.append(str(exception))
            return await super().on_error(agent, ctx, exception)

    class FailingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            raise ValueError("Test exception")

    agent = (
        orchestrator.agent("test_agent")
        .consumes(ComponentInput)
        .with_utilities(ErrorHandlingComponent())
        .with_engines(FailingEngine())
    )

    input_artifact = ComponentInput(data="test")

    # Act - execution should fail but on_error should be called
    try:
        await orchestrator.invoke(agent, input_artifact)
        await orchestrator.run_until_idle()
    except Exception:
        pass  # Expected to fail

    # Assert - on_error hook should have been called
    assert len(error_caught) > 0
    assert "Test exception" in error_caught[0]


@pytest.mark.asyncio
async def test_agent_component_config_with_fields():
    """Test AgentComponentConfig.with_fields() dynamic config creation."""
    # Create a new config class with additional fields
    CustomConfig = AgentComponentConfig.with_fields(
        temperature=(float, Field(default=0.7, description="LLM temperature")),
        max_tokens=(int, Field(default=1000, description="Max tokens to generate")),
        custom_flag=(bool, Field(default=True, description="Custom boolean flag")),
    )

    # Create an instance with default values
    config = CustomConfig()
    assert config.enabled is True  # Inherited from base class
    assert config.model is None  # Inherited from base class
    assert config.temperature == 0.7
    assert config.max_tokens == 1000
    assert config.custom_flag is True

    # Create an instance with custom values
    config2 = CustomConfig(
        enabled=False,
        model="gpt-4",
        temperature=0.9,
        max_tokens=2000,
        custom_flag=False,
    )
    assert config2.enabled is False
    assert config2.model == "gpt-4"
    assert config2.temperature == 0.9
    assert config2.max_tokens == 2000
    assert config2.custom_flag is False

    # Verify the class name contains "Dynamic"
    assert "Dynamic" in CustomConfig.__name__


@pytest.mark.asyncio
async def test_engine_component_get_conversation_context():
    """Test EngineComponent.get_conversation_context() method - Phase 8 pattern."""
    from flock.utils.runtime import Context

    # Phase 8: Context contains pre-filtered artifacts (evaluated by orchestrator)
    correlation_id = uuid4()

    pre_filtered_artifacts = [
        Artifact(
            id=uuid4(),
            type="user_message",
            payload={"message": "Hello"},
            produced_by="agent1",
            created_at=datetime.now(UTC),
        ),
        Artifact(
            id=uuid4(),
            type="assistant_response",
            payload={"message": "Hi there!"},
            produced_by="agent2",
            created_at=datetime.now(UTC),
        ),
    ]

    ctx = Context(
        artifacts=pre_filtered_artifacts,
        correlation_id=correlation_id,
        task_id="test-task",
    )

    # Phase 8: Engine simply reads pre-filtered context (returns Artifact objects)
    engine = EngineComponent()
    context = engine.get_conversation_context(ctx)

    # Should get pre-filtered Artifact objects with full metadata
    assert len(context) == 2
    assert context[0].type == "user_message"
    assert context[0].payload == {"message": "Hello"}
    assert context[0].produced_by == "agent1"
    assert context[1].type == "assistant_response"
    assert context[1].payload == {"message": "Hi there!"}
    assert context[1].produced_by == "agent2"


@pytest.mark.asyncio
async def test_engine_component_get_context_with_max_artifacts():
    """Test get_conversation_context with max_artifacts limit - Phase 8 pattern."""
    from flock.utils.runtime import Context

    # Phase 8: Context contains pre-filtered artifacts (10 artifacts from orchestrator)
    pre_filtered_artifacts = [
        Artifact(
            id=uuid4(),
            type=f"message_{i}",
            payload={"content": f"Content {i}"},
            produced_by=f"agent_{i}",
            created_at=datetime.now(UTC),
        )
        for i in range(10)
    ]

    ctx = Context(
        artifacts=pre_filtered_artifacts,
        correlation_id=uuid4(),
        task_id="test-task",
    )

    # Test with max_artifacts parameter (limits already-filtered list)
    engine = EngineComponent()
    context = engine.get_conversation_context(ctx, max_artifacts=3)

    assert len(context) == 3
    # Should get the last 3 artifacts
    assert context[0].type == "message_7"
    assert context[1].type == "message_8"
    assert context[2].type == "message_9"

    # Test with instance-level max_artifacts
    engine2 = EngineComponent(context_max_artifacts=5)
    context2 = engine2.get_conversation_context(ctx)

    assert len(context2) == 5
    # Should get the last 5 artifacts
    assert context2[0].type == "message_5"
    assert context2[4].type == "message_9"


@pytest.mark.asyncio
async def test_engine_component_get_context_with_exclude_types():
    """Test get_conversation_context with excluded types - Phase 8 pattern."""
    from flock.utils.runtime import Context

    # Phase 8: Context contains pre-filtered artifacts
    pre_filtered_artifacts = [
        Artifact(
            id=uuid4(),
            type="user_message",
            payload={"message": "Hello"},
            produced_by="agent1",
            created_at=datetime.now(UTC),
        ),
        Artifact(
            id=uuid4(),
            type="system_log",
            payload={"info": "System info"},
            produced_by="system",
            created_at=datetime.now(UTC),
        ),
        Artifact(
            id=uuid4(),
            type="assistant_response",
            payload={"message": "Hi there!"},
            produced_by="agent2",
            created_at=datetime.now(UTC),
        ),
    ]

    ctx = Context(
        artifacts=pre_filtered_artifacts,
        correlation_id=uuid4(),
        task_id="test-task",
    )

    # Test with excluded types (engine-level filtering)
    engine = EngineComponent(context_exclude_types={"system_log"})
    context = engine.get_conversation_context(ctx)

    assert len(context) == 2  # system_log should be excluded
    assert context[0].type == "user_message"
    assert context[1].type == "assistant_response"


@pytest.mark.asyncio
async def test_engine_component_get_context_disabled():
    """Test get_conversation_context when context is disabled."""
    from flock.utils.runtime import Context

    ctx = Context(
        artifacts=[
            Artifact(
                id=uuid4(),
                type="test",
                payload={},
                produced_by="test",
                created_at=datetime.now(UTC),
            )
        ],
        correlation_id=uuid4(),
        task_id="test-task",
    )

    engine = EngineComponent(enable_context=False)
    context = engine.get_conversation_context(ctx)
    assert context == []


@pytest.mark.asyncio
async def test_engine_component_get_context_no_ctx():
    """Test get_conversation_context with no context."""
    engine = EngineComponent()

    # Test with None ctx
    context = engine.get_conversation_context(None)
    assert context == []


@pytest.mark.asyncio
async def test_engine_component_should_use_context():
    """Test EngineComponent.should_use_context() method."""
    # Test with context enabled and correlation_id present
    engine = EngineComponent(enable_context=True)

    artifact_with_corr_id = Artifact(
        correlation_id=uuid4(),
        type="test_message",
        payload={"test": "data"},
        produced_by="test_agent",
    )

    inputs = EvalInputs(artifacts=[artifact_with_corr_id], state={})
    assert engine.should_use_context(inputs) is True

    # Test with context enabled but no correlation_id
    artifact_no_corr_id = Artifact(
        correlation_id=None,
        type="test_message",
        payload={"test": "data"},
        produced_by="test_agent",
    )
    inputs = EvalInputs(artifacts=[artifact_no_corr_id], state={})
    assert engine.should_use_context(inputs) is False

    # Test with context disabled
    engine2 = EngineComponent(enable_context=False)
    inputs = EvalInputs(artifacts=[artifact_with_corr_id], state={})
    assert engine2.should_use_context(inputs) is False

    # Test with no artifacts
    engine3 = EngineComponent(enable_context=True)
    inputs = EvalInputs(artifacts=[], state={})
    assert engine3.should_use_context(inputs) is False


@pytest.mark.asyncio
async def test_engine_component_evaluate_not_implemented():
    """Test that EngineComponent.evaluate raises NotImplementedError."""
    engine = EngineComponent()
    output_group = OutputGroup(outputs=[], group_description=None)

    with pytest.raises(NotImplementedError):
        await engine.evaluate(
            None, None, EvalInputs(artifacts=[], state={}), output_group
        )


@pytest.mark.asyncio
async def test_agent_component_default_hooks():
    """Test AgentComponent default hook implementations."""
    component = AgentComponent()
    mock_agent = MagicMock()
    mock_ctx = MagicMock()
    mock_artifact = MagicMock()

    # Test on_initialize (no-op)
    result = await component.on_initialize(mock_agent, mock_ctx)
    assert result is None

    # Test on_post_publish (no-op)
    result = await component.on_post_publish(mock_agent, mock_ctx, mock_artifact)
    assert result is None

    # Test on_terminate (no-op)
    result = await component.on_terminate(mock_agent, mock_ctx)
    assert result is None

    # Test on_pre_consume
    inputs = [mock_artifact]
    result = await component.on_pre_consume(mock_agent, mock_ctx, inputs)
    assert result == inputs  # Should return inputs unchanged
