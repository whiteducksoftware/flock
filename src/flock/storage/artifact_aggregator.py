"""Artifact aggregation utilities for summary statistics.

Handles aggregation logic for artifact collections, computing statistics
like type distribution, producer counts, and time ranges.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flock.core.artifacts import Artifact
from flock.utils.time_utils import format_time_span


class ArtifactAggregator:
    """
    Aggregates artifact statistics for summary reports.

    Provides clean separation of aggregation logic from storage implementations.
    Each aggregation method is simple and focused.
    """

    def aggregate_by_type(self, artifacts: list[Artifact]) -> dict[str, int]:
        """
        Count artifacts by type.

        Args:
            artifacts: List of artifacts to aggregate

        Returns:
            Dict mapping type names to counts
        """
        by_type: dict[str, int] = {}
        for artifact in artifacts:
            by_type[artifact.type] = by_type.get(artifact.type, 0) + 1
        return by_type

    def aggregate_by_producer(self, artifacts: list[Artifact]) -> dict[str, int]:
        """
        Count artifacts by producer.

        Args:
            artifacts: List of artifacts to aggregate

        Returns:
            Dict mapping producer names to counts
        """
        by_producer: dict[str, int] = {}
        for artifact in artifacts:
            by_producer[artifact.produced_by] = (
                by_producer.get(artifact.produced_by, 0) + 1
            )
        return by_producer

    def aggregate_by_visibility(self, artifacts: list[Artifact]) -> dict[str, int]:
        """
        Count artifacts by visibility kind.

        Args:
            artifacts: List of artifacts to aggregate

        Returns:
            Dict mapping visibility kinds to counts
        """
        by_visibility: dict[str, int] = {}
        for artifact in artifacts:
            kind = getattr(artifact.visibility, "kind", "Unknown")
            by_visibility[kind] = by_visibility.get(kind, 0) + 1
        return by_visibility

    def aggregate_tags(self, artifacts: list[Artifact]) -> dict[str, int]:
        """
        Count tag occurrences across artifacts.

        Args:
            artifacts: List of artifacts to aggregate

        Returns:
            Dict mapping tag names to occurrence counts
        """
        tag_counts: dict[str, int] = {}
        for artifact in artifacts:
            for tag in artifact.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return tag_counts

    def get_date_range(
        self, artifacts: list[Artifact]
    ) -> tuple[datetime | None, datetime | None]:
        """
        Find earliest and latest creation times.

        Args:
            artifacts: List of artifacts to analyze

        Returns:
            Tuple of (earliest, latest) datetimes, or (None, None) if empty
        """
        if not artifacts:
            return None, None

        earliest: datetime | None = None
        latest: datetime | None = None

        for artifact in artifacts:
            if earliest is None or artifact.created_at < earliest:
                earliest = artifact.created_at
            if latest is None or artifact.created_at > latest:
                latest = artifact.created_at

        return earliest, latest

    def build_summary(
        self,
        artifacts: list[Artifact],
        total: int,
        is_full_window: bool,
    ) -> dict[str, Any]:
        """
        Build complete summary statistics for artifacts.

        Args:
            artifacts: List of artifacts to summarize
            total: Total count (may differ from len(artifacts) if paginated)
            is_full_window: Whether this represents all artifacts (no filters)

        Returns:
            Dictionary with complete summary statistics:
            - total: Total artifact count
            - by_type: Type distribution
            - by_producer: Producer distribution
            - by_visibility: Visibility distribution
            - tag_counts: Tag occurrence counts
            - earliest_created_at: ISO string of earliest artifact
            - latest_created_at: ISO string of latest artifact
            - is_full_window: Whether all artifacts included
            - window_span_label: Human-readable time span
        """
        by_type = self.aggregate_by_type(artifacts)
        by_producer = self.aggregate_by_producer(artifacts)
        by_visibility = self.aggregate_by_visibility(artifacts)
        tag_counts = self.aggregate_tags(artifacts)
        earliest, latest = self.get_date_range(artifacts)

        window_span_label = format_time_span(earliest, latest)

        return {
            "total": total,
            "by_type": by_type,
            "by_producer": by_producer,
            "by_visibility": by_visibility,
            "tag_counts": tag_counts,
            "earliest_created_at": earliest.isoformat() if earliest else None,
            "latest_created_at": latest.isoformat() if latest else None,
            "is_full_window": is_full_window,
            "window_span_label": window_span_label,
        }
