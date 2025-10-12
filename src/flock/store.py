from __future__ import annotations


"""Blackboard storage primitives and metadata envelopes.

Future backends should read the docstrings on :class:`FilterConfig`,
:class:`ConsumptionRecord`, and :class:`BlackboardStore` to understand the
contract expected by the REST layer and dashboard.
"""

import asyncio
import json
import re
from asyncio import Lock
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

import aiosqlite
from opentelemetry import trace

from flock.artifacts import Artifact
from flock.registry import type_registry
from flock.visibility import (
    AfterVisibility,
    LabelledVisibility,
    PrivateVisibility,
    PublicVisibility,
    TenantVisibility,
    Visibility,
)


T = TypeVar("T")
tracer = trace.get_tracer(__name__)

ISO_DURATION_RE = re.compile(
    r"^P(?:T?(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)$"
)


def _parse_iso_duration(value: str | None) -> timedelta:
    if not value:
        return timedelta(0)
    match = ISO_DURATION_RE.match(value)
    if not match:
        return timedelta(0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _deserialize_visibility(data: Any) -> Visibility:
    if isinstance(data, Visibility):
        return data
    if not data:
        return PublicVisibility()
    kind = data.get("kind") if isinstance(data, dict) else None
    if kind == "Public":
        return PublicVisibility()
    if kind == "Private":
        return PrivateVisibility(agents=set(data.get("agents", [])))
    if kind == "Labelled":
        return LabelledVisibility(required_labels=set(data.get("required_labels", [])))
    if kind == "Tenant":
        return TenantVisibility(tenant_id=data.get("tenant_id"))
    if kind == "After":
        ttl = _parse_iso_duration(data.get("ttl"))
        then_data = data.get("then") if isinstance(data, dict) else None
        then_visibility = _deserialize_visibility(then_data) if then_data else None
        return AfterVisibility(ttl=ttl, then=then_visibility)
    return PublicVisibility()


@dataclass(slots=True)
class ConsumptionRecord:
    """Historical record describing which agent consumed an artifact."""

    artifact_id: UUID
    consumer: str
    run_id: str | None = None
    correlation_id: str | None = None
    consumed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class FilterConfig:
    """Shared filter configuration used by all stores."""

    type_names: set[str] | None = None
    produced_by: set[str] | None = None
    correlation_id: str | None = None
    tags: set[str] | None = None
    visibility: set[str] | None = None
    start: datetime | None = None
    end: datetime | None = None


@dataclass(slots=True)
class ArtifactEnvelope:
    """Wrapper returned when ``embed_meta`` is requested."""

    artifact: Artifact
    consumptions: list[ConsumptionRecord] = field(default_factory=list)


@dataclass(slots=True)
class AgentSnapshotRecord:
    """Persistent metadata about an agent's behaviour."""

    agent_name: str
    description: str
    subscriptions: list[str]
    output_types: list[str]
    labels: list[str]
    first_seen: datetime
    last_seen: datetime
    signature: str


class BlackboardStore:
    async def publish(self, artifact: Artifact) -> None:
        raise NotImplementedError

    async def get(self, artifact_id: UUID) -> Artifact | None:
        raise NotImplementedError

    async def list(self) -> list[Artifact]:
        raise NotImplementedError

    async def list_by_type(self, type_name: str) -> list[Artifact]:
        raise NotImplementedError

    async def get_by_type(self, artifact_type: type[T]) -> list[T]:
        """Get artifacts by Pydantic type, returning data already cast.

        Args:
            artifact_type: The Pydantic model class (e.g., BugAnalysis)

        Returns:
            List of data objects of the specified type (not Artifact wrappers)

        Example:
            bug_analyses = await store.get_by_type(BugAnalysis)
            # Returns list[BugAnalysis] directly, no .data access needed
        """
        raise NotImplementedError

    async def record_consumptions(
        self,
        records: Iterable[ConsumptionRecord],
    ) -> None:
        """Persist one or more consumption events."""
        raise NotImplementedError

    async def query_artifacts(
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        embed_meta: bool = False,
    ) -> tuple[list[Artifact | ArtifactEnvelope], int]:
        """Search artifacts with filtering and pagination."""
        raise NotImplementedError

    async def fetch_graph_artifacts(
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[ArtifactEnvelope], int]:
        """Return artifact envelopes (artifact + consumptions) for graph assembly."""
        artifacts, total = await self.query_artifacts(
            filters=filters,
            limit=limit,
            offset=offset,
            embed_meta=True,
        )

        envelopes: list[ArtifactEnvelope] = []
        for item in artifacts:
            if isinstance(item, ArtifactEnvelope):
                envelopes.append(item)
            elif isinstance(item, Artifact):
                envelopes.append(ArtifactEnvelope(artifact=item))
        return envelopes, total

    async def summarize_artifacts(
        self,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        """Return aggregate artifact statistics for the given filters."""
        raise NotImplementedError

    async def agent_history_summary(
        self,
        agent_id: str,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        """Return produced/consumed counts for the specified agent."""
        raise NotImplementedError

    async def upsert_agent_snapshot(self, snapshot: AgentSnapshotRecord) -> None:
        """Persist metadata describing an agent."""
        raise NotImplementedError

    async def load_agent_snapshots(self) -> list[AgentSnapshotRecord]:
        """Return all persisted agent metadata records."""
        raise NotImplementedError

    async def clear_agent_snapshots(self) -> None:
        """Remove all persisted agent metadata."""
        raise NotImplementedError


class InMemoryBlackboardStore(BlackboardStore):
    """Simple in-memory implementation suitable for local dev and tests."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[UUID, Artifact] = {}
        self._by_type: dict[str, list[Artifact]] = defaultdict(list)
        self._consumptions_by_artifact: dict[UUID, list[ConsumptionRecord]] = defaultdict(list)
        self._agent_snapshots: dict[str, AgentSnapshotRecord] = {}

    async def publish(self, artifact: Artifact) -> None:
        async with self._lock:
            self._by_id[artifact.id] = artifact
            self._by_type[artifact.type].append(artifact)

    async def get(self, artifact_id: UUID) -> Artifact | None:
        async with self._lock:
            return self._by_id.get(artifact_id)

    async def list(self) -> list[Artifact]:
        async with self._lock:
            return list(self._by_id.values())

    async def list_by_type(self, type_name: str) -> list[Artifact]:
        async with self._lock:
            canonical = type_registry.resolve_name(type_name)
            return list(self._by_type.get(canonical, []))

    async def get_by_type(self, artifact_type: type[T]) -> list[T]:
        async with self._lock:
            canonical = type_registry.resolve_name(artifact_type.__name__)
            artifacts = self._by_type.get(canonical, [])
            return [artifact_type(**artifact.payload) for artifact in artifacts]  # type: ignore

    async def extend(self, artifacts: Iterable[Artifact]) -> None:  # pragma: no cover - helper
        for artifact in artifacts:
            await self.publish(artifact)

    async def record_consumptions(
        self,
        records: Iterable[ConsumptionRecord],
    ) -> None:
        async with self._lock:
            for record in records:
                self._consumptions_by_artifact[record.artifact_id].append(record)

    async def query_artifacts(
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        embed_meta: bool = False,
    ) -> tuple[list[Artifact | ArtifactEnvelope], int]:
        async with self._lock:
            artifacts = list(self._by_id.values())

        filters = filters or FilterConfig()
        canonical: set[str] | None = None
        if filters.type_names:
            canonical = {type_registry.resolve_name(name) for name in filters.type_names}

        visibility_filter = filters.visibility or set()

        def _matches(artifact: Artifact) -> bool:
            if canonical and artifact.type not in canonical:
                return False
            if filters.produced_by and artifact.produced_by not in filters.produced_by:
                return False
            if filters.correlation_id and (
                artifact.correlation_id is None
                or str(artifact.correlation_id) != filters.correlation_id
            ):
                return False
            if filters.tags and not filters.tags.issubset(artifact.tags):
                return False
            if visibility_filter and artifact.visibility.kind not in visibility_filter:
                return False
            if filters.start and artifact.created_at < filters.start:
                return False
            return not (filters.end and artifact.created_at > filters.end)

        filtered = [artifact for artifact in artifacts if _matches(artifact)]
        filtered.sort(key=lambda a: (a.created_at, a.id))

        total = len(filtered)
        offset = max(offset, 0)
        if limit <= 0:
            page = filtered[offset:]
        else:
            page = filtered[offset : offset + limit]

        if not embed_meta:
            return page, total

        envelopes = [
            ArtifactEnvelope(
                artifact=artifact,
                consumptions=list(self._consumptions_by_artifact.get(artifact.id, [])),
            )
            for artifact in page
        ]
        return envelopes, total

    async def summarize_artifacts(
        self,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        filters = filters or FilterConfig()
        artifacts, total = await self.query_artifacts(
            filters=filters,
            limit=0,
            offset=0,
            embed_meta=False,
        )

        by_type: dict[str, int] = {}
        by_producer: dict[str, int] = {}
        by_visibility: dict[str, int] = {}
        tag_counts: dict[str, int] = {}
        earliest: datetime | None = None
        latest: datetime | None = None

        for artifact in artifacts:
            if not isinstance(artifact, Artifact):
                raise TypeError("Expected Artifact instance")
            by_type[artifact.type] = by_type.get(artifact.type, 0) + 1
            by_producer[artifact.produced_by] = by_producer.get(artifact.produced_by, 0) + 1
            kind = getattr(artifact.visibility, "kind", "Unknown")
            by_visibility[kind] = by_visibility.get(kind, 0) + 1
            for tag in artifact.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if earliest is None or artifact.created_at < earliest:
                earliest = artifact.created_at
            if latest is None or artifact.created_at > latest:
                latest = artifact.created_at

        if earliest and latest:
            span = latest - earliest
            if span.days >= 2:
                span_label = f"{span.days} days"
            elif span.total_seconds() >= 3600:
                hours = span.total_seconds() / 3600
                span_label = f"{hours:.1f} hours"
            elif span.total_seconds() > 0:
                minutes = max(1, int(span.total_seconds() / 60))
                span_label = f"{minutes} minutes"
            else:
                span_label = "moments"
        else:
            span_label = "empty"

        return {
            "total": total,
            "by_type": by_type,
            "by_producer": by_producer,
            "by_visibility": by_visibility,
            "tag_counts": tag_counts,
            "earliest_created_at": earliest.isoformat() if earliest else None,
            "latest_created_at": latest.isoformat() if latest else None,
            "is_full_window": filters.start is None and filters.end is None,
            "window_span_label": span_label,
        }

    async def agent_history_summary(
        self,
        agent_id: str,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        filters = filters or FilterConfig()
        envelopes, _ = await self.query_artifacts(
            filters=filters,
            limit=0,
            offset=0,
            embed_meta=True,
        )

        produced_total = 0
        produced_by_type: dict[str, int] = defaultdict(int)
        consumed_total = 0
        consumed_by_type: dict[str, int] = defaultdict(int)

        for envelope in envelopes:
            if not isinstance(envelope, ArtifactEnvelope):
                raise TypeError("Expected ArtifactEnvelope instance")
            artifact = envelope.artifact
            if artifact.produced_by == agent_id:
                produced_total += 1
                produced_by_type[artifact.type] += 1
            for consumption in envelope.consumptions:
                if consumption.consumer == agent_id:
                    consumed_total += 1
                    consumed_by_type[artifact.type] += 1

        return {
            "produced": {"total": produced_total, "by_type": dict(produced_by_type)},
            "consumed": {"total": consumed_total, "by_type": dict(consumed_by_type)},
        }

    async def upsert_agent_snapshot(self, snapshot: AgentSnapshotRecord) -> None:
        async with self._lock:
            self._agent_snapshots[snapshot.agent_name] = snapshot

    async def load_agent_snapshots(self) -> list[AgentSnapshotRecord]:
        async with self._lock:
            return list(self._agent_snapshots.values())

    async def clear_agent_snapshots(self) -> None:
        async with self._lock:
            self._agent_snapshots.clear()


__all__ = [
    "AgentSnapshotRecord",
    "BlackboardStore",
    "InMemoryBlackboardStore",
    "SQLiteBlackboardStore",
]


class SQLiteBlackboardStore(BlackboardStore):
    """SQLite-backed implementation of :class:`BlackboardStore`."""

    SCHEMA_VERSION = 3

    def __init__(self, db_path: str, *, timeout: float = 5.0) -> None:
        self._db_path = Path(db_path)
        self._timeout = timeout
        self._connection: aiosqlite.Connection | None = None
        self._connection_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._schema_ready = False

    async def publish(self, artifact: Artifact) -> None:  # type: ignore[override]
        with tracer.start_as_current_span("sqlite_store.publish"):
            conn = await self._get_connection()

            payload_json = json.dumps(artifact.payload)
            visibility_json = json.dumps(artifact.visibility.model_dump(mode="json"))
            tags_json = json.dumps(sorted(artifact.tags))
            created_at = artifact.created_at.isoformat()

            try:
                canonical_type = type_registry.resolve_name(artifact.type)
            except Exception:
                canonical_type = artifact.type

            record = {
                "artifact_id": str(artifact.id),
                "type": artifact.type,
                "canonical_type": canonical_type,
                "produced_by": artifact.produced_by,
                "payload": payload_json,
                "version": artifact.version,
                "visibility": visibility_json,
                "tags": tags_json,
                "correlation_id": str(artifact.correlation_id) if artifact.correlation_id else None,
                "partition_key": artifact.partition_key,
                "created_at": created_at,
            }

            async with self._write_lock:
                await conn.execute(
                    """
                    INSERT INTO artifacts (
                        artifact_id,
                        type,
                        canonical_type,
                        produced_by,
                        payload,
                        version,
                        visibility,
                        tags,
                        correlation_id,
                        partition_key,
                        created_at
                    ) VALUES (
                        :artifact_id,
                        :type,
                        :canonical_type,
                        :produced_by,
                        :payload,
                        :version,
                        :visibility,
                        :tags,
                        :correlation_id,
                        :partition_key,
                        :created_at
                    )
                    ON CONFLICT(artifact_id) DO UPDATE SET
                        type=excluded.type,
                        canonical_type=excluded.canonical_type,
                        produced_by=excluded.produced_by,
                        payload=excluded.payload,
                        version=excluded.version,
                        visibility=excluded.visibility,
                        tags=excluded.tags,
                        correlation_id=excluded.correlation_id,
                        partition_key=excluded.partition_key,
                        created_at=excluded.created_at
                    """,
                    record,
                )
                await conn.commit()

    async def record_consumptions(  # type: ignore[override]
        self,
        records: Iterable[ConsumptionRecord],
    ) -> None:
        with tracer.start_as_current_span("sqlite_store.record_consumptions"):
            rows = [
                (
                    str(record.artifact_id),
                    record.consumer,
                    record.run_id,
                    record.correlation_id,
                    record.consumed_at.isoformat(),
                )
                for record in records
            ]
            if not rows:
                return

            conn = await self._get_connection()
            async with self._write_lock:
                await conn.executemany(
                    """
                    INSERT OR REPLACE INTO artifact_consumptions (
                        artifact_id,
                        consumer,
                        run_id,
                        correlation_id,
                        consumed_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    rows,
                )
                await conn.commit()

    async def fetch_graph_artifacts(  # type: ignore[override]
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> tuple[list[ArtifactEnvelope], int]:
        with tracer.start_as_current_span("sqlite_store.fetch_graph_artifacts"):
            return await super().fetch_graph_artifacts(
                filters,
                limit=limit,
                offset=offset,
            )

    async def get(self, artifact_id: UUID) -> Artifact | None:  # type: ignore[override]
        with tracer.start_as_current_span("sqlite_store.get"):
            conn = await self._get_connection()
            cursor = await conn.execute(
                """
                SELECT
                    artifact_id,
                    type,
                    canonical_type,
                    produced_by,
                    payload,
                    version,
                    visibility,
                    tags,
                    correlation_id,
                    partition_key,
                    created_at
                FROM artifacts
                WHERE artifact_id = ?
                """,
                (str(artifact_id),),
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                return None
            return self._row_to_artifact(row)

    async def list(self) -> list[Artifact]:  # type: ignore[override]
        with tracer.start_as_current_span("sqlite_store.list"):
            conn = await self._get_connection()
            cursor = await conn.execute(
                """
                SELECT
                    artifact_id,
                    type,
                    canonical_type,
                    produced_by,
                    payload,
                    version,
                    visibility,
                    tags,
                    correlation_id,
                    partition_key,
                    created_at
                FROM artifacts
                ORDER BY created_at ASC, rowid ASC
                """
            )
            rows = await cursor.fetchall()
            await cursor.close()
            return [self._row_to_artifact(row) for row in rows]

    async def list_by_type(self, type_name: str) -> list[Artifact]:  # type: ignore[override]
        with tracer.start_as_current_span("sqlite_store.list_by_type"):
            conn = await self._get_connection()
            canonical = type_registry.resolve_name(type_name)
            cursor = await conn.execute(
                """
                SELECT
                    artifact_id,
                    type,
                    canonical_type,
                    produced_by,
                    payload,
                    version,
                    visibility,
                    tags,
                    correlation_id,
                    partition_key,
                    created_at
                FROM artifacts
                WHERE canonical_type = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (canonical,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
            return [self._row_to_artifact(row) for row in rows]

    async def get_by_type(self, artifact_type: type[T]) -> list[T]:  # type: ignore[override]
        with tracer.start_as_current_span("sqlite_store.get_by_type"):
            conn = await self._get_connection()
            canonical = type_registry.resolve_name(artifact_type.__name__)
            cursor = await conn.execute(
                """
                SELECT payload
                FROM artifacts
                WHERE canonical_type = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (canonical,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
            results: list[T] = []
            for row in rows:
                payload = json.loads(row["payload"])
                results.append(artifact_type(**payload))  # type: ignore[arg-type]
            return results

    async def query_artifacts(
        self,
        filters: FilterConfig | None = None,
        *,
        limit: int = 50,
        offset: int = 0,
        embed_meta: bool = False,
    ) -> tuple[list[Artifact | ArtifactEnvelope], int]:
        filters = filters or FilterConfig()
        conn = await self._get_connection()

        where_clause, params = self._build_filters(filters)
        count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"  # nosec B608 - where_clause contains only parameter placeholders from _build_filters
        cursor = await conn.execute(count_query, tuple(params))  # nosec B608
        total_row = await cursor.fetchone()
        await cursor.close()
        total = total_row["total"] if total_row else 0

        query = f"""
            SELECT
                artifact_id,
                type,
                canonical_type,
                produced_by,
                payload,
                version,
                visibility,
                tags,
                correlation_id,
                partition_key,
                created_at
            FROM artifacts
            {where_clause}
            ORDER BY created_at ASC, rowid ASC
        """  # nosec B608 - where_clause contains only parameter placeholders from _build_filters
        query_params: tuple[Any, ...]
        if limit <= 0:
            if offset > 0:
                query += " LIMIT -1 OFFSET ?"
                query_params = (*params, max(offset, 0))
            else:
                query_params = tuple(params)
        else:
            query += " LIMIT ? OFFSET ?"
            query_params = (*params, limit, max(offset, 0))

        cursor = await conn.execute(query, query_params)
        rows = await cursor.fetchall()
        await cursor.close()
        artifacts = [self._row_to_artifact(row) for row in rows]

        if not embed_meta or not artifacts:
            return artifacts, total

        artifact_ids = [str(artifact.id) for artifact in artifacts]
        placeholders = ", ".join("?" for _ in artifact_ids)
        consumption_query = f"""
            SELECT
                artifact_id,
                consumer,
                run_id,
                correlation_id,
                consumed_at
            FROM artifact_consumptions
            WHERE artifact_id IN ({placeholders})
            ORDER BY consumed_at ASC
        """  # nosec B608 - placeholders string contains only '?' characters
        cursor = await conn.execute(consumption_query, artifact_ids)
        consumption_rows = await cursor.fetchall()
        await cursor.close()

        consumptions_map: dict[UUID, list[ConsumptionRecord]] = defaultdict(list)
        for row in consumption_rows:
            artifact_uuid = UUID(row["artifact_id"])
            consumptions_map[artifact_uuid].append(
                ConsumptionRecord(
                    artifact_id=artifact_uuid,
                    consumer=row["consumer"],
                    run_id=row["run_id"],
                    correlation_id=row["correlation_id"],
                    consumed_at=datetime.fromisoformat(row["consumed_at"]),
                )
            )

        envelopes: list[ArtifactEnvelope] = [
            ArtifactEnvelope(
                artifact=artifact,
                consumptions=consumptions_map.get(artifact.id, []),
            )
            for artifact in artifacts
        ]
        return envelopes, total

    async def summarize_artifacts(
        self,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        filters = filters or FilterConfig()
        conn = await self._get_connection()

        where_clause, params = self._build_filters(filters)
        params_tuple = tuple(params)

        count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"  # nosec B608 - where_clause contains only parameter placeholders from _build_filters
        cursor = await conn.execute(count_query, params_tuple)  # nosec B608
        total_row = await cursor.fetchone()
        await cursor.close()
        total = total_row["total"] if total_row else 0

        by_type_query = f"""
            SELECT canonical_type, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY canonical_type
        """  # nosec B608 - where_clause contains only parameter placeholders from _build_filters
        cursor = await conn.execute(by_type_query, params_tuple)
        by_type_rows = await cursor.fetchall()
        await cursor.close()
        by_type = {row["canonical_type"]: row["count"] for row in by_type_rows}

        by_producer_query = f"""
            SELECT produced_by, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY produced_by
        """  # nosec B608 - where_clause contains only parameter placeholders from _build_filters
        cursor = await conn.execute(by_producer_query, params_tuple)
        by_producer_rows = await cursor.fetchall()
        await cursor.close()
        by_producer = {row["produced_by"]: row["count"] for row in by_producer_rows}

        by_visibility_query = f"""
            SELECT json_extract(visibility, '$.kind') AS visibility_kind, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY json_extract(visibility, '$.kind')
        """  # nosec B608 - where_clause contains only parameter placeholders from _build_filters
        cursor = await conn.execute(by_visibility_query, params_tuple)
        by_visibility_rows = await cursor.fetchall()
        await cursor.close()
        by_visibility = {
            (row["visibility_kind"] or "Unknown"): row["count"] for row in by_visibility_rows
        }

        tag_query = f"""
            SELECT json_each.value AS tag, COUNT(*) AS count
            FROM artifacts
            JOIN json_each(artifacts.tags)
            {where_clause}
            GROUP BY json_each.value
        """  # nosec B608 - where_clause contains only parameter placeholders produced by _build_filters
        cursor = await conn.execute(tag_query, params_tuple)
        tag_rows = await cursor.fetchall()
        await cursor.close()
        tag_counts = {row["tag"]: row["count"] for row in tag_rows}

        range_query = f"""
            SELECT MIN(created_at) AS earliest, MAX(created_at) AS latest
            FROM artifacts
            {where_clause}
        """  # nosec B608 - safe composition using parameterized where_clause
        cursor = await conn.execute(range_query, params_tuple)
        range_row = await cursor.fetchone()
        await cursor.close()
        earliest = range_row["earliest"] if range_row and range_row["earliest"] else None
        latest = range_row["latest"] if range_row and range_row["latest"] else None

        return {
            "total": total,
            "by_type": by_type,
            "by_producer": by_producer,
            "by_visibility": by_visibility,
            "tag_counts": tag_counts,
            "earliest_created_at": earliest,
            "latest_created_at": latest,
        }

    async def agent_history_summary(
        self,
        agent_id: str,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        filters = filters or FilterConfig()
        conn = await self._get_connection()

        produced_total = 0
        produced_by_type: dict[str, int] = {}

        if filters.produced_by and agent_id not in filters.produced_by:
            produced_total = 0
        else:
            produced_filter = FilterConfig(
                type_names=set(filters.type_names) if filters.type_names else None,
                produced_by={agent_id},
                correlation_id=filters.correlation_id,
                tags=set(filters.tags) if filters.tags else None,
                visibility=set(filters.visibility) if filters.visibility else None,
                start=filters.start,
                end=filters.end,
            )
            where_clause, params = self._build_filters(produced_filter)
            produced_query = f"""
                SELECT canonical_type, COUNT(*) AS count
                FROM artifacts
                {where_clause}
                GROUP BY canonical_type
            """  # nosec B608 - produced_filter yields parameter placeholders only
            cursor = await conn.execute(produced_query, tuple(params))
            rows = await cursor.fetchall()
            await cursor.close()
            produced_by_type = {row["canonical_type"]: row["count"] for row in rows}
            produced_total = sum(produced_by_type.values())

        where_clause, params = self._build_filters(filters, table_alias="a")
        params_with_consumer = (*params, agent_id)
        consumption_query = f"""
            SELECT a.canonical_type AS canonical_type, COUNT(*) AS count
            FROM artifact_consumptions c
            JOIN artifacts a ON a.artifact_id = c.artifact_id
            {where_clause}
            {"AND" if where_clause else "WHERE"} c.consumer = ?
            GROUP BY a.canonical_type
        """  # nosec B608 - where_clause joins parameter placeholders only
        cursor = await conn.execute(consumption_query, params_with_consumer)
        consumption_rows = await cursor.fetchall()
        await cursor.close()

        consumed_by_type = {row["canonical_type"]: row["count"] for row in consumption_rows}
        consumed_total = sum(consumed_by_type.values())

        return {
            "produced": {"total": produced_total, "by_type": produced_by_type},
            "consumed": {"total": consumed_total, "by_type": consumed_by_type},
        }

    async def upsert_agent_snapshot(self, snapshot: AgentSnapshotRecord) -> None:
        with tracer.start_as_current_span("sqlite_store.upsert_agent_snapshot"):
            conn = await self._get_connection()
            payload = {
                "agent_name": snapshot.agent_name,
                "description": snapshot.description,
                "subscriptions": json.dumps(snapshot.subscriptions),
                "output_types": json.dumps(snapshot.output_types),
                "labels": json.dumps(snapshot.labels),
                "first_seen": snapshot.first_seen.isoformat(),
                "last_seen": snapshot.last_seen.isoformat(),
                "signature": snapshot.signature,
            }
            async with self._write_lock:
                await conn.execute(
                    """
                    INSERT INTO agent_snapshots (
                        agent_name, description, subscriptions, output_types, labels,
                        first_seen, last_seen, signature
                    ) VALUES (
                        :agent_name, :description, :subscriptions, :output_types, :labels,
                        :first_seen, :last_seen, :signature
                    )
                    ON CONFLICT(agent_name) DO UPDATE SET
                        description=excluded.description,
                        subscriptions=excluded.subscriptions,
                        output_types=excluded.output_types,
                        labels=excluded.labels,
                        first_seen=excluded.first_seen,
                        last_seen=excluded.last_seen,
                        signature=excluded.signature
                    """,
                    payload,
                )
                await conn.commit()

    async def load_agent_snapshots(self) -> list[AgentSnapshotRecord]:
        with tracer.start_as_current_span("sqlite_store.load_agent_snapshots"):
            conn = await self._get_connection()
            cursor = await conn.execute(
                """
                SELECT agent_name, description, subscriptions, output_types, labels,
                       first_seen, last_seen, signature
                FROM agent_snapshots
                """
            )
            rows = await cursor.fetchall()
            await cursor.close()

            snapshots: list[AgentSnapshotRecord] = []
            for row in rows:
                snapshots.append(
                    AgentSnapshotRecord(
                        agent_name=row["agent_name"],
                        description=row["description"],
                        subscriptions=json.loads(row["subscriptions"] or "[]"),
                        output_types=json.loads(row["output_types"] or "[]"),
                        labels=json.loads(row["labels"] or "[]"),
                        first_seen=datetime.fromisoformat(row["first_seen"]),
                        last_seen=datetime.fromisoformat(row["last_seen"]),
                        signature=row["signature"],
                    )
                )
            return snapshots

    async def clear_agent_snapshots(self) -> None:
        with tracer.start_as_current_span("sqlite_store.clear_agent_snapshots"):
            conn = await self._get_connection()
            async with self._write_lock:
                await conn.execute("DELETE FROM agent_snapshots")
                await conn.commit()

    async def ensure_schema(self) -> None:
        conn = await self._ensure_connection()
        await self._apply_schema(conn)

    async def close(self) -> None:
        async with self._connection_lock:
            if self._connection is not None:
                await self._connection.close()
                self._connection = None
                self._schema_ready = False

    async def vacuum(self) -> None:
        """Run SQLite VACUUM for maintenance."""
        with tracer.start_as_current_span("sqlite_store.vacuum"):
            conn = await self._get_connection()
            async with self._write_lock:
                await conn.execute("VACUUM")
                await conn.commit()

    async def delete_before(self, before: datetime) -> int:
        """Delete artifacts persisted before the given timestamp."""
        with tracer.start_as_current_span("sqlite_store.delete_before"):
            conn = await self._get_connection()
            async with self._write_lock:
                cursor = await conn.execute(
                    "DELETE FROM artifacts WHERE created_at < ?", (before.isoformat(),)
                )
                await conn.commit()
                deleted = cursor.rowcount or 0
                await cursor.close()
            return deleted

    async def _ensure_connection(self) -> aiosqlite.Connection:
        async with self._connection_lock:
            if self._connection is None:
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                conn = await aiosqlite.connect(
                    str(self._db_path), timeout=self._timeout, isolation_level=None
                )
                conn.row_factory = aiosqlite.Row
                await conn.execute("PRAGMA journal_mode=WAL;")
                await conn.execute("PRAGMA synchronous=NORMAL;")
                await conn.execute("PRAGMA foreign_keys=ON;")
                self._connection = conn
                self._schema_ready = False
            return self._connection

    async def _get_connection(self) -> aiosqlite.Connection:
        conn = await self._ensure_connection()
        if not self._schema_ready:
            await self._apply_schema(conn)
        return conn

    async def _apply_schema(self, conn: aiosqlite.Connection) -> None:
        async with self._connection_lock:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await conn.execute(
                """
                INSERT OR IGNORE INTO schema_meta (id, version)
                VALUES (1, ?)
                """,
                (self.SCHEMA_VERSION,),
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    canonical_type TEXT NOT NULL,
                    produced_by TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    visibility TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    correlation_id TEXT,
                    partition_key TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_canonical_type_created
                ON artifacts(canonical_type, created_at)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_produced_by_created
                ON artifacts(produced_by, created_at)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_correlation
                ON artifacts(correlation_id)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_partition
                ON artifacts(partition_key)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifact_consumptions (
                    artifact_id TEXT NOT NULL,
                    consumer TEXT NOT NULL,
                    run_id TEXT,
                    correlation_id TEXT,
                    consumed_at TEXT NOT NULL,
                    PRIMARY KEY (artifact_id, consumer, consumed_at)
                )
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_consumptions_artifact
                ON artifact_consumptions(artifact_id)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_consumptions_consumer
                ON artifact_consumptions(consumer)
                """
            )
            await conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_consumptions_correlation
                ON artifact_consumptions(correlation_id)
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_snapshots (
                    agent_name TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    subscriptions TEXT NOT NULL,
                    output_types TEXT NOT NULL,
                    labels TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    signature TEXT NOT NULL
                )
                """
            )
            await conn.execute(
                "UPDATE schema_meta SET version=? WHERE id=1",
                (self.SCHEMA_VERSION,),
            )
            await conn.commit()
            self._schema_ready = True

    def _build_filters(
        self,
        filters: FilterConfig,
        *,
        table_alias: str | None = None,
    ) -> tuple[str, list[Any]]:
        prefix = f"{table_alias}." if table_alias else ""
        conditions: list[str] = []
        params: list[Any] = []

        if filters.type_names:
            canonical = {type_registry.resolve_name(name) for name in filters.type_names}
            placeholders = ", ".join("?" for _ in canonical)
            conditions.append(f"{prefix}canonical_type IN ({placeholders})")
            params.extend(sorted(canonical))

        if filters.produced_by:
            placeholders = ", ".join("?" for _ in filters.produced_by)
            conditions.append(f"{prefix}produced_by IN ({placeholders})")
            params.extend(sorted(filters.produced_by))

        if filters.correlation_id:
            conditions.append(f"{prefix}correlation_id = ?")
            params.append(filters.correlation_id)

        if filters.visibility:
            placeholders = ", ".join("?" for _ in filters.visibility)
            conditions.append(f"json_extract({prefix}visibility, '$.kind') IN ({placeholders})")
            params.extend(sorted(filters.visibility))

        if filters.start is not None:
            conditions.append(f"{prefix}created_at >= ?")
            params.append(filters.start.isoformat())

        if filters.end is not None:
            conditions.append(f"{prefix}created_at <= ?")
            params.append(filters.end.isoformat())

        if filters.tags:
            column = f"{prefix}tags" if table_alias else "artifacts.tags"
            for tag in sorted(filters.tags):
                conditions.append(
                    f"EXISTS (SELECT 1 FROM json_each({column}) WHERE json_each.value = ?)"  # nosec B608 - column is internal constant
                )
                params.append(tag)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_clause, params

    def _row_to_artifact(self, row: Any) -> Artifact:
        payload = json.loads(row["payload"])
        visibility_data = json.loads(row["visibility"])
        tags = json.loads(row["tags"])
        correlation_raw = row["correlation_id"]
        correlation = UUID(correlation_raw) if correlation_raw else None
        return Artifact(
            id=UUID(row["artifact_id"]),
            type=row["type"],
            payload=payload,
            produced_by=row["produced_by"],
            visibility=_deserialize_visibility(visibility_data),
            tags=set(tags),
            correlation_id=correlation,
            partition_key=row["partition_key"],
            created_at=datetime.fromisoformat(row["created_at"]),
            version=row["version"],
        )
