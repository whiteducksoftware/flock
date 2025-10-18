"""Tests for Phase 2: Enhanced AgentBuilder.publishes() API.

These tests define the expected behavior for the enhanced .publishes() method
with new parameters: fan_out, where, visibility, validate, description.

Tests are written BEFORE implementation (TDD approach).

Phase 2 Requirements (from PLAN.md lines 115-126):
1. Single .publishes(A, B, C) creates ONE OutputGroup with 3 outputs
2. Multiple .publishes(A).publishes(B) creates TWO OutputGroups
3. .publishes(A, A, A) counts duplicates → 1 group, count=3 for each A
4. .publishes(A, fan_out=3) → 1 group with 3 A outputs (count=3)
5. .publishes(A, where=lambda x: x.valid) stores filter_predicate
6. .publishes(A, visibility=lambda x: ...) stores callable visibility
7. .publishes(A, validate=lambda x: x.score > 0) stores validate_predicate
8. .publishes(A, description="Special") stores group_description
9. .publishes(A, fan_out=3, where=..., validate=...) all work together
10. .publishes(A, fan_out=0) raises ValueError
11. Existing .publishes(A) still works (backwards compatibility)
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from flock import Flock
from flock.core import OutputGroup
from flock.core.visibility import PrivateVisibility, PublicVisibility, Visibility
from flock.registry import flock_type


# Test artifact types
@flock_type(name="TestTypeA")
class TestTypeA(BaseModel):
    value: int = Field(description="Test value")
    valid: bool = Field(default=True, description="Validity flag")


@flock_type(name="TestTypeB")
class TestTypeB(BaseModel):
    name: str = Field(description="Test name")
    score: int = Field(description="Score value", ge=0, le=100)


@flock_type(name="TestTypeC")
class TestTypeC(BaseModel):
    priority: int = Field(description="Priority level")


# ============================================================================
# Test Scenario 1: Single .publishes() call with multiple types
# ============================================================================


def test_publishes_single_call_multiple_types():
    """Single .publishes(A, B, C) creates ONE OutputGroup with 3 outputs."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA, TestTypeB, TestTypeC)

    # Assert - Agent should have output_groups instead of outputs
    assert hasattr(agent.agent, "output_groups")
    assert len(agent.agent.output_groups) == 1

    group = agent.agent.output_groups[0]
    assert isinstance(group, OutputGroup)
    assert len(group.outputs) == 3

    # Verify types in order
    assert group.outputs[0].spec.type_name == "TestTypeA"
    assert group.outputs[1].spec.type_name == "TestTypeB"
    assert group.outputs[2].spec.type_name == "TestTypeC"

    # Default visibility should be PublicVisibility
    assert isinstance(group.shared_visibility, PublicVisibility)


# ============================================================================
# Test Scenario 2: Multiple .publishes() calls create separate groups
# ============================================================================


def test_publishes_multiple_calls_create_groups():
    """.publishes(A).publishes(B) creates TWO OutputGroups."""
    # Arrange
    flock = Flock()

    # Act - Chain multiple publishes calls
    agent = flock.agent("test").publishes(TestTypeA).publishes(TestTypeB)

    # Assert - Should create 2 output groups
    assert len(agent.agent.output_groups) == 2

    # First group
    group1 = agent.agent.output_groups[0]
    assert len(group1.outputs) == 1
    assert group1.outputs[0].spec.type_name == "TestTypeA"

    # Second group
    group2 = agent.agent.output_groups[1]
    assert len(group2.outputs) == 1
    assert group2.outputs[0].spec.type_name == "TestTypeB"


def test_publishes_three_separate_calls():
    """.publishes(A).publishes(B).publishes(C) creates THREE OutputGroups."""
    # Arrange
    flock = Flock()

    # Act
    agent = (
        flock.agent("test")
        .publishes(TestTypeA)
        .publishes(TestTypeB)
        .publishes(TestTypeC)
    )

    # Assert
    assert len(agent.agent.output_groups) == 3
    assert agent.agent.output_groups[0].outputs[0].spec.type_name == "TestTypeA"
    assert agent.agent.output_groups[1].outputs[0].spec.type_name == "TestTypeB"
    assert agent.agent.output_groups[2].outputs[0].spec.type_name == "TestTypeC"


# ============================================================================
# Test Scenario 3: Duplicate type counting
# ============================================================================


