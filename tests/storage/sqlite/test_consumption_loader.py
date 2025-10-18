"""Tests for SQLite consumption record loading.

Validates the SQLiteConsumptionLoader handles loading and organizing
consumption records correctly.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from flock.core.store import ConsumptionRecord
from flock.storage.sqlite.consumption_loader import SQLiteConsumptionLoader


@pytest.fixture
def loader():
    """Create a SQLiteConsumptionLoader instance."""
    return SQLiteConsumptionLoader()


@pytest.fixture
def mock_connection():
    """Create a mock aiosqlite connection."""
    conn = AsyncMock()
    return conn


class TestLoadForArtifacts:
    """Test consumption record loading for artifacts."""

    @pytest.mark.asyncio
    async def test_load_for_artifacts_empty(self, loader, mock_connection):
        """Should return empty dict for empty artifact_ids list."""
        result = await loader.load_for_artifacts(mock_connection, [])
        assert result == {}
        # Should not execute any queries
        mock_connection.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_load_for_artifacts_single(self, loader, mock_connection):
        """Should load consumptions for single artifact."""
        artifact_id = str(uuid4())
        consumed_at = datetime.now().isoformat()

        # Mock database response
        mock_row = {
            "artifact_id": artifact_id,
            "consumer": "agent1",
            "run_id": "run-123",
            "correlation_id": "corr-456",
            "consumed_at": consumed_at,
        }
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [mock_row]
        mock_connection.execute.return_value = mock_cursor

        result = await loader.load_for_artifacts(mock_connection, [artifact_id])

        # Verify query execution
        mock_connection.execute.assert_called_once()
        call_args = mock_connection.execute.call_args
        assert "SELECT" in call_args[0][0]
        assert "artifact_consumptions" in call_args[0][0]
        assert call_args[0][1] == [artifact_id]

        # Verify result
        assert len(result) == 1
        artifact_uuid = UUID(artifact_id)
        assert artifact_uuid in result
        assert len(result[artifact_uuid]) == 1

        consumption = result[artifact_uuid][0]
        assert isinstance(consumption, ConsumptionRecord)
        assert consumption.artifact_id == artifact_uuid
        assert consumption.consumer == "agent1"
        assert consumption.run_id == "run-123"
        assert consumption.correlation_id == "corr-456"
        assert consumption.consumed_at == datetime.fromisoformat(consumed_at)

    @pytest.mark.asyncio
    async def test_load_for_artifacts_multiple(self, loader, mock_connection):
        """Should load consumptions for multiple artifacts."""
        artifact_id1 = str(uuid4())
        artifact_id2 = str(uuid4())
        consumed_at = datetime.now().isoformat()

        # Mock database response with consumptions for both artifacts
        mock_rows = [
            {
                "artifact_id": artifact_id1,
                "consumer": "agent1",
                "run_id": "run-1",
                "correlation_id": "corr-1",
                "consumed_at": consumed_at,
            },
            {
                "artifact_id": artifact_id1,
                "consumer": "agent2",
                "run_id": "run-2",
                "correlation_id": "corr-2",
                "consumed_at": consumed_at,
            },
            {
                "artifact_id": artifact_id2,
                "consumer": "agent3",
                "run_id": "run-3",
                "correlation_id": "corr-3",
                "consumed_at": consumed_at,
            },
        ]
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_connection.execute.return_value = mock_cursor

        result = await loader.load_for_artifacts(
            mock_connection, [artifact_id1, artifact_id2]
        )

        # Verify both artifacts have consumptions
        assert len(result) == 2
        assert UUID(artifact_id1) in result
        assert UUID(artifact_id2) in result

        # artifact1 should have 2 consumptions
        assert len(result[UUID(artifact_id1)]) == 2
        # artifact2 should have 1 consumption
        assert len(result[UUID(artifact_id2)]) == 1

    @pytest.mark.asyncio
    async def test_load_for_artifacts_no_consumptions(self, loader, mock_connection):
        """Should return empty map when no consumptions exist."""
        artifact_id = str(uuid4())

        # Mock empty database response
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.execute.return_value = mock_cursor

        result = await loader.load_for_artifacts(mock_connection, [artifact_id])

        # Should return empty dict (no consumptions found)
        assert result == {}

    @pytest.mark.asyncio
    async def test_load_for_artifacts_sql_injection_protection(
        self, loader, mock_connection
    ):
        """Should use parameterized queries to prevent SQL injection."""
        artifact_ids = ["id1", "id2", "id3"]

        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []
        mock_connection.execute.return_value = mock_cursor

        await loader.load_for_artifacts(mock_connection, artifact_ids)

        # Verify placeholders are used
        call_args = mock_connection.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Should have placeholders, not direct string interpolation
        assert "?, ?, ?" in query
        assert params == artifact_ids


class TestBuildConsumptionMap:
    """Test consumption map building from database rows."""

    def test_build_consumption_map_empty(self, loader):
        """Should return empty map for empty rows."""
        result = loader._build_consumption_map([])
        assert result == {}

    def test_build_consumption_map_single(self, loader):
        """Should build map with single consumption."""
        artifact_id = str(uuid4())
        consumed_at = datetime.now().isoformat()

        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            "artifact_id": artifact_id,
            "consumer": "agent1",
            "run_id": "run-1",
            "correlation_id": "corr-1",
            "consumed_at": consumed_at,
        }[key]

        result = loader._build_consumption_map([mock_row])

        assert len(result) == 1
        artifact_uuid = UUID(artifact_id)
        assert artifact_uuid in result
        assert len(result[artifact_uuid]) == 1

    def test_build_consumption_map_multiple_per_artifact(self, loader):
        """Should group multiple consumptions per artifact."""
        artifact_id = str(uuid4())
        consumed_at = datetime.now().isoformat()

        def make_row(consumer):
            mock_row = MagicMock()
            mock_row.__getitem__ = lambda self, key: {
                "artifact_id": artifact_id,
                "consumer": consumer,
                "run_id": "run-1",
                "correlation_id": "corr-1",
                "consumed_at": consumed_at,
            }[key]
            return mock_row

        rows = [make_row("agent1"), make_row("agent2"), make_row("agent3")]
        result = loader._build_consumption_map(rows)

        artifact_uuid = UUID(artifact_id)
        assert len(result[artifact_uuid]) == 3
        consumers = [c.consumer for c in result[artifact_uuid]]
        assert consumers == ["agent1", "agent2", "agent3"]
