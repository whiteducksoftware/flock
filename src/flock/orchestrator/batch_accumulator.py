"""
BatchAccumulator: Manages batch collection with size/timeout triggers.

Supports BatchSpec-based batching:
- Accumulates artifacts in batches per subscription
- Flushes on size threshold (e.g., batch of 25)
- Flushes on timeout (e.g., every 30 seconds)
- Whichever comes first wins
- Ensures zero data loss on shutdown
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from flock.core.artifacts import Artifact
    from flock.core.subscription import BatchSpec, Subscription


class BatchAccumulator:
    """
    Tracks artifact batches waiting for size/timeout triggers.

    Example: For orders, accumulate 25 at a time to batch process payments.
    When 25th order arrives OR 30 seconds elapse, flush the batch.
    """

    def __init__(
        self,
        *,
        batch_spec: BatchSpec,
        created_at: datetime,
    ):
        self.batch_spec = batch_spec
        self.created_at = created_at  # When first artifact arrived
        self.artifacts: list[Artifact] = []

    def add_artifact(self, artifact: Artifact) -> bool:
        """
        Add artifact to batch.

        Returns:
            True if batch should flush (size threshold reached), False otherwise
        """
        self.artifacts.append(artifact)

        # Check size threshold
        if self.batch_spec.size is not None:
            if len(self.artifacts) >= self.batch_spec.size:
                return True  # Flush now (size threshold reached)

        return False  # Not ready to flush yet

    def is_timeout_expired(self) -> bool:
        """Check if timeout has expired since batch started."""
        if self.batch_spec.timeout is None:
            return False

        elapsed = datetime.now() - self.created_at
        return elapsed >= self.batch_spec.timeout

    def get_artifacts(self) -> list[Artifact]:
        """Get all artifacts in batch."""
        return self.artifacts.copy()

    def clear(self) -> None:
        """Clear the batch after flush."""
        self.artifacts.clear()


class BatchEngine:
    """
    Manages batch state for BatchSpec subscriptions.

    Responsibilities:
    1. Accumulate artifacts per (agent, subscription_index)
    2. Track batch size and timeout per batch
    3. Return complete batches when size or timeout threshold met
    4. Provide shutdown flush for partial batches

    Example usage:
        engine = BatchEngine()

        # Add artifact to batch
        should_flush = engine.add_artifact(
            artifact=order_artifact,
            subscription=subscription,  # Has BatchSpec
            subscription_index=0,
        )

        if should_flush:
            # Size threshold reached! Flush batch
            artifacts = engine.flush_batch("agent_name", 0)
            # Trigger agent with batch
    """

    def __init__(self):
        # Batch state per (agent_name, subscription_index)
        # Key: (agent_name, subscription_index)
        # Value: BatchAccumulator
        self.batches: dict[tuple[str, int], BatchAccumulator] = {}

    def add_artifact(
        self,
        *,
        artifact: Artifact,
        subscription: Subscription,
        subscription_index: int,
    ) -> bool:
        """
        Add artifact to batch accumulator.

        Returns:
            True if batch should flush (size threshold reached), False otherwise
        """
        if subscription.batch is None:
            raise ValueError("Subscription must have BatchSpec for batching")

        batch_key = (subscription.agent_name, subscription_index)

        # Get or create batch accumulator
        if batch_key not in self.batches:
            self.batches[batch_key] = BatchAccumulator(
                batch_spec=subscription.batch,
                created_at=datetime.now(),
            )

        accumulator = self.batches[batch_key]

        # Add artifact to batch
        should_flush = accumulator.add_artifact(artifact)

        return should_flush

    def add_artifact_group(
        self,
        *,
        artifacts: list[Artifact],
        subscription: Subscription,
        subscription_index: int,
    ) -> bool:
        """
        Add a GROUP of artifacts (e.g., correlated pair) as a SINGLE batch item.

        This is used for JoinSpec + BatchSpec combinations where we want to batch
        correlated groups, not individual artifacts.

        Example: JoinSpec + BatchSpec(size=2) means "batch 2 correlated pairs",
                 not "batch 2 individual artifacts".

        Returns:
            True if batch should flush (size threshold reached), False otherwise
        """
        if subscription.batch is None:
            raise ValueError("Subscription must have BatchSpec for batching")

        batch_key = (subscription.agent_name, subscription_index)

        # Get or create batch accumulator
        if batch_key not in self.batches:
            self.batches[batch_key] = BatchAccumulator(
                batch_spec=subscription.batch,
                created_at=datetime.now(),
            )

        accumulator = self.batches[batch_key]

        # Add ALL artifacts from the group
        for artifact in artifacts:
            accumulator.artifacts.append(artifact)

        # Check size threshold - count GROUPS, not artifacts
        # We track how many groups have been added by checking batch_spec metadata
        if subscription.batch.size is not None:
            # For group batching, we need to track group count separately
            # For now, we'll use a simple heuristic: count groups by dividing by expected group size
            # But this is NOT perfect - we need better tracking

            # BETTER APPROACH: Count how many times we've called add_artifact_group
            # For now, let's use artifact count as a proxy and check if we've hit the threshold
            # This will work correctly if all groups are the same size

            # Actually, let's track group count properly:
            if not hasattr(accumulator, "_group_count"):
                accumulator._group_count = 0

            accumulator._group_count += 1

            if accumulator._group_count >= subscription.batch.size:
                return True  # Flush now

        return False  # Not ready to flush yet

    def flush_batch(
        self, agent_name: str, subscription_index: int
    ) -> list[Artifact] | None:
        """
        Flush a batch and return its artifacts.

        Returns:
            List of artifacts in batch, or None if no batch exists
        """
        batch_key = (agent_name, subscription_index)

        accumulator = self.batches.get(batch_key)
        if accumulator is None or not accumulator.artifacts:
            return None

        # Get artifacts and clear batch
        artifacts = accumulator.get_artifacts()
        del self.batches[batch_key]

        return artifacts

    def check_timeouts(self) -> list[tuple[str, int]]:
        """
        Check all batches for timeout expiry.

        Returns:
            List of (agent_name, subscription_index) tuples that should flush
        """
        expired = []

        for batch_key, accumulator in list(self.batches.items()):
            if accumulator.is_timeout_expired():
                expired.append(batch_key)

        return expired

    def flush_all(self) -> list[tuple[str, int, list[Artifact]]]:
        """
        Flush ALL partial batches (for shutdown).

        Returns:
            List of (agent_name, subscription_index, artifacts) tuples
        """
        results = []

        for batch_key, accumulator in list(self.batches.items()):
            if accumulator.artifacts:
                artifacts = accumulator.get_artifacts()
                agent_name, subscription_index = batch_key
                results.append((agent_name, subscription_index, artifacts))

        # Clear all batches after flush
        self.batches.clear()

        return results


__all__ = ["BatchAccumulator", "BatchEngine"]