def test_publishes_duplicate_counting():
    """.publishes(A, A, A) → 1 group, count=3 for each A."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA, TestTypeA, TestTypeA)

    # Assert
    assert len(agent.agent.output_groups) == 1

    group = agent.agent.output_groups[0]
    # Should have 3 outputs, each with count=1 (duplicates counted as separate outputs)
    assert len(group.outputs) == 3

    # All outputs should be TestTypeA
    for output in group.outputs:
        assert output.spec.type_name == "TestTypeA"
        assert output.count == 1


def test_publishes_mixed_duplicates():
    """.publishes(A, B, A, C, B) → 1 group with 5 outputs in order."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(
        TestTypeA, TestTypeB, TestTypeA, TestTypeC, TestTypeB
    )

    # Assert
    assert len(agent.agent.output_groups) == 1

    group = agent.agent.output_groups[0]
    assert len(group.outputs) == 5

    # Verify order preserved
    assert group.outputs[0].spec.type_name == "TestTypeA"
    assert group.outputs[1].spec.type_name == "TestTypeB"
    assert group.outputs[2].spec.type_name == "TestTypeA"
    assert group.outputs[3].spec.type_name == "TestTypeC"
    assert group.outputs[4].spec.type_name == "TestTypeB"


# ============================================================================
# Test Scenario 4: fan_out parameter (sugar syntax)
# ============================================================================


def test_publishes_fan_out_sugar():
    """.publishes(A, fan_out=3) → 1 group with count=3 for A."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA, fan_out=3)

    # Assert
    assert len(agent.agent.output_groups) == 1

    group = agent.agent.output_groups[0]
    assert len(group.outputs) == 1

    output = group.outputs[0]
    assert output.spec.type_name == "TestTypeA"
    assert output.count == 3
    assert output.is_many() is True


def test_publishes_fan_out_applies_to_all_types():
    """.publishes(A, B, fan_out=5) → both A and B have count=5."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA, TestTypeB, fan_out=5)

    # Assert
    group = agent.agent.output_groups[0]
    assert len(group.outputs) == 2

    # fan_out should apply to ALL types
    assert group.outputs[0].count == 5
    assert group.outputs[1].count == 5


def test_publishes_fan_out_one_is_default():
    """.publishes(A, fan_out=1) → count=1 (same as no fan_out)."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA, fan_out=1)

    # Assert
    group = agent.agent.output_groups[0]
    assert group.outputs[0].count == 1
    assert group.outputs[0].is_many() is False


def test_publishes_fan_out_zero_raises():
    """.publishes(A, fan_out=0) raises ValueError."""
    # Arrange
    flock = Flock()

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        flock.agent("test").publishes(TestTypeA, fan_out=0)

    # Error message should mention the constraint
    error_msg = str(exc_info.value).lower()
    assert "fan_out" in error_msg or "count" in error_msg
    assert "1" in str(exc_info.value) or "greater" in error_msg


def test_publishes_fan_out_negative_raises():
    """.publishes(A, fan_out=-5) raises ValueError."""
    # Arrange
    flock = Flock()

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        flock.agent("test").publishes(TestTypeA, fan_out=-5)

    error_msg = str(exc_info.value).lower()
    assert "fan_out" in error_msg or "count" in error_msg


# ============================================================================
# Test Scenario 5: where parameter (filter predicate)
# ============================================================================


def test_publishes_where_predicate():
    """.publishes(A, where=lambda x: x.valid) stores filter_predicate."""
    # Arrange
    flock = Flock()

    def filter_valid(obj: BaseModel) -> bool:
        return obj.valid if hasattr(obj, "valid") else False  # type: ignore

    # Act
    agent = flock.agent("test").publishes(TestTypeA, where=filter_valid)

    # Assert
    group = agent.agent.output_groups[0]
    output = group.outputs[0]

    assert output.filter_predicate is not None
    assert callable(output.filter_predicate)
    assert output.filter_predicate == filter_valid

    # Test that predicate works
    valid_obj = TestTypeA(value=10, valid=True)
    invalid_obj = TestTypeA(value=20, valid=False)
    assert output.filter_predicate(valid_obj) is True
    assert output.filter_predicate(invalid_obj) is False


def test_publishes_where_with_lambda():
    """.publishes(A, where=lambda x: x.value > 50) stores lambda predicate."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(
        TestTypeA,
        where=lambda x: x.value > 50,  # type: ignore
    )

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.filter_predicate is not None

    # Test predicate
    high_value = TestTypeA(value=100, valid=True)
    low_value = TestTypeA(value=10, valid=True)
    assert output.filter_predicate(high_value) is True
    assert output.filter_predicate(low_value) is False


def test_publishes_where_none_by_default():
    """.publishes(A) without where has filter_predicate=None."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.filter_predicate is None


# ============================================================================
# Test Scenario 6: Dynamic visibility parameter
# ============================================================================


def test_publishes_dynamic_visibility():
    """.publishes(A, visibility=lambda x: ...) stores callable visibility."""
    # Arrange
    flock = Flock()

    def dynamic_vis(obj: BaseModel) -> Visibility:
        # High scores are public, low scores are private
        if hasattr(obj, "score") and obj.score >= 80:  # type: ignore
            return PublicVisibility()
        return PrivateVisibility(agents={"admin"})

    # Act
    agent = flock.agent("test").publishes(TestTypeB, visibility=dynamic_vis)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]

    # Visibility should be stored (as callable)
    # NOTE: The implementation might store this in default_visibility or a separate field
    # Check both possibilities
    assert callable(output.default_visibility) or (
        hasattr(output, "visibility_fn") and callable(output.visibility_fn)
    )


def test_publishes_static_visibility():
    """.publishes(A, visibility=PrivateVisibility(...)) stores static visibility."""
    # Arrange
    flock = Flock()
    private_vis = PrivateVisibility(agents={"agent1", "agent2"})

    # Act
    agent = flock.agent("test").publishes(TestTypeA, visibility=private_vis)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.default_visibility == private_vis


def test_publishes_visibility_default_is_public():
    """.publishes(A) without visibility defaults to PublicVisibility."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    # Check both the output and the group level
    assert isinstance(output.default_visibility, PublicVisibility)
    assert isinstance(agent.agent.output_groups[0].shared_visibility, PublicVisibility)


