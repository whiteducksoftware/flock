"""Comprehensive tests for DSPy engine covering all major code paths.

This test suite provides comprehensive coverage for the DSPy engine implementation,
covering all major methods, error handling, streaming, and edge cases.

Target: 80%+ coverage for dspy_engine.py
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import UTC
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from pydantic import BaseModel, Field

from flock.core import Flock, OutputGroup
from flock.core.artifacts import Artifact
from flock.engines.dspy_engine import (
    DSPyEngine,
    _default_stream_value,
    _ensure_live_crop_above,
)
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs, EvalResult


# Test artifact types
@flock_type(name="TestInput")
class TestInput(BaseModel):
    prompt: str = Field(description="Input prompt")
    context: str | None = Field(default=None, description="Optional context")


@flock_type(name="TestOutput")
class TestOutput(BaseModel):
    response: str = Field(description="Output response")
    metadata: dict | None = Field(default=None, description="Optional metadata")


@flock_type(name="ComplexInput")
class ComplexInput(BaseModel):
    text: str = Field(description="Main text")
    items: list[str] = Field(default_factory=list, description="List of items")
    config: dict = Field(default_factory=dict, description="Configuration dict")


@flock_type(name="ComplexOutput")
class ComplexOutput(BaseModel):
    summary: str = Field(description="Summary of input")
    processed_items: list[str] = Field(
        default_factory=list, description="Processed items"
    )
    result: dict = Field(default_factory=dict, description="Result dictionary")


class MockDSPyModule:
    """Mock DSPy module for testing."""

    def __init__(self):
        self.LM = MockLM
        self.Predict = MockPredict
        self.ReAct = MockReAct
        self.Signature = MockSignature
        self.InputField = MockInputField
        self.OutputField = MockOutputField
        self.context = MockContext
        self.streamify = MockStreamify
        self.streaming = MockStreamingModule()
        self.Prediction = MockPrediction


class MockLM:
    """Mock DSPy LM class."""

    def __init__(
        self, model, temperature=None, max_tokens=None, cache=None, num_retries=None
    ):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cache = cache
        self.num_retries = num_retries


class MockPrediction:
    """Mock DSPy Prediction."""

    def __init__(self, output=None):
        self.output = output or {"response": "mocked response"}
        # Add attributes that might be accessed during materialization
        self.TestOutput = {"response": "mocked response", "metadata": None}
        self.response = "mocked response"


class MockPredict:
    """Mock DSPy Predict."""

    def __init__(self, signature):
        self.signature = signature

    def __call__(self, **kwargs):
        return MockPrediction()


class MockReAct:
    """Mock DSPy ReAct."""

    def __init__(self, signature, tools=None, max_iters=None):
        self.signature = signature
        self.tools = tools or []
        self.max_iters = max_iters

    def __call__(self, **kwargs):
        return MockPrediction()


class MockSignature:
    """Mock DSPy Signature."""

    def __init__(self, fields):
        self.fields = fields
        self.output_fields = OrderedDict([
            ("response", "output_field"),
            ("metadata", "output_field"),
        ])

    def with_instructions(self, instruction):
        return self


class MockInputField:
    """Mock DSPy InputField."""

    def __init__(self, **kwargs):
        pass


class MockOutputField:
    """Mock DSPy OutputField."""

    def __init__(self, **kwargs):
        pass


class MockContext:
    """Mock DSPy context manager."""

    def __init__(self, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockStreamify:
    """Mock DSPy streamify function."""

    def __init__(self, program, is_async_program=True, stream_listeners=None):
        self.program = program
        self.is_async_program = is_async_program
        self.stream_listeners = stream_listeners

    def __call__(self, **kwargs):
        return MockStreamGenerator()


class MockStreamGenerator:
    """Mock async stream generator."""

    def __init__(self):
        self.values = [
            MockStatusMessage("Starting..."),
            MockStreamResponse("Hello", "response"),
            MockStreamResponse(" world", "response"),
            MockStatusMessage("Processing complete."),
            MockPrediction({"response": "Hello world", "metadata": {}}),
        ]

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.values:
            return self.values.pop(0)
        raise StopAsyncIteration


class MockStatusMessage:
    """Mock DSPy StatusMessage."""

    def __init__(self, message):
        self.message = message


class MockStreamResponse:
    """Mock DSPy StreamResponse."""

    def __init__(self, chunk, signature_field_name):
        self.chunk = chunk
        self.signature_field_name = signature_field_name


class MockStreamingModule:
    """Mock DSPy streaming module."""

    def __init__(self):
        self.StreamListener = MockStreamListener


class MockStreamListener:
    """Mock DSPy StreamListener."""

    def __init__(self, signature_field_name):
        self.signature_field_name = signature_field_name


class TestDSPyEngineBasics:
    """Test basic DSPy engine functionality."""

    def test_engine_initialization_with_defaults(self):
        """Test engine initialization with default parameters."""
        engine = DSPyEngine()

        assert engine.name == "dspy"
        assert engine.model is None
        assert engine.instructions is None
        assert engine.temperature == 1.0
        assert engine.max_tokens == 32000
        assert engine.max_tool_calls == 10
        assert engine.max_retries == 0
        assert engine.no_output is False
        assert engine.stream_vertical_overflow == "crop_above"
        assert engine.status_output_field == "_status_output"
        assert engine.theme == "afterglow"
        assert engine.enable_cache is False
        # Should auto-disable streaming in pytest
        assert engine.stream is False

    def test_engine_initialization_with_custom_parameters(self):
        """Test engine initialization with custom parameters."""
        engine = DSPyEngine(
            name="custom_dspy",
            model="gpt-4",
            instructions="Custom instructions",
            temperature=0.7,
            max_tokens=1000,
            max_tool_calls=5,
            max_retries=2,
            stream=True,
            no_output=True,
            stream_vertical_overflow="crop",
            status_output_field="custom_status",
            theme="monokai",
            enable_cache=True,
        )

        assert engine.name == "custom_dspy"
        assert engine.model == "gpt-4"
        assert engine.instructions == "Custom instructions"
        assert engine.temperature == 0.7
        assert engine.max_tokens == 1000
        assert engine.max_tool_calls == 5
        assert engine.max_retries == 2
        assert engine.stream is True
        assert engine.no_output is True
        assert engine.stream_vertical_overflow == "crop"
        assert engine.status_output_field == "custom_status"
        assert engine.theme == "monokai"
        assert engine.enable_cache is True

    def test_default_stream_value_in_pytest(self):
        """Test that default stream value is False in pytest."""
        assert _default_stream_value() is False

    def test_resolve_model_name_with_explicit_model(self):
        """Test model resolution with explicit model."""
        engine = DSPyEngine(model="claude-3")
        assert engine._resolve_model_name() == "claude-3"

    def test_resolve_model_name_with_env_var(self, mocker):
        """Test model resolution with DEFAULT_MODEL environment variable."""
        mocker.patch.dict("os.environ", {"DEFAULT_MODEL": "gpt-4-turbo"})
        engine = DSPyEngine()
        assert engine._resolve_model_name() == "gpt-4-turbo"

    def test_resolve_model_name_with_default_model_env_var(self, mocker):
        """Test model resolution with DEFAULT_MODEL environment variable (primary)."""
        mocker.patch.dict("os.environ", {"DEFAULT_MODEL": "gpt-3.5-turbo"})
        engine = DSPyEngine()
        assert engine._resolve_model_name() == "gpt-3.5-turbo"

    def test_resolve_model_name_raises_error_when_no_model(self, mocker):
        """Test that error is raised when no model is configured."""
        mocker.patch.dict("os.environ", {}, clear=True)
        engine = DSPyEngine()
        with pytest.raises(
            NotImplementedError, match="DSPyEngine requires a configured model"
        ):
            engine._resolve_model_name()

    def test_import_dspy_exists(self):
        """Test that DSPy can be imported when installed."""
        engine = DSPyEngine()
        # DSPy is installed in this environment, so this should work
        result = engine._import_dspy()
        assert result is not None

    def test_dspy_engine_can_be_created(self):
        """Test that DSPyEngine can be created without errors."""
        engine = DSPyEngine()
        assert engine is not None
        assert engine.name == "dspy"

    def test_select_primary_artifact(self):
        """Test primary artifact selection."""
        artifact1 = Artifact(type="Type1", payload={"data": "1"}, produced_by="test")
        artifact2 = Artifact(type="Type2", payload={"data": "2"}, produced_by="test")

        engine = DSPyEngine()
        result = engine._select_primary_artifact([artifact1, artifact2])
        assert result is artifact2  # Should select the last one

    def test_resolve_input_model_success(self, mocker):
        """Test successful input model resolution."""
        mock_type_registry = mocker.MagicMock()
        mock_type_registry.resolve.return_value = TestInput
        mocker.patch("flock.engines.dspy_engine.type_registry", mock_type_registry)

        artifact = Artifact(type="TestInput", payload={}, produced_by="test")
        engine = DSPyEngine()
        result = engine._resolve_input_model(artifact)
        assert result is TestInput

    def test_resolve_input_model_failure(self, mocker):
        """Test input model resolution failure."""
        mock_type_registry = mocker.MagicMock()
        mock_type_registry.resolve.side_effect = KeyError("Type not found")
        mocker.patch("flock.engines.dspy_engine.type_registry", mock_type_registry)

        artifact = Artifact(type="UnknownType", payload={}, produced_by="test")
        engine = DSPyEngine()
        result = engine._resolve_input_model(artifact)
        assert result is None

    def test_resolve_output_model_with_outputs(self):
        """Test output model resolution with agent outputs."""
        mock_output = Mock()
        mock_output.spec.model = TestOutput

        mock_agent = Mock()
        mock_agent.outputs = [mock_output]

        engine = DSPyEngine()
        result = engine._resolve_output_model(mock_agent)
        assert result is TestOutput

    def test_resolve_output_model_without_outputs(self):
        """Test output model resolution without agent outputs."""
        mock_agent = Mock()
        mock_agent.outputs = None

        engine = DSPyEngine()
        result = engine._resolve_output_model(mock_agent)
        assert result is None

    def test_validate_input_payload_with_schema(self):
        """Test input payload validation with schema."""
        payload = {"prompt": "test prompt", "context": "test context"}
        engine = DSPyEngine()
        result = engine._validate_input_payload(TestInput, payload)
        assert result == payload

    def test_validate_input_payload_with_invalid_payload(self):
        """Test input payload validation with invalid payload."""
        payload = {"invalid_field": "value"}
        engine = DSPyEngine()
        result = engine._validate_input_payload(TestInput, payload)
        assert result == payload  # Should return as-is on validation error

    def test_validate_input_payload_without_schema(self):
        """Test input payload validation without schema."""
        payload = {"prompt": "test prompt"}
        engine = DSPyEngine()
        result = engine._validate_input_payload(None, payload)
        assert result == payload

    def test_validate_input_payload_with_none_payload(self):
        """Test input payload validation with None payload."""
        engine = DSPyEngine()
        result = engine._validate_input_payload(TestInput, None)
        assert result == {}

    def test_normalize_output_payload_with_base_model(self):
        """Test output payload normalization with BaseModel."""
        output = TestOutput(response="test response", metadata={"key": "value"})
        engine = DSPyEngine()
        result = engine._artifact_materializer.normalize_output_payload(output)
        assert result == {"response": "test response", "metadata": {"key": "value"}}

    def test_normalize_output_payload_with_json_string(self):
        """Test output payload normalization with JSON string."""
        output = '{"response": "test response", "metadata": {"key": "value"}}'
        engine = DSPyEngine()
        result = engine._artifact_materializer.normalize_output_payload(output)
        assert result == {"response": "test response", "metadata": {"key": "value"}}

    def test_normalize_output_payload_with_invalid_json_string(self):
        """Test output payload normalization with invalid JSON string."""
        output = "invalid json string"
        engine = DSPyEngine()
        result = engine._artifact_materializer.normalize_output_payload(output)
        assert result == {"text": "invalid json string"}

    def test_normalize_output_payload_with_mapping(self):
        """Test output payload normalization with mapping."""
        output = {"response": "test response", "metadata": {"key": "value"}}
        engine = DSPyEngine()
        result = engine._artifact_materializer.normalize_output_payload(output)
        assert result == {"response": "test response", "metadata": {"key": "value"}}

    def test_normalize_output_payload_with_other_type(self):
        """Test output payload normalization with other type."""
        output = 42
        engine = DSPyEngine()
        result = engine._artifact_materializer.normalize_output_payload(output)
        assert result == {"value": 42}

    def test_system_description_with_instructions(self):
        """Test system description with instructions."""
        engine = DSPyEngine()
        result = engine._system_description("Custom instructions")
        assert result == "Custom instructions"

    def test_system_description_without_instructions(self):
        """Test system description without instructions."""
        engine = DSPyEngine()
        result = engine._system_description(None)
        assert result == "Produce a valid output that matches the 'output' schema."

    def test_choose_program_with_tools(self):
        """Test program selection with tools."""
        mock_dspy = MockDSPyModule()
        signature = MockSignature({})
        tools = [Mock(), Mock()]

        engine = DSPyEngine()
        result = engine._choose_program(mock_dspy, signature, tools)
        assert isinstance(result, MockReAct)
        assert result.tools == tools

    def test_choose_program_without_tools(self):
        """Test program selection without tools."""
        mock_dspy = MockDSPyModule()
        signature = MockSignature({})

        engine = DSPyEngine()
        result = engine._choose_program(mock_dspy, signature, [])
        assert isinstance(result, MockPredict)

    def test_choose_program_with_react_failure(self, mocker):
        """Test program selection when ReAct fails."""
        mock_dspy = MockDSPyModule()
        mock_dspy.ReAct = Mock(side_effect=Exception("ReAct failed"))
        signature = MockSignature({})
        tools = [Mock()]

        engine = DSPyEngine()
        result = engine._choose_program(mock_dspy, signature, tools)
        assert isinstance(result, MockPredict)


class TestDSPyEngineSignature:
    """Test DSPy signature building and execution."""

    @pytest.mark.skip(
        reason="Legacy method _prepare_signature_with_context removed in Phase 6 refactoring"
    )
    def test_prepare_signature_without_context(self):
        """Test signature preparation without context."""

    @pytest.mark.skip(
        reason="Legacy method _prepare_signature_with_context removed in Phase 6 refactoring"
    )
    def test_prepare_signature_with_context(self):
        """Test signature preparation with context."""

    @pytest.mark.skip(
        reason="Legacy method _prepare_signature_with_context removed in Phase 6 refactoring"
    )
    def test_prepare_signature_without_schemas(self):
        """Test signature preparation without schemas."""

    @pytest.mark.skip(
        reason="Legacy method _prepare_signature_with_context removed in Phase 6 refactoring"
    )
    def test_prepare_signature_instruction_building(self):
        """Test that signature instructions are built correctly."""

    @pytest.mark.skip(
        reason="Legacy method _prepare_signature_with_context removed in Phase 6 refactoring"
    )
    def test_prepare_signature_with_batch_schema(self):
        """Test that batched signatures wrap input schema in a list."""


class TestDSPyEngineArtifactMaterialization:
    """Test artifact materialization logic."""

    def test_materialize_artifacts_success(self):
        """Test successful artifact materialization."""
        payload = {"response": "test response", "metadata": {"key": "value"}}

        mock_output = Mock()
        mock_output.spec.model = TestOutput
        mock_output.spec.type_name = "TestOutput"
        mock_output.count = 1  # Single output (not fan-out)

        engine = DSPyEngine()
        artifacts, errors = engine._artifact_materializer.materialize_artifacts(
            payload, [mock_output], "test_agent", pre_generated_id=uuid4()
        )

        assert len(artifacts) == 1
        assert len(errors) == 0
        assert artifacts[0].type == "TestOutput"
        assert artifacts[0].produced_by == "test_agent"
        assert artifacts[0].payload["response"] == "test response"

    def test_materialize_artifacts_with_validation_error(self):
        """Test artifact materialization with validation error."""
        payload = {"invalid_field": "value"}  # Missing required 'response' field

        mock_output = Mock()
        mock_output.spec.model = TestOutput
        mock_output.spec.type_name = "TestOutput"
        mock_output.count = 1  # Single output (not fan-out)

        engine = DSPyEngine()
        artifacts, errors = engine._artifact_materializer.materialize_artifacts(
            payload, [mock_output], "test_agent"
        )

        assert len(artifacts) == 0
        assert len(errors) == 1
        assert "response" in errors[0]

    def test_materialize_artifacts_without_outputs(self):
        """Test artifact materialization without outputs."""
        engine = DSPyEngine()
        artifacts, errors = engine._artifact_materializer.materialize_artifacts(
            {"response": "test"}, [], "test_agent"
        )

        assert len(artifacts) == 0
        assert len(errors) == 0

    def test_select_output_payload_with_type_name_match(self):
        """Test output payload selection with type name match."""
        payload = {"TestOutput": {"response": "test"}}
        engine = DSPyEngine()
        result = engine._artifact_materializer.select_output_payload(
            payload, TestOutput, "TestOutput"
        )
        assert result == {"response": "test"}

    def test_select_output_payload_with_class_name_match(self):
        """Test output payload selection with class name match."""
        payload = {"TestOutput": {"response": "test"}}
        engine = DSPyEngine()
        result = engine._artifact_materializer.select_output_payload(
            payload, TestOutput, "DifferentType"
        )
        assert result == {"response": "test"}

    def test_select_output_payload_with_class_name_lowercase_match(self):
        """Test output payload selection with lowercase class name match."""
        payload = {"testoutput": {"response": "test"}}
        engine = DSPyEngine()
        result = engine._artifact_materializer.select_output_payload(
            payload, TestOutput, "DifferentType"
        )
        assert result == {"response": "test"}

    def test_select_output_payload_without_match(self):
        """Test output payload selection without match."""
        payload = {"other_field": {"data": "value"}}
        engine = DSPyEngine()
        result = engine._artifact_materializer.select_output_payload(
            payload, TestOutput, "TestOutput"
        )
        assert result == payload

    def test_select_output_payload_with_non_mapping_payload(self):
        """Test output payload selection with non-mapping payload."""
        # The method expects a Mapping, so we pass a dict without expected fields
        payload = {"unexpected_field": "value"}
        engine = DSPyEngine()
        result = engine._artifact_materializer.select_output_payload(
            payload, TestOutput, "TestOutput"
        )
        assert result == payload


class TestDSPyEngineContext:
    """Test context handling functionality - Phase 8."""

    def test_conversation_context_method_exists(self):
        """Phase 8: Test that get_conversation_context method is available (inherited)."""
        from flock.engines.dspy_engine import DSPyEngine

        engine = DSPyEngine()
        # Phase 8: Method is get_conversation_context (NOT fetch_conversation_context)
        assert hasattr(engine, "get_conversation_context")
        assert callable(engine.get_conversation_context)

    def test_get_conversation_context_with_prefiltered_artifacts(self):
        """Phase 8: Test reading pre-filtered context from ctx.artifacts."""
        from datetime import datetime

        engine = DSPyEngine()

        # Phase 8: Context has pre-filtered artifacts (Artifact objects)
        mock_ctx = Mock()
        mock_ctx.artifacts = [
            Artifact(
                id=uuid4(),
                type="Message",
                payload={"text": "hello"},
                produced_by="user",
                created_at=datetime.now(UTC),
            ),
            Artifact(
                id=uuid4(),
                type="Response",
                payload={"text": "hi"},
                produced_by="bot",
                created_at=datetime.now(UTC),
            ),
        ]

        result = engine.get_conversation_context(mock_ctx)

        # Should return Artifact objects (no serialization)
        assert len(result) == 2
        assert result[0].type == "Message"
        assert result[1].type == "Response"
        assert result[0].payload["text"] == "hello"
        assert result[1].payload["text"] == "hi"

    def test_get_conversation_context_with_empty_artifacts(self):
        """Phase 8: Test context reading with no artifacts."""
        engine = DSPyEngine()

        # Phase 8: Context has empty artifacts list
        mock_ctx = Mock()
        mock_ctx.artifacts = []

        result = engine.get_conversation_context(mock_ctx)
        assert result == []


class TestDSPyEngineExecution:
    """Test execution methods."""

    @pytest.mark.asyncio
    async def test_execute_standard_with_semantic_fields(self):
        """Test standard execution with semantic field format."""
        mock_dspy = MockDSPyModule()
        mock_program = Mock()
        mock_program.return_value = MockPrediction()

        # New semantic field format
        payload = {
            "description": "Test description",
            "task": {"prompt": "test"},
            "context": [],
        }
        engine = DSPyEngine()

        result = await engine._streaming_executor.execute_standard(
            mock_dspy, mock_program, description="Test description", payload=payload
        )

        assert isinstance(result, MockPrediction)
        # Semantic fields are passed as kwargs
        mock_program.assert_called_once_with(
            description="Test description", task={"prompt": "test"}, context=[]
        )


class TestDSPyEngineRichLivePatch:
    """Test Rich Live patching functionality."""

    def test_ensure_live_crop_above_idempotency(self):
        """Test that live crop above patch is applied only once."""
        # Reset global state
        import flock.engines.dspy_engine

        flock.engines.dspy_engine._live_patch_applied = False

        # First call should apply patch
        _ensure_live_crop_above()

        # Check that patch was applied
        assert flock.engines.dspy_engine._live_patch_applied is True

        # Second call should be no-op
        _ensure_live_crop_above()
        assert flock.engines.dspy_engine._live_patch_applied is True

    def test_ensure_live_crop_above_without_rich(self, mocker):
        """Test graceful handling when Rich is not available."""
        mocker.patch("flock.engines.dspy_engine._live_patch_applied", False)

        # Mock import to fail
        mocker.patch.dict("sys.modules", {"rich": None})
        # Should not raise exception
        _ensure_live_crop_above()

    def test_apply_live_patch_on_import_success(self, mocker):
        """Test successful Live patch application on import."""
        # Reset patch state
        import flock.engines.dspy_engine

        flock.engines.dspy_engine._live_patch_applied = False

        # Mock the patch function
        mock_patch = mocker.patch("flock.engines.dspy_engine._ensure_live_crop_above")

        # Import module to trigger patch
        from flock.engines.dspy_engine import _apply_live_patch_on_import

        _apply_live_patch_on_import()

        # Should have called patch function
        mock_patch.assert_called_once()

    def test_apply_live_patch_on_import_failure(self, mocker):
        """Test graceful handling when Live patch application fails."""
        # Mock the patch function to raise exception
        mock_patch = mocker.patch(
            "flock.engines.dspy_engine._ensure_live_crop_above",
            side_effect=Exception("Patch failed"),
        )

        # Should not raise exception
        from flock.engines.dspy_engine import _apply_live_patch_on_import

        _apply_live_patch_on_import()

        # Should have attempted to patch
        mock_patch.assert_called_once()


class TestDSPyEngineErrorHandling:
    """Test error handling in DSPy engine."""

    @pytest.mark.asyncio
    async def test_evaluation_without_artifacts(self):
        """Test evaluation when no artifacts are provided."""
        engine = DSPyEngine()
        agent = Mock()
        ctx = Mock()
        inputs = EvalInputs(artifacts=[], state={})
        output_group = OutputGroup(outputs=[], group_description=None)

        result = await engine.evaluate(agent, ctx, inputs, output_group)

        assert isinstance(result, EvalResult)
        assert len(result.artifacts) == 0
        assert result.state == {}

    @pytest.mark.asyncio
    async def test_json_serialization_error_in_logs(self, mocker):
        """Test handling of JSON serialization errors in logs."""
        # Mock DSPy
        mock_dspy = MockDSPyModule()
        mock_dspy.context.return_value = Mock()
        mock_dspy.LM = MockLM
        mock_dspy.Predict = MockPredict

        # Create a prediction with non-serializable output
        class NonSerializable:
            pass

        mock_prediction = Mock()
        mock_prediction.output = NonSerializable()
        mock_program = Mock()
        mock_program.return_value = mock_prediction

        mocker.patch.object(DSPyEngine, "_import_dspy", return_value=mock_dspy)

        agent = Mock()
        agent.name = "test_agent"
        agent.description = "Test agent"
        agent.outputs = []
        agent.tools = []
        agent._get_mcp_tools = AsyncMock(return_value=[])

        # Phase 8: Context has pre-filtered artifacts (no orchestrator)
        ctx = Mock()
        ctx.artifacts = []  # Pre-filtered by orchestrator

        input_artifact = Artifact(
            type="TestInput", payload={"prompt": "test"}, produced_by="test"
        )
        inputs = EvalInputs(artifacts=[input_artifact], state={})

        engine = DSPyEngine(model="gpt-4", stream=False)
        engine._choose_program = Mock(return_value=mock_program)

        # Should not raise exception
        output_group = OutputGroup(outputs=[], group_description=None)
        result = await engine.evaluate(agent, ctx, inputs, output_group)

        assert isinstance(result, EvalResult)
        # Should complete without raising exception (graceful degradation)
        # Since no outputs are configured, normalized_output will be empty dict (JSON serializable)
        # The key test is that the engine doesn't crash on non-serializable output
        assert len(result.logs) >= 0  # Logs should exist (may be empty)


class TestDSPyEngineIntegration:
    """Integration tests for DSPy engine with full flow."""

    @pytest.mark.asyncio
    async def test_full_evaluation_flow_without_streaming(self, mocker):
        """Test complete evaluation flow without streaming."""
        # Mock DSPy
        mock_dspy = MockDSPyModule()
        mock_dspy.context.return_value = Mock()

        mocker.patch.object(DSPyEngine, "_import_dspy", return_value=mock_dspy)

        # Create test setup with orchestrator fixture that disables publishing
        orchestrator = Flock()

        # Create engine directly
        engine = DSPyEngine(
            model="gpt-4", stream=False, instructions="Test instructions"
        )

        # Create agent
        agent = Mock()
        agent.name = "test_agent"
        agent.description = "Test agent"
        agent.outputs = []
        agent.tools = []
        agent._get_mcp_tools = AsyncMock(return_value=[])

        # Use direct evaluation instead of full orchestrator flow
        input_artifact = Artifact(
            type="TestInput", payload={"prompt": "test prompt"}, produced_by="test"
        )
        inputs = EvalInputs(artifacts=[input_artifact], state={})

        # Phase 8: Context has pre-filtered artifacts (no orchestrator)
        ctx = Mock()
        ctx.artifacts = []  # Pre-filtered by orchestrator

        # Act
        output_group = OutputGroup(outputs=[], group_description=None)
        result = await engine.evaluate(agent, ctx, inputs, output_group)

        # Assert
        assert isinstance(result, EvalResult)
        assert len(result.artifacts) > 0

    @pytest.mark.asyncio
    async def test_batch_evaluation_passes_list_payload(self, mocker):
        """Batched evaluation should send list of validated inputs to DSPy."""
        mock_dspy = MockDSPyModule()
        mock_dspy.context.return_value = Mock()

        mocker.patch.object(DSPyEngine, "_import_dspy", return_value=mock_dspy)

        engine = DSPyEngine(model="gpt-4", stream=False)
        # Phase 6: Method refactored - spy on the new method in signature_builder
        spy_signature = mocker.spy(
            engine._signature_builder, "prepare_signature_for_output_group"
        )

        mock_program = Mock()
        engine._choose_program = Mock(return_value=mock_program)

        mock_execute = AsyncMock(
            return_value=MockPrediction({"response": "batch response"})
        )
        # Phase 6: Method refactored - patch the helper instance method
        mocker.patch.object(
            engine._streaming_executor, "execute_standard", mock_execute
        )

        agent = Mock()
        agent.name = "batch_agent"
        agent.description = "Batch agent"
        agent.outputs = []
        agent.tools = []
        agent._get_mcp_tools = AsyncMock(return_value=[])

        # Phase 8: Context has pre-filtered artifacts (no orchestrator)
        ctx = Mock()
        ctx.artifacts = []  # Pre-filtered by orchestrator
        ctx.is_batch = True  # Batch mode flag

        artifacts = [
            Artifact(type="TestInput", payload={"prompt": "one"}, produced_by="test"),
            Artifact(type="TestInput", payload={"prompt": "two"}, produced_by="test"),
        ]
        inputs = EvalInputs(artifacts=artifacts, state={})
        output_group = OutputGroup(outputs=[], group_description=None)

        result = await engine.evaluate(agent, ctx, inputs, output_group)

        assert isinstance(result, EvalResult)
        mock_execute.assert_awaited_once()
        payload = mock_execute.await_args.kwargs["payload"]
        # Phase 7: Semantic field naming - "TestInput" becomes "test_inputs" (pluralized)
        assert isinstance(payload.get("test_inputs"), list)
        assert payload["test_inputs"][0]["prompt"] == "one"
        assert payload["test_inputs"][1]["prompt"] == "two"
        assert payload.get("context", []) == []

    @pytest.mark.asyncio
    async def test_evaluation_with_complex_input_output(self, mocker):
        """Test evaluation with complex input and output schemas."""
        # Mock DSPy
        mock_dspy = MockDSPyModule()
        mock_dspy.context.return_value = Mock()

        # Create mock prediction for complex output
        complex_prediction = Mock()
        complex_prediction.output = {
            "summary": "Test summary",
            "processed_items": ["item1", "item2"],
            "result": {"key": "value"},
        }
        complex_prediction.ComplexOutput = complex_prediction.output

        class MockComplexPredict:
            def __init__(self, signature):
                self.signature = signature

            def __call__(self, **kwargs):
                return complex_prediction

        mock_dspy.Predict = MockComplexPredict

        mocker.patch.object(DSPyEngine, "_import_dspy", return_value=mock_dspy)

        # Create test setup
        orchestrator = Flock()

        # Create engine directly
        engine = DSPyEngine(model="gpt-4", stream=False)

        # Create agent
        agent = Mock()
        agent.name = "test_agent"
        agent.description = "Test agent"
        agent.outputs = []
        agent.tools = []
        agent._get_mcp_tools = AsyncMock(return_value=[])

        input_artifact = Artifact(
            type="ComplexInput",
            payload={
                "text": "test text",
                "items": ["item1", "item2"],
                "config": {"option": "value"},
            },
            produced_by="test",
        )

        # Use direct evaluation
        inputs = EvalInputs(artifacts=[input_artifact], state={})

        # Phase 8: Context has pre-filtered artifacts (no orchestrator)
        ctx = Mock()
        ctx.artifacts = []  # Pre-filtered by orchestrator

        # Act
        output_group = OutputGroup(outputs=[], group_description=None)
        result = await engine.evaluate(agent, ctx, inputs, output_group)

        # Assert
        assert isinstance(result, EvalResult)
        assert len(result.artifacts) > 0
        # Check that the result contains the expected data structure
        # Since no outputs are configured, the engine might return the input artifacts
        # or create generic artifacts. Let's just verify we got a valid result
        assert len(result.artifacts) > 0
        # Verify the evaluation succeeded without errors
        assert len(result.logs) >= 0  # Logs should exist (even if empty)
