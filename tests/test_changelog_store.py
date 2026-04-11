"""Tests for changelog store implementations (SQLite + in-memory) and atomic persist."""

from __future__ import annotations

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore, SQLiteBlackboardStore
from flock.core.visibility import PublicVisibility
from flock.models.changelog import (
    ChangelogEvent,
    ChangelogEventType,
    ChangelogFilter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_store() -> InMemoryBlackboardStore:
    return InMemoryBlackboardStore()


@pytest.fixture
async def sqlite_store(tmp_path: Path) -> SQLiteBlackboardStore:
    store = SQLiteBlackboardStore(str(tmp_path / "test.db"))
    await store.ensure_schema()
    return store


def _make_artifact(
    *,
    artifact_type: str = "BugReport",
    produced_by: str = "scanner",
    correlation_id: str | None = None,
) -> Artifact:
    return Artifact(
        type=artifact_type,
        payload={"title": "test bug"},
        produced_by=produced_by,
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )


def _make_event(
    *,
    artifact: Artifact | None = None,
    event_type: ChangelogEventType = ChangelogEventType.artifact_published,
    timestamp: datetime | None = None,
) -> ChangelogEvent:
    aid = artifact.id if artifact else uuid4()
    return ChangelogEvent(
        event_type=event_type,
        artifact_id=aid,
        artifact_type=artifact.type if artifact else "BugReport",
        produced_by=artifact.produced_by if artifact else "scanner",
        correlation_id=artifact.correlation_id if artifact else None,
        visibility={"kind": "Public"},
        timestamp=timestamp or datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# Parametrized store tests (both backends)
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "sqlite"])
async def store(
    request: pytest.FixtureRequest,
    tmp_path: Path,
) -> InMemoryBlackboardStore | SQLiteBlackboardStore:
    if request.param == "memory":
        return InMemoryBlackboardStore()
    store = SQLiteBlackboardStore(str(tmp_path / "test.db"))
    await store.ensure_schema()
    return store