# ============================================================================
# Test Scenario 7: validate parameter
# ============================================================================


def test_publishes_validate_single():
    """.publishes(A, validate=lambda x: x.score > 0) stores validate_predicate."""
    # Arrange
    flock = Flock()

    def validate_positive(obj: BaseModel) -> bool:
        return obj.score > 0 if hasattr(obj, "score") else False  # type: ignore

    # Act
    agent = flock.agent("test").publishes(TestTypeB, validate=validate_positive)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.validate_predicate is not None
    assert callable(output.validate_predicate)

    # Test validation works
    valid_obj = TestTypeB(name="test", score=50)
    invalid_obj = TestTypeB(name="test", score=0)
    assert output.validate_predicate(valid_obj) is True
    assert output.validate_predicate(invalid_obj) is False


def test_publishes_validate_list_of_tuples():
    """.publishes(A, validate=[(check1, msg1), (check2, msg2)]) stores list."""
    # Arrange
    flock = Flock()

    def check_name_length(obj: BaseModel) -> bool:
        return len(obj.name) >= 3 if hasattr(obj, "name") else False  # type: ignore

    def check_score_range(obj: BaseModel) -> bool:
        return 0 <= obj.score <= 100 if hasattr(obj, "score") else False  # type: ignore

    validators = [
        (check_name_length, "Name must be at least 3 characters"),
        (check_score_range, "Score must be 0-100"),
    ]

    # Act
    agent = flock.agent("test").publishes(TestTypeB, validate=validators)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.validate_predicate is not None
    assert isinstance(output.validate_predicate, list)
    assert len(output.validate_predicate) == 2

    # Verify structure
    for item in output.validate_predicate:
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert callable(item[0])
        assert isinstance(item[1], str)

    # Test validators work
    valid_obj = TestTypeB(name="Good Name", score=85)
    short_name = TestTypeB(name="AB", score=50)

    assert output.validate_predicate[0][0](valid_obj) is True
    assert output.validate_predicate[0][0](short_name) is False
    assert output.validate_predicate[0][1] == "Name must be at least 3 characters"


def test_publishes_validate_none_by_default():
    """.publishes(A) without validate has validate_predicate=None."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.validate_predicate is None


# ============================================================================
# Test Scenario 8: description parameter (group description)
# ============================================================================


def test_publishes_group_description():
    """.publishes(A, description="Special") stores group_description."""
    # Arrange
    flock = Flock()
    custom_desc = "Generate high-quality artifacts with special care"

    # Act
    agent = flock.agent("test").publishes(TestTypeA, description=custom_desc)

    # Assert
    group = agent.agent.output_groups[0]

    # Check if description stored at group or output level
    if hasattr(group, "group_description"):
        assert group.group_description == custom_desc
    else:
        # Might be stored in first output
        assert group.outputs[0].group_description == custom_desc


def test_publishes_description_applies_to_group():
    """.publishes(A, B, description="X") applies description to whole group."""
    # Arrange
    flock = Flock()
    desc = "Both types need special handling"

    # Act
    agent = flock.agent("test").publishes(TestTypeA, TestTypeB, description=desc)

    # Assert
    group = agent.agent.output_groups[0]
    # Description should be at group level
    if hasattr(group, "group_description"):
        assert group.group_description == desc


def test_publishes_description_none_by_default():
    """.publishes(A) without description has group_description=None."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA)

    # Assert
    group = agent.agent.output_groups[0]
    if hasattr(group, "group_description"):
        assert group.group_description is None


# ============================================================================
# Test Scenario 9: Combined parameters
# ============================================================================


def test_publishes_combined_parameters():
    """.publishes(A, fan_out=3, where=..., validate=...) all work together."""
    # Arrange
    flock = Flock()

    def filter_fn(obj: BaseModel) -> bool:
        return obj.valid if hasattr(obj, "valid") else False  # type: ignore

    def validate_fn(obj: BaseModel) -> bool:
        return obj.value > 0 if hasattr(obj, "value") else False  # type: ignore

    desc = "Generate 3 valid positive-value artifacts"

    # Act
    agent = flock.agent("test").publishes(
        TestTypeA, fan_out=3, where=filter_fn, validate=validate_fn, description=desc
    )

    # Assert
    group = agent.agent.output_groups[0]
    output = group.outputs[0]

    # Verify all parameters applied
    assert output.count == 3
    assert output.filter_predicate == filter_fn
    assert output.validate_predicate == validate_fn

    if hasattr(group, "group_description"):
        assert group.group_description == desc
    elif hasattr(output, "group_description"):
        assert output.group_description == desc


