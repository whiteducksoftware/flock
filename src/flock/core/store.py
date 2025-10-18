from __future__ import annotations


"""Blackboard storage primitives and metadata envelopes.

Future backends should read the docstrings on :class:`FilterConfig`,
:class:`ConsumptionRecord`, and :class:`BlackboardStore` to understand the
contract expected by the REST layer and dashboard.
"""

import asyncio
import json
from asyncio import Lock
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

import aiosqlite
from opentelemetry import trace

from flock.core.artifacts import Artifact
from flock.registry import type_registry
from flock.storage.artifact_aggregator import ArtifactAggregator
from flock.utils.type_resolution import TypeResolutionHelper
from flock.utils.visibility_utils import deserialize_visibility


T = TypeVar("T")
tracer = trace.get_tracer(__name__)


@dataclass(slots=True)
class ConsumptionRecord:
    """Historical record describing which agent consumed an artifact."""

    artifact_id: UUID
    consumer: str
    run_id: str | None = None
    correlation_id: str | None = None
    consumed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


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
        self._consumptions_by_artifact: dict[UUID, list[ConsumptionRecord]] = (
            defaultdict(list)
        )
        self._agent_snapshots: dict[str, AgentSnapshotRecord] = {}

        # Initialize helper subsystems
        from flock.storage.in_memory.history_aggregator import HistoryAggregator

        self._aggregator = ArtifactAggregator()
        self._history_aggregator = HistoryAggregator()

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

    async def extend(
        self, artifacts: Iterable[Artifact]
    ) -> None:  # pragma: no cover - helper
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
        """Query artifacts using artifact filter helper."""
        async with self._lock:
            artifacts = list(self._by_id.values())

        # Use artifact filter helper for filtering logic
        filters = filters or FilterConfig()
        from flock.storage.in_memory.artifact_filter import ArtifactFilter

        artifact_filter = ArtifactFilter(filters)
        filtered = [a for a in artifacts if artifact_filter.matches(a)]
        filtered.sort(key=lambda a: (a.created_at, a.id))

        # Apply pagination
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
        """Summarize artifacts using artifact aggregator."""
        filters = filters or FilterConfig()
        artifacts, total = await self.query_artifacts(
            filters=filters,
            limit=0,
            offset=0,
            embed_meta=False,
        )

        # Validate artifacts are correct type
        for artifact in artifacts:
            if not isinstance(artifact, Artifact):
                raise TypeError("Expected Artifact instance")

        # Delegate to aggregator for all aggregation logic
        is_full_window = filters.start is None and filters.end is None
        return self._aggregator.build_summary(artifacts, total, is_full_window)

    async def agent_history_summary(
        self,
        agent_id: str,
        filters: FilterConfig | None = None,
    ) -> dict[str, Any]:
        """Summarize agent history using history aggregator."""
        filters = filters or FilterConfig()
        envelopes, _ = await self.query_artifacts(
            filters=filters,
            limit=0,
            offset=0,
            embed_meta=True,
        )

        # Delegate to history aggregator for aggregation logic
        return self._history_aggregator.aggregate(envelopes, agent_id)

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

    def __init__(self, db_path: str, *, timeout: float = 5.0) -> None:
        self._db_path = Path(db_path)
        self._timeout = timeout
        self._connection: aiosqlite.Connection | None = None
        self._connection_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._schema_ready = False

        # Initialize helper subsystems
        from flock.storage.sqlite.agent_history_queries import AgentHistoryQueries
        from flock.storage.sqlite.consumption_loader import SQLiteConsumptionLoader
        from flock.storage.sqlite.query_builder import SQLiteQueryBuilder
        from flock.storage.sqlite.query_params_builder import QueryParamsBuilder
        from flock.storage.sqlite.schema_manager import SQLiteSchemaManager
        from flock.storage.sqlite.summary_queries import SQLiteSummaryQueries

        self._schema_manager = SQLiteSchemaManager()
        self._query_builder = SQLiteQueryBuilder()
        self._consumption_loader = SQLiteConsumptionLoader()
        self._summary_queries = SQLiteSummaryQueries()
        self._query_params_builder = QueryParamsBuilder()
        self._agent_history_queries = AgentHistoryQueries()

    async def publish(self, artifact: Artifact) -> None:  # type: ignore[override]
        with tracer.start_as_current_span("sqlite_store.publish"):
            conn = await self._get_connection()

            payload_json = json.dumps(artifact.payload)
            visibility_json = json.dumps(artifact.visibility.model_dump(mode="json"))
            tags_json = json.dumps(sorted(artifact.tags))
            created_at = artifact.created_at.isoformat()

            canonical_type = TypeResolutionHelper.safe_resolve(
                type_registry, artifact.type
            )

            record = {
                "artifact_id": str(artifact.id),
                "type": artifact.type,
                "canonical_type": canonical_type,
                "produced_by": artifact.produced_by,
                "payload": payload_json,
                "version": artifact.version,
                "visibility": visibility_json,
                "tags": tags_json,
                "correlation_id": str(artifact.correlation_id)
                if artifact.correlation_id
                else None,
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
        """Query artifacts using query params builder."""
        filters = filters or FilterConfig()
        conn = await self._get_connection()

        where_clause, params = self._build_filters(filters)
        count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"  # nosec B608
        cursor = await conn.execute(count_query, tuple(params))
        total_row = await cursor.fetchone()
        await cursor.close()
        total = total_row["total"] if total_row else 0

        # Build base query
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
        """  # nosec B608

        # Use query params builder for pagination
        pagination_clause, query_params = (
            self._query_params_builder.build_pagination_params(params, limit, offset)
        )
        query += pagination_clause

        cursor = await conn.execute(query, query_params)
        rows = await cursor.fetchall()
        await cursor.close()
        artifacts = [self._row_to_artifact(row) for row in rows]

        if not embed_meta or not artifacts:
            return artifacts, total

        # Load consumptions using consumption loader
        artifact_ids = [str(artifact.id) for artifact in artifacts]
        consumptions_map = await self._consumption_loader.load_for_artifacts(
            conn, artifact_ids
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
        """Summarize artifacts using summary query builder."""
        filters = filters or FilterConfig()
        conn = await self._get_connection()

        where_clause, params = self._build_filters(filters)
        params_tuple = tuple(params)

        # Execute all summary queries using summary query builder
        total = await self._summary_queries.count_total(
            conn, where_clause, params_tuple
        )
        by_type = await self._summary_queries.group_by_type(
            conn, where_clause, params_tuple
        )
        by_producer = await self._summary_queries.group_by_producer(
            conn, where_clause, params_tuple
        )
        by_visibility = await self._summary_queries.group_by_visibility(
            conn, where_clause, params_tuple
        )
        tag_counts = await self._summary_queries.count_tags(
            conn, where_clause, params_tuple
        )
        earliest, latest = await self._summary_queries.get_date_range(
            conn, where_clause, params_tuple
        )

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
        """Summarize agent history using agent history queries."""
        filters = filters or FilterConfig()
        conn = await self._get_connection()

        # Use agent history queries helper for both produced and consumed
        produced_by_type = await self._agent_history_queries.query_produced(
            conn, agent_id, filters, self._build_filters
        )
        consumed_by_type = await self._agent_history_queries.query_consumed(
            conn, agent_id, filters, self._build_filters
        )

        return {
            "produced": {
                "total": sum(produced_by_type.values()),
                "by_type": produced_by_type,
            },
            "consumed": {
                "total": sum(consumed_by_type.values()),
                "by_type": consumed_by_type,
            },
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
        """Apply database schema using schema manager."""
        async with self._connection_lock:
            await self._schema_manager.apply_schema(conn)
            self._schema_ready = True

    def _build_filters(
        self,
        filters: FilterConfig,
        *,
        table_alias: str | None = None,
    ) -> tuple[str, list[Any]]:
        """Build WHERE clause using query builder."""
        return self._query_builder.build_filters(filters, table_alias=table_alias)

    def _row_to_artifact(self, row: Any) -> Artifact:
        """Convert database row to Artifact using visibility utils."""
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
            visibility=deserialize_visibility(visibility_data),
            tags=set(tags),
            correlation_id=correlation,
            partition_key=row["partition_key"],
            created_at=datetime.fromisoformat(row["created_at"]),
            version=row["version"],
        )
