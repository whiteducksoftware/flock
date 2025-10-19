"""SQLite consumption record loading utilities.

Handles loading and organizing consumption records for artifacts.
Extracted from query_artifacts to reduce complexity.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from flock.core.store import ConsumptionRecord


if TYPE_CHECKING:
    import aiosqlite


class SQLiteConsumptionLoader:
    """
    Loads consumption records from SQLite database.

    Separates consumption loading logic from main query method
    for better testability and maintainability.
    """

    async def load_for_artifacts(
        self,
        conn: aiosqlite.Connection,
        artifact_ids: list[str],
    ) -> dict[UUID, list[ConsumptionRecord]]:
        """
        Load consumption records for given artifact IDs.

        Args:
            conn: Active database connection
            artifact_ids: List of artifact ID strings

        Returns:
            Dict mapping artifact UUIDs to their consumption records

        Example:
            >>> loader = SQLiteConsumptionLoader()
            >>> consumptions = await loader.load_for_artifacts(conn, ["id1", "id2"])
            >>> consumptions[UUID("id1")]  # List[ConsumptionRecord]
        """
        if not artifact_ids:
            return {}

        # Build query with proper placeholders
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

        # Execute query
        cursor = await conn.execute(consumption_query, artifact_ids)
        consumption_rows = await cursor.fetchall()
        await cursor.close()

        # Build consumption map
        return self._build_consumption_map(consumption_rows)

    def _build_consumption_map(
        self, rows: list[aiosqlite.Row]
    ) -> dict[UUID, list[ConsumptionRecord]]:
        """
        Build consumption map from database rows.

        Args:
            rows: Database rows with consumption data

        Returns:
            Dict mapping artifact UUIDs to consumption records
        """
        consumptions_map: dict[UUID, list[ConsumptionRecord]] = defaultdict(list)

        for row in rows:
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

        return consumptions_map