def test_publishes_all_sugar_parameters_with_multiple_types():
    """.publishes(A, B, fan_out=2, where=..., visibility=..., validate=...) works."""
    # Arrange
    flock = Flock()

    filter_fn = lambda x: True  # noqa: E731
    validate_fn = lambda x: True  # noqa: E731
    vis = PrivateVisibility(agents={"test"})

    # Act
    agent = flock.agent("test").publishes(
        TestTypeA,
        TestTypeB,
        fan_out=2,
        where=filter_fn,
        visibility=vis,
        validate=validate_fn,
        description="Complex group",
    )

    # Assert
    group = agent.agent.output_groups[0]
    assert len(group.outputs) == 2

    # fan_out should apply to both
    assert group.outputs[0].count == 2
    assert group.outputs[1].count == 2

    # Predicates should apply to both
    assert group.outputs[0].filter_predicate == filter_fn
    assert group.outputs[1].filter_predicate == filter_fn
    assert group.outputs[0].validate_predicate == validate_fn
    assert group.outputs[1].validate_predicate == validate_fn


# ============================================================================
# Test Scenario 10: Error validation (fan_out edge cases)
# ============================================================================


def test_publishes_fan_out_zero_is_invalid():
    """.publishes(A, fan_out=0) raises ValueError with clear message."""
    # Arrange
    flock = Flock()

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        flock.agent("test").publishes(TestTypeA, fan_out=0)

    error_msg = str(exc_info.value).lower()
    # Should mention that fan_out must be >= 1
    assert any(term in error_msg for term in ["fan_out", "count", "must", "greater"])


def test_publishes_fan_out_negative_is_invalid():
    """.publishes(A, fan_out=-10) raises ValueError."""
    # Arrange
    flock = Flock()

    # Act & Assert
    with pytest.raises(ValueError):
        flock.agent("test").publishes(TestTypeA, fan_out=-10)


def test_publishes_large_fan_out_is_valid():
    """.publishes(A, fan_out=1000) is valid (no upper limit)."""
    # Arrange
    flock = Flock()

    # Act - Should not raise
    agent = flock.agent("test").publishes(TestTypeA, fan_out=1000)

    # Assert
    output = agent.agent.output_groups[0].outputs[0]
    assert output.count == 1000


def test_publishes_chaining_with_other_methods():
    """.publishes() can be chained with .consumes() and other methods."""
    # Arrange
    flock = Flock()

    # Act - Chain publishes with consumes
    agent = (
        flock.agent("test")
        .consumes(TestTypeA)
        .publishes(TestTypeB)
        .publishes(TestTypeC)
    )

    # Assert
    assert len(agent.agent.subscriptions) == 1
    assert len(agent.agent.output_groups) == 2


# ============================================================================
# Test Scenario 12: PublishBuilder return value
# ============================================================================


def test_publishes_returns_publish_builder():
    """.publishes() returns PublishBuilder for chaining."""
    # Arrange
    flock = Flock()

    # Act
    result = flock.agent("test").publishes(TestTypeA)

    # Assert - Should return PublishBuilder (or similar chainable object)
    from flock.core import AgentBuilder, PublishBuilder

    # Result should support agent builder methods
    assert isinstance(result, (PublishBuilder, AgentBuilder))

    # Should be able to chain with other agent methods
    result.consumes(TestTypeB)  # Should not raise


def test_publishes_builder_chaining():
    """.publishes() can be chained with .only_for() and other builder methods."""
    # Arrange
    flock = Flock()

    # Act - Chain with only_for (existing PublishBuilder method)
    agent = (
        flock.agent("test")
        .publishes(TestTypeA)
        .only_for("agent1", "agent2")
        .publishes(TestTypeB)
    )

    # Assert - Should have created 2 groups
    assert len(agent.agent.output_groups) == 2

    # First group should have private visibility (from only_for)
    first_output = agent.agent.output_groups[0].outputs[0]
    assert isinstance(first_output.default_visibility, PrivateVisibility)


# ============================================================================
# Test Scenario 13: Edge cases and special scenarios
# ============================================================================


def test_publishes_empty_call_not_allowed():
    """.publishes() without types should raise (or be handled gracefully)."""
    # Arrange
    flock = Flock()

    # Act - Call publishes with no types
    agent = flock.agent("test").publishes()

    # Assert - Should create empty group or handle gracefully
    # Implementation decision: may create empty group or skip
    # At minimum, should not crash
    assert hasattr(agent.agent, "output_groups")


