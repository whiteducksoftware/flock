"""Tests for HistoryAggregator."""

import pytest

from flock.core.artifacts import Artifact
from flock.core.store import ArtifactEnvelope, ConsumptionRecord
from flock.storage.in_memory.history_aggregator import HistoryAggregator


@pytest.fixture
def aggregator():
    """Create history aggregator instance."""
    return HistoryAggregator()


@pytest.fixture
def sample_envelopes():
    """Create sample artifact envelopes for testing."""
    # Agent1 produces 2 Results
    result1 = Artifact(
        type="Result",
        produced_by="agent1",
        payload={"value": 1},
    )
    result2 = Artifact(
        type="Result",
        produced_by="agent1",
        payload={"value": 2},
    )

    # Agent2 produces 1 Message
    message = Artifact(
        type="Message",
        produced_by="agent2",
        payload={"text": "hello"},
    )

    # Agent3 produces 1 Result
    result3 = Artifact(
        type="Result",
        produced_by="agent3",
        payload={"value": 3},
    )

    # Create consumptions: agent1 consumes message, agent2 consumes result1
    consumption1 = ConsumptionRecord(
        artifact_id=message.id,
        consumer="agent1",
        consumed_at=message.created_at,
    )
    consumption2 = ConsumptionRecord(
        artifact_id=result1.id,
        consumer="agent2",
        consumed_at=result1.created_at,
    )

    return [
        ArtifactEnvelope(artifact=result1, consumptions=[consumption2]),
        ArtifactEnvelope(artifact=result2, consumptions=[]),
        ArtifactEnvelope(artifact=message, consumptions=[consumption1]),
        ArtifactEnvelope(artifact=result3, consumptions=[]),
    ]


def test_aggregate_produced_count(aggregator, sample_envelopes):
    """Test aggregating produced artifacts count."""
    summary = aggregator.aggregate(sample_envelopes, "agent1")

    assert summary["produced"]["total"] == 2
    assert summary["produced"]["by_type"]["Result"] == 2


def test_aggregate_consumed_count(aggregator, sample_envelopes):
    """Test aggregating consumed artifacts count."""
    summary = aggregator.aggregate(sample_envelopes, "agent1")

    assert summary["consumed"]["total"] == 1
    assert summary["consumed"]["by_type"]["Message"] == 1


def test_aggregate_no_production(aggregator, sample_envelopes):
    """Test aggregating when agent produced nothing."""
    summary = aggregator.aggregate(sample_envelopes, "agent_nonexistent")

    assert summary["produced"]["total"] == 0
    assert summary["produced"]["by_type"] == {}


def test_aggregate_no_consumption(aggregator, sample_envelopes):
    """Test aggregating when agent consumed nothing."""
    summary = aggregator.aggregate(sample_envelopes, "agent3")

    assert summary["consumed"]["total"] == 0
    assert summary["consumed"]["by_type"] == {}


def test_aggregate_multiple_types(aggregator):
    """Test aggregating with multiple artifact types."""
    envelopes = [
        ArtifactEnvelope(
            artifact=Artifact(type="Result", produced_by="agent1", payload={}),
            consumptions=[],
        ),
        ArtifactEnvelope(
            artifact=Artifact(type="Message", produced_by="agent1", payload={}),
            consumptions=[],
        ),
        ArtifactEnvelope(
            artifact=Artifact(type="Error", produced_by="agent1", payload={}),
            consumptions=[],
        ),
    ]

    summary = aggregator.aggregate(envelopes, "agent1")

    assert summary["produced"]["total"] == 3
    assert summary["produced"]["by_type"]["Result"] == 1
    assert summary["produced"]["by_type"]["Message"] == 1
    assert summary["produced"]["by_type"]["Error"] == 1


def test_aggregate_multiple_consumptions(aggregator):
    """Test aggregating with multiple consumptions of same type."""
    artifact1 = Artifact(type="Result", produced_by="agent2", payload={})
    artifact2 = Artifact(type="Result", produced_by="agent3", payload={})

    consumption1 = ConsumptionRecord(
        artifact_id=artifact1.id,
        consumer="agent1",
        consumed_at=artifact1.created_at,
    )
    consumption2 = ConsumptionRecord(
        artifact_id=artifact2.id,
        consumer="agent1",
        consumed_at=artifact2.created_at,
    )

    envelopes = [
        ArtifactEnvelope(artifact=artifact1, consumptions=[consumption1]),
        ArtifactEnvelope(artifact=artifact2, consumptions=[consumption2]),
    ]

    summary = aggregator.aggregate(envelopes, "agent1")

    assert summary["consumed"]["total"] == 2
    assert summary["consumed"]["by_type"]["Result"] == 2


def test_aggregate_empty_envelopes(aggregator):
    """Test aggregating with empty envelope list."""
    summary = aggregator.aggregate([], "agent1")

    assert summary["produced"]["total"] == 0
    assert summary["produced"]["by_type"] == {}
    assert summary["consumed"]["total"] == 0
    assert summary["consumed"]["by_type"] == {}


def test_aggregate_produced_type_error(aggregator):
    """Test _aggregate_produced with non-ArtifactEnvelope raises TypeError."""
    with pytest.raises(TypeError, match="Expected ArtifactEnvelope instance"):
        aggregator._aggregate_produced(["not an envelope"], "agent1")


def test_aggregate_consumed_type_error(aggregator):
    """Test _aggregate_consumed with non-ArtifactEnvelope raises TypeError."""
    with pytest.raises(TypeError, match="Expected ArtifactEnvelope instance"):
        aggregator._aggregate_consumed(["not an envelope"], "agent1")


def test_aggregate_summary_structure(aggregator, sample_envelopes):
    """Test that aggregate returns correct structure."""
    summary = aggregator.aggregate(sample_envelopes, "agent1")

    # Check top-level keys
    assert "produced" in summary
    assert "consumed" in summary

    # Check produced structure
    assert "total" in summary["produced"]
    assert "by_type" in summary["produced"]
    assert isinstance(summary["produced"]["total"], int)
    assert isinstance(summary["produced"]["by_type"], dict)

    # Check consumed structure
    assert "total" in summary["consumed"]
    assert "by_type" in summary["consumed"]
    assert isinstance(summary["consumed"]["total"], int)
    assert isinstance(summary["consumed"]["by_type"], dict)


def test_aggregate_multiple_consumers_same_artifact(aggregator):
    """Test aggregating when multiple agents consume same artifact."""
    artifact = Artifact(type="Result", produced_by="agent3", payload={})

    consumption1 = ConsumptionRecord(
        artifact_id=artifact.id,
        consumer="agent1",
        consumed_at=artifact.created_at,
    )
    consumption2 = ConsumptionRecord(
        artifact_id=artifact.id,
        consumer="agent2",
        consumed_at=artifact.created_at,
    )

    envelopes = [
        ArtifactEnvelope(artifact=artifact, consumptions=[consumption1, consumption2])
    ]

    # Agent1 consumed it once
    summary1 = aggregator.aggregate(envelopes, "agent1")
    assert summary1["consumed"]["total"] == 1

    # Agent2 also consumed it once
    summary2 = aggregator.aggregate(envelopes, "agent2")
    assert summary2["consumed"]["total"] == 1
