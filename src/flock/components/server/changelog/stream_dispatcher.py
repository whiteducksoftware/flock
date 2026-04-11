"""StreamDispatcher — manages per-subscriber queues for changelog event delivery.

Each subscriber gets an independent asyncio.Queue with configurable maxsize.
When a queue is full, the oldest event is dropped (backpressure via drop-oldest).
Events are serialized once and the string reference is shared across all queues.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from flock.logging.logging import get_logger
from flock.models.changelog import ChangelogEvent, ChangelogFilter


logger = get_logger(__name__)


@dataclass
class Subscription:
    """A single subscriber's state."""

    id: str = field(default_factory=lambda: str(uuid4()))
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=256))
    filters: ChangelogFilter = field(default_factory=ChangelogFilter)


class StreamDispatcher:
    """Manages per-subscriber queues and publishes changelog events.

    Thread-safe: all mutations go through an asyncio.Lock.
    publish() is non-blocking — it enqueues via create_task so the caller
    never awaits subscriber delivery.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._subscriptions: dict[str, Subscription] = {}

    async def subscribe(
        self,
        filters: ChangelogFilter | None = None,
        queue_maxsize: int = 256,
    ) -> Subscription:
        """Create a new subscription and return it.

        Args:
            filters: Optional filter — only matching events are delivered.
            queue_maxsize: Max events buffered before drop-oldest kicks in.

        Returns:
            The new Subscription (caller reads from subscription.queue).
        """
        sub = Subscription(
            queue=asyncio.Queue(maxsize=queue_maxsize),
            filters=filters or ChangelogFilter(),
        )
        async with self._lock:
            self._subscriptions[sub.id] = sub
        logger.debug(f"Subscription created: {sub.id}")
        return sub

    async def unsubscribe(self, subscription_id: str) -> None:
        """Remove a subscription, freeing resources."""
        async with self._lock:
            removed = self._subscriptions.pop(subscription_id, None)
        if removed:
            logger.debug(f"Subscription removed: {subscription_id}")
        else:
            logger.warning(f"Subscription not found for removal: {subscription_id}")

    def publish(self, event: ChangelogEvent) -> None:
        """Fire-and-forget publish — NEVER blocks the caller.

        Serializes the event once, then dispatches to all matching subscriber
        queues via create_task.
        """
        # Serialize once — shared string across all queues
        serialized = event.model_dump_json()
        asyncio.create_task(self._dispatch(event, serialized))

    async def _dispatch(self, event: ChangelogEvent, serialized: str) -> None:
        """Internal: enqueue serialized event to all matching subscribers."""
        async with self._lock:
            subs = list(self._subscriptions.values())

        for sub in subs:
            if not sub.filters.matches(event):
                continue
            try:
                sub.queue.put_nowait(serialized)
            except asyncio.QueueFull:
                # Drop oldest to make room (backpressure)
                try:
                    sub.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    sub.queue.put_nowait(serialized)
                except asyncio.QueueFull:
                    # Should not happen after dropping one, but be safe
                    logger.warning(
                        f"Queue still full after drop for subscription {sub.id}"
                    )

    @property
    async def subscriber_count(self) -> int:
        """Return the current number of active subscriptions."""
        async with self._lock:
            return len(self._subscriptions)

    async def shutdown(self) -> None:
        """Clear all subscriptions."""
        async with self._lock:
            self._subscriptions.clear()
        logger.info("StreamDispatcher shutdown — all subscriptions cleared")


__all__ = ["StreamDispatcher", "Subscription"]
