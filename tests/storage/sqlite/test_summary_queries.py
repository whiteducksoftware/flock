"""Tests for SQLite summary query utilities.

Validates the SQLiteSummaryQueries executes aggregation queries correctly
and returns properly formatted results.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flock.storage.sqlite.summary_queries import SQLiteSummaryQueries


@pytest.fixture
def queries():
    """Create a SQLiteSummaryQueries instance."""
    return SQLiteSummaryQueries()


@pytest.fixture
def mock_connection():
    """Create a mock aiosqlite connection."""
    conn = AsyncMock()
    return conn


class TestCountTotal:
    """Test total artifact counting."""

    @pytest.mark.asyncio
    async def test_count_total(self, queries, mock_connection):
        """Should execute count query and return total."""
        mock_row = {"total": 42}
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_cursor

        result = await queries.count_total(
            mock_connection, " WHERE type = ?", ("Result",)
        )

        assert result == 42
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "COUNT(*)" in call_args[0][0]
        assert call_args[0][1] == ("Result",)

    @pytest.mark.asyncio
    async def test_count_total_no_results(self, queries, mock_connection):
        """Should return 0 when no results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None
        mock_connection.execute.return_value = mock_cursor

        result = await queries.count_total(mock_connection, "", ())
        assert result == 0


class TestGroupByType:
    """Test grouping by artifact type."""

    @pytest.mark.asyncio
    async def test_group_by_type(self, queries, mock_connection):
        """Should execute group by type query and return counts."""
        mock_rows = [
            {"canonical_type": "Result", "count": 10},
            {"canonical_type": "Message", "count": 5},
        ]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_cursor

        result = await queries.group_by_type(mock_connection, "", ())

        assert result == {"Result": 10, "Message": 5}
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "GROUP BY canonical_type" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_group_by_type_empty(self, queries, mock_connection):
        """Should return empty dict when no results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.execute.return_value = mock_cursor

        result = await queries.group_by_type(mock_connection, "", ())
        assert result == {}


class TestGroupByProducer:
    """Test grouping by producer."""

    @pytest.mark.asyncio
    async def test_group_by_producer(self, queries, mock_connection):
        """Should execute group by producer query and return counts."""
        mock_rows = [
            {"produced_by": "agent1", "count": 15},
            {"produced_by": "agent2", "count": 7},
        ]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_cursor

        result = await queries.group_by_producer(mock_connection, "", ())

        assert result == {"agent1": 15, "agent2": 7}
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "GROUP BY produced_by" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_group_by_producer_empty(self, queries, mock_connection):
        """Should return empty dict when no results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.execute.return_value = mock_cursor

        result = await queries.group_by_producer(mock_connection, "", ())
        assert result == {}


class TestGroupByVisibility:
    """Test grouping by visibility kind."""

    @pytest.mark.asyncio
    async def test_group_by_visibility(self, queries, mock_connection):
        """Should execute group by visibility query and return counts."""
        mock_rows = [
            {"visibility_kind": "Public", "count": 20},
            {"visibility_kind": "Private", "count": 5},
        ]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_cursor

        result = await queries.group_by_visibility(mock_connection, "", ())

        assert result == {"Public": 20, "Private": 5}
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "json_extract(visibility, '$.kind')" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_group_by_visibility_unknown(self, queries, mock_connection):
        """Should handle NULL visibility as 'Unknown'."""
        mock_rows = [
            {"visibility_kind": None, "count": 3},
        ]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_cursor

        result = await queries.group_by_visibility(mock_connection, "", ())
        assert result == {"Unknown": 3}


class TestCountTags:
    """Test tag occurrence counting."""

    @pytest.mark.asyncio
    async def test_count_tags(self, queries, mock_connection):
        """Should execute tag count query and return counts."""
        mock_rows = [
            {"tag": "important", "count": 8},
            {"tag": "urgent", "count": 3},
        ]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_cursor

        result = await queries.count_tags(mock_connection, "", ())

        assert result == {"important": 8, "urgent": 3}
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "json_each" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_count_tags_empty(self, queries, mock_connection):
        """Should return empty dict when no tags."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.execute.return_value = mock_cursor

        result = await queries.count_tags(mock_connection, "", ())
        assert result == {}


class TestGetDateRange:
    """Test date range extraction."""

    @pytest.mark.asyncio
    async def test_get_date_range(self, queries, mock_connection):
        """Should execute date range query and return earliest/latest."""
        mock_row = {
            "earliest": "2025-01-15T10:00:00",
            "latest": "2025-01-15T12:30:00",
        }
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_cursor

        earliest, latest = await queries.get_date_range(mock_connection, "", ())

        assert earliest == "2025-01-15T10:00:00"
        assert latest == "2025-01-15T12:30:00"
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "MIN(created_at)" in call_args[0][0]
        assert "MAX(created_at)" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_date_range_no_results(self, queries, mock_connection):
        """Should return (None, None) when no results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = None
        mock_connection.execute.return_value = mock_cursor

        earliest, latest = await queries.get_date_range(mock_connection, "", ())
        assert earliest is None
        assert latest is None

    @pytest.mark.asyncio
    async def test_get_date_range_null_values(self, queries, mock_connection):
        """Should handle NULL values in date range."""
        mock_row = {"earliest": None, "latest": None}
        mock_cursor = AsyncMock()
        mock_cursor.fetchone.return_value = mock_row
        mock_connection.execute.return_value = mock_cursor

        earliest, latest = await queries.get_date_range(mock_connection, "", ())
        assert earliest is None
        assert latest is None
