"""Tests for Phase 1: OutputGroup and enhanced AgentOutput data structures.

These tests define the expected behavior for the multi-publishes fan-out feature.
Tests are written BEFORE implementation (TDD approach).

Phase 1 adds:
- OutputGroup: Represents a single .publishes() call with multiple AgentOutput objects
- Enhanced AgentOutput: Adds count, filter_predicate, validate_predicate, group_description
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field

from flock.core import AgentOutput, OutputGroup
from flock.core.artifacts import ArtifactSpec
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type


# Test artifact types
@flock_type(name="TestReport")
class TestReport(BaseModel):
    title: str = Field(description="Report title")
    score: int = Field(description="Report score", ge=0, le=100)


@flock_type(name="TestTask")
class TestTask(BaseModel):
    name: str = Field(description="Task name")
    priority: int = Field(description="Task priority")


# ============================================================================
# Test Scenario 1: Test OutputGroup creation
# ============================================================================


def test_output_group_creation_with_single_output():
    """Test creating OutputGroup with a single AgentOutput."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility())

    # Act
    group = OutputGroup(outputs=[output], shared_visibility=PublicVisibility())

    # Assert
    assert len(group.outputs) == 1
    assert group.outputs[0] == output
    assert group.shared_visibility == PublicVisibility()


def test_output_group_creation_with_multiple_outputs():
    """Test creating OutputGroup with multiple AgentOutput objects."""
    # Arrange
    spec1 = ArtifactSpec.from_model(TestReport)
    spec2 = ArtifactSpec.from_model(TestTask)
    output1 = AgentOutput(spec=spec1, default_visibility=PublicVisibility())
    output2 = AgentOutput(spec=spec2, default_visibility=PublicVisibility())

    # Act
    group = OutputGroup(
        outputs=[output1, output2], shared_visibility=PublicVisibility()
    )

    # Assert
    assert len(group.outputs) == 2
    assert group.outputs[0] == output1
    assert group.outputs[1] == output2
    assert group.shared_visibility == PublicVisibility()


def test_output_group_is_single_call_returns_true():
    """Test that is_single_call() returns True for OutputGroup.

    This indicates all outputs in the group are generated together
    in one engine call.
    """
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility())
    group = OutputGroup(outputs=[output], shared_visibility=PublicVisibility())

    # Act & Assert
    assert group.is_single_call() is True


# ============================================================================
# Test Scenario 2: Test Enhanced AgentOutput
# ============================================================================


def test_agent_output_with_default_values():
    """Test creating AgentOutput uses correct default values for new fields."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility())

    # Assert - All new fields should have sensible defaults
    assert output.count == 1  # Default count
    assert output.filter_predicate is None  # Optional where filter
    assert output.validate_predicate is None  # Optional validation
    assert output.group_description is None  # Optional description override


def test_agent_output_with_all_new_fields():
    """Test creating AgentOutput with all new fields specified."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def filter_fn(obj: BaseModel) -> bool:
        return obj.score >= 50  # type: ignore

    def validate_fn(obj: BaseModel) -> bool:
        return obj.title != ""  # type: ignore

    # Act
    output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=5,
        filter_predicate=filter_fn,
        validate_predicate=validate_fn,
        group_description="Custom description for this output group",
    )

    # Assert
    assert output.count == 5
    assert output.filter_predicate == filter_fn
    assert output.validate_predicate == validate_fn
    assert output.group_description == "Custom description for this output group"


def test_agent_output_is_many_returns_false_when_count_is_one():
    """Test that is_many() returns False when count == 1."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=1)

    # Act & Assert
    assert output.is_many() is False


def test_agent_output_is_many_returns_true_when_count_greater_than_one():
    """Test that is_many() returns True when count > 1."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=3)

    # Act & Assert
    assert output.is_many() is True


def test_agent_output_is_many_returns_true_for_large_counts():
    """Test that is_many() works correctly for large fan-out counts."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=100)

    # Act & Assert
    assert output.is_many() is True


# ============================================================================
# Test Scenario 3: Test Validation - fan_out (count)
# ============================================================================


def test_agent_output_allows_count_of_one():
    """Test that count=1 is valid."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act - Should not raise
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=1)

    # Assert
    assert output.count == 1


def test_agent_output_allows_count_greater_than_one():
    """Test that count > 1 is valid."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act - Should not raise
    output = AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=10)

    # Assert
    assert output.count == 10


def test_agent_output_rejects_count_of_zero():
    """Test that count=0 raises ValueError."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=0)

    # Verify error message mentions the constraint
    assert (
        "count" in str(exc_info.value).lower()
        or "fan_out" in str(exc_info.value).lower()
    )
    assert "1" in str(exc_info.value) or "greater" in str(exc_info.value).lower()


