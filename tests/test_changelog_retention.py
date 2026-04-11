"""Tests for RetentionPolicyComponent — background changelog pruning."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from flock.components.orchestrator.retention import (
    RetentionConfig,
    RetentionPolicyComponent,
)
from flock.core.store import InMemoryBlackboardStore
from flock.models.changelog import ChangelogEvent, ChangelogEventType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    *,
    event_type: ChangelogEventType = ChangelogEventType.artifact_published,
    timestamp: datetime | None = None,
) -> ChangelogEvent:
    return ChangelogEvent(
        event_type=event_type,
        artifact_id=uuid4(),
        artifact_type="TestType",
        produced_by="test_agent",
        timestamp=timestamp or datetime.now(UTC),
    )


class FakeOrchestrator:
    """Minimal stand-in for Flock — exposes .store."""

    def __init__(self, store: InMemoryBlackboardStore):
        self.store = store


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryBlackboardStore:
    return InMemoryBlackboardStore()


@pytest.fixture
def orchestrator(store: InMemoryBlackboardStore) -> FakeOrchestrator:
    return FakeOrchestrator(store)


class TestRetentionConfig:
    """Verify defaults and construction."""

    def test_defaults(self):
        cfg = RetentionConfig()
        assert cfg.max_age == timedelta(days=7)
        assert cfg.max_count is None
        assert cfg.check_interval == timedelta(hours=1)

    def test_custom(self):
        cfg = RetentionConfig(
            max_age=timedelta(hours=12),
            max_count=500,
            check_interval=timedelta(minutes=10),
        )
        assert cfg.max_age == timedelta(hours=12)
        assert cfg.max_count == 500
        assert cfg.check_interval == timedelta(minutes=10)


class TestAgeBasedPruning:
    """Events older than max_age are removed."""

    @pytest.mark.asyncio
    async def test_old_events_pruned(self, store, orchestrator):
        """Events beyond max_age are pruned on schedule."""
        # Insert events: 3 old, 2 recent
        old_ts = datetime.now(UTC) - timedelta(days=10)
        for _ in range(3):
            await store.append_changelog_event(_make_event(timestamp=old_ts))
        for _ in range(2):
            await store.append_changelog_event(_make_event())

        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=7),
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        # Let the loop fire at least once
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        # Only 2 recent events remain
        bounds = await store.get_changelog_bounds()
        result = await store.query_changelog(after_seq=0, limit=100)
        assert len(result.events) == 2

    @pytest.mark.asyncio
    async def test_no_events_to_prune(self, store, orchestrator):
        """Component runs without error when nothing is prunable."""
        # All events are recent
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=7),
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        result = await store.query_changelog(after_seq=0, limit=100)
        assert len(result.events) == 5


class TestCountBasedPruning:
    """Events beyond max_count (oldest first) are removed."""

    @pytest.mark.asyncio
    async def test_excess_events_pruned(self, store, orchestrator):
        """When count exceeds max_count, oldest events are removed."""
        # Insert 10 events
        for i in range(10):
            ts = datetime.now(UTC) - timedelta(minutes=10 - i)
            await store.append_changelog_event(_make_event(timestamp=ts))

        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=30),  # Won't trigger age-based
                max_count=5,
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        result = await store.query_changelog(after_seq=0, limit=100)
        assert len(result.events) == 5
        # The remaining events should be the 5 most recent (highest seq)
        seqs = [ev.seq for ev in result.events]
        assert seqs == [6, 7, 8, 9, 10]

    @pytest.mark.asyncio
    async def test_within_count_limit_no_prune(self, store, orchestrator):
        """No pruning when event count is within max_count."""
        for _ in range(3):
            await store.append_changelog_event(_make_event())

        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=30),
                max_count=10,
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        result = await store.query_changelog(after_seq=0, limit=100)
        assert len(result.events) == 3


class TestCombinedPolicy:
    """Both age and count constraints apply together."""

    @pytest.mark.asyncio
    async def test_age_and_count_both_apply(self, store, orchestrator):
        """Combined: age prunes first, then count prunes further if needed."""
        old_ts = datetime.now(UTC) - timedelta(days=10)
        # 3 old events (will be pruned by age)
        for _ in range(3):
            await store.append_changelog_event(_make_event(timestamp=old_ts))
        # 8 recent events (count limit will prune down to 5)
        for i in range(8):
            ts = datetime.now(UTC) - timedelta(minutes=8 - i)
            await store.append_changelog_event(_make_event(timestamp=ts))

        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=7),
                max_count=5,
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        result = await store.query_changelog(after_seq=0, limit=100)
        # Age removes 3, then count trims 8 to 5 => 5 remain
        assert len(result.events) == 5


class TestEdgeCases:
    """Edge cases: empty store, all prunable, clean shutdown."""

    @pytest.mark.asyncio
    async def test_empty_store(self, store, orchestrator):
        """No events at all — component runs without error."""
        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=1),
                max_count=10,
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        result = await store.query_changelog(after_seq=0, limit=100)
        assert len(result.events) == 0

    @pytest.mark.asyncio
    async def test_all_events_prunable(self, store, orchestrator):
        """All events are old enough to prune — store ends up empty."""
        old_ts = datetime.now(UTC) - timedelta(days=30)
        for _ in range(5):
            await store.append_changelog_event(_make_event(timestamp=old_ts))

        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                max_age=timedelta(days=7),
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        await component.on_shutdown(orchestrator)

        result = await store.query_changelog(after_seq=0, limit=100)
        assert len(result.events) == 0

    @pytest.mark.asyncio
    async def test_shutdown_cancels_task(self, store, orchestrator):
        """Shutdown cancels the background task cleanly without raising."""
        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                check_interval=timedelta(hours=1),  # Long interval — won't fire
            )
        )

        await component.on_initialize(orchestrator)
        # Task should be running (sleeping for 1 hour)
        assert component._task is not None
        assert not component._task.done()

        # Shutdown should cancel cleanly
        await component.on_shutdown(orchestrator)
        assert component._task is None

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, store, orchestrator):
        """Calling shutdown when task is already done is safe."""
        component = RetentionPolicyComponent(
            retention=RetentionConfig(
                check_interval=timedelta(seconds=0.01),
            )
        )

        await component.on_initialize(orchestrator)
        await asyncio.sleep(0.05)
        # Shutdown twice — second call should be a no-op
        await component.on_shutdown(orchestrator)
        await component.on_shutdown(orchestrator)
