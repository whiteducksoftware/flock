from __future__ import annotations


"""Blackboard storage primitives."""

import asyncio
import json
from asyncio import Lock
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from uuid import UUID

import aiosqlite
from opentelemetry import trace

from flock.artifacts import Artifact
from flock.registry import type_registry
from flock.visibility import ensure_visibility


if TYPE_CHECKING:
    from collections.abc import Iterable

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

    def _row_to_artifact(self, row: Any) -> Artifact:
        payload = json.loads(row["payload"])
        visibility_data = json.loads(row["visibility"])
        tags = json.loads(row["tags"])
        return Artifact(
            id=UUID(row["artifact_id"]),
            type=row["type"],
            payload=payload,
            produced_by=row["produced_by"],
            visibility=ensure_visibility(visibility_data),
            tags=set(tags),
            correlation_id=row["correlation_id"],
            partition_key=row["partition_key"],
            created_at=datetime.fromisoformat(row["created_at"]),
            version=row["version"],
        )
