"""SQLite summary query utilities.

Provides focused methods for executing summary/aggregation queries.
Extracted from summarize_artifacts to reduce complexity and improve testability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import aiosqlite


class SQLiteSummaryQueries:
    """
    Executes summary SQL queries for artifact statistics.

    Each method handles one specific aggregation query, making them
    simple, testable, and easy to maintain.
    """

    async def count_total(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
    ) -> int:
        """
        Get total artifact count.

        Args:
            conn: Database connection
            where_clause: SQL WHERE clause (e.g., " WHERE type = ?")
            params: Parameter values for WHERE clause

        Returns:
            Total count of matching artifacts
        """
        count_query = f"SELECT COUNT(*) AS total FROM artifacts{where_clause}"  # nosec B608
        cursor = await conn.execute(count_query, params)
        total_row = await cursor.fetchone()
        await cursor.close()
        return total_row["total"] if total_row else 0

    async def group_by_type(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
    ) -> dict[str, int]:
        """
        Get artifact counts grouped by type.

        Args:
            conn: Database connection
            where_clause: SQL WHERE clause
            params: Parameter values for WHERE clause

        Returns:
            Dict mapping canonical type names to counts
        """
        by_type_query = f"""
            SELECT canonical_type, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY canonical_type
        """  # nosec B608
        cursor = await conn.execute(by_type_query, params)
        by_type_rows = await cursor.fetchall()
        await cursor.close()
        return {row["canonical_type"]: row["count"] for row in by_type_rows}

    async def group_by_producer(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
    ) -> dict[str, int]:
        """
        Get artifact counts grouped by producer.

        Args:
            conn: Database connection
            where_clause: SQL WHERE clause
            params: Parameter values for WHERE clause

        Returns:
            Dict mapping producer names to counts
        """
        by_producer_query = f"""
            SELECT produced_by, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY produced_by
        """  # nosec B608
        cursor = await conn.execute(by_producer_query, params)
        by_producer_rows = await cursor.fetchall()
        await cursor.close()
        return {row["produced_by"]: row["count"] for row in by_producer_rows}

    async def group_by_visibility(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
    ) -> dict[str, int]:
        """
        Get artifact counts grouped by visibility kind.

        Args:
            conn: Database connection
            where_clause: SQL WHERE clause
            params: Parameter values for WHERE clause

        Returns:
            Dict mapping visibility kinds to counts
        """
        by_visibility_query = f"""
            SELECT json_extract(visibility, '$.kind') AS visibility_kind, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY json_extract(visibility, '$.kind')
        """  # nosec B608
        cursor = await conn.execute(by_visibility_query, params)
        by_visibility_rows = await cursor.fetchall()
        await cursor.close()
        return {
            (row["visibility_kind"] or "Unknown"): row["count"]
            for row in by_visibility_rows
        }

    async def count_tags(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
    ) -> dict[str, int]:
        """
        Get tag occurrence counts.

        Args:
            conn: Database connection
            where_clause: SQL WHERE clause
            params: Parameter values for WHERE clause

        Returns:
            Dict mapping tag names to occurrence counts
        """
        tag_query = f"""
            SELECT json_each.value AS tag, COUNT(*) AS count
            FROM artifacts
            JOIN json_each(artifacts.tags)
            {where_clause}
            GROUP BY json_each.value
        """  # nosec B608
        cursor = await conn.execute(tag_query, params)
        tag_rows = await cursor.fetchall()
        await cursor.close()
        return {row["tag"]: row["count"] for row in tag_rows}

    async def get_date_range(
        self,
        conn: aiosqlite.Connection,
        where_clause: str,
        params: tuple[Any, ...],
    ) -> tuple[str | None, str | None]:
        """
        Get earliest and latest creation timestamps.

        Args:
            conn: Database connection
            where_clause: SQL WHERE clause
            params: Parameter values for WHERE clause

        Returns:
            Tuple of (earliest, latest) ISO timestamp strings, or (None, None)
        """
        range_query = f"""
            SELECT MIN(created_at) AS earliest, MAX(created_at) AS latest
            FROM artifacts
            {where_clause}
        """  # nosec B608
        cursor = await conn.execute(range_query, params)
        range_row = await cursor.fetchone()
        await cursor.close()

        if not range_row:
            return None, None

        earliest = range_row["earliest"] if range_row["earliest"] else None
        latest = range_row["latest"] if range_row["latest"] else None
        return earliest, latest
