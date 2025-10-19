"""Tests for ArtifactFilter."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import BaseModel

from flock.core.artifacts import Artifact
from flock.core.store import FilterConfig
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type
from flock.storage.in_memory.artifact_filter import ArtifactFilter


@flock_type(name="TestFilterTypeA")
class TestFilterTypeA(BaseModel):
    """Test type A for filter tests."""

    data: str


@flock_type(name="TestFilterTypeB")
class TestFilterTypeB(BaseModel):
    """Test type B for filter tests."""

    value: int


@pytest.fixture
def base_artifact():
    """Create a base artifact for testing."""
    return Artifact(
        type="TestFilterTypeA",
        produced_by="agent1",
        payload={"data": "test"},
        tags={"alpha", "beta"},
        correlation_id=uuid4(),
        visibility=PublicVisibility(),
    )


def test_empty_filter_matches_all(base_artifact):
    """Test that empty filter matches all artifacts."""
    artifact_filter = ArtifactFilter(FilterConfig())
    assert artifact_filter.matches(base_artifact)


def test_filter_by_type_name_matches(base_artifact):
    """Test filtering by matching type name."""
    artifact_filter = ArtifactFilter(FilterConfig(type_names={"TestFilterTypeA"}))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_type_name_no_match(base_artifact):
    """Test filtering by non-matching type name."""
    artifact_filter = ArtifactFilter(FilterConfig(type_names={"TestFilterTypeB"}))
    assert not artifact_filter.matches(base_artifact)


def test_filter_by_producer_matches(base_artifact):
    """Test filtering by matching producer."""
    artifact_filter = ArtifactFilter(FilterConfig(produced_by={"agent1"}))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_producer_no_match(base_artifact):
    """Test filtering by non-matching producer."""
    artifact_filter = ArtifactFilter(FilterConfig(produced_by={"agent2"}))
    assert not artifact_filter.matches(base_artifact)


def test_filter_by_correlation_id_matches(base_artifact):
    """Test filtering by matching correlation ID."""
    corr_id = str(base_artifact.correlation_id)
    artifact_filter = ArtifactFilter(FilterConfig(correlation_id=corr_id))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_correlation_id_no_match(base_artifact):
    """Test filtering by non-matching correlation ID."""
    artifact_filter = ArtifactFilter(FilterConfig(correlation_id="different-id"))
    assert not artifact_filter.matches(base_artifact)


def test_filter_by_correlation_id_none_artifact():
    """Test filtering when artifact has no correlation ID."""
    artifact = Artifact(
        type="TestFilterTypeA",
        produced_by="agent1",
        payload={"data": "test"},
        correlation_id=None,
    )
    artifact_filter = ArtifactFilter(FilterConfig(correlation_id="some-id"))
    assert not artifact_filter.matches(artifact)


def test_filter_by_tags_matches(base_artifact):
    """Test filtering by tags subset."""
    artifact_filter = ArtifactFilter(FilterConfig(tags={"alpha"}))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_tags_multiple_matches(base_artifact):
    """Test filtering by multiple tags."""
    artifact_filter = ArtifactFilter(FilterConfig(tags={"alpha", "beta"}))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_tags_no_match(base_artifact):
    """Test filtering by non-matching tags."""
    artifact_filter = ArtifactFilter(FilterConfig(tags={"gamma"}))
    assert not artifact_filter.matches(base_artifact)


def test_filter_by_visibility_matches(base_artifact):
    """Test filtering by matching visibility."""
    artifact_filter = ArtifactFilter(FilterConfig(visibility={"Public"}))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_visibility_no_match(base_artifact):
    """Test filtering by non-matching visibility."""
    artifact_filter = ArtifactFilter(FilterConfig(visibility={"Private"}))
    assert not artifact_filter.matches(base_artifact)


def test_filter_by_time_range_within(base_artifact):
    """Test filtering by time range when artifact is within range."""
    now = datetime.now(UTC)
    start = now.replace(year=now.year - 1)  # One year ago
    end = now.replace(year=now.year + 1)  # One year from now

    artifact_filter = ArtifactFilter(FilterConfig(start=start, end=end))
    assert artifact_filter.matches(base_artifact)


def test_filter_by_time_range_before_start(base_artifact):
    """Test filtering when artifact is before start time."""
    future_start = datetime.now(UTC).replace(year=datetime.now(UTC).year + 1)

    artifact_filter = ArtifactFilter(FilterConfig(start=future_start))
    assert not artifact_filter.matches(base_artifact)


def test_filter_by_time_range_after_end(base_artifact):
    """Test filtering when artifact is after end time."""
    past_end = datetime.now(UTC).replace(year=datetime.now(UTC).year - 1)

    artifact_filter = ArtifactFilter(FilterConfig(end=past_end))
    assert not artifact_filter.matches(base_artifact)


def test_filter_combined_all_match(base_artifact):
    """Test combined filters when all criteria match."""
    corr_id = str(base_artifact.correlation_id)
    artifact_filter = ArtifactFilter(
        FilterConfig(
            type_names={"TestFilterTypeA"},
            produced_by={"agent1"},
            correlation_id=corr_id,
            tags={"alpha"},
            visibility={"Public"},
        )
    )
    assert artifact_filter.matches(base_artifact)


def test_filter_combined_one_fails(base_artifact):
    """Test combined filters when one criterion fails."""
    corr_id = str(base_artifact.correlation_id)
    artifact_filter = ArtifactFilter(
        FilterConfig(
            type_names={"TestFilterTypeA"},
            produced_by={"agent2"},  # This doesn't match
            correlation_id=corr_id,
            tags={"alpha"},
            visibility={"Public"},
        )
    )
    assert not artifact_filter.matches(base_artifact)


def test_canonical_type_resolution():
    """Test that type names are resolved to canonical names."""
    # Create filter with type name
    artifact_filter = ArtifactFilter(FilterConfig(type_names={"TestFilterTypeA"}))

    # Should have canonical types set
    assert artifact_filter.canonical_types is not None
    assert "TestFilterTypeA" in artifact_filter.canonical_types