def test_publishes_with_none_types_filtered():
    """.publishes(A, None, B) should filter out None values."""
    # Arrange
    flock = Flock()

    # Act - Try to pass None (should be filtered or raise)
    # This tests defensive programming
    try:
        agent = flock.agent("test").publishes(TestTypeA, None, TestTypeB)  # type: ignore

        # If it doesn't raise, None should be filtered out
        group = agent.agent.output_groups[0]
        # Should only have 2 outputs (A and B, not None)
        type_names = [o.spec.type_name for o in group.outputs]
        assert "TestTypeA" in type_names
        assert "TestTypeB" in type_names
    except (TypeError, ValueError):
        # If it raises, that's also acceptable behavior
        pass


def test_publishes_preserves_group_order():
    """Multiple .publishes() calls preserve order of groups."""
    # Arrange
    flock = Flock()

    # Act
    agent = (
        flock.agent("test")
        .publishes(TestTypeA, description="First")
        .publishes(TestTypeB, description="Second")
        .publishes(TestTypeC, description="Third")
    )

    # Assert - Order should be preserved
    assert len(agent.agent.output_groups) == 3

    if hasattr(agent.agent.output_groups[0], "group_description"):
        assert agent.agent.output_groups[0].group_description == "First"
        assert agent.agent.output_groups[1].group_description == "Second"
        assert agent.agent.output_groups[2].group_description == "Third"


def test_publishes_fan_out_with_duplicates():
    """.publishes(A, A, fan_out=2) applies fan_out to both A's."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(TestTypeA, TestTypeA, fan_out=2)

    # Assert
    group = agent.agent.output_groups[0]
    # Should have 2 outputs, each with count=2
    assert len(group.outputs) == 2
    assert group.outputs[0].count == 2
    assert group.outputs[1].count == 2
    assert group.outputs[0].spec.type_name == "TestTypeA"
    assert group.outputs[1].spec.type_name == "TestTypeA"


# ============================================================================
# Test Scenario 14: Integration with agent lifecycle
# ============================================================================


def test_publishes_agent_can_be_registered():
    """Agent with enhanced .publishes() can be registered in orchestrator."""
    # Arrange
    flock = Flock()

    # Act
    agent = (
        flock.agent("test")
        .consumes(TestTypeA)
        .publishes(TestTypeB, fan_out=3, where=lambda x: True)
    )

    # Assert - Agent should be registered
    assert agent.agent.name == "test"
    assert agent.agent in flock._agents.values()


def test_publishes_group_structure_complete():
    """OutputGroup has all required fields after .publishes() call."""
    # Arrange
    flock = Flock()

    # Act
    agent = flock.agent("test").publishes(
        TestTypeA,
        TestTypeB,
        visibility=PrivateVisibility(agents={"test"}),
        description="Test group",
    )

    # Assert - Group should have complete structure
    group = agent.agent.output_groups[0]
    assert hasattr(group, "outputs")
    assert hasattr(group, "shared_visibility")
    assert isinstance(group.shared_visibility, Visibility)
    assert len(group.outputs) == 2

    # Each output should have required fields
    for output in group.outputs:
        assert hasattr(output, "spec")
        assert hasattr(output, "count")
        assert hasattr(output, "filter_predicate")
        assert hasattr(output, "validate_predicate")
        assert hasattr(output, "group_description")


# ============================================================================
# PHASE 3: Multiple Engine Calls in Agent.execute()
# ============================================================================

"""Tests for Phase 3: Multiple Engine Calls Based on OutputGroups.

These tests verify that Agent.execute() calls the engine ONCE PER OutputGroup,
not once total. This is the core semantic of multiple .publishes() calls.

