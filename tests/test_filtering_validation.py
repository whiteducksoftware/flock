"""Tests for Phase 5: Filtering, Validation, and Visibility

These tests verify that `where`, `validate`, and dynamic `visibility` work correctly
in `_make_outputs_for_group()`.
"""

import pytest
from pydantic import BaseModel, Field

from flock import Flock
from flock.components.agent import AgentComponent, EngineComponent
from flock.core.artifacts import Artifact
from flock.core.visibility import PrivateVisibility, PublicVisibility
from flock.utils.runtime import Context, EvalResult


# NoOp utility to bypass console output issues
class NoOpUtility(AgentComponent):
    """Silent utility that does nothing - bypasses default console output."""


# Test artifact types
class ScoredResult(BaseModel):
    """Result with a score for filtering/validation tests."""

    id: int
    score: float = Field(ge=0, le=100)
    category: str
    is_valid: bool = True


class FilteredOutput(BaseModel):
    """Output artifact for filtering tests."""

    value: int
    passed: bool


class ValidatedData(BaseModel):
    """Data artifact for validation tests."""

    name: str
    priority: str
    confidence: float


# Mock board for tests
class MockBoard:
    """Mock blackboard that collects published artifacts without side effects."""

    def __init__(self):
        self.published: list[Artifact] = []

    async def publish(self, artifact: Artifact) -> None:
        """Record published artifacts."""
        self.published.append(artifact)

    async def list(self) -> list[Artifact]:
        """Return published artifacts (for context fetching)."""
        return self.published


# ============================================================================
# Phase 5.1: WHERE Filtering Tests
# ============================================================================


