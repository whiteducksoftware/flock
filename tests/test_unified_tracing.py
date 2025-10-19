"""Tests for unified tracing with traced_run() context manager."""

import os
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.registry import flock_type


@flock_type
class TestInput(BaseModel):
    value: str


@flock_type
class TestOutput(BaseModel):
    result: str


@pytest.mark.asyncio
async def test_traced_run_creates_parent_span(orchestrator):
    """Test that traced_run() creates a parent span for all operations."""
    with patch("flock.orchestrator.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        async with orchestrator.traced_run("test_workflow"):
            pass

        # Verify span was created with correct name
        mock_tracer.start_as_current_span.assert_called_once_with("test_workflow")

        # Verify workflow attributes were set
        assert mock_span.set_attribute.call_count >= 3
        attribute_calls = {
            call[0][0]: call[0][1] for call in mock_span.set_attribute.call_args_list
        }
        assert attribute_calls["flock.workflow"] is True
        assert attribute_calls["workflow.name"] == "test_workflow"
        assert "workflow.flock_id" in attribute_calls


@pytest.mark.asyncio
async def test_traced_run_yields_span_for_custom_attributes(orchestrator):
    """Test that traced_run() yields the span for custom attributes."""
    with patch("flock.orchestrator.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        async with orchestrator.traced_run("custom_workflow") as span:
            # User should be able to set custom attributes
            span.set_attribute("custom.key", "custom_value")

        # Verify custom attribute was set on the span
        span.set_attribute.assert_any_call("custom.key", "custom_value")


@pytest.mark.asyncio
async def test_traced_run_handles_exceptions(orchestrator):
    """Test that traced_run() properly handles and records exceptions."""
    with patch("flock.orchestrator.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        test_error = ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            async with orchestrator.traced_run("error_workflow"):
                raise test_error

        # Verify error status was set
        from opentelemetry.trace import StatusCode

        mock_span.set_status.assert_called()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.ERROR

        # Verify exception was recorded
        mock_span.record_exception.assert_called_once_with(test_error)


@pytest.mark.asyncio
async def test_traced_run_restores_previous_workflow_span(orchestrator):
    """Test that nested traced_run calls properly restore previous workflow span."""
    with patch("flock.orchestrator.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = Mock()
        mock_span1 = Mock()
        mock_span2 = Mock()
        mock_span1.__enter__ = Mock(return_value=mock_span1)
        mock_span1.__exit__ = Mock(return_value=None)
        mock_span2.__enter__ = Mock(return_value=mock_span2)
        mock_span2.__exit__ = Mock(return_value=None)

        mock_tracer.start_as_current_span.side_effect = [mock_span1, mock_span2]
        mock_get_tracer.return_value = mock_tracer

        # Initial state: no workflow span
        assert orchestrator._workflow_span is None

        async with orchestrator.traced_run("outer"):
            assert orchestrator._workflow_span == mock_span1

            async with orchestrator.traced_run("inner"):
                assert orchestrator._workflow_span == mock_span2

            # After inner exits, should restore outer
            assert orchestrator._workflow_span == mock_span1

        # After outer exits, should restore to None
        assert orchestrator._workflow_span is None


@pytest.mark.asyncio
async def test_traced_run_default_workflow_name(orchestrator):
    """Test that traced_run() uses default name if not provided."""
    with patch("flock.orchestrator.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        async with orchestrator.traced_run():
            pass

        # Should use default "workflow" name
        mock_tracer.start_as_current_span.assert_called_once_with("workflow")


@pytest.mark.asyncio
async def test_traced_run_sets_success_status(orchestrator):
    """Test that traced_run() sets OK status on successful completion."""
    with patch("flock.orchestrator.tracing.trace.get_tracer") as mock_get_tracer:
        mock_tracer = Mock()
        mock_span = Mock()
        mock_span.__enter__ = Mock(return_value=mock_span)
        mock_span.__exit__ = Mock(return_value=None)
        mock_tracer.start_as_current_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        async with orchestrator.traced_run("success_workflow"):
            pass

        # Verify success status was set
        from opentelemetry.trace import StatusCode

        mock_span.set_status.assert_called()
        status_call = mock_span.set_status.call_args[0][0]
        assert status_call.status_code == StatusCode.OK


@pytest.mark.asyncio
async def test_auto_workflow_trace_disabled_by_default(orchestrator):
    """Test that auto-workflow tracing is disabled by default."""
    assert orchestrator._auto_workflow_enabled is False


@pytest.mark.asyncio
async def test_auto_workflow_trace_env_var_true():
    """Test that FLOCK_AUTO_WORKFLOW_TRACE=true enables auto-workflow tracing."""
    with patch.dict(os.environ, {"FLOCK_AUTO_WORKFLOW_TRACE": "true"}):
        flock = Flock("test-model")
        assert flock._auto_workflow_enabled is True


@pytest.mark.asyncio
async def test_auto_workflow_trace_env_var_1():
    """Test that FLOCK_AUTO_WORKFLOW_TRACE=1 enables auto-workflow tracing."""
    with patch.dict(os.environ, {"FLOCK_AUTO_WORKFLOW_TRACE": "1"}):
        flock = Flock("test-model")
        assert flock._auto_workflow_enabled is True


@pytest.mark.asyncio
async def test_auto_workflow_trace_env_var_false():
    """Test that FLOCK_AUTO_WORKFLOW_TRACE=false disables auto-workflow tracing."""
    with patch.dict(os.environ, {"FLOCK_AUTO_WORKFLOW_TRACE": "false"}):
        flock = Flock("test-model")
        assert flock._auto_workflow_enabled is False
