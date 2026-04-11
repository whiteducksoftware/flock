"""Tests for ChangelogEvent model, ChangelogFilter, and in-memory store changelog operations."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from flock.core.store import InMemoryBlackboardStore
from flock.models.changelog import (
    ChangelogEvent,
    ChangelogEventType,
    ChangelogFilter,
    ChangelogQueryResult,
)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestChangelogEvent:
    def test_create_with_all_fields(self) -> None:
        aid = uuid4()
        ev = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_id=aid,
            artifact_type="BugReport",
            produced_by="scanner",
            correlation_id="wf-1",
            visibility={"kind": "Public"},
            payload_summary={"title": "bug"},
        )
        assert ev.seq == 0
        assert ev.event_type == ChangelogEventType.artifact_published
        assert ev.artifact_id == aid
        assert ev.artifact_type == "BugReport"
        assert ev.produced_by == "scanner"

    def test_serialization_roundtrip(self) -> None:
        ev = ChangelogEvent(
            event_type=ChangelogEventType.artifact_consumed,
            artifact_id=uuid4(),
            artifact_type="Review",
            produced_by="reviewer",
        )
        data = ev.model_dump(mode="json")
        restored = ChangelogEvent.model_validate(data)
        assert restored.event_type == ev.event_type
        assert restored.artifact_id == ev.artifact_id

    def test_json_roundtrip(self) -> None:
        ev = ChangelogEvent(
            event_type=ChangelogEventType.agent_snapshot_updated,
            produced_by="system",
        )
        json_str = ev.model_dump_json()
        restored = ChangelogEvent.model_validate_json(json_str)
        assert restored.event_type == ChangelogEventType.agent_snapshot_updated

    def test_none_optional_fields_serialize_cleanly(self) -> None:
        ev = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
        )
        data = ev.model_dump(mode="json")
        assert data["artifact_id"] is None
        assert data["artifact_type"] is None
        assert data["produced_by"] is None
        assert data["correlation_id"] is None
        assert data["visibility"] is None

    def test_event_type_enum_covers_all_types(self) -> None:
        expected = {"artifact_published", "artifact_consumed", "agent_snapshot_updated"}
        assert {e.value for e in ChangelogEventType} == expected


class TestChangelogFilter:
    def test_empty_filter_matches_all(self) -> None:
        f = ChangelogFilter()
        ev = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_type="BugReport",
            produced_by="scanner",
        )
        assert f.matches(ev) is True

    def test_type_filter(self) -> None:
        f = ChangelogFilter(artifact_types={"BugReport"})
        match = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_type="BugReport",
        )
        no_match = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_type="Review",
        )
        assert f.matches(match) is True
        assert f.matches(no_match) is False

    def test_produced_by_filter(self) -> None:
        f = ChangelogFilter(produced_by={"scanner", "reviewer"})
        ev = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            produced_by="scanner",
        )
        assert f.matches(ev) is True

    def test_correlation_id_filter(self) -> None:
        f = ChangelogFilter(correlation_id="wf-42")
        match = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            correlation_id="wf-42",
        )
        no_match = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            correlation_id="wf-99",
        )
        assert f.matches(match) is True
        assert f.matches(no_match) is False

    def test_event_type_filter(self) -> None:
        f = ChangelogFilter(event_types={ChangelogEventType.artifact_consumed})
        match = ChangelogEvent(
            event_type=ChangelogEventType.artifact_consumed,
        )
        no_match = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
        )
        assert f.matches(match) is True
        assert f.matches(no_match) is False

    def test_combined_filters_are_anded(self) -> None:
        f = ChangelogFilter(
            artifact_types={"BugReport"},
            produced_by={"scanner"},
        )
        both = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_type="BugReport",
            produced_by="scanner",
        )
        wrong_type = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_type="Review",
            produced_by="scanner",
        )
        wrong_producer = ChangelogEvent(
            event_type=ChangelogEventType.artifact_published,
            artifact_type="BugReport",
            produced_by="reviewer",
        )
        assert f.matches(both) is True
        assert f.matches(wrong_type) is False
        assert f.matches(wrong_producer) is False


class TestChangelogQueryResult:
    def test_default_empty(self) -> None:
        r = ChangelogQueryResult()
        assert r.events == []
        assert r.oldest_available_seq == 0
        assert r.latest_seq == 0

    def test_with_bounds(self) -> None:
        r = ChangelogQueryResult(
            events=[],
            oldest_available_seq=5,
            latest_seq=42,
        )
        assert r.oldest_available_seq == 5
        assert r.latest_seq == 42


# ---------------------------------------------------------------------------
# In-memory store changelog tests
# ---------------------------------------------------------------------------


@pytest.fixture
def store() -> InMemoryBlackboardStore:
    return InMemoryBlackboardStore()


def _make_event(
    *,
    event_type: ChangelogEventType = ChangelogEventType.artifact_published,
    artifact_type: str = "BugReport",
    produced_by: str = "scanner",
    correlation_id: str | None = None,
    timestamp: datetime | None = None,
) -> ChangelogEvent:
    return ChangelogEvent(
        event_type=event_type,
        artifact_id=uuid4(),
        artifact_type=artifact_type,
        produced_by=produced_by,
        correlation_id=correlation_id,
        timestamp=timestamp or datetime.now(UTC),
    )


class TestInMemoryChangelog:
    @pytest.mark.asyncio
    async def test_append_returns_sequence(self, store: InMemoryBlackboardStore) -> None:
        ev = _make_event()
        seq = await store.append_changelog_event(ev)
        assert seq == 1
        assert ev.seq == 1

    @pytest.mark.asyncio
    async def test_monotonic_sequence(self, store: InMemoryBlackboardStore) -> None:
        seqs = []
        for _ in range(5):
            seqs.append(await store.append_changelog_event(_make_event()))
        assert seqs == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_query_after_seq(self, store: InMemoryBlackboardStore) -> None:
        for _ in range(10):
            await store.append_changelog_event(_make_event())

        result = await store.query_changelog(after_seq=5, limit=10)
        assert len(result.events) == 5
        assert result.events[0].seq == 6
        assert result.events[-1].seq == 10

    @pytest.mark.asyncio
    async def test_query_with_limit(self, store: InMemoryBlackboardStore) -> None:
        for _ in range(10):
            await store.append_changelog_event(_make_event())

        result = await store.query_changelog(after_seq=0, limit=3)
        assert len(result.events) == 3

    @pytest.mark.asyncio
    async def test_query_with_type_filter(self, store: InMemoryBlackboardStore) -> None:
        await store.append_changelog_event(_make_event(artifact_type="BugReport"))
        await store.append_changelog_event(_make_event(artifact_type="Review"))
        await store.append_changelog_event(_make_event(artifact_type="BugReport"))

        result = await store.query_changelog(
            filters=ChangelogFilter(artifact_types={"BugReport"}),
        )
        assert len(result.events) == 2
        assert all(e.artifact_type == "BugReport" for e in result.events)

    @pytest.mark.asyncio
    async def test_query_empty_store(self, store: InMemoryBlackboardStore) -> None:
        result = await store.query_changelog()
        assert result.events == []
        assert result.oldest_available_seq == 0
        assert result.latest_seq == 0

    @pytest.mark.asyncio
    async def test_query_includes_bounds(self, store: InMemoryBlackboardStore) -> None:
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        result = await store.query_changelog(after_seq=3)
        assert result.oldest_available_seq == 1
        assert result.latest_seq == 5

    @pytest.mark.asyncio
    async def test_get_bounds(self, store: InMemoryBlackboardStore) -> None:
        assert await store.get_changelog_bounds() == (0, 0)

        for _ in range(3):
            await store.append_changelog_event(_make_event())

        assert await store.get_changelog_bounds() == (1, 3)

    @pytest.mark.asyncio
    async def test_prune_by_seq(self, store: InMemoryBlackboardStore) -> None:
        for _ in range(10):
            await store.append_changelog_event(_make_event())

        deleted = await store.prune_changelog(before_seq=6)
        assert deleted == 5

        oldest, latest = await store.get_changelog_bounds()
        assert oldest == 6
        assert latest == 10

    @pytest.mark.asyncio
    async def test_prune_by_time(self, store: InMemoryBlackboardStore) -> None:
        old_time = datetime.now(UTC) - timedelta(hours=2)
        recent_time = datetime.now(UTC)

        for _ in range(3):
            await store.append_changelog_event(_make_event(timestamp=old_time))
        for _ in range(2):
            await store.append_changelog_event(_make_event(timestamp=recent_time))

        cutoff = datetime.now(UTC) - timedelta(hours=1)
        deleted = await store.prune_changelog(before_time=cutoff)
        assert deleted == 3

        result = await store.query_changelog()
        assert len(result.events) == 2

    @pytest.mark.asyncio
    async def test_prune_all_events(self, store: InMemoryBlackboardStore) -> None:
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        deleted = await store.prune_changelog(before_seq=100)
        assert deleted == 5
        assert await store.get_changelog_bounds() == (0, 0)

    @pytest.mark.asyncio
    async def test_prune_nothing(self, store: InMemoryBlackboardStore) -> None:
        for _ in range(5):
            await store.append_changelog_event(_make_event())

        deleted = await store.prune_changelog(before_seq=0)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_empty_filter_matches_all(self, store: InMemoryBlackboardStore) -> None:
        await store.append_changelog_event(_make_event(artifact_type="A"))
        await store.append_changelog_event(_make_event(artifact_type="B"))

        result = await store.query_changelog(filters=ChangelogFilter())
        assert len(result.events) == 2
