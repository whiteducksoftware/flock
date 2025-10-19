"""
CorrelationEngine: Manages correlated AND gates with time/count windows.

Supports JoinSpec-based correlation:
- Extracts correlation keys from artifacts
- Groups artifacts by correlation key
- Enforces time windows (timedelta) or count windows (int)
- Triggers agents when all required types arrive within window
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact
    from flock.core.subscription import JoinSpec, Subscription


class CorrelationGroup:
    """
    Tracks artifacts waiting for correlation within a specific key group.

    Example: For patient-123, track X-ray (TypeA) and Lab results (TypeB).
    When both arrive within time/count window, trigger the agent.
    """

    def __init__(
        self,
        *,
        correlation_key: Any,
        required_types: set[str],
        type_counts: dict[str, int],
        window_spec: timedelta | int,
        created_at_sequence: int,
    ):
        self.correlation_key = correlation_key
        self.required_types = required_types  # e.g., {"TypeA", "TypeB"}
        self.type_counts = type_counts  # e.g., {"TypeA": 1, "TypeB": 1}
        self.window_spec = window_spec  # timedelta or int
        self.created_at_sequence = (
            created_at_sequence  # Global sequence when first artifact arrived
        )
        self.created_at_time: datetime | None = (
            None  # Timestamp when first artifact arrived
        )

        # Waiting pool: type -> list of artifacts
        self.waiting_artifacts: dict[str, list[Artifact]] = defaultdict(list)

    def add_artifact(self, artifact: Artifact, current_sequence: int) -> None:
        """Add artifact to this correlation group's waiting pool."""
        if self.created_at_time is None:
            self.created_at_time = datetime.now(UTC)

        self.waiting_artifacts[artifact.type].append(artifact)

    def is_complete(self) -> bool:
        """Check if all required types have arrived with correct counts."""
        for type_name, required_count in self.type_counts.items():
            if len(self.waiting_artifacts.get(type_name, [])) < required_count:
                return False
        return True

    def is_expired(self, current_sequence: int) -> bool:
        """Check if this correlation group has expired based on window."""
        if isinstance(self.window_spec, int):
            # Count window: expired if current sequence exceeds created + window
            return (current_sequence - self.created_at_sequence) > self.window_spec
        if isinstance(self.window_spec, timedelta):
            # Time window: expired if current time exceeds created + window
            if self.created_at_time is None:
                return False

            elapsed = datetime.now(UTC) - self.created_at_time
            return elapsed > self.window_spec
        return False

    def get_artifacts(self) -> list[Artifact]:
        """Get all artifacts in the order they should be passed to the agent."""
        result = []
        for type_name in self.required_types:
            # Get the required number of artifacts for this type
            required_count = self.type_counts[type_name]
            artifacts_for_type = self.waiting_artifacts[type_name][:required_count]
            result.extend(artifacts_for_type)
        return result


class CorrelationEngine:
    """
    Manages correlation state for JoinSpec subscriptions.

    Responsibilities:
    1. Extract correlation keys from artifacts using JoinSpec.by lambda
    2. Group artifacts by correlation key
    3. Track time/count windows per correlation group
    4. Return complete correlation groups when all types arrive within window
    5. Clean up expired correlations

    Example usage:
        engine = CorrelationEngine()

        # Add artifact to correlation tracking
        completed = engine.add_artifact(
            artifact=xray_artifact,
            subscription=subscription,  # Has JoinSpec with by + within
            agent_name="diagnostician"
        )

        if completed:
            # All types arrived! Trigger agent with correlated artifacts
            artifacts = completed.get_artifacts()
    """

    def __init__(self):
        # Global artifact sequence (for count windows)
        self.global_sequence = 0

        # Correlation state per (agent, subscription_index)
        # Key: (agent_name, subscription_index)
        # Value: dict[correlation_key, CorrelationGroup]
        self.correlation_groups: dict[tuple[str, int], dict[Any, CorrelationGroup]] = (
            defaultdict(dict)
        )

    def add_artifact(
        self,
        *,
        artifact: Artifact,
        subscription: Subscription,
        subscription_index: int,
    ) -> CorrelationGroup | None:
        """
        Add artifact to correlation tracking.

        Returns:
            CorrelationGroup if correlation is complete, None otherwise
        """
        # Increment global sequence (for count windows)
        self.global_sequence += 1
        current_sequence = self.global_sequence

        # Extract correlation key using JoinSpec.by lambda
        if subscription.join is None:
            raise ValueError("Subscription must have JoinSpec for correlation")

        join_spec: JoinSpec = subscription.join

        # Parse artifact payload to extract correlation key
        from flock.registry import type_registry

        model_cls = type_registry.resolve(artifact.type)
        payload_instance = model_cls(**artifact.payload)

        try:
            correlation_key = join_spec.by(payload_instance)
        except Exception:
            # Key extraction failed - skip this artifact
            # TODO: Log warning?
            return None

        # Get or create correlation group for this key
        pool_key = (subscription.agent_name, subscription_index)
        groups = self.correlation_groups[pool_key]

        if correlation_key not in groups:
            # Create new correlation group
            groups[correlation_key] = CorrelationGroup(
                correlation_key=correlation_key,
                required_types=subscription.type_names,
                type_counts=subscription.type_counts,
                window_spec=join_spec.within,
                created_at_sequence=current_sequence,
            )

        group = groups[correlation_key]

        # Check if group expired (for count windows, check BEFORE adding)
        if group.is_expired(current_sequence):
            # Group expired - remove it and start fresh
            del groups[correlation_key]
            # Create new group
            groups[correlation_key] = CorrelationGroup(
                correlation_key=correlation_key,
                required_types=subscription.type_names,
                type_counts=subscription.type_counts,
                window_spec=join_spec.within,
                created_at_sequence=current_sequence,
            )
            group = groups[correlation_key]

        # Add artifact to group
        group.add_artifact(artifact, current_sequence)

        # Check if correlation is complete
        if group.is_complete():
            # Complete! Remove from tracking and return
            completed_group = groups.pop(correlation_key)
            return completed_group

        # Not complete yet
        return None

    def cleanup_expired(self, agent_name: str, subscription_index: int) -> None:
        """Clean up expired correlation groups for a specific subscription."""
        pool_key = (agent_name, subscription_index)
        groups = self.correlation_groups.get(pool_key, {})

        # Remove expired groups
        expired_keys = [
            key
            for key, group in groups.items()
            if group.is_expired(self.global_sequence)
        ]

        for key in expired_keys:
            del groups[key]


__all__ = ["CorrelationEngine", "CorrelationGroup"]
