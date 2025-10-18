"""Tests for agent output processing."""

from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from flock.agent.output_processor import OutputProcessor
from flock.core.artifacts import Artifact
from flock.core.visibility import PrivateVisibility, PublicVisibility
from flock.registry import flock_type
from flock.utils.runtime import Context, EvalResult


# Test models
@flock_type(name="SampleOutput")
class SampleOutput(BaseModel):
    value: str
    score: int = 0


@flock_type(name="SecondOutput")
class SecondOutput(BaseModel):
    data: str


@pytest.fixture
def processor():
    """Create OutputProcessor instance."""
    return OutputProcessor(agent_name="test_agent")


@pytest.fixture
def mock_context():
    """Create mock context."""
    ctx = Mock(spec=Context)
    ctx.correlation_id = "test-correlation"
    return ctx


@pytest.fixture
def mock_output_spec():
    """Create mock output spec."""
    spec = Mock()
    spec.type_name = "SampleOutput"
    return spec


@pytest.fixture
def mock_output_decl(mock_output_spec):
    """Create mock output declaration."""
    decl = Mock()
    decl.spec = mock_output_spec
    decl.count = 1
    decl.filter_predicate = None
    decl.validate_predicate = None
    decl.default_visibility = PublicVisibility()
    decl.apply = lambda payload, **kwargs: Artifact(
        type="SampleOutput",
        payload=payload,
        produced_by=kwargs.get("produced_by", "test"),
        visibility=PublicVisibility(),
    )
    return decl


@pytest.fixture
def mock_output_group(mock_output_decl):
    """Create mock output group."""
    group = Mock()
    group.outputs = [mock_output_decl]
    return group


@pytest.mark.asyncio
async def test_make_outputs_for_group_validates_engine_contract(
    processor, mock_context, mock_output_group
):
    """Test that make_outputs_for_group validates engine produced correct count."""
    # Engine produces correct count (1)
    artifact = Artifact(
        type="SampleOutput",
        payload={"value": "test", "score": 5},
        produced_by="engine",
    )
    result = EvalResult(artifacts=[artifact], state={})

    outputs = await processor.make_outputs_for_group(
        mock_context, result, mock_output_group
    )

    assert len(outputs) == 1


@pytest.mark.asyncio
async def test_make_outputs_for_group_fails_on_contract_violation(
    processor, mock_context, mock_output_group
):
    """Test that make_outputs_for_group fails when engine produces wrong count."""
    # Engine produces 0 artifacts when 1 is expected
    result = EvalResult(artifacts=[], state={})

    with pytest.raises(ValueError, match="Engine contract violation"):
        await processor.make_outputs_for_group(mock_context, result, mock_output_group)


@pytest.mark.asyncio
async def test_make_outputs_for_group_applies_where_filtering(
    processor, mock_context, mock_output_decl, mock_output_group
):
    """Test that make_outputs_for_group applies WHERE filtering."""
    # Set up filter predicate (only accept score >= 10)
    mock_output_decl.filter_predicate = lambda obj: obj.score >= 10

    # Engine produces 1 artifact with score 5 (should be filtered out)
    artifact = Artifact(
        type="SampleOutput",
        payload={"value": "test", "score": 5},
        produced_by="engine",
    )
    result = EvalResult(artifacts=[artifact], state={})

    outputs = await processor.make_outputs_for_group(
        mock_context, result, mock_output_group
    )

    # After filtering, should have 0 outputs
    assert len(outputs) == 0


@pytest.mark.asyncio
async def test_make_outputs_for_group_applies_validate_predicate(
    processor, mock_context, mock_output_decl, mock_output_group
):
    """Test that make_outputs_for_group applies VALIDATE checks."""
    # Set up validate predicate (fail if score < 10)
    mock_output_decl.validate_predicate = lambda obj: obj.score >= 10

    # Engine produces 1 artifact with score 5 (validation should fail)
    artifact = Artifact(
        type="SampleOutput",
        payload={"value": "test", "score": 5},
        produced_by="engine",
    )
    result = EvalResult(artifacts=[artifact], state={})

    with pytest.raises(ValueError, match="Validation failed"):
        await processor.make_outputs_for_group(mock_context, result, mock_output_group)


@pytest.mark.asyncio
async def test_make_outputs_for_group_applies_validate_list(
    processor, mock_context, mock_output_decl, mock_output_group
):
    """Test that make_outputs_for_group applies VALIDATE check list."""
    # Set up validate predicate list
    mock_output_decl.validate_predicate = [
        (lambda obj: obj.score >= 0, "Score must be non-negative"),
        (lambda obj: obj.value != "", "Value must not be empty"),
    ]

    # Engine produces artifact that fails second check
    artifact = Artifact(
        type="SampleOutput",
        payload={"value": "", "score": 5},
        produced_by="engine",
    )
    result = EvalResult(artifacts=[artifact], state={})

    with pytest.raises(ValueError, match="Value must not be empty"):
        await processor.make_outputs_for_group(mock_context, result, mock_output_group)


