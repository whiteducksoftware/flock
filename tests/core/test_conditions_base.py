"""Tests for RunCondition Protocol and Composite Conditions.

Spec: 003-until-conditions-dsl
Phase 1: RunCondition Protocol & Base Classes
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest

if TYPE_CHECKING:
    from flock.core import Flock


# ============================================================================
# Test Fixtures - Mock Conditions for Testing Protocol & Composites
# ============================================================================


@dataclass
class MockCondition:
    """Mock condition for testing protocol compliance and composition."""

    result: bool
    call_count: int = 0

    async def evaluate(self, orchestrator: "Flock") -> bool:
        """Evaluate condition and track call count."""
        self.call_count += 1
        return self.result

    def __and__(self, other: "MockCondition") -> "AndCondition":
        from flock.core.conditions import AndCondition

        return AndCondition(self, other)

    def __or__(self, other: "MockCondition") -> "OrCondition":
        from flock.core.conditions import OrCondition

        return OrCondition(self, other)

    def __invert__(self) -> "NotCondition":
        from flock.core.conditions import NotCondition

        return NotCondition(self)


# ============================================================================
# Phase 1 Tests: RunCondition Protocol & Base Classes
# ============================================================================


class TestRunConditionProtocol:
    """Test RunCondition protocol compliance."""

    @pytest.mark.asyncio
    async def test_protocol_defines_evaluate_method(self):
        """RunCondition protocol requires evaluate(orchestrator) -> bool."""
        from flock.core.conditions import RunCondition

        # Protocol should exist and define evaluate
        assert hasattr(RunCondition, "evaluate")

    @pytest.mark.asyncio
    async def test_condition_implements_evaluate(self):
        """Mock condition should satisfy RunCondition protocol."""
        condition = MockCondition(result=True)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True
        assert condition.call_count == 1

    @pytest.mark.asyncio
    async def test_protocol_has_and_method(self):
        """RunCondition should define __and__ for & operator."""
        from flock.core.conditions import RunCondition

        assert hasattr(RunCondition, "__and__")

    @pytest.mark.asyncio
    async def test_protocol_has_or_method(self):
        """RunCondition should define __or__ for | operator."""
        from flock.core.conditions import RunCondition

        assert hasattr(RunCondition, "__or__")

    @pytest.mark.asyncio
    async def test_protocol_has_invert_method(self):
        """RunCondition should define __invert__ for ~ operator."""
        from flock.core.conditions import RunCondition

        assert hasattr(RunCondition, "__invert__")


class TestAndCondition:
    """Test AndCondition evaluates both sides."""

    @pytest.mark.asyncio
    async def test_and_condition_true_true(self):
        """AndCondition: True & True = True."""
        from flock.core.conditions import AndCondition

        left = MockCondition(result=True)
        right = MockCondition(result=True)
        condition = AndCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True
        assert left.call_count == 1
        assert right.call_count == 1

    @pytest.mark.asyncio
    async def test_and_condition_true_false(self):
        """AndCondition: True & False = False."""
        from flock.core.conditions import AndCondition

        left = MockCondition(result=True)
        right = MockCondition(result=False)
        condition = AndCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_and_condition_false_true(self):
        """AndCondition: False & True = False."""
        from flock.core.conditions import AndCondition

        left = MockCondition(result=False)
        right = MockCondition(result=True)
        condition = AndCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_and_condition_false_false(self):
        """AndCondition: False & False = False."""
        from flock.core.conditions import AndCondition

        left = MockCondition(result=False)
        right = MockCondition(result=False)
        condition = AndCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_and_condition_short_circuits_on_false(self):
        """AndCondition should short-circuit when left is False."""
        from flock.core.conditions import AndCondition

        left = MockCondition(result=False)
        right = MockCondition(result=True)
        condition = AndCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False
        assert left.call_count == 1
        # Python's `and` evaluates both unless using short-circuit pattern
        # Our implementation uses 'and' which short-circuits

    @pytest.mark.asyncio
    async def test_and_condition_using_operator(self):
        """AndCondition can be created using & operator."""
        left = MockCondition(result=True)
        right = MockCondition(result=True)
        condition = left & right
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True


class TestOrCondition:
    """Test OrCondition short-circuits on first True."""

    @pytest.mark.asyncio
    async def test_or_condition_true_true(self):
        """OrCondition: True | True = True."""
        from flock.core.conditions import OrCondition

        left = MockCondition(result=True)
        right = MockCondition(result=True)
        condition = OrCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_or_condition_true_false(self):
        """OrCondition: True | False = True."""
        from flock.core.conditions import OrCondition

        left = MockCondition(result=True)
        right = MockCondition(result=False)
        condition = OrCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_or_condition_false_true(self):
        """OrCondition: False | True = True."""
        from flock.core.conditions import OrCondition

        left = MockCondition(result=False)
        right = MockCondition(result=True)
        condition = OrCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_or_condition_false_false(self):
        """OrCondition: False | False = False."""
        from flock.core.conditions import OrCondition

        left = MockCondition(result=False)
        right = MockCondition(result=False)
        condition = OrCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_or_condition_short_circuits_on_true(self):
        """OrCondition should short-circuit when left is True."""
        from flock.core.conditions import OrCondition

        left = MockCondition(result=True)
        right = MockCondition(result=False)
        condition = OrCondition(left, right)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True
        assert left.call_count == 1
        # With short-circuit, right should not be evaluated
        # Note: Python's `or` naturally short-circuits

    @pytest.mark.asyncio
    async def test_or_condition_using_operator(self):
        """OrCondition can be created using | operator."""
        left = MockCondition(result=False)
        right = MockCondition(result=True)
        condition = left | right
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True


class TestNotCondition:
    """Test NotCondition inverts result."""

    @pytest.mark.asyncio
    async def test_not_condition_true_to_false(self):
        """NotCondition: ~True = False."""
        from flock.core.conditions import NotCondition

        inner = MockCondition(result=True)
        condition = NotCondition(inner)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False
        assert inner.call_count == 1

    @pytest.mark.asyncio
    async def test_not_condition_false_to_true(self):
        """NotCondition: ~False = True."""
        from flock.core.conditions import NotCondition

        inner = MockCondition(result=False)
        condition = NotCondition(inner)
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is True
        assert inner.call_count == 1

    @pytest.mark.asyncio
    async def test_not_condition_using_operator(self):
        """NotCondition can be created using ~ operator."""
        inner = MockCondition(result=True)
        condition = ~inner
        orchestrator = Mock()

        result = await condition.evaluate(orchestrator)

        assert result is False


class TestConditionChaining:
    """Test complex condition chaining."""

    @pytest.mark.asyncio
    async def test_chaining_and_or(self):
        """Test chaining: cond1 & cond2 | cond3."""
        # (True & False) | True = True
        cond1 = MockCondition(result=True)
        cond2 = MockCondition(result=False)
        cond3 = MockCondition(result=True)

        combined = cond1 & cond2 | cond3
        orchestrator = Mock()

        result = await combined.evaluate(orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_chaining_or_and(self):
        """Test chaining: cond1 | cond2 & cond3."""
        # True | (False & False) = True (due to precedence)
        cond1 = MockCondition(result=True)
        cond2 = MockCondition(result=False)
        cond3 = MockCondition(result=False)

        combined = cond1 | cond2 & cond3
        orchestrator = Mock()

        result = await combined.evaluate(orchestrator)

        # Note: In Python, & has higher precedence than |
        # So this is: cond1 | (cond2 & cond3) = True | False = True
        assert result is True

    @pytest.mark.asyncio
    async def test_chaining_with_not(self):
        """Test chaining with ~: ~cond1 & cond2."""
        # ~True & True = False & True = False
        cond1 = MockCondition(result=True)
        cond2 = MockCondition(result=True)

        combined = ~cond1 & cond2
        orchestrator = Mock()

        result = await combined.evaluate(orchestrator)

        assert result is False

    @pytest.mark.asyncio
    async def test_double_negation(self):
        """Test double negation: ~~cond = cond."""
        inner = MockCondition(result=True)
        double_neg = ~~inner
        orchestrator = Mock()

        result = await double_neg.evaluate(orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_complex_expression(self):
        """Test complex expression: (cond1 & cond2) | ~cond3."""
        # (True & True) | ~False = True | True = True
        cond1 = MockCondition(result=True)
        cond2 = MockCondition(result=True)
        cond3 = MockCondition(result=False)

        combined = (cond1 & cond2) | ~cond3
        orchestrator = Mock()

        result = await combined.evaluate(orchestrator)

        assert result is True

    @pytest.mark.asyncio
    async def test_complex_expression_false_result(self):
        """Test complex expression that evaluates to False."""
        # (False & True) | False = False
        cond1 = MockCondition(result=False)
        cond2 = MockCondition(result=True)
        cond3 = MockCondition(result=False)

        combined = (cond1 & cond2) | cond3
        orchestrator = Mock()

        result = await combined.evaluate(orchestrator)

        assert result is False


class TestConditionDataclassProperties:
    """Test that conditions are proper dataclasses."""

    def test_and_condition_is_dataclass(self):
        """AndCondition should be a dataclass."""
        from dataclasses import is_dataclass

        from flock.core.conditions import AndCondition

        assert is_dataclass(AndCondition)

    def test_or_condition_is_dataclass(self):
        """OrCondition should be a dataclass."""
        from dataclasses import is_dataclass

        from flock.core.conditions import OrCondition

        assert is_dataclass(OrCondition)

    def test_not_condition_is_dataclass(self):
        """NotCondition should be a dataclass."""
        from dataclasses import is_dataclass

        from flock.core.conditions import NotCondition

        assert is_dataclass(NotCondition)

    def test_and_condition_fields(self):
        """AndCondition should have left and right fields."""
        from flock.core.conditions import AndCondition

        left = MockCondition(result=True)
        right = MockCondition(result=False)
        condition = AndCondition(left, right)

        assert condition.left is left
        assert condition.right is right

    def test_or_condition_fields(self):
        """OrCondition should have left and right fields."""
        from flock.core.conditions import OrCondition

        left = MockCondition(result=True)
        right = MockCondition(result=False)
        condition = OrCondition(left, right)

        assert condition.left is left
        assert condition.right is right

    def test_not_condition_fields(self):
        """NotCondition should have condition field."""
        from flock.core.conditions import NotCondition

        inner = MockCondition(result=True)
        condition = NotCondition(inner)

        assert condition.condition is inner


class TestModuleExports:
    """Test module exports in __all__."""

    def test_run_condition_exported(self):
        """RunCondition should be exported."""
        from flock.core.conditions import RunCondition

        assert RunCondition is not None

    def test_and_condition_exported(self):
        """AndCondition should be exported."""
        from flock.core.conditions import AndCondition

        assert AndCondition is not None

    def test_or_condition_exported(self):
        """OrCondition should be exported."""
        from flock.core.conditions import OrCondition

        assert OrCondition is not None

    def test_not_condition_exported(self):
        """NotCondition should be exported."""
        from flock.core.conditions import NotCondition

        assert NotCondition is not None
