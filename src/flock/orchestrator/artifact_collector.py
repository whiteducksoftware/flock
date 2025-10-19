"""Artifact collection and waiting pool management for AND gate logic.

This module implements the waiting pool mechanism that enables `.consumes(A, B)`
to wait for BOTH types before triggering an agent (AND gate logic).

Architecture:
- Each subscription gets a unique waiting pool identified by (agent_name, subscription_index)
- Artifacts are collected per type until all required types are present
- When complete, all collected artifacts are returned for agent execution
- After triggering, the waiting pool is cleared for the next cycle
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from flock.core import Agent
    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription


class ArtifactCollector:
    """Manages waiting pools for multi-type subscriptions (AND gate logic).

    Each subscription with multiple types gets a waiting pool that collects
    artifacts until all required types are present. Single-type subscriptions
    bypass the waiting pool for immediate triggering.

    Example:
        agent.consumes(TypeA, TypeB)  # Creates waiting pool for 2 types

        # TypeA published → added to pool (not complete yet)
        # TypeB published → added to pool (NOW complete!)
        # → Agent triggered with [TypeA_artifact, TypeB_artifact]
        # → Waiting pool cleared for next cycle
    """

    def __init__(self) -> None:
        """Initialize empty waiting pools."""
        # Structure: {(agent_name, subscription_index): {type_name: [artifact1, artifact2, ...]}}
        # Example: {("diagnostician", 0): {"XRay": [artifact1], "LabResult": [artifact2]}}
        # For count-based AND gates: {"TypeA": [artifact1, artifact2, artifact3]} (3 As collected)
        self._waiting_pools: dict[tuple[str, int], dict[str, list[Artifact]]] = (
            defaultdict(lambda: defaultdict(list))
        )

    def add_artifact(
        self,
        agent: Agent,
        subscription: Subscription,
        artifact: Artifact,
    ) -> tuple[bool, list[Artifact]]:
        """Add artifact to waiting pool and check for completeness.

        Args:
            agent: Agent that will process the artifacts
            subscription: Subscription that matched the artifact
            artifact: Artifact to add to the waiting pool

        Returns:
            Tuple of (is_complete, artifacts):
                - is_complete: True if all required types are now present
                - artifacts: List of collected artifacts (empty if incomplete, all artifacts if complete)

        Design Notes:
            - Single-type subscriptions with count=1 bypass the pool and return immediately complete
            - Multi-type or count-based subscriptions collect artifacts until all required counts met
            - Latest artifacts win (keeps most recent N artifacts per type)
            - After returning complete=True, the pool is automatically cleared
        """
        # Single-type subscription with count=1: No waiting needed (immediate trigger)
        if (
            len(subscription.type_names) == 1
            and subscription.type_counts[artifact.type] == 1
        ):
            return (True, [artifact])

        # Multi-type or count-based subscription: Use waiting pool (AND gate logic)

        # Find subscription index (agents can have multiple subscriptions)
        try:
            subscription_index = agent.subscriptions.index(subscription)
        except ValueError:
            # Should never happen, but defensive programming
            raise RuntimeError(
                f"Subscription not found in agent {agent.name}. "
                "This indicates an internal orchestrator error."
            )

        pool_key = (agent.name, subscription_index)

        # Add artifact to pool (collect in list for count-based logic)
        self._waiting_pools[pool_key][artifact.type].append(artifact)

        # Check if all required counts are met
        is_complete = True
        for type_name, required_count in subscription.type_counts.items():
            collected_count = len(self._waiting_pools[pool_key][type_name])
            if collected_count < required_count:
                is_complete = False
                break

        if is_complete:
            # Complete! Collect all artifacts (flatten lists) and clear the pool
            artifacts = []
            for type_name, required_count in subscription.type_counts.items():
                # Take exactly the required count (latest artifacts)
                type_artifacts = self._waiting_pools[pool_key][type_name]
                artifacts.extend(type_artifacts[:required_count])

            del self._waiting_pools[pool_key]  # Clear for next cycle
            return (True, artifacts)
        # Incomplete - still waiting for more artifacts
        return (False, [])

    def get_waiting_status(
        self, agent: Agent, subscription_index: int
    ) -> dict[str, list[Artifact]]:
        """Get current waiting pool contents for debugging/inspection.

        Args:
            agent: Agent to inspect
            subscription_index: Index of the subscription

        Returns:
            Dictionary mapping type names to lists of collected artifacts (empty if none)
        """
        pool_key = (agent.name, subscription_index)
        # Return a copy to prevent external mutation
        pool = self._waiting_pools.get(pool_key, {})
        return {type_name: list(artifacts) for type_name, artifacts in pool.items()}

    def clear_waiting_pool(self, agent: Agent, subscription_index: int) -> None:
        """Manually clear a waiting pool.

        Useful for cleanup or resetting agent state.

        Args:
            agent: Agent whose pool to clear
            subscription_index: Index of the subscription
        """
        pool_key = (agent.name, subscription_index)
        if pool_key in self._waiting_pools:
            del self._waiting_pools[pool_key]

    def clear_all_pools(self) -> None:
        """Clear all waiting pools.

        Useful for orchestrator shutdown or test cleanup.
        """
        self._waiting_pools.clear()

    def get_pool_count(self) -> int:
        """Get total number of active waiting pools (for metrics/debugging)."""
        return len(self._waiting_pools)


__all__ = ["ArtifactCollector"]
