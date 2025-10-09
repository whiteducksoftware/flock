from __future__ import annotations


"""Blackboard storage primitives."""

import asyncio
import json
from asyncio import Lock
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

import aiosqlite
from opentelemetry import trace

from flock.artifacts import Artifact
from flock.registry import type_registry
from flock.visibility import ensure_visibility


T = TypeVar("T")
tracer = trace.get_tracer(__name__)


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

    async def query_artifacts(
        self,
        *,
        type_name: str | None = None,
        produced_by: str | None = None,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        """Search artifacts with filtering and pagination."""
        raise NotImplementedError

    async def summarize_artifacts(
        self,
        *,
        type_name: str | None = None,
        produced_by: str | None = None,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        """Return aggregate artifact statistics for the given filters."""
        raise NotImplementedError


class InMemoryBlackboardStore(BlackboardStore):
    """Simple in-memory implementation suitable for local dev and tests."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[UUID, Artifact] = {}
        self._by_type: dict[str, list[Artifact]] = defaultdict(list)

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
        """Get artifacts by Pydantic type, returning data already cast.

        Args:
            artifact_type: The Pydantic model class (e.g., BugAnalysis)

        Returns:
            List of data objects of the specified type (not Artifact wrappers)
        """
        async with self._lock:
            # Get canonical name from the type
            canonical = type_registry.resolve_name(artifact_type.__name__)
            artifacts = self._by_type.get(canonical, [])
            # Reconstruct Pydantic models from payload dictionaries
            return [artifact_type(**artifact.payload) for artifact in artifacts]  # type: ignore

    async def extend(self, artifacts: Iterable[Artifact]) -> None:  # pragma: no cover - helper
        for artifact in artifacts:
            await self.publish(artifact)

    async def query_artifacts(
        self,
        *,
        type_name: str | None = None,
        produced_by: str | None = None,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        async with self._lock:
            artifacts = list(self._by_id.values())

        canonical: str | None = None
        if type_name is not None:
            canonical = type_registry.resolve_name(type_name)

        filtered = [
            artifact
            for artifact in artifacts
            if (
                (canonical is None or artifact.type == canonical)
                and (produced_by is None or artifact.produced_by == produced_by)
                and (
                    correlation_id is None
                    or (
                        artifact.correlation_id is not None
                        and str(artifact.correlation_id) == correlation_id
                    )
                )
                and (tags is None or tags.issubset(artifact.tags))
                and (start is None or artifact.created_at >= start)
                and (end is None or artifact.created_at <= end)
            )
        ]

        total = len(filtered)
        offset = max(offset, 0)
        if limit <= 0:
            sliced: list[Artifact] = []
        else:
            sliced = filtered[offset : offset + limit]
        return sliced, total

    async def summarize_artifacts(
        self,
        *,
        type_name: str | None = None,
        produced_by: str | None = None,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        artifacts, total = await self.query_artifacts(
            type_name=type_name,
            produced_by=produced_by,
            correlation_id=correlation_id,
            tags=tags,
            start=start,
            end=end,
            limit=0,
            offset=0,
        )

        if not artifacts and total > 0:
            artifacts, _ = await self.query_artifacts(
                type_name=type_name,
                produced_by=produced_by,
                correlation_id=correlation_id,
                tags=tags,
                start=start,
                end=end,
                limit=total,
                offset=0,
            )

        by_type: dict[str, int] = {}
        by_producer: dict[str, int] = {}
        earliest = None
        latest = None

        for artifact in artifacts:
            by_type[artifact.type] = by_type.get(artifact.type, 0) + 1
            by_producer[artifact.produced_by] = by_producer.get(artifact.produced_by, 0) + 1
            earliest = (
                artifact.created_at
                if earliest is None or artifact.created_at < earliest
                else earliest
            )
            latest = (
                artifact.created_at if latest is None or artifact.created_at > latest else latest
            )

        return {
            "total": total,
            "by_type": by_type,
            "by_producer": by_producer,
            "earliest_created_at": earliest.isoformat() if earliest else None,
            "latest_created_at": latest.isoformat() if latest else None,
        }


__all__ = [
    "BlackboardStore",
    "InMemoryBlackboardStore",
    "SQLiteBlackboardStore",
]


class SQLiteBlackboardStore(BlackboardStore):
    """SQLite-backed implementation of :class:`BlackboardStore`."""

    SCHEMA_VERSION = 1

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
        *,
        type_name: str | None = None,
        produced_by: str | None = None,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Artifact], int]:
        conn = await self._get_connection()
        where_clause, params = self._build_filters(
            type_name=type_name,
            produced_by=produced_by,
            correlation_id=correlation_id,
            tags=tags,
            start=start,
            end=end,
        )

        cursor = await conn.execute(
            f"SELECT COUNT(*) FROM artifacts{where_clause}",
            params,
        )
        total_row = await cursor.fetchone()
        await cursor.close()
        total = total_row[0] if total_row else 0

        if limit <= 0:
            return [], total
        offset = max(offset, 0)

        cursor = await conn.execute(
            f"""
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
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        return [self._row_to_artifact(row) for row in rows], total

    async def summarize_artifacts(
        self,
        *,
        type_name: str | None = None,
        produced_by: str | None = None,
        correlation_id: str | None = None,
        tags: set[str] | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> dict[str, Any]:
        conn = await self._get_connection()
        where_clause, params = self._build_filters(
            type_name=type_name,
            produced_by=produced_by,
            correlation_id=correlation_id,
            tags=tags,
            start=start,
            end=end,
        )

        cursor = await conn.execute(
            f"SELECT COUNT(*) as total FROM artifacts{where_clause}",
            params,
        )
        total_row = await cursor.fetchone()
        await cursor.close()
        total = total_row["total"] if total_row else 0

        cursor = await conn.execute(
            f"""
            SELECT canonical_type, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY canonical_type
            """,
            params,
        )
        by_type_rows = await cursor.fetchall()
        await cursor.close()
        by_type = {row["canonical_type"]: row["count"] for row in by_type_rows}

        cursor = await conn.execute(
            f"""
            SELECT produced_by, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY produced_by
            """,
            params,
        )
        by_producer_rows = await cursor.fetchall()
        await cursor.close()
        by_producer = {row["produced_by"]: row["count"] for row in by_producer_rows}

        cursor = await conn.execute(
            f"""
            SELECT MIN(created_at) AS earliest, MAX(created_at) AS latest
            FROM artifacts
            {where_clause}
            """,
            params,
        )
        range_row = await cursor.fetchone()
        await cursor.close()
        earliest = range_row["earliest"] if range_row and range_row["earliest"] else None
        latest = range_row["latest"] if range_row and range_row["latest"] else None

        return {
            "total": total,
            "by_type": by_type,
            "by_producer": by_producer,
            "earliest_created_at": earliest,
            "latest_created_at": latest,
        }

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
            await conn.commit()
            self._schema_ready = True

    def _build_filters(
        self,
        *,
        type_name: str | None,
        produced_by: str | None,
        correlation_id: str | None,
        tags: set[str] | None,
        start: datetime | None,
        end: datetime | None,
    ) -> tuple[str, tuple[Any, ...]]:
        conditions: list[str] = []
        params: list[Any] = []

        if type_name is not None:
            canonical = type_registry.resolve_name(type_name)
            conditions.append("canonical_type = ?")
            params.append(canonical)

        if produced_by is not None:
            conditions.append("produced_by = ?")
            params.append(produced_by)

        if correlation_id is not None:
            conditions.append("correlation_id = ?")
            params.append(correlation_id)

        if start is not None:
            conditions.append("created_at >= ?")
            params.append(start.isoformat())

        if end is not None:
            conditions.append("created_at <= ?")
            params.append(end.isoformat())

        if tags:
            for tag in tags:
                conditions.append(
                    "EXISTS (SELECT 1 FROM json_each(artifacts.tags) WHERE json_each.value = ?)"
                )
                params.append(tag)

        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_clause, tuple(params)

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
            visibility=ensure_visibility(visibility_data),
            tags=set(tags),
            correlation_id=correlation,
            partition_key=row["partition_key"],
            created_at=datetime.fromisoformat(row["created_at"]),
            version=row["version"],
        )