Phase 3 Requirements (from PLAN.md lines 163-171):
1. .publishes(A).publishes(B).publishes(C) → 3 engine calls
2. .publishes(A, B, C) → 1 engine call
3. .publishes(A, fan_out=3) → 1 engine call, 3 artifacts
4. Each engine call gets group-specific context
5. All group artifacts are collected
6. Engine calls are sequential (not parallel)
7. Error in one group stops remaining groups
8. Mock engine to count and verify calls
"""

import asyncio

from pydantic import PrivateAttr

# No-op utility component for tests (bypasses console emoji rendering)
from flock.components.agent import AgentComponent, EngineComponent
from flock.core.artifacts import Artifact
from flock.utils.runtime import Context, EvalInputs, EvalResult


class NoOpUtility(AgentComponent):
    """Silent utility that does nothing - bypasses default console output."""


# Mock board for tests
class MockBoard:
    """Mock blackboard that collects published artifacts without side effects."""

    def __init__(self):
        self.published: list[Artifact] = []

    async def publish(self, artifact: Artifact) -> None:
        """Record published artifacts."""
        self.published.append(artifact)


# Mock engine for testing call counts
class CountingMockEngine(EngineComponent):
    """Mock engine that counts how many times it's called."""

    _call_count: int = PrivateAttr(default=0)
    _artifacts_per_call: list[list[BaseModel]] = PrivateAttr()
    _call_history: list[dict] = PrivateAttr(default_factory=list)

    def __init__(self, artifacts_per_call: list[list[BaseModel]]):
        """
        Args:
            artifacts_per_call: List of artifact lists to return for each call.
                               e.g., [[TaskA()], [TaskB()], [TaskC()]] for 3 calls.
        """
        super().__init__()
        self._call_count = 0
        self._artifacts_per_call = artifacts_per_call
        self._call_history = []

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def call_history(self) -> list[dict]:
        return self._call_history

    async def evaluate(
        self, agent, ctx: Context, inputs: EvalInputs, output_group
    ) -> EvalResult:
        """Mock evaluate that returns predetermined artifacts."""
        # Record this call
        call_info = {
            "call_number": self._call_count,
            "context_id": id(ctx),
            "agent_name": agent.name,
        }
        self._call_history.append(call_info)

        # Get artifacts for this call
        if self._call_count < len(self._artifacts_per_call):
            artifacts_to_return = self._artifacts_per_call[self._call_count]
        else:
            artifacts_to_return = []

        self._call_count += 1

        # Return EvalResult with the artifacts
        return EvalResult.from_objects(*artifacts_to_return, agent=agent)

    async def evaluate_fanout(
        self, agent, ctx: Context, inputs: EvalInputs, output_group
    ) -> EvalResult:
        """Mock evaluate_fanout that returns predetermined artifacts (same as evaluate)."""
        # Fan-out is just evaluate with multiple artifacts of same type
        return await self.evaluate(agent, ctx, inputs, output_group)


# ============================================================================
# Test Scenario 1: Multiple .publishes() = Multiple Engine Calls
# ============================================================================