class TestAtomicPublish:
    """Artifact publish + changelog event in one atomic operation."""

    @pytest.mark.asyncio
    async def test_publish_with_event(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        artifact = _make_artifact()
        event = _make_event(artifact=artifact)

        await store.publish(artifact, event)

        # Artifact persisted
        stored = await store.get(artifact.id)
        assert stored is not None
        assert stored.type == "BugReport"

        # Changelog event persisted with correct seq
        assert event.seq >= 1
        result = await store.query_changelog()
        assert len(result.events) == 1
        assert result.events[0].artifact_type == "BugReport"
        assert result.events[0].seq == event.seq

    @pytest.mark.asyncio
    async def test_sequential_publishes_monotonic_seq(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        seqs = []
        for i in range(5):
            artifact = _make_artifact(produced_by=f"agent-{i}")
            event = _make_event(artifact=artifact)
            await store.publish(artifact, event)
            seqs.append(event.seq)

        # Monotonically increasing
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 5  # No duplicates

    @pytest.mark.asyncio
    async def test_publish_without_event(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        """Backward compat — publish without changelog event still works."""
        artifact = _make_artifact()
        await store.publish(artifact)

        stored = await store.get(artifact.id)
        assert stored is not None

        # No changelog events
        result = await store.query_changelog()
        assert len(result.events) == 0


class TestChangelogQuery:
    @pytest.mark.asyncio
    async def test_query_after_seq(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        for _ in range(10):
            await store.append_changelog_event(_make_event())

        result = await store.query_changelog(after_seq=5, limit=100)
        assert len(result.events) == 5
        assert result.events[0].seq == 6

    @pytest.mark.asyncio
    async def test_query_with_type_filter(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        a = _make_artifact(artifact_type="BugReport")
        b = _make_artifact(artifact_type="Review")
        await store.append_changelog_event(_make_event(artifact=a))
        await store.append_changelog_event(_make_event(artifact=b))
        await store.append_changelog_event(_make_event(artifact=a))

        result = await store.query_changelog(
            filters=ChangelogFilter(artifact_types={"BugReport"})
        )
        assert len(result.events) == 2

    @pytest.mark.asyncio
    async def test_query_empty_store(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        result = await store.query_changelog()
        assert result.events == []
        assert result.oldest_available_seq == 0
        assert result.latest_seq == 0

    @pytest.mark.asyncio
    async def test_query_bounds_correct(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        result = await store.query_changelog(after_seq=3)
        assert result.oldest_available_seq == 1
        assert result.latest_seq == 5


class TestChangelogBounds:
    @pytest.mark.asyncio
    async def test_empty_bounds(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        assert await store.get_changelog_bounds() == (0, 0)

    @pytest.mark.asyncio
    async def test_bounds_after_inserts(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        for _ in range(3):
            await store.append_changelog_event(_make_event())
        assert await store.get_changelog_bounds() == (1, 3)


class TestChangelogPrune:
    @pytest.mark.asyncio
    async def test_prune_by_seq(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        for _ in range(10):
            await store.append_changelog_event(_make_event())

        deleted = await store.prune_changelog(before_seq=6)
        assert deleted == 5

        oldest, latest = await store.get_changelog_bounds()
        assert oldest == 6
        assert latest == 10

    @pytest.mark.asyncio
    async def test_prune_by_time(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        old_time = datetime.now(UTC) - timedelta(hours=2)
        recent_time = datetime.now(UTC)

        for _ in range(3):
            await store.append_changelog_event(_make_event(timestamp=old_time))
        for _ in range(2):
            await store.append_changelog_event(_make_event(timestamp=recent_time))

        cutoff = datetime.now(UTC) - timedelta(hours=1)
        deleted = await store.prune_changelog(before_time=cutoff)
        assert deleted == 3

    @pytest.mark.asyncio
    async def test_prune_all(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        deleted = await store.prune_changelog(before_seq=100)
        assert deleted == 5
        assert await store.get_changelog_bounds() == (0, 0)

    @pytest.mark.asyncio
    async def test_prune_nothing(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        deleted = await store.prune_changelog(before_seq=0)
        assert deleted == 0


class TestChangelogVisibilityFilter:
    """Visibility filtering is done at the query consumer level, not store level.
    Store tests verify that visibility data round-trips correctly."""

    @pytest.mark.asyncio
    async def test_visibility_data_roundtrip(
        self,
        store: InMemoryBlackboardStore | SQLiteBlackboardStore,
    ) -> None:
        event = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_id=uuid4(),
            artifact_type="Secret",
            visibility={"kind": "Private", "agents": ["admin"]},
        )
        await store.append_changelog_event(event)

        result = await store.query_changelog()
        assert result.events[0].visibility == {"kind": "Private", "agents": ["admin"]}


class TestSchemaV4Migration:
    """Schema v3 → v4 migration (changelog_events table)."""

    @pytest.mark.asyncio
    async def test_schema_migration_idempotent(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "migrate.db")

        # First open — creates schema
        store1 = SQLiteBlackboardStore(db_path)
        await store1.ensure_schema()
        await store1.append_changelog_event(_make_event())
        await store1.close()

        # Second open — schema already exists
        store2 = SQLiteBlackboardStore(db_path)
        await store2.ensure_schema()
        result = await store2.query_changelog()
        assert len(result.events) == 1
        await store2.close()

    @pytest.mark.asyncio
    async def test_existing_artifacts_survive_migration(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "existing.db")

        store = SQLiteBlackboardStore(db_path)
        await store.ensure_schema()

        # Publish artifact + check it survives
        artifact = _make_artifact()
        await store.publish(artifact)
        stored = await store.get(artifact.id)
        assert stored is not None
        await store.close()

        # Reopen — schema applies again
        store2 = SQLiteBlackboardStore(db_path)
        await store2.ensure_schema()
        stored2 = await store2.get(artifact.id)
        assert stored2 is not None
        assert stored2.type == artifact.type
        await store2.close()