def test_agent_output_rejects_negative_count():
    """Test that negative count raises ValueError."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        AgentOutput(spec=spec, default_visibility=PublicVisibility(), count=-5)

    # Verify error message
    assert (
        "count" in str(exc_info.value).lower()
        or "fan_out" in str(exc_info.value).lower()
    )


# ============================================================================
# Test Scenario 4: Test Validation - where callable (filter_predicate)
# ============================================================================


def test_agent_output_accepts_valid_filter_predicate():
    """Test that valid filter predicate (callable accepting BaseModel) is accepted."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def valid_filter(obj: BaseModel) -> bool:
        return True

    # Act - Should not raise
    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), filter_predicate=valid_filter
    )

    # Assert
    assert output.filter_predicate == valid_filter
    # Verify it can be called with a BaseModel
    test_obj = TestReport(title="Test", score=50)
    assert callable(output.filter_predicate)
    assert output.filter_predicate(test_obj) is True


def test_agent_output_filter_predicate_can_be_none():
    """Test that filter_predicate is optional (can be None)."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act - Should not raise
    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), filter_predicate=None
    )

    # Assert
    assert output.filter_predicate is None


def test_agent_output_filter_predicate_works_with_real_filtering():
    """Test that filter predicate can perform actual filtering logic."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def high_score_filter(obj: BaseModel) -> bool:
        if hasattr(obj, "score"):
            return obj.score >= 75  # type: ignore
        return False

    output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        filter_predicate=high_score_filter,
    )

    # Act
    high_report = TestReport(title="High", score=90)
    low_report = TestReport(title="Low", score=40)

    # Assert
    assert output.filter_predicate(high_report) is True
    assert output.filter_predicate(low_report) is False


# ============================================================================
# Test Scenario 5: Test Validation - validate predicate
# ============================================================================


def test_agent_output_accepts_simple_validate_callable():
    """Test that validate_predicate accepts a simple callable."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def validate_fn(obj: BaseModel) -> bool:
        return True

    # Act - Should not raise
    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), validate_predicate=validate_fn
    )

    # Assert
    assert output.validate_predicate == validate_fn
    assert callable(output.validate_predicate)


def test_agent_output_accepts_validate_as_list_of_tuples():
    """Test that validate_predicate accepts list of (callable, error_msg) tuples."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def check_title(obj: BaseModel) -> bool:
        return hasattr(obj, "title") and obj.title != ""  # type: ignore

    def check_score(obj: BaseModel) -> bool:
        return hasattr(obj, "score") and 0 <= obj.score <= 100  # type: ignore

    validators = [
        (check_title, "Title must not be empty"),
        (check_score, "Score must be between 0 and 100"),
    ]

    # Act - Should not raise
    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), validate_predicate=validators
    )

    # Assert
    assert output.validate_predicate == validators
    assert isinstance(output.validate_predicate, list)
    assert len(output.validate_predicate) == 2
    assert callable(output.validate_predicate[0][0])
    assert isinstance(output.validate_predicate[0][1], str)


def test_agent_output_validate_predicate_can_be_none():
    """Test that validate_predicate is optional (can be None)."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    # Act - Should not raise
    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), validate_predicate=None
    )

    # Assert
    assert output.validate_predicate is None


def test_agent_output_validate_tuple_format_is_correct():
    """Test that each validation tuple has correct format: (callable, str)."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def validator(obj: BaseModel) -> bool:
        return True

    validators = [(validator, "Error message 1"), (validator, "Error message 2")]

    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), validate_predicate=validators
    )

    # Act & Assert
    for item in output.validate_predicate:
        assert isinstance(item, tuple)
        assert len(item) == 2
        callable_fn, error_msg = item
        assert callable(callable_fn)
        assert isinstance(error_msg, str)