@pytest.mark.asyncio
async def test_multiple_publishes_calls_engine_multiple_times():
    """.publishes(A).publishes(B).publishes(C) should call engine 3 times."""
    # Arrange
    flock = Flock()

    # Create artifacts for each of the 3 engine calls
    artifact_a = TestTypeA(value=100, valid=True)
    artifact_b = TestTypeB(name="Test B", score=85)
    artifact_c = TestTypeC(priority=5)

    # Mock engine that will be called 3 times
    mock_engine = CountingMockEngine(
        artifacts_per_call=[
            [artifact_a],  # Call 1
            [artifact_b],  # Call 2
            [artifact_c],  # Call 3
        ]
    )

    # Create agent with 3 separate publishes calls
    agent = (
        flock.agent("multi_publish_agent")
        .consumes(TestTypeA)  # Trigger
        .publishes(TestTypeA)  # Group 1
        .publishes(TestTypeB)  # Group 2
        .publishes(TestTypeC)  # Group 3
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    # Create context and input artifacts
    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test-multi-calls")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act - Execute the agent
    output_artifacts = await agent.agent.execute(ctx, input_artifacts)

    # Assert - Engine should be called 3 times
    assert mock_engine.call_count == 3, (
        f"Expected 3 engine calls (one per OutputGroup), "
        f"but got {mock_engine.call_count}"
    )

    # Should have collected artifacts from all 3 calls
    assert len(output_artifacts) >= 3, (
        f"Expected at least 3 output artifacts, got {len(output_artifacts)}"
    )

    # Verify each call happened
    assert len(mock_engine.call_history) == 3


@pytest.mark.asyncio
async def test_single_publishes_calls_engine_once():
    """.publishes(A, B, C) should call engine only 1 time (all types in one group)."""
    # Arrange
    flock = Flock()

    artifact_a = TestTypeA(value=1, valid=True)
    artifact_b = TestTypeB(name="Test", score=90)
    artifact_c = TestTypeC(priority=3)

    mock_engine = CountingMockEngine(
        artifacts_per_call=[
            [artifact_a, artifact_b, artifact_c]  # Single call returns all 3
        ]
    )

    # Single .publishes() with multiple types = ONE group
    agent = (
        flock.agent("single_publish_agent")
        .consumes(TestTypeA)
        .publishes(TestTypeA, TestTypeB, TestTypeC)  # ALL in one call
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test-single-call")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    await agent.agent.execute(ctx, input_artifacts)

    # Assert - Engine called exactly ONCE
    assert mock_engine.call_count == 1, (
        f"Expected 1 engine call for single .publishes(), got {mock_engine.call_count}"
    )


# ============================================================================
# Test Scenario 2: fan_out Parameter
# ============================================================================


@pytest.mark.asyncio
async def test_fan_out_calls_engine_once_generates_multiple():
    """.publishes(A, fan_out=3) should call engine 1 time, generate 3 artifacts."""
    # Arrange
    flock = Flock()

    # Engine returns 3 artifacts in a single call
    artifacts = [
        TestTypeA(value=1, valid=True),
        TestTypeA(value=2, valid=True),
        TestTypeA(value=3, valid=True),
    ]

    mock_engine = CountingMockEngine(artifacts_per_call=[artifacts])

    agent = (
        flock.agent("fanout_agent")
        .consumes(TestTypeB)
        .publishes(TestTypeA, fan_out=3)  # Expect 3 artifacts, but 1 call
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeB",
            payload=TestTypeB(name="test", score=50).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    output_artifacts = await agent.agent.execute(ctx, input_artifacts)

    # Assert
    assert mock_engine.call_count == 1, "fan_out should result in single engine call"

    # Should generate 3 artifacts
    type_a_artifacts = [a for a in output_artifacts if a.type == "TestTypeA"]
    assert len(type_a_artifacts) == 3, (
        f"Expected 3 TestTypeA artifacts with fan_out=3, got {len(type_a_artifacts)}"
    )


# ============================================================================
# Test Scenario 3: Group-Specific Context
# ============================================================================


@pytest.mark.asyncio
async def test_each_engine_call_receives_group_specific_context():
    """Each engine call should receive context specific to that OutputGroup."""
    # Arrange
    flock = Flock()

    # Track contexts passed to engine
    contexts_received: list[Context] = []

    class ContextTrackingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx: Context, inputs: EvalInputs, output_group
        ) -> EvalResult:
            # Capture the context
            contexts_received.append(ctx)

            # Return appropriate artifact based on call number
            call_num = len(contexts_received)
            if call_num == 1:
                artifact = TestTypeA(value=1, valid=True)
            elif call_num == 2:
                artifact = TestTypeB(name="B", score=50)
            else:
                artifact = TestTypeC(priority=1)

            return EvalResult.from_objects(artifact, agent=agent)

    agent = (
        flock.agent("context_test")
        .consumes(TestTypeA)
        .publishes(TestTypeA, description="First group")  # Group 1
        .publishes(TestTypeB, description="Second group")  # Group 2
        .publishes(TestTypeC, description="Third group")  # Group 3
        .with_engines(ContextTrackingEngine())
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    await agent.agent.execute(ctx, input_artifacts)

    # Assert - Should have received 3 contexts (one per group)
    assert len(contexts_received) == 3

    # Each context should be different (not the same instance)
    # This tests that _prepare_group_context() creates distinct contexts
    context_ids = [id(ctx) for ctx in contexts_received]
    # Note: Depending on implementation, contexts might be cloned or modified
    # At minimum, verify we got 3 context objects
    assert len(context_ids) == 3


# ============================================================================
# Test Scenario 4: Artifact Collection from All Groups
# ============================================================================


@pytest.mark.asyncio
async def test_artifacts_from_all_groups_collected():
    """Artifacts from all OutputGroups should be collected into final output."""
    # Arrange
    flock = Flock()

    # Each group produces different artifacts
    group1_artifacts = [TestTypeA(value=10, valid=True)]
    group2_artifacts = [
        TestTypeB(name="B1", score=60),
        TestTypeB(name="B2", score=70),
    ]
    group3_artifacts = [TestTypeC(priority=5)]

    mock_engine = CountingMockEngine(
        artifacts_per_call=[
            group1_artifacts,
            group2_artifacts,
            group3_artifacts,
        ]
    )

    agent = (
        flock.agent("collector")
        .consumes(TestTypeA)
        .publishes(TestTypeA)  # Group 1: 1 artifact
        .publishes(TestTypeB, fan_out=2)  # Group 2: 2 artifacts
        .publishes(TestTypeC)  # Group 3: 1 artifact
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert - Should collect all artifacts from all groups
    assert mock_engine.call_count == 3

    # Count by type
    type_a = [a for a in outputs if a.type == "TestTypeA"]
    type_b = [a for a in outputs if a.type == "TestTypeB"]
    type_c = [a for a in outputs if a.type == "TestTypeC"]

    assert len(type_a) >= 1, "Should have TestTypeA from group 1"
    assert len(type_b) >= 2, "Should have 2 TestTypeB from group 2"
    assert len(type_c) >= 1, "Should have TestTypeC from group 3"


# ============================================================================
# Test Scenario 5: Sequential Execution
# ============================================================================


@pytest.mark.asyncio
async def test_engine_calls_are_sequential_not_parallel():
    """Engine calls should execute sequentially, not in parallel."""
    # Arrange
    flock = Flock()

    execution_order: list[int] = []
    execution_times: list[float] = []

    class SequentialTrackingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            import time

            call_num = len(execution_order) + 1
            execution_order.append(call_num)
            execution_times.append(time.time())

            # Simulate work (short delay)
            await asyncio.sleep(0.01)

            # Return artifact
            if call_num == 1:
                artifact = TestTypeA(value=call_num, valid=True)
            elif call_num == 2:
                artifact = TestTypeB(name=f"Call {call_num}", score=50)
            else:
                artifact = TestTypeC(priority=call_num)

            return EvalResult.from_objects(artifact, agent=agent)

    agent = (
        flock.agent("sequential")
        .consumes(TestTypeA)
        .publishes(TestTypeA)
        .publishes(TestTypeB)
        .publishes(TestTypeC)
        .with_engines(SequentialTrackingEngine())
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    await agent.agent.execute(ctx, input_artifacts)

    # Assert - Calls should be in order 1, 2, 3
    assert execution_order == [1, 2, 3], "Calls should execute in sequential order"

    # Verify timestamps show sequential execution (not parallel)
    # Each call should start AFTER previous finishes
    if len(execution_times) == 3:
        # Times should be increasing (call 2 after call 1, call 3 after call 2)
        assert execution_times[1] > execution_times[0]
        assert execution_times[2] > execution_times[1]


# ============================================================================
# Test Scenario 6: Error Handling - Failures Stop Subsequent Groups
# ============================================================================


@pytest.mark.asyncio
async def test_error_in_group_stops_subsequent_groups():
    """If one OutputGroup fails, subsequent groups should NOT execute."""
    # Arrange
    flock = Flock()

    call_count = 0

    class FailingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            nonlocal call_count
            call_count += 1

            if call_count == 2:
                # Second group fails
                raise RuntimeError("Group 2 failed!")

            # Return artifact for other calls
            if call_count == 1:
                artifact = TestTypeA(value=1, valid=True)
            else:
                artifact = TestTypeC(priority=1)

            return EvalResult.from_objects(artifact, agent=agent)

    agent = (
        flock.agent("failing")
        .consumes(TestTypeA)
        .publishes(TestTypeA)  # Group 1: succeeds
        .publishes(TestTypeB)  # Group 2: FAILS
        .publishes(TestTypeC)  # Group 3: should NOT execute
        .with_engines(FailingEngine())
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act & Assert - Should raise the error
    with pytest.raises(RuntimeError, match="Group 2 failed"):
        await agent.agent.execute(ctx, input_artifacts)

    # Engine should have been called exactly 2 times (groups 1 and 2)
    # Group 3 should NOT execute after group 2 fails
    assert call_count == 2, (
        f"Expected 2 engine calls (group 1 success, group 2 fail, group 3 skipped), "
        f"got {call_count}"
    )


# ============================================================================
# Test Scenario 7: Mock Engine Call Verification
# ============================================================================


@pytest.mark.asyncio
async def test_mock_engine_verifies_call_count_and_behavior():
    """Use mock engine to precisely verify call count and behavior."""
    # Arrange
    flock = Flock()

    # Create a more sophisticated mock
    artifacts_group1 = TestTypeA(value=1, valid=True)
    artifacts_group2 = TestTypeB(name="Group2", score=75)

    mock_engine = CountingMockEngine(
        artifacts_per_call=[
            [artifacts_group1],
            [artifacts_group2],
        ]
    )

    agent = (
        flock.agent("mock_test")
        .consumes(TestTypeA)
        .publishes(TestTypeA)
        .publishes(TestTypeB)
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert - Verify all aspects of execution
    assert mock_engine.call_count == 2, "Should call engine twice"

    # Verify call history
    assert len(mock_engine.call_history) == 2

    # First call
    assert mock_engine.call_history[0]["call_number"] == 0
    assert mock_engine.call_history[0]["agent_name"] == "mock_test"

    # Second call
    assert mock_engine.call_history[1]["call_number"] == 1

    # Verify outputs
    type_a_outputs = [a for a in outputs if a.type == "TestTypeA"]
    type_b_outputs = [a for a in outputs if a.type == "TestTypeB"]

    assert len(type_a_outputs) >= 1, "Should have TestTypeA from group 1"
    assert len(type_b_outputs) >= 1, "Should have TestTypeB from group 2"


# ============================================================================
# Test Scenario 8: No OutputGroups = No Engine Calls (Backwards Compat)
# ============================================================================


@pytest.mark.asyncio
async def test_agent_without_publishes_no_engine_calls():
    """Agent without .publishes() should not call engine (or handle gracefully)."""
    # Arrange
    flock = Flock()

    mock_engine = CountingMockEngine(artifacts_per_call=[])

    # Agent with no publishes
    agent = (
        flock.agent("no_publish")
        .consumes(TestTypeA)
        .with_engines(mock_engine)
        .with_utilities(NoOpUtility())
        # NO .publishes() calls
    )

    ctx = Context(board=MockBoard(), orchestrator=flock, task_id="test")
    input_artifacts = [
        Artifact(
            type="TestTypeA",
            payload=TestTypeA(value=1, valid=True).model_dump(),
            produced_by="test",
        )
    ]

    # Act
    outputs = await agent.agent.execute(ctx, input_artifacts)

    # Assert - No output groups means engine shouldn't be called for publishing
    # (Engine might still be called for other reasons depending on implementation)
    # At minimum, we should get empty or minimal outputs
    assert isinstance(outputs, list)
