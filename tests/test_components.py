"""Tests for component system."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from flock.artifacts import Artifact
from flock.components import AgentComponent, AgentComponentConfig, EngineComponent
from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.runtime import EvalInputs, EvalResult


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

    async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
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
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
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
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
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
        async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
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
        enabled=False, model="gpt-4", temperature=0.9, max_tokens=2000, custom_flag=False
    )
    assert config2.enabled is False
    assert config2.model == "gpt-4"
    assert config2.temperature == 0.9
    assert config2.max_tokens == 2000
    assert config2.custom_flag is False

    # Verify the class name contains "Dynamic"
    assert "Dynamic" in CustomConfig.__name__


@pytest.mark.asyncio
async def test_engine_component_fetch_conversation_context():
    """Test EngineComponent.fetch_conversation_context() method."""
    # Create mock context and artifacts
    correlation_id = uuid4()

    artifact1 = Artifact(
        correlation_id=correlation_id,
        type="user_message",
        payload={"message": "Hello"},
        produced_by="agent1",
        created_at=datetime.now(timezone.utc),
    )

    artifact2 = Artifact(
        correlation_id=correlation_id,
        type="assistant_response",
        payload={"message": "Hi there!"},
        produced_by="agent2",
        created_at=datetime.now(timezone.utc),
    )

    artifact3 = Artifact(
        correlation_id=uuid4(),  # Different correlation_id
        type="other_message",
        payload={"message": "Not related"},
        produced_by="agent3",
        created_at=datetime.now(timezone.utc),
    )

    mock_board = AsyncMock()
    mock_board.list = AsyncMock(return_value=[artifact1, artifact2, artifact3])

    mock_ctx = MagicMock()
    mock_ctx.board = mock_board
    mock_ctx.correlation_id = correlation_id

    # Test basic context fetching
    engine = EngineComponent()
    context = await engine.fetch_conversation_context(mock_ctx)

    assert len(context) == 2  # Only artifacts with matching correlation_id
    assert context[0]["type"] == "user_message"
    assert context[0]["payload"] == {"message": "Hello"}
    assert context[0]["produced_by"] == "agent1"
    assert context[0]["event_number"] == 0
    assert context[1]["type"] == "assistant_response"
    assert context[1]["payload"] == {"message": "Hi there!"}
    assert context[1]["produced_by"] == "agent2"
    assert context[1]["event_number"] == 1


@pytest.mark.asyncio
async def test_engine_component_fetch_context_with_max_artifacts():
    """Test fetch_conversation_context with max_artifacts limit."""
    correlation_id = uuid4()

    # Create many artifacts
    artifacts = []
    base_time = datetime.now(timezone.utc)
    for i in range(10):
        artifact = Artifact(
            correlation_id=correlation_id,
            type=f"message_{i}",
            payload={"content": f"Content {i}"},
            produced_by=f"agent_{i}",
            created_at=base_time,
        )
        artifacts.append(artifact)

    mock_board = AsyncMock()
    mock_board.list = AsyncMock(return_value=artifacts)

    mock_ctx = MagicMock()
    mock_ctx.board = mock_board

    # Test with max_artifacts parameter
    engine = EngineComponent()
    context = await engine.fetch_conversation_context(mock_ctx, correlation_id, max_artifacts=3)

    assert len(context) == 3
    # Should get the last 3 artifacts
    assert context[0]["type"] == "message_7"
    assert context[1]["type"] == "message_8"
    assert context[2]["type"] == "message_9"

    # Test with instance-level max_artifacts
    engine2 = EngineComponent(context_max_artifacts=5)
    context2 = await engine2.fetch_conversation_context(mock_ctx, correlation_id)

    assert len(context2) == 5
    # Should get the last 5 artifacts
    assert context2[0]["type"] == "message_5"
    assert context2[4]["type"] == "message_9"


@pytest.mark.asyncio
async def test_engine_component_fetch_context_with_exclude_types():
    """Test fetch_conversation_context with excluded types."""
    correlation_id = uuid4()

    artifact1 = Artifact(
        correlation_id=correlation_id,
        type="user_message",
        payload={"message": "Hello"},
        produced_by="agent1",
        created_at=datetime.now(timezone.utc),
    )

    artifact2 = Artifact(
        correlation_id=correlation_id,
        type="system_log",  # This should be excluded
        payload={"info": "System info"},
        produced_by="system",
        created_at=datetime.now(timezone.utc),
    )

    artifact3 = Artifact(
        correlation_id=correlation_id,
        type="assistant_response",
        payload={"message": "Hi there!"},
        produced_by="agent2",
        created_at=datetime.now(timezone.utc),
    )

    mock_board = AsyncMock()
    mock_board.list = AsyncMock(return_value=[artifact1, artifact2, artifact3])

    mock_ctx = MagicMock()
    mock_ctx.board = mock_board

    # Test with excluded types
    engine = EngineComponent(context_exclude_types={"system_log"})
    context = await engine.fetch_conversation_context(mock_ctx, correlation_id)

    assert len(context) == 2  # system_log should be excluded
    assert context[0]["type"] == "user_message"
    assert context[1]["type"] == "assistant_response"


@pytest.mark.asyncio
async def test_engine_component_fetch_context_disabled():
    """Test fetch_conversation_context when context is disabled."""
    engine = EngineComponent(enable_context=False)
    mock_ctx = MagicMock()

    context = await engine.fetch_conversation_context(mock_ctx, uuid4())
    assert context == []


@pytest.mark.asyncio
async def test_engine_component_fetch_context_no_ctx():
    """Test fetch_conversation_context with no context."""
    engine = EngineComponent()

    # Test with None ctx
    context = await engine.fetch_conversation_context(None)
    assert context == []


@pytest.mark.asyncio
async def test_engine_component_fetch_context_no_correlation_id():
    """Test fetch_conversation_context with no correlation_id."""
    engine = EngineComponent()
    mock_ctx = MagicMock()
    mock_ctx.correlation_id = None

    context = await engine.fetch_conversation_context(mock_ctx)
    assert context == []


@pytest.mark.asyncio
async def test_engine_component_fetch_context_exception_handling():
    """Test fetch_conversation_context exception handling."""
    mock_board = AsyncMock()
    mock_board.list = AsyncMock(side_effect=Exception("Database error"))

    mock_ctx = MagicMock()
    mock_ctx.board = mock_board
    mock_ctx.correlation_id = uuid4()

    engine = EngineComponent()
    context = await engine.fetch_conversation_context(mock_ctx)

    # Should return empty list on exception
    assert context == []


@pytest.mark.asyncio
async def test_engine_component_get_latest_artifact_of_type():
    """Test EngineComponent.get_latest_artifact_of_type() method."""
    correlation_id = uuid4()

    artifact1 = Artifact(
        correlation_id=correlation_id,
        type="user_message",
        payload={"message": "First message"},
        produced_by="agent1",
        created_at=datetime.now(timezone.utc),
    )

    artifact2 = Artifact(
        correlation_id=correlation_id,
        type="user_message",
        payload={"message": "Second message"},
        produced_by="agent1",
        created_at=datetime.now(timezone.utc),
    )

    artifact3 = Artifact(
        correlation_id=correlation_id,
        type="assistant_response",
        payload={"message": "Response"},
        produced_by="agent2",
        created_at=datetime.now(timezone.utc),
    )

    mock_board = AsyncMock()
    mock_board.list = AsyncMock(return_value=[artifact1, artifact2, artifact3])

    mock_ctx = MagicMock()
    mock_ctx.board = mock_board

    engine = EngineComponent()

    # Test getting latest user_message
    latest = await engine.get_latest_artifact_of_type(mock_ctx, "user_message", correlation_id)
    assert latest is not None
    assert latest["type"] == "user_message"
    assert latest["payload"] == {"message": "Second message"}  # Should get the latest one

    # Test getting assistant_response
    latest = await engine.get_latest_artifact_of_type(
        mock_ctx, "assistant_response", correlation_id
    )
    assert latest is not None
    assert latest["type"] == "assistant_response"
    assert latest["payload"] == {"message": "Response"}

    # Test getting non-existent type
    latest = await engine.get_latest_artifact_of_type(mock_ctx, "non_existent", correlation_id)
    assert latest is None


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

    with pytest.raises(NotImplementedError):
        await engine.evaluate(None, None, EvalInputs(artifacts=[], state={}))


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
