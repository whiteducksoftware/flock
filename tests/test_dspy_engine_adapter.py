"""Tests for DSPy adapter configuration in DSPyEngine.

This test suite verifies that DSPyEngine correctly:
- Accepts adapter parameter
- Passes adapter to dspy.context()
- Defaults to ChatAdapter when not specified
- Works with JSONAdapter for better structured outputs
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from flock.core import Flock, OutputGroup
from flock.engines.dspy_engine import DSPyEngine
from flock.registry import flock_type
from flock.utils.runtime import EvalInputs
from pydantic import BaseModel, Field


# Test artifact types
@flock_type(name="AdapterTestInput")
class AdapterTestInput(BaseModel):
    text: str = Field(description="Input text")


@flock_type(name="AdapterTestOutput")
class AdapterTestOutput(BaseModel):
    result: str = Field(description="Output result")


class TestDSPyEngineAdapter:
    """Test adapter configuration in DSPyEngine."""

    @pytest.mark.asyncio
    async def test_dspy_engine_defaults_to_none_adapter(self):
        """DSPyEngine should have adapter=None by default (will use DSPy's ChatAdapter)."""
        engine = DSPyEngine(model="gpt-4")
        assert engine.adapter is None

    @pytest.mark.asyncio
    async def test_dspy_engine_accepts_custom_adapter(self):
        """DSPyEngine should accept and store custom adapter."""
        try:
            from dspy.adapters import JSONAdapter

            engine = DSPyEngine(model="gpt-4", adapter=JSONAdapter())
            assert engine.adapter is not None
            assert isinstance(engine.adapter, JSONAdapter)
        except ImportError:
            pytest.skip("DSPy adapters not available")

    @pytest.mark.asyncio
    async def test_dspy_engine_accepts_chat_adapter(self):
        """DSPyEngine should accept ChatAdapter explicitly."""
        try:
            from dspy.adapters import ChatAdapter

            engine = DSPyEngine(model="gpt-4", adapter=ChatAdapter())
            assert engine.adapter is not None
            assert isinstance(engine.adapter, ChatAdapter)
        except ImportError:
            pytest.skip("DSPy adapters not available")

    @pytest.mark.asyncio
    async def test_adapter_passed_to_dspy_context(self, mocker):
        """Adapter should be passed to dspy.context() when executing."""
        try:
            from dspy.adapters import JSONAdapter
        except ImportError:
            pytest.skip("DSPy adapters not available")

        # Use MockDSPyModule pattern from test_dspy_engine.py
        from tests.test_dspy_engine import MockDSPyModule

        # Track context calls
        context_calls = []

        class TrackingMockContext:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                context_calls.append(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_dspy = MockDSPyModule()
        mock_dspy.context = TrackingMockContext

        mocker.patch(
            "flock.engines.dspy_engine.DSPyEngine._import_dspy", return_value=mock_dspy
        )

        # Create engine with JSONAdapter
        engine = DSPyEngine(model="gpt-4", adapter=JSONAdapter(), stream=False)

        # Create mock agent and context
        agent = mocker.MagicMock()
        agent.name = "test_agent"
        agent.description = "Test agent"
        agent.tools = []
        agent._get_mcp_tools = AsyncMock(return_value=[])

        ctx = mocker.MagicMock()
        ctx.artifacts = []
        ctx.correlation_id = None

        # Create test inputs with actual artifact
        from flock.core.artifacts import Artifact

        input_artifact = Artifact(
            type="AdapterTestInput",
            payload={"text": "test input"},
            produced_by="test",
        )
        inputs = EvalInputs(artifacts=[input_artifact], state={})

        # Create output group
        from flock.core.agent import AgentOutput
        from flock.core.artifacts import ArtifactSpec

        output_spec = ArtifactSpec(
            type_name="AdapterTestOutput", model=AdapterTestOutput
        )
        output_decl = AgentOutput(spec=output_spec, default_visibility=None)
        output_group = OutputGroup(outputs=[output_decl])

        # Execute engine
        await engine.evaluate(agent, ctx, inputs, output_group)

        # Verify dspy.context() was called with adapter
        assert len(context_calls) > 0
        last_call = context_calls[-1]
        assert "adapter" in last_call
        assert isinstance(last_call["adapter"], JSONAdapter)

    @pytest.mark.asyncio
    async def test_default_adapter_used_when_none_specified(self, mocker):
        """When adapter is None, ChatAdapter should be used."""
        try:
            from dspy.adapters import ChatAdapter
        except ImportError:
            pytest.skip("DSPy adapters not available")

        # Use MockDSPyModule pattern from test_dspy_engine.py
        from tests.test_dspy_engine import MockDSPyModule

        # Track context calls
        context_calls = []

        class TrackingMockContext:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
                context_calls.append(kwargs)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        mock_dspy = MockDSPyModule()
        mock_dspy.context = TrackingMockContext

        mocker.patch(
            "flock.engines.dspy_engine.DSPyEngine._import_dspy", return_value=mock_dspy
        )

        # Create engine without adapter (should default to ChatAdapter)
        engine = DSPyEngine(model="gpt-4", stream=False)
        assert engine.adapter is None

        # Create mock agent and context
        agent = mocker.MagicMock()
        agent.name = "test_agent"
        agent.description = "Test agent"
        agent.tools = []
        agent._get_mcp_tools = AsyncMock(return_value=[])

        ctx = mocker.MagicMock()
        ctx.artifacts = []
        ctx.correlation_id = None

        # Create test inputs with actual artifact
        from flock.core.artifacts import Artifact

        input_artifact = Artifact(
            type="AdapterTestInput",
            payload={"text": "test input"},
            produced_by="test",
        )
        inputs = EvalInputs(artifacts=[input_artifact], state={})

        # Create output group
        from flock.core.agent import AgentOutput
        from flock.core.artifacts import ArtifactSpec

        output_spec = ArtifactSpec(
            type_name="AdapterTestOutput", model=AdapterTestOutput
        )
        output_decl = AgentOutput(spec=output_spec, default_visibility=None)
        output_group = OutputGroup(outputs=[output_decl])

        # Execute engine
        await engine.evaluate(agent, ctx, inputs, output_group)

        # Verify dspy.context() was called with ChatAdapter
        assert len(context_calls) > 0
        last_call = context_calls[-1]
        assert "adapter" in last_call
        assert isinstance(last_call["adapter"], ChatAdapter)

    @pytest.mark.asyncio
    async def test_json_adapter_enables_native_function_calling(self):
        """JSONAdapter should have use_native_function_calling=True by default."""
        try:
            from dspy.adapters import JSONAdapter

            engine = DSPyEngine(model="gpt-4", adapter=JSONAdapter())
            assert engine.adapter is not None
            assert engine.adapter.use_native_function_calling is True
        except ImportError:
            pytest.skip("DSPy adapters not available")
        except AttributeError:
            # If JSONAdapter doesn't have this attribute, skip test
            pytest.skip("JSONAdapter doesn't expose use_native_function_calling")

    @pytest.mark.asyncio
    async def test_backward_compatibility_no_adapter_specified(self):
        """Existing code without adapter parameter should work unchanged."""
        # This test ensures backward compatibility
        engine = DSPyEngine(model="gpt-4")
        assert engine.adapter is None  # Will use DSPy's default (ChatAdapter)

        # Engine should still be usable
        assert engine.model == "gpt-4"
        assert engine.stream is not None  # Has default value

