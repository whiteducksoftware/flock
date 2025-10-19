"""Agent history aggregation for in-memory storage.

Handles aggregation of produced/consumed artifacts for agent history summaries.
Extracted from store.py to reduce complexity from B (7) to A (4).
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.core.store import ArtifactEnvelope


class HistoryAggregator:
    """
    Aggregate agent history from artifact envelopes.

    Provides focused aggregation methods for produced and consumed artifacts,
    keeping complexity low through functional patterns.
    """

    def aggregate(
        self, envelopes: list[ArtifactEnvelope], agent_id: str
    ) -> dict[str, Any]:
        """
        Aggregate produced and consumed statistics for an agent.

        Args:
            envelopes: List of artifact envelopes with consumptions
            agent_id: Agent to aggregate history for

        Returns:
            Dictionary with produced and consumed statistics:
            {
                "produced": {"total": int, "by_type": dict[str, int]},
                "consumed": {"total": int, "by_type": dict[str, int]}
            }

        Examples:
            >>> aggregator = HistoryAggregator()
            >>> summary = aggregator.aggregate(envelopes, "agent1")
            >>> summary["produced"]["total"]
            42
        """
        produced = self._aggregate_produced(envelopes, agent_id)
        consumed = self._aggregate_consumed(envelopes, agent_id)

        return {
            "produced": {
                "total": sum(produced.values()),
                "by_type": dict(produced),
            },
            "consumed": {
                "total": sum(consumed.values()),
                "by_type": dict(consumed),
            },
        }

    def _aggregate_produced(
        self, envelopes: list[ArtifactEnvelope], agent_id: str
    ) -> defaultdict[str, int]:
        """
        Count artifacts produced by agent, grouped by type.

        Args:
            envelopes: Artifact envelopes to analyze
            agent_id: Producer to match

        Returns:
            Dict mapping artifact types to counts
        """
        from flock.core.store import ArtifactEnvelope

        produced_by_type: defaultdict[str, int] = defaultdict(int)

        for envelope in envelopes:
            if not isinstance(envelope, ArtifactEnvelope):
                raise TypeError("Expected ArtifactEnvelope instance")

            artifact = envelope.artifact
            if artifact.produced_by == agent_id:
                produced_by_type[artifact.type] += 1

        return produced_by_type

    def _aggregate_consumed(
        self, envelopes: list[ArtifactEnvelope], agent_id: str
    ) -> defaultdict[str, int]:
        """
        Count artifacts consumed by agent, grouped by type.

        Args:
            envelopes: Artifact envelopes with consumption records
            agent_id: Consumer to match

        Returns:
            Dict mapping artifact types to consumption counts
        """
        from flock.core.store import ArtifactEnvelope

        consumed_by_type: defaultdict[str, int] = defaultdict(int)

        for envelope in envelopes:
            if not isinstance(envelope, ArtifactEnvelope):
                raise TypeError("Expected ArtifactEnvelope instance")

            artifact = envelope.artifact
            for consumption in envelope.consumptions:
                if consumption.consumer == agent_id:
                    consumed_by_type[artifact.type] += 1

        return consumed_by_type
