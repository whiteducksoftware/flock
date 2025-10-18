"""SQLite schema management for Flock blackboard store.

This module handles database schema creation, versioning, and migrations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    import aiosqlite


class SQLiteSchemaManager:
    """
    Manages SQLite database schema for blackboard storage.

    Responsibilities:
    - Schema version tracking
    - Table creation
    - Index creation
    - Schema migrations

    The schema includes:
    - artifacts table: Core artifact storage
    - artifact_consumptions table: Consumption tracking
    - agent_snapshots table: Agent metadata
    - schema_meta table: Version tracking
    """

    SCHEMA_VERSION = 3

    async def apply_schema(self, conn: aiosqlite.Connection) -> None:
        """
        Apply the blackboard schema to the SQLite connection.

        Creates all tables and indices if they don't exist. Handles schema
        versioning and migrations.

        Args:
            conn: Active SQLite connection

        Schema Tables:
            - schema_meta: Tracks schema version
            - artifacts: Core artifact storage
            - artifact_consumptions: Consumption events
            - agent_snapshots: Agent metadata
        """
        # Schema version tracking
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

        # Main artifacts table
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

        # Artifact indices for performance
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

        # Consumption tracking table
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

        # Consumption indices
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

        # Agent snapshots table
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

        # Update schema version
        await conn.execute(
            "UPDATE schema_meta SET version=? WHERE id=1",
            (self.SCHEMA_VERSION,),
        )
        await conn.commit()
