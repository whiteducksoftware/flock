"""Query parameter building utilities for SQLite storage.

Handles pagination parameter construction for SQLite queries.
Extracted from store.py to reduce complexity from B (10) to A (4).
"""

from __future__ import annotations

from typing import Any


class QueryParamsBuilder:
    """
    Build query parameters for SQLite pagination.

    Simplifies limit/offset parameter handling by providing focused
    methods for different pagination scenarios.
    """

    def build_pagination_params(
        self,
        base_params: list[Any],
        limit: int,
        offset: int,
    ) -> tuple[str, tuple[Any, ...]]:
        """
        Build LIMIT/OFFSET clause and parameters for pagination.

        Handles three scenarios:
        1. No limit, no offset: Return all results
        2. No limit, with offset: Skip first N results
        3. With limit: Standard pagination

        Args:
            base_params: Base query parameters (from WHERE clause)
            limit: Maximum number of results (0 = unlimited)
            offset: Number of results to skip

        Returns:
            Tuple of (SQL clause suffix, complete parameters tuple)

        Examples:
            >>> builder = QueryParamsBuilder()
            >>> clause, params = builder.build_pagination_params([], 10, 0)
            >>> clause
            ' LIMIT ? OFFSET ?'
            >>> params
            (10, 0)
        """
        normalized_offset = max(offset, 0)

        if limit <= 0:
            return self._build_unlimited_params(base_params, normalized_offset)

        return self._build_limited_params(base_params, limit, normalized_offset)

    def _build_unlimited_params(
        self, base_params: list[Any], offset: int
    ) -> tuple[str, tuple[Any, ...]]:
        """
        Build parameters for unlimited results with optional offset.

        Args:
            base_params: Base query parameters
            offset: Number of results to skip (0 = no offset)

        Returns:
            Tuple of (SQL clause, parameters)
        """
        if offset > 0:
            # Need to skip first N results but return rest
            return " LIMIT -1 OFFSET ?", (*base_params, offset)

        # Return all results, no pagination
        return "", tuple(base_params)

    def _build_limited_params(
        self, base_params: list[Any], limit: int, offset: int
    ) -> tuple[str, tuple[Any, ...]]:
        """
        Build parameters for standard pagination with limit and offset.

        Args:
            base_params: Base query parameters
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            Tuple of (SQL clause, parameters)
        """
        return " LIMIT ? OFFSET ?", (*base_params, limit, offset)
