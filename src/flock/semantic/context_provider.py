"""Semantic context providers for agent execution.

This module provides context providers that use semantic similarity to find
relevant historical artifacts for agent context.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact
    from flock.core.store import ArtifactStore


class SemanticContextProvider:
    """Context provider that retrieves semantically relevant historical artifacts.

    This provider uses semantic similarity to find artifacts that are relevant
    to a given query text, enabling agents to make decisions based on similar
    past events.

    Args:
        query_text: The semantic query to match against artifacts
        threshold: Minimum similarity score (0.0 to 1.0) to include in results
        limit: Maximum number of artifacts to return
        extract_field: Optional field name to extract from artifact payload for matching.
                      If None, uses all text from payload.
        artifact_type: Optional type filter - only return artifacts of this type
        where: Optional predicate filter for additional filtering

    Example:
        ```python
        provider = SemanticContextProvider(
            query_text="user authentication issues", threshold=0.5, limit=5
        )

        relevant_artifacts = await provider.get_context(store)
        ```
    """

    def __init__(
        self,
        query_text: str,
        threshold: float = 0.4,
        limit: int = 10,
        extract_field: str | None = None,
        artifact_type: type[BaseModel] | None = None,
        where: Callable[[Artifact], bool] | None = None,
    ):
        """Initialize semantic context provider.

        Args:
            query_text: The semantic query text
            threshold: Minimum similarity score (default: 0.4)
            limit: Maximum results to return (default: 10)
            extract_field: Optional field to extract from payload
            artifact_type: Optional type filter
            where: Optional predicate for additional filtering
        """
        if not query_text or not query_text.strip():
            raise ValueError("query_text cannot be empty")

        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be between 0 and 1")

        if limit < 1:
            raise ValueError("limit must be at least 1")

        self.query_text = query_text
        self.threshold = threshold
        self.limit = limit
        self.extract_field = extract_field
        self.artifact_type = artifact_type
        self.where = where

    async def get_context(self, store: ArtifactStore) -> list[Artifact]:
        """Retrieve semantically relevant artifacts from store.

        Args:
            store: The artifact store to query

        Returns:
            List of relevant artifacts, sorted by similarity (highest first)
        """
        # Check if semantic features available
        try:
            from flock.semantic import SEMANTIC_AVAILABLE, EmbeddingService
        except ImportError:
            return []

        if not SEMANTIC_AVAILABLE:
            return []

        try:
            embedding_service = EmbeddingService.get_instance()
        except Exception:
            return []

        # Get query embedding
        try:
            query_embedding = embedding_service.embed(self.query_text)
        except Exception:
            return []

        # Get all artifacts from store
        all_artifacts = await store.list()

        # Filter by type if specified
        if self.artifact_type:
            from flock.registry import type_registry

            type_name = type_registry.register(self.artifact_type)
            all_artifacts = [a for a in all_artifacts if a.type == type_name]

        # Filter by where clause if specified
        if self.where:
            all_artifacts = [a for a in all_artifacts if self.where(a)]

        # Compute similarities and filter
        results: list[tuple[Artifact, float]] = []

        for artifact in all_artifacts:
            try:
                # Extract text from artifact
                if self.extract_field:
                    # Use specific field
                    text = str(artifact.payload.get(self.extract_field, ""))
                else:
                    # Use all text from payload
                    text = self._extract_text_from_payload(artifact.payload)

                if not text or not text.strip():
                    continue

                # Compute similarity
                similarity = embedding_service.similarity(self.query_text, text)

                # Check threshold
                if similarity >= self.threshold:
                    results.append((artifact, similarity))

            except Exception:
                # Skip artifacts that fail processing
                continue

        # Sort by similarity (highest first) and take top N
        results.sort(key=lambda x: x[1], reverse=True)
        return [artifact for artifact, _ in results[: self.limit]]

    def _extract_text_from_payload(self, payload: dict[str, Any]) -> str:
        """Extract all text content from payload.

        Args:
            payload: The artifact payload dict

        Returns:
            str: Concatenated text from all string fields
        """
        text_parts = []
        for value in payload.values():
            if isinstance(value, str):
                text_parts.append(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, str):
                        text_parts.append(item)

        return " ".join(text_parts)
