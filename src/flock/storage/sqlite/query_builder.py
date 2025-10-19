"""SQLite query building utilities for artifact filtering.

This module constructs safe, parameterized SQL queries from filter configurations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from flock.core.store import FilterConfig


class SQLiteQueryBuilder:
    """
    Builds safe SQL queries with proper parameter binding.

    Responsibilities:
    - Build SELECT queries from filter configurations
    - Construct WHERE clauses with parameter placeholders
    - Prevent SQL injection via proper parameter binding
    - Support complex filtering (types, producers, tags, visibility, dates)

    All queries use parameter placeholders (?) and return both the SQL string
    and parameter list to ensure safe execution.
    """

    def build_filters(
        self,
        filters: FilterConfig,
        *,
        table_alias: str | None = None,
    ) -> tuple[str, list[Any]]:
        """
        Build WHERE clause and parameters from filter configuration.

        Args:
            filters: Filter configuration specifying query constraints
            table_alias: Optional table alias prefix (e.g., "a" for "a.type")

        Returns:
            Tuple of (where_clause, parameters):
            - where_clause: SQL WHERE clause string (e.g., " WHERE type = ?")
            - parameters: List of values for parameter binding

        Example:
            >>> filters = FilterConfig(type_names={"BugReport"}, limit=10)
            >>> where, params = builder.build_filters(filters)
            >>> # where = " WHERE canonical_type IN (?)"
            >>> # params = ["flock.BugReport"]

        Security:
            All values are bound via parameters, preventing SQL injection.
            The WHERE clause contains only placeholders (?), never raw values.
        """
        # Import here to avoid circular dependency
        from flock.registry import type_registry

        prefix = f"{table_alias}." if table_alias else ""
        conditions: list[str] = []
        params: list[Any] = []

        # Type filter
        if filters.type_names:
            canonical = {
                type_registry.resolve_name(name) for name in filters.type_names
            }
            placeholders = ", ".join("?" for _ in canonical)
            conditions.append(f"{prefix}canonical_type IN ({placeholders})")
            params.extend(sorted(canonical))

        # Producer filter
        if filters.produced_by:
            placeholders = ", ".join("?" for _ in filters.produced_by)
            conditions.append(f"{prefix}produced_by IN ({placeholders})")
            params.extend(sorted(filters.produced_by))

        # Correlation ID filter
        if filters.correlation_id:
            conditions.append(f"{prefix}correlation_id = ?")
            params.append(filters.correlation_id)

        # Visibility filter
        if filters.visibility:
            placeholders = ", ".join("?" for _ in filters.visibility)
            conditions.append(
                f"json_extract({prefix}visibility, '$.kind') IN ({placeholders})"
            )
            params.extend(sorted(filters.visibility))

        # Date range filters
        if filters.start is not None:
            conditions.append(f"{prefix}created_at >= ?")
            params.append(filters.start.isoformat())

        if filters.end is not None:
            conditions.append(f"{prefix}created_at <= ?")
            params.append(filters.end.isoformat())

        # Tag filter (JSON array contains check)
        if filters.tags:
            column = f"{prefix}tags" if table_alias else "artifacts.tags"
            for tag in sorted(filters.tags):
                conditions.append(
                    f"EXISTS (SELECT 1 FROM json_each({column}) WHERE json_each.value = ?)"  # nosec B608 - column is internal constant
                )
                params.append(tag)

        # Build final WHERE clause
        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        return where_clause, params
