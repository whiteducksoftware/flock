"""Artifact filtering utilities for in-memory storage.

Provides focused filtering logic for InMemoryBlackboardStore.query_artifacts.
Extracted from store.py to reduce complexity from B (10) to A (4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact
    from flock.core.store import FilterConfig


class ArtifactFilter:
    """
    Filter artifacts based on FilterConfig criteria.

    Separates filtering logic from query orchestration for better
    testability and reduced complexity.
    """

    def __init__(self, filters: FilterConfig):
        """
        Initialize filter with configuration.

        Args:
            filters: Filter configuration with optional criteria
        """
        from flock.registry import type_registry

        # Pre-resolve canonical types once
        self.canonical_types: set[str] | None = None
        if filters.type_names:
            self.canonical_types = {
                type_registry.resolve_name(name) for name in filters.type_names
            }

        self.produced_by = filters.produced_by or set()
        self.correlation_id = filters.correlation_id
        self.tags = filters.tags or set()
        self.visibility_kinds = filters.visibility or set()
        self.start = filters.start
        self.end = filters.end

    def matches(self, artifact: Artifact) -> bool:
        """
        Check if artifact matches all filter criteria.

        Uses focused helper methods to keep complexity low (A-rated).
        Each criterion is evaluated independently for clarity.

        Args:
            artifact: Artifact to check against filters

        Returns:
            True if artifact matches all criteria, False otherwise

        Examples:
            >>> filter = ArtifactFilter(FilterConfig(produced_by={"agent1"}))
            >>> artifact = Artifact(type="Result", produced_by="agent1", ...)
            >>> filter.matches(artifact)
            True
        """
        return (
            self._matches_type(artifact)
            and self._matches_producer(artifact)
            and self._matches_correlation(artifact)
            and self._matches_tags(artifact)
            and self._matches_visibility(artifact)
            and self._matches_time_range(artifact)
        )

    def _matches_type(self, artifact: Artifact) -> bool:
        """Check if artifact type matches filter."""
        if not self.canonical_types:
            return True
        return artifact.type in self.canonical_types

    def _matches_producer(self, artifact: Artifact) -> bool:
        """Check if artifact producer matches filter."""
        if not self.produced_by:
            return True
        return artifact.produced_by in self.produced_by

    def _matches_correlation(self, artifact: Artifact) -> bool:
        """Check if artifact correlation ID matches filter."""
        if not self.correlation_id:
            return True
        if artifact.correlation_id is None:
            return False
        return str(artifact.correlation_id) == self.correlation_id

    def _matches_tags(self, artifact: Artifact) -> bool:
        """Check if artifact has all required tags."""
        if not self.tags:
            return True
        return self.tags.issubset(artifact.tags)

    def _matches_visibility(self, artifact: Artifact) -> bool:
        """Check if artifact visibility kind matches filter."""
        if not self.visibility_kinds:
            return True
        return artifact.visibility.kind in self.visibility_kinds

    def _matches_time_range(self, artifact: Artifact) -> bool:
        """Check if artifact creation time is within range."""
        if self.start and artifact.created_at < self.start:
            return False
        if self.end and artifact.created_at > self.end:
            return False
        return True