@pytest.mark.asyncio
async def test_where_filtering_reduces_published_artifacts():
    """Test that `where` filters artifacts before publishing.

    GIVEN: Agent with fan_out=10 and where clause
    WHEN: Engine generates 10 artifacts, 3 pass filter
    THEN: Only 3 artifacts are published
    """
    orchestrator = Flock()

    class FilteringEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # Generate 10 results with varying scores
            results = [
                ScoredResult(id=i, score=i * 10, category="test", is_valid=True)
                for i in range(1, 11)
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            # Same as evaluate for these tests
            return await self.evaluate(agent, ctx, inputs, output_group)

    # Agent with where filter: only scores >= 70
    agent = (
        orchestrator.agent("filter_agent")
        .publishes(
            ScoredResult,
            fan_out=10,
            where=lambda r: r.score >= 70,  # Only 70, 80, 90, 100 (4 artifacts)
        )
        .with_engines(FilteringEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Execute agent directly
    outputs = await agent.agent.execute(ctx, [])

    # Verify: Only 4 artifacts passed the filter (scores 70, 80, 90, 100)
    scored_results = [a for a in outputs if "ScoredResult" in a.type]
    assert len(scored_results) == 4, (
        f"Expected 4 filtered artifacts, got {len(scored_results)}"
    )
    scores = sorted([a.payload["score"] for a in scored_results])
    assert scores == [70.0, 80.0, 90.0, 100.0]


@pytest.mark.asyncio
async def test_where_filtering_with_no_matches_publishes_nothing():
    """Test that where filter that matches nothing publishes no artifacts."""
    orchestrator = Flock()

    class FilteringEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # Generate 5 results, all with score < 50
            results = [
                ScoredResult(id=i, score=i * 5, category="test", is_valid=True)
                for i in range(1, 6)
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("filter_agent")
        .publishes(
            ScoredResult,
            fan_out=5,
            where=lambda r: r.score >= 90,  # No results meet this
        )
        .with_engines(FilteringEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Execute agent
    outputs = await agent.agent.execute(ctx, [])

    # Verify: No artifacts published
    scored_outputs = [a for a in outputs if "ScoredResult" in a.type]
    assert len(scored_outputs) == 0


@pytest.mark.asyncio
async def test_where_filtering_with_complex_predicate():
    """Test where filter with complex boolean logic."""
    orchestrator = Flock()

    class FilteringEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ScoredResult(id=1, score=75, category="A", is_valid=True),
                ScoredResult(id=2, score=85, category="B", is_valid=True),
                ScoredResult(id=3, score=95, category="A", is_valid=False),
                ScoredResult(id=4, score=65, category="A", is_valid=True),
                ScoredResult(id=5, score=85, category="A", is_valid=True),
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("filter_agent")
        .publishes(
            ScoredResult,
            fan_out=5,
            # Complex filter: category A AND score >= 70 AND is_valid
            where=lambda r: r.category == "A" and r.score >= 70 and r.is_valid,
        )
        .with_engines(FilteringEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Execute agent directly
    outputs = await agent.agent.execute(ctx, [])

    # Only id=1 (75, A, valid) and id=5 (85, A, valid) pass
    scored_results = [a for a in outputs if "ScoredResult" in a.type]
    assert len(scored_results) == 2
    ids = [a.payload["id"] for a in scored_results]
    assert ids == [1, 5]


# ============================================================================
# Phase 5.2: VALIDATE Predicate Tests
# ============================================================================


@pytest.mark.asyncio
async def test_validate_single_predicate_rejects_invalid():
    """Test that validate predicate raises ValueError for invalid artifacts."""
    orchestrator = Flock()

    class ValidatingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # One valid, one invalid
            results = [
                ValidatedData(name="Valid", priority="high", confidence=0.9),
                ValidatedData(
                    name="Invalid", priority="invalid_priority", confidence=0.8
                ),
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("validate_agent")
        .publishes(
            ValidatedData,
            fan_out=2,
            validate=lambda d: d.priority in ["high", "medium", "low"],
        )
        .with_engines(ValidatingEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Should raise ValueError because second artifact has invalid priority
    with pytest.raises(ValueError) as exc_info:
        await agent.agent.execute(ctx, [])

    # Verify error message is helpful
    error_msg = str(exc_info.value)
    assert "Validation failed" in error_msg
    assert "ValidatedData" in error_msg


@pytest.mark.asyncio
async def test_validate_list_of_tuples_with_custom_messages():
    """Test validate with list of (callable, error_msg) tuples."""
    orchestrator = Flock()

    class ValidatingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # Create artifact that fails second validation
            results = [
                ValidatedData(
                    name="Test", priority="high", confidence=0.3
                ),  # Low confidence
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("validate_agent")
        .publishes(
            ValidatedData,
            fan_out=1,
            validate=[
                (
                    lambda d: d.priority in ["high", "medium", "low"],
                    "Priority must be high/medium/low",
                ),
                (lambda d: d.confidence >= 0.5, "Confidence must be at least 0.5"),
                (lambda d: len(d.name) > 0, "Name cannot be empty"),
            ],
        )
        .with_engines(ValidatingEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Should raise ValueError with custom message
    with pytest.raises(ValueError) as exc_info:
        await agent.agent.execute(ctx, [])

    error_msg = str(exc_info.value)
    assert "Confidence must be at least 0.5" in error_msg


@pytest.mark.asyncio
async def test_validate_all_checks_must_pass():
    """Test that ALL validation checks must pass."""
    orchestrator = Flock()

    class ValidatingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ValidatedData(name="A", priority="high", confidence=0.9),  # Passes all
                ValidatedData(
                    name="", priority="high", confidence=0.9
                ),  # Fails name check
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("validate_agent")
        .publishes(
            ValidatedData,
            fan_out=2,
            validate=[
                (lambda d: d.priority in ["high", "medium", "low"], "Invalid priority"),
                (lambda d: d.confidence >= 0.5, "Confidence too low"),
                (lambda d: len(d.name) > 0, "Name is required"),
            ],
        )
        .with_engines(ValidatingEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Second artifact fails name validation
    with pytest.raises(ValueError) as exc_info:
        await agent.agent.execute(ctx, [])

    assert "Name is required" in str(exc_info.value)


@pytest.mark.asyncio
async def test_validate_passes_when_all_artifacts_valid():
    """Test that validation passes when all artifacts are valid."""
    orchestrator = Flock()

    class ValidatingEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            # All valid
            results = [
                ValidatedData(name="A", priority="high", confidence=0.9),
                ValidatedData(name="B", priority="medium", confidence=0.7),
                ValidatedData(name="C", priority="low", confidence=0.6),
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("validate_agent")
        .publishes(
            ValidatedData,
            fan_out=3,
            validate=[
                (lambda d: d.priority in ["high", "medium", "low"], "Invalid priority"),
                (lambda d: d.confidence >= 0.5, "Confidence too low"),
                (lambda d: len(d.name) > 0, "Name is required"),
            ],
        )
        .with_engines(ValidatingEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Should NOT raise - all artifacts valid
    outputs = await agent.agent.execute(ctx, [])

    # Verify all 3 artifacts were published
    validated_results = [a for a in outputs if "ValidatedData" in a.type]
    assert len(validated_results) == 3


# ============================================================================
# Phase 5.3: Dynamic Visibility Tests
# ============================================================================


@pytest.mark.asyncio
async def test_dynamic_visibility_based_on_content():
    """Test that visibility callable determines visibility per artifact."""
    orchestrator = Flock()

    class VisibilityEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ScoredResult(id=1, score=95, category="important", is_valid=True),
                ScoredResult(id=2, score=50, category="normal", is_valid=True),
                ScoredResult(id=3, score=85, category="important", is_valid=True),
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("visibility_agent")
        .publishes(
            ScoredResult,
            fan_out=3,
            visibility=lambda r: PublicVisibility()
            if r.category == "important"
            else PrivateVisibility(),
        )
        .with_engines(VisibilityEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Execute agent directly
    outputs = await agent.agent.execute(ctx, [])

    # Verify visibility based on category
    scored_results = [a for a in outputs if "ScoredResult" in a.type]
    assert len(scored_results) == 3
    assert isinstance(scored_results[0].visibility, PublicVisibility)  # important
    assert isinstance(scored_results[1].visibility, PrivateVisibility)  # normal
    assert isinstance(scored_results[2].visibility, PublicVisibility)  # important


@pytest.mark.asyncio
async def test_static_visibility_applied_to_all():
    """Test that static visibility is applied to all artifacts."""
    orchestrator = Flock()

    class VisibilityEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ScoredResult(id=i, score=i * 20, category="test", is_valid=True)
                for i in range(1, 4)
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("visibility_agent")
        .publishes(
            ScoredResult,
            fan_out=3,
            visibility=PublicVisibility(),  # Static visibility
        )
        .with_engines(VisibilityEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Execute agent directly
    outputs = await agent.agent.execute(ctx, [])

    # All should have PublicVisibility
    scored_results = [a for a in outputs if "ScoredResult" in a.type]
    assert len(scored_results) == 3
    for artifact in scored_results:
        assert isinstance(artifact.visibility, PublicVisibility)


# ============================================================================
# Phase 5.4: Combined Features Tests
# ============================================================================


@pytest.mark.asyncio
async def test_where_and_validate_applied_in_order():
    """Test that where filters BEFORE validate checks."""
    orchestrator = Flock()

    class CombinedEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ScoredResult(
                    id=1, score=95, category="A", is_valid=True
                ),  # Passes filter AND validation
                ScoredResult(
                    id=2, score=50, category="A", is_valid=False
                ),  # Filtered out (score < 70)
                ScoredResult(
                    id=3, score=85, category="A", is_valid=True
                ),  # Passes filter AND validation
                ScoredResult(
                    id=4, score=75, category="A", is_valid=False
                ),  # Passes filter, FAILS validation
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("combined_agent")
        .publishes(
            ScoredResult,
            fan_out=4,
            where=lambda r: r.score >= 70,  # Filters to id=1, 3, 4
            validate=lambda r: r.is_valid,  # id=4 fails here
        )
        .with_engines(CombinedEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Should raise on id=4 (passed filter but failed validation)
    with pytest.raises(ValueError) as exc_info:
        await agent.agent.execute(ctx, [])

    assert "Validation failed" in str(exc_info.value)


@pytest.mark.asyncio
async def test_where_validate_and_visibility_all_together():
    """Test combining where, validate, and dynamic visibility."""
    orchestrator = Flock()

    class CompleteEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ScoredResult(id=1, score=95, category="high", is_valid=True),
                ScoredResult(id=2, score=85, category="medium", is_valid=True),
                ScoredResult(id=3, score=75, category="high", is_valid=True),
                ScoredResult(
                    id=4, score=65, category="low", is_valid=True
                ),  # Filtered out
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("complete_agent")
        .publishes(
            ScoredResult,
            fan_out=4,
            where=lambda r: r.score >= 70,  # Filters to id=1, 2, 3
            validate=[
                (lambda r: r.is_valid, "Must be valid"),
                (lambda r: r.score > 0, "Score must be positive"),
            ],
            visibility=lambda r: PublicVisibility()
            if r.category == "high"
            else PrivateVisibility(),
        )
        .with_engines(CompleteEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    # Execute agent directly
    outputs = await agent.agent.execute(ctx, [])

    # Should publish 3 artifacts (id=1, 2, 3)
    scored_results = [a for a in outputs if "ScoredResult" in a.type]
    assert len(scored_results) == 3

    # Check visibility
    assert isinstance(scored_results[0].visibility, PublicVisibility)  # high
    assert isinstance(scored_results[1].visibility, PrivateVisibility)  # medium
    assert isinstance(scored_results[2].visibility, PublicVisibility)  # high

    # Check filtered correctly
    ids = [a.payload["id"] for a in scored_results]
    assert ids == [1, 2, 3]  # id=4 was filtered out


@pytest.mark.asyncio
async def test_error_messages_include_artifact_type():
    """Test that error messages include helpful context."""
    orchestrator = Flock()

    class ErrorEngine(EngineComponent):
        async def evaluate(self, agent, ctx, inputs, output_group):
            results = [
                ValidatedData(name="Test", priority="invalid", confidence=0.9),
            ]
            return EvalResult.from_objects(*results, agent=agent)

        async def evaluate_fanout(self, agent, ctx, inputs, output_group):
            return await self.evaluate(agent, ctx, inputs, output_group)

    agent = (
        orchestrator.agent("error_agent")
        .publishes(
            ValidatedData,
            fan_out=1,
            validate=[
                (
                    lambda d: d.priority in ["high", "medium", "low"],
                    "Priority must be high/medium/low",
                ),
            ],
        )
        .with_engines(ErrorEngine())
        .with_utilities(NoOpUtility())
    )

    # Create proper context with MockBoard
    ctx = Context(board=MockBoard(), orchestrator=orchestrator, task_id="test")

    with pytest.raises(ValueError) as exc_info:
        await agent.agent.execute(ctx, [])

    error_msg = str(exc_info.value)
    # Should include custom message
    assert "Priority must be high/medium/low" in error_msg
    # Should include artifact type
    assert "ValidatedData" in error_msg
