"""Agent history query utilities for SQLite storage.

Handles agent-specific produced/consumed queries for history summaries.
Extracted from store.py to reduce complexity from B (10) to A (5).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import aiosqlite

    from flock.core.store import FilterConfig


class AgentHistoryQueries:
    """
    Execute SQLite queries for agent history summaries.

    Provides focused methods for querying produced and consumed artifacts
    for a specific agent.
    """

    async def query_produced(
        self,
        conn: aiosqlite.Connection,
        agent_id: str,
        filters: FilterConfig,
        build_filters_fn: Any,  # Callable for filter building
    ) -> dict[str, int]:
        """
        Query artifacts produced by agent, grouped by type.

        Args:
            conn: Active database connection
            agent_id: Producer to query for
            filters: Base filter configuration
            build_filters_fn: Function to build WHERE clause from filters

        Returns:
            Dict mapping canonical types to production counts

        Examples:
            >>> queries = AgentHistoryQueries()
            >>> produced = await queries.query_produced(
            ...     conn, "agent1", filters, builder
            ... )
            >>> produced
            {"Result": 10, "Message": 5}
        """
        # Check if agent is excluded by filters
        if filters.produced_by and agent_id not in filters.produced_by:
            return {}

        # Derive filter for this specific agent
        produced_filter = self._derive_produced_filter(filters, agent_id)

        # Build WHERE clause
        where_clause, params = build_filters_fn(produced_filter)

        # Execute query
        produced_query = f"""
            SELECT canonical_type, COUNT(*) AS count
            FROM artifacts
            {where_clause}
            GROUP BY canonical_type
        """  # nosec B608 - where_clause contains only parameter placeholders

        cursor = await conn.execute(produced_query, tuple(params))
        rows = await cursor.fetchall()
        await cursor.close()

        return {row["canonical_type"]: row["count"] for row in rows}

    async def query_consumed(
        self,
        conn: aiosqlite.Connection,
        agent_id: str,
        filters: FilterConfig,
        build_filters_fn: Any,  # Callable for filter building
    ) -> dict[str, int]:
        """
        Query artifacts consumed by agent, grouped by type.

        Args:
            conn: Active database connection
            agent_id: Consumer to query for
            filters: Base filter configuration
            build_filters_fn: Function to build WHERE clause from filters

        Returns:
            Dict mapping canonical types to consumption counts

        Examples:
            >>> queries = AgentHistoryQueries()
            >>> consumed = await queries.query_consumed(
            ...     conn, "agent1", filters, builder
            ... )
            >>> consumed
            {"Result": 8, "Message": 3}
        """
        # Build WHERE clause with table alias for JOIN
        where_clause, params = build_filters_fn(filters, table_alias="a")
        params_with_consumer = (*params, agent_id)

        # Execute query with JOIN
        consumption_query = f"""
            SELECT a.canonical_type AS canonical_type, COUNT(*) AS count
            FROM artifact_consumptions c
            JOIN artifacts a ON a.artifact_id = c.artifact_id
            {where_clause}
            {"AND" if where_clause else "WHERE"} c.consumer = ?
            GROUP BY a.canonical_type
        """  # nosec B608 - where_clause contains only parameter placeholders

        cursor = await conn.execute(consumption_query, params_with_consumer)
        rows = await cursor.fetchall()
        await cursor.close()

        return {row["canonical_type"]: row["count"] for row in rows}

    def _derive_produced_filter(
        self, base_filters: FilterConfig, agent_id: str
    ) -> FilterConfig:
        """
        Derive a filter configuration specific to agent's production.

        Creates a new FilterConfig with agent_id as producer while
        preserving other filter criteria.

        Args:
            base_filters: Base filter configuration
            agent_id: Agent to filter production for

        Returns:
            New FilterConfig with agent_id as producer
        """
        from flock.core.store import FilterConfig

        return FilterConfig(
            type_names=set(base_filters.type_names)
            if base_filters.type_names
            else None,
            produced_by={agent_id},
            correlation_id=base_filters.correlation_id,
            tags=set(base_filters.tags) if base_filters.tags else None,
            visibility=set(base_filters.visibility)
            if base_filters.visibility
            else None,
            start=base_filters.start,
            end=base_filters.end,
        )