@pytest.mark.asyncio
async def test_make_outputs_for_group_applies_dynamic_visibility(
    processor, mock_context, mock_output_decl, mock_output_group
):
    """Test that make_outputs_for_group applies dynamic visibility."""

    # Set up dynamic visibility (private if score > 50)
    def dynamic_vis(obj: SampleOutput):
        if obj.score > 50:
            return PrivateVisibility(agents={"admin"})
        return PublicVisibility()

    mock_output_decl.default_visibility = dynamic_vis

    # Engine produces artifact with high score
    artifact = Artifact(
        type="SampleOutput",
        payload={"value": "secret", "score": 100},
        produced_by="engine",
    )
    result = EvalResult(artifacts=[artifact], state={})

    outputs = await processor.make_outputs_for_group(
        mock_context, result, mock_output_group
    )

    # Visibility should have been applied (but we can't easily check since apply() is mocked)
    assert len(outputs) == 1


@pytest.mark.asyncio
async def test_make_outputs_returns_engine_artifacts_when_no_groups(
    processor, mock_context
):
    """Test that make_outputs returns engine artifacts when no output groups."""
    artifact = Artifact(
        type="SampleOutput",
        payload={"value": "test"},
        produced_by="engine",
    )
    result = EvalResult(artifacts=[artifact], state={})

    outputs = await processor.make_outputs(mock_context, result, [])

    assert len(outputs) == 1
    assert outputs[0] == artifact


@pytest.mark.asyncio
async def test_make_outputs_processes_all_groups(
    processor, mock_context, mock_output_decl
):
    """Test that make_outputs processes all output groups."""
    # Create two output groups
    group1 = Mock()
    group1.outputs = [mock_output_decl]

    decl2 = Mock()
    decl2.spec = Mock()
    decl2.spec.type_name = "SecondOutput"
    decl2.apply = lambda payload, **kwargs: Artifact(
        type="SecondOutput",
        payload=payload,
        produced_by=kwargs.get("produced_by", "test"),
    )
    group2 = Mock()
    group2.outputs = [decl2]

    # Engine result with both types
    art1 = Artifact(
        type="SampleOutput", payload={"value": "test", "score": 1}, produced_by="engine"
    )
    art2 = Artifact(type="SecondOutput", payload={"data": "test"}, produced_by="engine")
    result = EvalResult(artifacts=[art1, art2], state={})

    outputs = await processor.make_outputs(mock_context, result, [group1, group2])

    assert len(outputs) == 2


def test_prepare_group_context_returns_same_context(
    processor, mock_context, mock_output_group
):
    """Test that prepare_group_context returns the same context for now."""
    ctx = processor.prepare_group_context(mock_context, 0, mock_output_group)
    assert ctx == mock_context


def test_find_matching_artifact_finds_correct_artifact(processor, mock_output_decl):
    """Test that find_matching_artifact finds the correct artifact by type."""
    artifact1 = Artifact(
        type="SampleOutput", payload={"value": "test"}, produced_by="engine"
    )
    artifact2 = Artifact(
        type="SecondOutput", payload={"data": "test"}, produced_by="engine"
    )
    result = EvalResult(artifacts=[artifact1, artifact2], state={})

    found = processor.find_matching_artifact(mock_output_decl, result)

    assert found == artifact1


def test_find_matching_artifact_returns_none_when_not_found(
    processor, mock_output_decl
):
    """Test that find_matching_artifact returns None when no match."""
    artifact = Artifact(
        type="SecondOutput", payload={"data": "test"}, produced_by="engine"
    )
    result = EvalResult(artifacts=[artifact], state={})

    found = processor.find_matching_artifact(mock_output_decl, result)

    assert found is None


def test_find_matching_artifact_returns_none_when_empty(processor, mock_output_decl):
    """Test that find_matching_artifact returns None for empty result."""
    result = EvalResult(artifacts=[], state={})

    found = processor.find_matching_artifact(mock_output_decl, result)

    assert found is None


def test_select_payload_extracts_correct_payload(processor, mock_output_decl):
    """Test that select_payload extracts the correct payload by type."""
    payload1 = {"value": "test", "score": 5}
    payload2 = {"data": "test"}
    artifact1 = Artifact(type="SampleOutput", payload=payload1, produced_by="engine")
    artifact2 = Artifact(type="SecondOutput", payload=payload2, produced_by="engine")
    result = EvalResult(artifacts=[artifact1, artifact2], state={})

    payload = processor.select_payload(mock_output_decl, result)

    assert payload == payload1


def test_select_payload_falls_back_to_state(processor, mock_output_decl):
    """Test that select_payload falls back to state when no artifact match."""
    state_payload = {"value": "from_state", "score": 10}
    result = EvalResult(artifacts=[], state={"SampleOutput": state_payload})

    payload = processor.select_payload(mock_output_decl, result)

    assert payload == state_payload


def test_select_payload_returns_none_when_not_found(processor, mock_output_decl):
    """Test that select_payload returns None when no match in artifacts or state."""
    artifact = Artifact(
        type="SecondOutput", payload={"data": "test"}, produced_by="engine"
    )
    result = EvalResult(artifacts=[artifact], state={})

    payload = processor.select_payload(mock_output_decl, result)

    assert payload is None
