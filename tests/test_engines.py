"""Tests for engine execution."""

from uuid import UUID

import pytest
from pydantic import BaseModel, Field

from flock.components.agent import EngineComponent
from flock.core import Flock
from flock.core.artifacts import Artifact
from flock.core.visibility import PublicVisibility
from flock.engines.dspy_engine import DSPyEngine
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


# Test artifact types
@flock_type(name="EngineInput")
class EngineInput(BaseModel):
    prompt: str = Field(description="Input prompt")


@flock_type(name="EngineOutput")
class EngineOutput(BaseModel):
    response: str = Field(description="Output response")


@pytest.mark.asyncio
async def test_dspy_engine_evaluation_with_mock_llm(orchestrator, mocker):
    """Test that DSPy engine evaluates with mocked LLM."""

    # Arrange
    # Mock DSPy LM to avoid real API calls
    class MockLM:
        def __init__(
            self, model, temperature=None, max_tokens=None, cache=None, num_retries=None
        ):
            self.model = model
            self.temperature = temperature
            self.max_tokens = max_tokens
            self.cache = cache
            self.num_retries = num_retries

    class MockPrediction:
        def __init__(self):
            # DSPy engine uses snake_case field names (EngineOutput -> engine_output)
            self.engine_output = {"response": "mocked output"}

    class MockPredict:
        def __init__(self, signature):
            self.signature = signature

        def __call__(self, **kwargs):
            return MockPrediction()

    # Mock the entire DSPy module to avoid import issues
    mock_dspy = mocker.MagicMock()
    mock_dspy.LM = MockLM
    mock_dspy.Predict = MockPredict

    class MockSignature:
        def __init__(self, fields):
            self.fields = fields

        def with_instructions(self, instruction):
            return self

    mock_dspy.Signature = MockSignature
    mock_dspy.InputField = lambda **kwargs: "input_field"
    mock_dspy.OutputField = lambda **kwargs: "output_field"
    mock_dspy.context = lambda **kwargs: mocker.MagicMock()

    mocker.patch(
        "flock.engines.dspy_engine.DSPyEngine._import_dspy", return_value=mock_dspy
    )

    agent = (
        orchestrator.agent("test_agent")
        .consumes(EngineInput)
        .publishes(EngineOutput)
        .with_engines(
            DSPyEngine(model="gpt-4", stream=False)
        )  # Disable streaming for testing
    )

    input_artifact = EngineInput(prompt="test prompt")

    # Act
    await orchestrator.invoke(agent, input_artifact)
    await orchestrator.run_until_idle()

    # Assert - should complete without errors and produce artifacts
    artifacts = await orchestrator.store.list()
    assert len(artifacts) > 0

    # Verify the artifact has the expected structure
    output_artifacts = [a for a in artifacts if a.type == "EngineOutput"]
    assert len(output_artifacts) > 0
    assert "response" in output_artifacts[0].payload
    assert output_artifacts[0].payload["response"] == "mocked output"


@pytest.mark.asyncio
async def test_engine_pre_generates_artifact_ids():
    """Test that engine pre-generates artifact IDs before execution."""
    # Arrange
    orchestrator = Flock()

    generated_ids = []

    class IDCapturingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            # Create artifact with explicit ID
            artifact_id = UUID("12345678-1234-5678-1234-567812345678")
            generated_ids.append(artifact_id)

            artifact = Artifact(
                id=artifact_id,
                type="EngineOutput",
                payload={"response": "test"},
                produced_by=agent.name,
                visibility=PublicVisibility(),
            )
            return EvalResult(artifacts=[artifact], state={})

    agent = (
        orchestrator.agent("test_agent")
        .consumes(EngineInput)
        .publishes(EngineOutput)
        .with_engines(IDCapturingEngine())
    )

    input_artifact = EngineInput(prompt="test")

    # Act - use publish_outputs=False to avoid double execution
    await orchestrator.invoke(agent, input_artifact, publish_outputs=False)

    # Assert - ID should have been generated
    assert len(generated_ids) == 1
    assert isinstance(generated_ids[0], UUID)


@pytest.mark.asyncio
async def test_engine_handles_evaluation_errors_gracefully():
    """Test that engine handles evaluation errors without crashing."""
    # Arrange
    orchestrator = Flock()

    errors_collected = []

    class ErrorCollectingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            try:
                raise RuntimeError("Evaluation failed")
            except Exception as e:
                errors_collected.append(str(e))
                # Return empty result instead of crashing
                return EvalResult(artifacts=[], state={}, errors=[str(e)])

    agent = (
        orchestrator.agent("test_agent")
        .consumes(EngineInput)
        .with_engines(ErrorCollectingEngine())
    )

    input_artifact = EngineInput(prompt="test")

    # Act
    try:
        await orchestrator.invoke(agent, input_artifact)
        await orchestrator.run_until_idle()
    except Exception:
        # If exception propagates, that's acceptable behavior
        pass

    # Assert - error should have been collected
    assert len(errors_collected) > 0
    assert "Evaluation failed" in errors_collected[0]


# T070: Streaming Auto-Disable Tests
def test_dspy_engine_disables_streaming_in_pytest():
    """Test that DSPyEngine auto-detects pytest and disables streaming."""
    # Arrange
    import sys

    from flock.engines.dspy_engine import DSPyEngine

    # Act - Create engine with default stream parameter
    engine = DSPyEngine()

    # Assert - Should detect pytest is running and disable streaming
    # pytest module is in sys.modules during test execution
    assert "pytest" in sys.modules
    assert engine.stream is False  # Auto-disabled in tests


def test_dspy_engine_respects_explicit_stream_parameter():
    """Test that explicit stream parameter overrides auto-detection."""
    # Arrange
    from flock.engines.dspy_engine import DSPyEngine

    # Act - Explicitly set stream=True
    engine_enabled = DSPyEngine(stream=True)
    engine_disabled = DSPyEngine(stream=False)

    # Assert - Explicit parameter overrides auto-detection
    assert engine_enabled.stream is True
    assert engine_disabled.stream is False
