"""Tests for agent component lifecycle management."""

from unittest.mock import Mock

import pytest
from pydantic import ConfigDict

from flock.agent.component_lifecycle import ComponentLifecycle
from flock.components.agent import AgentComponent, EngineComponent
from flock.core.artifacts import Artifact
from flock.utils.runtime import Context, EvalInputs, EvalResult


class MockComponent(AgentComponent):
    """Mock component for testing."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self, name: str = "mock", priority: int = 0):
        super().__init__(priority=priority)
        self.name = name
        self.initialize_called = False
        self.pre_consume_called = False
        self.pre_evaluate_called = False
        self.post_evaluate_called = False
        self.post_publish_called = False
        self.error_called = False
        self.terminate_called = False

    async def on_initialize(self, agent, ctx):
        self.initialize_called = True

    async def on_pre_consume(self, agent, ctx, inputs):
        self.pre_consume_called = True
        return inputs

    async def on_pre_evaluate(self, agent, ctx, inputs):
        self.pre_evaluate_called = True
        return inputs

    async def on_post_evaluate(self, agent, ctx, inputs, result):
        self.post_evaluate_called = True
        return result

    async def on_post_publish(self, agent, ctx, artifact):
        self.post_publish_called = True

    async def on_error(self, agent, ctx, error):
        self.error_called = True

    async def on_terminate(self, agent, ctx):
        self.terminate_called = True


class MockEngine(EngineComponent):
    """Mock engine for testing."""

    model_config = ConfigDict(extra="allow", arbitrary_types_allowed=True)

    def __init__(self):
        super().__init__()
        self.initialize_called = False
        self.error_called = False
        self.terminate_called = False

    async def on_initialize(self, agent, ctx):
        self.initialize_called = True

    async def on_error(self, agent, ctx, error):
        self.error_called = True

    async def on_terminate(self, agent, ctx):
        self.terminate_called = True


@pytest.fixture
def lifecycle():
    """Create ComponentLifecycle instance."""
    return ComponentLifecycle(agent_name="test_agent")


@pytest.fixture
def mock_agent():
    """Create mock agent."""
    agent = Mock()
    agent.name = "test_agent"
    return agent


@pytest.fixture
def mock_context():
    """Create mock context."""
    return Mock(spec=Context)


@pytest.mark.asyncio
async def test_run_initialize_calls_all_components(lifecycle, mock_agent, mock_context):
    """Test that run_initialize calls on_initialize for all components."""
    comp1 = MockComponent(name="comp1", priority=10)
    comp2 = MockComponent(name="comp2", priority=20)
    engine = MockEngine()

    await lifecycle.run_initialize(mock_agent, mock_context, [comp1, comp2], [engine])

    assert comp1.initialize_called
    assert comp2.initialize_called
    assert engine.initialize_called


@pytest.mark.asyncio
async def test_run_initialize_propagates_exceptions(
    lifecycle, mock_agent, mock_context
):
    """Test that run_initialize propagates component exceptions."""
    comp = MockComponent()

    async def failing_init(agent, ctx):
        raise ValueError("Initialization failed")

    comp.on_initialize = failing_init

    with pytest.raises(ValueError, match="Initialization failed"):
        await lifecycle.run_initialize(mock_agent, mock_context, [comp], [])


@pytest.mark.asyncio
async def test_run_pre_consume_transforms_inputs(lifecycle, mock_agent, mock_context):
    """Test that run_pre_consume allows components to transform inputs."""
    comp1 = MockComponent(name="comp1")
    comp2 = MockComponent(name="comp2")

    # Create mock artifacts
    artifact1 = Mock(spec=Artifact)
    artifact2 = Mock(spec=Artifact)
    inputs = [artifact1]

    # Make comp1 add another artifact
    async def add_artifact(agent, ctx, artifacts):
        return artifacts + [artifact2]

    comp1.on_pre_consume = add_artifact

    result = await lifecycle.run_pre_consume(
        mock_agent, mock_context, inputs, [comp1, comp2]
    )

    assert len(result) == 2
    assert artifact1 in result
    assert artifact2 in result


@pytest.mark.asyncio
async def test_run_pre_consume_propagates_exceptions(
    lifecycle, mock_agent, mock_context
):
    """Test that run_pre_consume propagates component exceptions."""
    comp = MockComponent()

    async def failing_pre_consume(agent, ctx, inputs):
        raise ValueError("Pre-consume failed")

    comp.on_pre_consume = failing_pre_consume

    with pytest.raises(ValueError, match="Pre-consume failed"):
        await lifecycle.run_pre_consume(mock_agent, mock_context, [], [comp])


@pytest.mark.asyncio
async def test_run_pre_evaluate_transforms_inputs(lifecycle, mock_agent, mock_context):
    """Test that run_pre_evaluate allows components to transform eval inputs."""
    comp = MockComponent()

    # Create mock eval inputs
    eval_inputs = Mock(spec=EvalInputs)
    eval_inputs.artifacts = []

    # Make component add an artifact
    async def add_artifact_to_eval(agent, ctx, inputs):
        modified = Mock(spec=EvalInputs)
        modified.artifacts = inputs.artifacts + [Mock(spec=Artifact)]
        return modified

    comp.on_pre_evaluate = add_artifact_to_eval

    result = await lifecycle.run_pre_evaluate(
        mock_agent, mock_context, eval_inputs, [comp]
    )

    assert len(result.artifacts) == 1


@pytest.mark.asyncio
async def test_run_pre_evaluate_propagates_exceptions(
    lifecycle, mock_agent, mock_context
):
    """Test that run_pre_evaluate propagates component exceptions."""
    comp = MockComponent()

    async def failing_pre_evaluate(agent, ctx, inputs):
        raise ValueError("Pre-evaluate failed")

    comp.on_pre_evaluate = failing_pre_evaluate

    eval_inputs = Mock(spec=EvalInputs)
    eval_inputs.artifacts = []

    with pytest.raises(ValueError, match="Pre-evaluate failed"):
        await lifecycle.run_pre_evaluate(mock_agent, mock_context, eval_inputs, [comp])


@pytest.mark.asyncio
async def test_run_post_evaluate_transforms_result(lifecycle, mock_agent, mock_context):
    """Test that run_post_evaluate allows components to transform results."""
    comp = MockComponent()

    # Create mock eval inputs and result
    eval_inputs = Mock(spec=EvalInputs)
    result = Mock(spec=EvalResult)
    result.artifacts = []

    # Make component add an artifact to result
    async def add_artifact_to_result(agent, ctx, inputs, res):
        modified = Mock(spec=EvalResult)
        modified.artifacts = res.artifacts + [Mock(spec=Artifact)]
        return modified

    comp.on_post_evaluate = add_artifact_to_result

    transformed = await lifecycle.run_post_evaluate(
        mock_agent, mock_context, eval_inputs, result, [comp]
    )

    assert len(transformed.artifacts) == 1


@pytest.mark.asyncio
async def test_run_post_evaluate_propagates_exceptions(
    lifecycle, mock_agent, mock_context
):
    """Test that run_post_evaluate propagates component exceptions."""
    comp = MockComponent()

    async def failing_post_evaluate(agent, ctx, inputs, result):
        raise ValueError("Post-evaluate failed")

    comp.on_post_evaluate = failing_post_evaluate

    eval_inputs = Mock(spec=EvalInputs)
    eval_inputs.artifacts = []
    result = Mock(spec=EvalResult)
    result.artifacts = []

    with pytest.raises(ValueError, match="Post-evaluate failed"):
        await lifecycle.run_post_evaluate(
            mock_agent, mock_context, eval_inputs, result, [comp]
        )


@pytest.mark.asyncio
async def test_run_post_publish_calls_for_each_artifact(
    lifecycle, mock_agent, mock_context
):
    """Test that run_post_publish calls hook for each published artifact."""
    comp = MockComponent()

    artifact1 = Mock(spec=Artifact)
    artifact1.id = "art1"
    artifact2 = Mock(spec=Artifact)
    artifact2.id = "art2"

    call_count = 0

    async def count_calls(agent, ctx, artifact):
        nonlocal call_count
        call_count += 1

    comp.on_post_publish = count_calls

    await lifecycle.run_post_publish(
        mock_agent, mock_context, [artifact1, artifact2], [comp]
    )

    assert call_count == 2


@pytest.mark.asyncio
async def test_run_post_publish_propagates_exceptions(
    lifecycle, mock_agent, mock_context
):
    """Test that run_post_publish propagates component exceptions."""
    comp = MockComponent()

    async def failing_post_publish(agent, ctx, artifact):
        raise ValueError("Post-publish failed")

    comp.on_post_publish = failing_post_publish

    artifact = Mock(spec=Artifact)
    artifact.id = "test"

    with pytest.raises(ValueError, match="Post-publish failed"):
        await lifecycle.run_post_publish(mock_agent, mock_context, [artifact], [comp])


@pytest.mark.asyncio
async def test_run_error_calls_all_components(lifecycle, mock_agent, mock_context):
    """Test that run_error calls on_error for all components."""
    comp1 = MockComponent(name="comp1")
    comp2 = MockComponent(name="comp2")
    engine = MockEngine()

    error = ValueError("Test error")

    await lifecycle.run_error(mock_agent, mock_context, error, [comp1, comp2], [engine])

    assert comp1.error_called
    assert comp2.error_called
    assert engine.error_called


@pytest.mark.asyncio
async def test_run_error_propagates_exceptions(lifecycle, mock_agent, mock_context):
    """Test that run_error propagates component exceptions."""
    comp = MockComponent()

    async def failing_error_handler(agent, ctx, error):
        raise RuntimeError("Error handler failed")

    comp.on_error = failing_error_handler

    error = ValueError("Original error")

    with pytest.raises(RuntimeError, match="Error handler failed"):
        await lifecycle.run_error(mock_agent, mock_context, error, [comp], [])


@pytest.mark.asyncio
async def test_run_terminate_calls_all_components(lifecycle, mock_agent, mock_context):
    """Test that run_terminate calls on_terminate for all components."""
    comp1 = MockComponent(name="comp1")
    comp2 = MockComponent(name="comp2")
    engine = MockEngine()

    await lifecycle.run_terminate(mock_agent, mock_context, [comp1, comp2], [engine])

    assert comp1.terminate_called
    assert comp2.terminate_called
    assert engine.terminate_called


@pytest.mark.asyncio
async def test_run_terminate_propagates_exceptions(lifecycle, mock_agent, mock_context):
    """Test that run_terminate propagates component exceptions."""
    comp = MockComponent()

    async def failing_terminate(agent, ctx):
        raise ValueError("Termination failed")

    comp.on_terminate = failing_terminate

    with pytest.raises(ValueError, match="Termination failed"):
        await lifecycle.run_terminate(mock_agent, mock_context, [comp], [])


def test_component_display_name_uses_name_attribute(lifecycle):
    """Test that _component_display_name uses component's name attribute if available."""
    comp = MockComponent(name="my_component")
    assert lifecycle._component_display_name(comp) == "my_component"


def test_component_display_name_falls_back_to_class_name(lifecycle):
    """Test that _component_display_name falls back to class name if no name attribute."""
    comp = MockComponent()
    comp.name = None  # Remove name
    assert lifecycle._component_display_name(comp) == "MockComponent"