def test_agent_output_validate_list_works_with_real_validation():
    """Test that validation list can perform actual validation logic."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def check_title_length(obj: BaseModel) -> bool:
        if hasattr(obj, "title"):
            return len(obj.title) >= 3  # type: ignore
        return False

    def check_score_range(obj: BaseModel) -> bool:
        if hasattr(obj, "score"):
            return 0 <= obj.score <= 100  # type: ignore
        return False

    validators = [
        (check_title_length, "Title must be at least 3 characters"),
        (check_score_range, "Score must be 0-100"),
    ]

    output = AgentOutput(
        spec=spec, default_visibility=PublicVisibility(), validate_predicate=validators
    )

    # Act
    valid_report = TestReport(title="Good Report", score=85)
    invalid_title_report = TestReport(title="AB", score=50)
    # Use model_construct to bypass Pydantic validation for testing custom validators
    invalid_score_report = TestReport.model_construct(title="Good", score=150)

    # Assert - Test each validator
    title_validator, title_msg = output.validate_predicate[0]
    score_validator, score_msg = output.validate_predicate[1]

    assert title_validator(valid_report) is True
    assert title_validator(invalid_title_report) is False
    assert score_validator(valid_report) is True
    assert score_validator(invalid_score_report) is False

    assert title_msg == "Title must be at least 3 characters"
    assert score_msg == "Score must be 0-100"


# ============================================================================
# Test Scenario 6: Integration tests
# ============================================================================


def test_agent_output_with_all_fields_integration():
    """Integration test: AgentOutput with all new fields working together."""
    # Arrange
    spec = ArtifactSpec.from_model(TestReport)

    def filter_high_scores(obj: BaseModel) -> bool:
        return hasattr(obj, "score") and obj.score >= 80  # type: ignore

    def validate_title(obj: BaseModel) -> bool:
        return hasattr(obj, "title") and len(obj.title) >= 5  # type: ignore

    def validate_score(obj: BaseModel) -> bool:
        return hasattr(obj, "score") and obj.score <= 100  # type: ignore

    validators = [
        (validate_title, "Title too short"),
        (validate_score, "Score too high"),
    ]

    # Act
    output = AgentOutput(
        spec=spec,
        default_visibility=PublicVisibility(),
        count=10,
        filter_predicate=filter_high_scores,
        validate_predicate=validators,
        group_description="High-quality reports with detailed validation",
    )

    # Assert
    assert output.is_many() is True
    assert output.count == 10
    assert callable(output.filter_predicate)
    assert isinstance(output.validate_predicate, list)
    assert len(output.validate_predicate) == 2
    assert output.group_description == "High-quality reports with detailed validation"

    # Test filter works
    high_score_report = TestReport(title="Excellent Report", score=95)
    low_score_report = TestReport(title="Average Report", score=60)
    assert output.filter_predicate(high_score_report) is True
    assert output.filter_predicate(low_score_report) is False

    # Test validators work
    title_validator, _ = output.validate_predicate[0]
    score_validator, _ = output.validate_predicate[1]
    assert title_validator(high_score_report) is True
    assert score_validator(high_score_report) is True


def test_output_group_with_multiple_enhanced_outputs():
    """Integration test: OutputGroup containing multiple enhanced AgentOutput objects."""
    # Arrange
    report_spec = ArtifactSpec.from_model(TestReport)
    task_spec = ArtifactSpec.from_model(TestTask)

    def filter_reports(obj: BaseModel) -> bool:
        return hasattr(obj, "score") and obj.score >= 70  # type: ignore

    def filter_tasks(obj: BaseModel) -> bool:
        return hasattr(obj, "priority") and obj.priority >= 5  # type: ignore

    report_output = AgentOutput(
        spec=report_spec,
        default_visibility=PublicVisibility(),
        count=5,
        filter_predicate=filter_reports,
        group_description="High-score reports",
    )

    task_output = AgentOutput(
        spec=task_spec,
        default_visibility=PublicVisibility(),
        count=3,
        filter_predicate=filter_tasks,
        group_description="High-priority tasks",
    )

    # Act
    group = OutputGroup(
        outputs=[report_output, task_output], shared_visibility=PublicVisibility()
    )

    # Assert
    assert len(group.outputs) == 2
    assert group.is_single_call() is True

    # Verify first output (reports)
    assert group.outputs[0].is_many() is True
    assert group.outputs[0].count == 5
    assert group.outputs[0].group_description == "High-score reports"

    # Verify second output (tasks)
    assert group.outputs[1].is_many() is True
    assert group.outputs[1].count == 3
    assert group.outputs[1].group_description == "High-priority tasks"


def test_output_group_preserves_output_ordering():
    """Test that OutputGroup preserves the order of outputs."""
    # Arrange
    specs = [
        ArtifactSpec.from_model(TestReport),
        ArtifactSpec.from_model(TestTask),
    ]

    outputs = [
        AgentOutput(spec=specs[0], default_visibility=PublicVisibility(), count=1),
        AgentOutput(spec=specs[1], default_visibility=PublicVisibility(), count=2),
    ]

    # Act
    group = OutputGroup(outputs=outputs, shared_visibility=PublicVisibility())

    # Assert - Order should be preserved
    assert group.outputs[0].spec.type_name == "TestReport"
    assert group.outputs[1].spec.type_name == "TestTask"
    assert group.outputs[0].count == 1
    assert group.outputs[1].count == 2
