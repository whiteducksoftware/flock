"""Tests for artifact aggregation utilities.

Validates the ArtifactAggregator handles statistics computation correctly
for summary reports.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from flock.core.artifacts import Artifact
from flock.core.visibility import (
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
)
from flock.storage.artifact_aggregator import ArtifactAggregator


@pytest.fixture
def aggregator():
    """Create an ArtifactAggregator instance."""
    return ArtifactAggregator()


@pytest.fixture
def sample_artifacts():
    """Create sample artifacts for testing."""
    now = datetime.now()
    return [
        Artifact(
            type="Result",
            payload={"value": 1},
            produced_by="agent1",
            visibility=PublicVisibility(),
            tags={"tag1", "tag2"},
            created_at=now,
        ),
        Artifact(
            type="Result",
            payload={"value": 2},
            produced_by="agent1",
            visibility=PrivateVisibility(),
            tags={"tag2", "tag3"},
            created_at=now + timedelta(minutes=10),
        ),
        Artifact(
            type="Message",
            payload={"text": "hello"},
            produced_by="agent2",
            visibility=LabelledVisibility(labels={"internal"}),
            tags={"tag1"},
            created_at=now + timedelta(hours=1),
        ),
    ]


class TestAggregateByType:
    """Test artifact type aggregation."""

    def test_aggregate_by_type(self, aggregator, sample_artifacts):
        """Should count artifacts by type correctly."""
        result = aggregator.aggregate_by_type(sample_artifacts)
        assert result == {"Result": 2, "Message": 1}

    def test_aggregate_by_type_empty(self, aggregator):
        """Should return empty dict for empty artifact list."""
        result = aggregator.aggregate_by_type([])
        assert result == {}

    def test_aggregate_by_type_single(self, aggregator):
        """Should handle single artifact correctly."""
        artifact = Artifact(
            type="Test",
            payload={},
            produced_by="agent",
            visibility=PublicVisibility(),
        )
        result = aggregator.aggregate_by_type([artifact])
        assert result == {"Test": 1}


class TestAggregateByProducer:
    """Test artifact producer aggregation."""

    def test_aggregate_by_producer(self, aggregator, sample_artifacts):
        """Should count artifacts by producer correctly."""
        result = aggregator.aggregate_by_producer(sample_artifacts)
        assert result == {"agent1": 2, "agent2": 1}

    def test_aggregate_by_producer_empty(self, aggregator):
        """Should return empty dict for empty artifact list."""
        result = aggregator.aggregate_by_producer([])
        assert result == {}

    def test_aggregate_by_producer_single(self, aggregator):
        """Should handle single artifact correctly."""
        artifact = Artifact(
            type="Test",
            payload={},
            produced_by="producer1",
            visibility=PublicVisibility(),
        )
        result = aggregator.aggregate_by_producer([artifact])
        assert result == {"producer1": 1}


class TestAggregateByVisibility:
    """Test artifact visibility aggregation."""

    def test_aggregate_by_visibility(self, aggregator, sample_artifacts):
        """Should count artifacts by visibility kind correctly."""
        result = aggregator.aggregate_by_visibility(sample_artifacts)
        assert result == {"Public": 1, "Private": 1, "Labelled": 1}

    def test_aggregate_by_visibility_empty(self, aggregator):
        """Should return empty dict for empty artifact list."""
        result = aggregator.aggregate_by_visibility([])
        assert result == {}

    def test_aggregate_by_visibility_unknown(self, aggregator):
        """Should handle artifacts with no visibility kind as 'Unknown'."""
        # Create a mock visibility without kind attribute
        artifact = Artifact(
            type="Test",
            payload={},
            produced_by="agent",
            visibility=PublicVisibility(),
        )
        # Remove kind attribute for testing
        artifact.visibility = type("MockVis", (), {})()
        result = aggregator.aggregate_by_visibility([artifact])
        assert result == {"Unknown": 1}


class TestAggregateTags:
    """Test tag occurrence counting."""

    def test_aggregate_tags(self, aggregator, sample_artifacts):
        """Should count tag occurrences correctly."""
        result = aggregator.aggregate_tags(sample_artifacts)
        assert result == {"tag1": 2, "tag2": 2, "tag3": 1}

    def test_aggregate_tags_empty(self, aggregator):
        """Should return empty dict for empty artifact list."""
        result = aggregator.aggregate_tags([])
        assert result == {}

    def test_aggregate_tags_no_tags(self, aggregator):
        """Should handle artifacts with no tags."""
        artifact = Artifact(
            type="Test",
            payload={},
            produced_by="agent",
            visibility=PublicVisibility(),
            tags=set(),
        )
        result = aggregator.aggregate_tags([artifact])
        assert result == {}


class TestGetDateRange:
    """Test date range extraction."""

    def test_get_date_range(self, aggregator, sample_artifacts):
        """Should find earliest and latest creation times."""
        earliest, latest = aggregator.get_date_range(sample_artifacts)
        assert earliest == sample_artifacts[0].created_at
        assert latest == sample_artifacts[2].created_at

    def test_get_date_range_empty(self, aggregator):
        """Should return (None, None) for empty artifact list."""
        earliest, latest = aggregator.get_date_range([])
        assert earliest is None
        assert latest is None

    def test_get_date_range_single(self, aggregator):
        """Should handle single artifact correctly."""
        now = datetime.now()
        artifact = Artifact(
            type="Test",
            payload={},
            produced_by="agent",
            visibility=PublicVisibility(),
            created_at=now,
        )
        earliest, latest = aggregator.get_date_range([artifact])
        assert earliest == now
        assert latest == now


class TestBuildSummary:
    """Test complete summary building."""

    def test_build_summary_full(self, aggregator, sample_artifacts):
        """Should build complete summary with all statistics."""
        result = aggregator.build_summary(
            sample_artifacts, total=3, is_full_window=True
        )

        assert result["total"] == 3
        assert result["by_type"] == {"Result": 2, "Message": 1}
        assert result["by_producer"] == {"agent1": 2, "agent2": 1}
        assert result["by_visibility"] == {"Public": 1, "Private": 1, "Labelled": 1}
        assert result["tag_counts"] == {"tag1": 2, "tag2": 2, "tag3": 1}
        assert (
            result["earliest_created_at"] == sample_artifacts[0].created_at.isoformat()
        )
        assert result["latest_created_at"] == sample_artifacts[2].created_at.isoformat()
        assert result["is_full_window"] is True
        assert "window_span_label" in result

    def test_build_summary_empty(self, aggregator):
        """Should handle empty artifact list correctly."""
        result = aggregator.build_summary([], total=0, is_full_window=True)

        assert result["total"] == 0
        assert result["by_type"] == {}
        assert result["by_producer"] == {}
        assert result["by_visibility"] == {}
        assert result["tag_counts"] == {}
        assert result["earliest_created_at"] is None
        assert result["latest_created_at"] is None
        assert result["is_full_window"] is True
        assert result["window_span_label"] == "empty"

    def test_build_summary_filtered(self, aggregator, sample_artifacts):
        """Should mark summary as not full window when filtered."""
        result = aggregator.build_summary(
            sample_artifacts, total=3, is_full_window=False
        )
        assert result["is_full_window"] is False

    def test_build_summary_paginated(self, aggregator, sample_artifacts):
        """Should handle total different from artifact count (pagination)."""
        # Simulates returning first 3 of 10 total artifacts
        result = aggregator.build_summary(
            sample_artifacts, total=10, is_full_window=False
        )
        assert result["total"] == 10
        assert len(sample_artifacts) == 3
