"""Agent subscription declarations and helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from flock.registry import type_registry


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact


Predicate = Callable[[BaseModel], bool]


@dataclass
class TextPredicate:
    """Semantic text matching predicate.

    Args:
        query: The semantic query text to match against
        threshold: Minimum similarity score (0.0 to 1.0) to consider a match
        field: Optional field name to extract from payload. If None, uses all text.
    """

    query: str
    threshold: float = 0.4  # Default threshold for semantic matching
    field: str | None = None  # Optional field to extract from payload


@dataclass
class JoinSpec:
    """
    Specification for correlated AND gates.

    Correlates artifacts by a common key within a time OR count window.

    Examples:
        # Time-based correlation (within 5 minutes)
        JoinSpec(
            by=lambda x: x.correlation_id,
            within=timedelta(minutes=5)
        )

        # Count-based correlation (within next 10 artifacts)
        JoinSpec(
            by=lambda x: x.correlation_id,
            within=10
        )

    Args:
        by: Callable that extracts the correlation key from an artifact payload
        within: Window for correlation
            - timedelta: Time window (artifacts must arrive within this time)
            - int: Count window (artifacts must arrive within N published artifacts)
    """

    by: Callable[[BaseModel], Any]  # Extract correlation key from payload
    within: timedelta | int  # Time window OR count window for correlation


@dataclass
class BatchSpec:
    """
    Specification for batch processing.

    Accumulates artifacts and triggers agent when:
    - Size threshold reached (e.g., batch of 10)
    - Timeout expires (e.g., flush every 30 seconds)
    - Whichever comes first

    Examples:
        # Size-based batching (flush when 25 artifacts accumulated)
        BatchSpec(size=25)

        # Timeout-based batching (flush every 30 seconds)
        BatchSpec(timeout=timedelta(seconds=30))

        # Hybrid (whichever comes first)
        BatchSpec(size=100, timeout=timedelta(minutes=5))

    Args:
        size: Optional batch size threshold (flush when this many artifacts accumulated)
        timeout: Optional timeout threshold (flush when this much time elapsed since first artifact)

    Note: At least one of size or timeout must be specified.
    """

    size: int | None = None
    timeout: timedelta | None = None

    def __post_init__(self):
        if self.size is None and self.timeout is None:
            raise ValueError("BatchSpec requires at least one of: size, timeout")


class Subscription:
    """Defines how an agent consumes artifacts from the blackboard."""

    def __init__(
        self,
        *,
        agent_name: str | None = None,
        types: Sequence[type[BaseModel]],
        where: Sequence[Predicate] | None = None,
        text_predicates: Sequence[TextPredicate] | None = None,
        semantic_match: str | list[str | dict[str, Any]] | dict[str, Any] | None = None,
        from_agents: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        join: JoinSpec | None = None,
        batch: BatchSpec | None = None,
        mode: str = "both",
        priority: int = 0,
    ) -> None:
        if not types:
            raise ValueError("Subscription must declare at least one type.")
        self.agent_name = agent_name or ""
        self.type_models: list[type[BaseModel]] = list(types)

        # Register all types and build counts (supports duplicates for count-based AND gates)
        type_name_list = [type_registry.register(t) for t in types]
        self.type_names: set[str] = set(
            type_name_list
        )  # Unique type names (for matching)

        # Count-based AND gate: Track how many of each type are required
        # Example: .consumes(A, A, B) → {"TypeA": 2, "TypeB": 1}
        self.type_counts: dict[str, int] = {}
        for type_name in type_name_list:
            self.type_counts[type_name] = self.type_counts.get(type_name, 0) + 1

        self.where = list(where or [])

        # Parse semantic_match parameter into TextPredicate objects
        parsed_text_predicates = self._parse_semantic_match_parameter(semantic_match)
        self.text_predicates = list(text_predicates or []) + parsed_text_predicates

        self.from_agents = set(from_agents or [])
        self.tags = set(tags or [])
        self.join = join
        self.batch = batch
        self.mode = mode
        self.priority = priority

    def _parse_semantic_match_parameter(
        self, semantic_match: str | list[str | dict[str, Any]] | dict[str, Any] | None
    ) -> list[TextPredicate]:
        """Parse the semantic_match parameter into TextPredicate objects.

        Args:
            semantic_match: Can be:
                - str: "query" → TextPredicate(query="query", threshold=0.4)
                - list: ["q1", "q2"] → multiple TextPredicates (AND logic)
                       or [{"query": "q1", "threshold": 0.8}, ...] with explicit thresholds
                - dict: {"query": "...", "threshold": 0.8, "field": "body"}

        Returns:
            List of TextPredicate objects
        """
        if semantic_match is None:
            return []

        if isinstance(semantic_match, str):
            return [TextPredicate(query=semantic_match)]

        if isinstance(semantic_match, list):
            # Handle both list of strings and list of dicts
            predicates = []
            for item in semantic_match:
                if isinstance(item, str):
                    predicates.append(TextPredicate(query=item))
                elif isinstance(item, dict):
                    query = item.get("query", "")
                    threshold = item.get("threshold", 0.4)
                    field = item.get("field", None)
                    predicates.append(
                        TextPredicate(query=query, threshold=threshold, field=field)
                    )
            return predicates

        if isinstance(semantic_match, dict):
            query = semantic_match.get("query", "")
            threshold = semantic_match.get("threshold", 0.4)  # Match dataclass default
            field = semantic_match.get("field", None)
            return [TextPredicate(query=query, threshold=threshold, field=field)]

        return []

    def accepts_direct(self) -> bool:
        return self.mode in {"direct", "both"}

    def accepts_events(self) -> bool:
        return self.mode in {"events", "both"}

    def matches(self, artifact: Artifact) -> bool:
        if artifact.type not in self.type_names:
            return False
        if self.from_agents and artifact.produced_by not in self.from_agents:
            return False
        if self.tags and not artifact.tags.intersection(self.tags):
            return False

        # Evaluate where predicates on typed payloads
        model_cls = type_registry.resolve(artifact.type)
        payload = model_cls(**artifact.payload)
        for predicate in self.where:
            try:
                if not predicate(payload):
                    return False
            except Exception:
                return False

        # Evaluate text predicates using semantic matching
        if self.text_predicates:
            if not self._matches_text_predicates(artifact):
                return False

        return True

    def _matches_text_predicates(self, artifact: Artifact) -> bool:
        """Check if artifact matches all text predicates (AND logic).

        Args:
            artifact: The artifact to check

        Returns:
            bool: True if all text predicates match (or if semantic unavailable)
        """
        # Check if semantic features available
        try:
            from flock.semantic import SEMANTIC_AVAILABLE, EmbeddingService
        except ImportError:
            # Graceful degradation - if semantic not available, skip text predicates
            return True

        if not SEMANTIC_AVAILABLE:
            # Graceful degradation
            return True

        try:
            embedding_service = EmbeddingService.get_instance()
        except Exception:
            # If embedding service fails, degrade gracefully
            return True

        # Extract text from artifact payload
        artifact_text = self._extract_text_from_payload(artifact.payload)
        if not artifact_text or not artifact_text.strip():
            # No text to match against
            return False

        # Check all predicates (AND logic)
        for predicate in self.text_predicates:
            try:
                # Extract text based on field specification
                if predicate.field:
                    # Use specific field
                    text_to_match = str(artifact.payload.get(predicate.field, ""))
                else:
                    # Use all text from payload
                    text_to_match = artifact_text

                if not text_to_match or not text_to_match.strip():
                    return False

                # Compute semantic similarity
                similarity = embedding_service.similarity(
                    predicate.query, text_to_match
                )

                # Check threshold
                if similarity < predicate.threshold:
                    return False

            except Exception:
                # If any error occurs, fail the match
                return False

        return True

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

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"Subscription(agent={self.agent_name!r}, types={list(self.type_names)!r}, "
            f"mode={self.mode!r})"
        )


__all__ = [
    "BatchSpec",
    "JoinSpec",
    "Subscription",
    "TextPredicate",
]
