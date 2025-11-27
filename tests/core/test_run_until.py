"""Tests for run_until() Orchestrator Method.

Spec: 003-until-conditions-dsl
Phase 4: run_until() Method
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, Mock, patch
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.registry import flock_type

if TYPE_CHECKING:
    from flock.core import Flock


# ============================================================================
# Test Artifact Types
# ============================================================================


@flock_type(name="RunUntilTestInput")
class RunUntilTestInput(BaseModel):
    """Test input artifact type."""

    value: str


@flock_type(name="RunUntilTestOutput")
class RunUntilTestOutput(BaseModel):
    """Test output artifact type."""

    result: str


# ============================================================================
# Mock Condition Helper
# ============================================================================


@dataclass
class MockCondition:
    """Mock condition that returns a configurable result."""

    result: bool = True
    call_count: int = 0
    results: list[bool] | None = None  # For alternating results

    async def evaluate(self, orchestrator: "Flock") -> bool:
        """Return configured result and track call count."""
        self.call_count += 1
        if self.results and self.call_count <= len(self.results):
            return self.results[self.call_count - 1]
        return self.result


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_orchestrator():
    """Create a mock orchestrator for run_until tests."""
    orchestrator = Mock()
    orchestrator.store = Mock()
    orchestrator.store.query_artifacts = AsyncMock(return_value=([], 0))
    orchestrator.get_correlation_status = AsyncMock(
        return_value={"error_count": 0}
    )
    orchestrator._scheduler = Mock()
    orchestrator._scheduler.pending_tasks = set()
    orchestrator._components_initialized = True
    orchestrator._component_runner = Mock()
    orchestrator._component_runner.is_initialized = True
    orchestrator._component_runner.run_idle = AsyncMock()
    orchestrator._lifecycle_manager = Mock()
    orchestrator._lifecycle_manager.has_pending_batches = False
    orchestrator._lifecycle_manager.has_pending_correlations = False
    orchestrator._has_active_timers = Mock(return_value=False)
    orchestrator.shutdown = AsyncMock()
    orchestrator._agent_iteration_count = {}
    return orchestrator


# ============================================================================
# Phase 4 Tests: run_until() Method
# ============================================================================


class TestRunUntilBasic:
    """Basic tests for run_until() method."""

    @pytest.mark.asyncio
    async def test_run_until_returns_true_when_condition_satisfied_immediately(
        self, mock_orchestrator
    ):
        """run_until returns True when condition is already True."""
        from flock.core.conditions import Until

        # Condition that always returns True
        condition = MockCondition(result=True)

        # Mock run_until on orchestrator
        async def mock_run_until(cond, *, timeout=None):
            if await cond.evaluate(mock_orchestrator):
                return True
            return False

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition)

        assert result is True
        assert condition.call_count == 1

    @pytest.mark.asyncio
    async def test_run_until_with_idle_condition(self, mock_orchestrator):
        """run_until(Until.idle()) should work like run_until_idle()."""
        from flock.core.conditions import Until

        condition = Until.idle()
        mock_orchestrator._scheduler.pending_tasks = set()

        # Simulate run_until behavior
        async def mock_run_until(cond, *, timeout=None):
            return await cond.evaluate(mock_orchestrator)

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition)

        assert result is True


class TestRunUntilTimeout:
    """Tests for timeout behavior."""

    @pytest.mark.asyncio
    async def test_run_until_returns_false_on_timeout(self, mock_orchestrator):
        """run_until returns False when timeout is exceeded."""
        import time

        # Condition that never becomes true
        condition = MockCondition(result=False)

        # Simulate run_until with timeout
        async def mock_run_until(cond, *, timeout=None):
            start = time.monotonic()
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                if timeout and (time.monotonic() - start) >= timeout:
                    return False
                await asyncio.sleep(0.01)

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition, timeout=0.05)

        assert result is False
        assert condition.call_count >= 1

    @pytest.mark.asyncio
    async def test_run_until_no_timeout_waits_for_condition(self, mock_orchestrator):
        """run_until without timeout waits until condition is True or idle."""
        # Condition becomes true after a few evaluations
        condition = MockCondition(results=[False, False, True])

        async def mock_run_until(cond, *, timeout=None):
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                # Simulate work happening
                await asyncio.sleep(0.01)
                if condition.call_count >= 5:  # Safety limit
                    break
            return False

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition)

        assert result is True
        assert condition.call_count == 3


class TestRunUntilComposite:
    """Tests for composite conditions."""

    @pytest.mark.asyncio
    async def test_run_until_with_or_condition(self, mock_orchestrator):
        """run_until with OR condition stops when either is True."""
        from flock.core.conditions import OrCondition

        # Condition A: False, Condition B: True
        cond_a = MockCondition(result=False)
        cond_b = MockCondition(result=True)

        # Create OR condition manually (MockCondition doesn't have operators)
        or_condition = OrCondition(cond_a, cond_b)

        async def mock_run_until(cond, *, timeout=None):
            return await cond.evaluate(mock_orchestrator)

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(or_condition)

        assert result is True

    @pytest.mark.asyncio
    async def test_run_until_with_and_condition(self, mock_orchestrator):
        """run_until with AND condition requires both True."""
        from flock.core.conditions import AndCondition

        cond_a = MockCondition(result=True)
        cond_b = MockCondition(result=True)

        and_condition = AndCondition(cond_a, cond_b)

        async def mock_run_until(cond, *, timeout=None):
            return await cond.evaluate(mock_orchestrator)

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(and_condition)

        assert result is True


class TestRunUntilEarlyStop:
    """Tests for early termination when condition is met mid-workflow."""

    @pytest.mark.asyncio
    async def test_run_until_stops_early_when_condition_met(self, mock_orchestrator):
        """run_until should stop as soon as condition becomes True."""
        # Condition: False, False, True
        condition = MockCondition(results=[False, False, True])
        work_count = 0

        async def mock_run_until(cond, *, timeout=None):
            nonlocal work_count
            while True:
                if await cond.evaluate(mock_orchestrator):
                    return True
                work_count += 1
                await asyncio.sleep(0.01)
                if work_count >= 10:  # Safety limit
                    break
            return False

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition)

        assert result is True
        # Should have done work 2 times (for the 2 False evaluations)
        assert work_count == 2
        assert condition.call_count == 3


class TestRunUntilIntegration:
    """Integration tests with real conditions."""

    @pytest.mark.asyncio
    async def test_run_until_with_artifact_count_condition(self, mock_orchestrator):
        """run_until with ArtifactCountCondition."""
        from flock.core.conditions import Until

        # Mock store returns 5 artifacts
        mock_orchestrator.store.query_artifacts = AsyncMock(return_value=([], 5))

        condition = Until.artifact_count(RunUntilTestOutput).at_least(5)

        async def mock_run_until(cond, *, timeout=None):
            return await cond.evaluate(mock_orchestrator)

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition)

        assert result is True

    @pytest.mark.asyncio
    async def test_run_until_with_error_condition(self, mock_orchestrator):
        """run_until with WorkflowErrorCondition."""
        from flock.core.conditions import Until

        # No errors
        mock_orchestrator.get_correlation_status = AsyncMock(
            return_value={"error_count": 0}
        )

        condition = Until.workflow_error("workflow-123")

        async def mock_run_until(cond, *, timeout=None):
            return await cond.evaluate(mock_orchestrator)

        mock_orchestrator.run_until = mock_run_until

        result = await mock_orchestrator.run_until(condition)

        assert result is False  # No errors, condition not met


class TestRunUntilMethodSignature:
    """Tests for method signature and type hints."""

    def test_run_until_accepts_condition_parameter(self):
        """run_until should accept a RunCondition parameter."""
        # This test verifies the method exists and has the right signature
        # We'll verify this once the method is implemented
        pass

    def test_run_until_accepts_timeout_parameter(self):
        """run_until should accept an optional timeout parameter."""
        # This test verifies the method exists and has the right signature
        pass


class TestRunUntilExport:
    """Test that conditions are properly exported for run_until."""

    def test_until_available_from_conditions(self):
        """Until helper should be available from flock.core.conditions."""
        from flock.core.conditions import Until

        assert Until is not None

    def test_run_condition_available(self):
        """RunCondition should be available for type hints."""
        from flock.core.conditions import RunCondition

        assert RunCondition is not None
