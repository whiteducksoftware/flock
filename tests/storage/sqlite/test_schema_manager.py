"""Tests for SQLite schema manager."""

import tempfile
from pathlib import Path

import aiosqlite
import pytest

from flock.storage.sqlite.schema_manager import SQLiteSchemaManager


@pytest.fixture
async def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        conn = await aiosqlite.connect(str(db_path))
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()


@pytest.fixture
def schema_manager():
    """Create schema manager instance."""
    return SQLiteSchemaManager()


@pytest.mark.asyncio
async def test_schema_manager_creates_tables(temp_db, schema_manager):
    """Test that schema manager creates all required tables."""
    await schema_manager.apply_schema(temp_db)

    # Verify all tables exist
    cursor = await temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row["name"] for row in await cursor.fetchall()]
    await cursor.close()

    expected_tables = [
        "agent_snapshots",
        "artifact_consumptions",
        "artifacts",
        "schema_meta",
    ]
    for table in expected_tables:
        assert table in tables, f"Table {table} should exist"


@pytest.mark.asyncio
async def test_schema_manager_creates_indices(temp_db, schema_manager):
    """Test that schema manager creates all required indices."""
    await schema_manager.apply_schema(temp_db)

    # Verify indices exist
    cursor = await temp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name"
    )
    indices = [row["name"] for row in await cursor.fetchall()]
    await cursor.close()

    expected_indices = [
        "idx_artifacts_canonical_type_created",
        "idx_artifacts_correlation",
        "idx_artifacts_partition",
        "idx_artifacts_produced_by_created",
        "idx_consumptions_artifact",
        "idx_consumptions_consumer",
        "idx_consumptions_correlation",
    ]
    for index in expected_indices:
        assert index in indices, f"Index {index} should exist"


@pytest.mark.asyncio
async def test_schema_manager_sets_version(temp_db, schema_manager):
    """Test that schema manager sets correct version."""
    await schema_manager.apply_schema(temp_db)

    # Verify schema version
    cursor = await temp_db.execute("SELECT version FROM schema_meta WHERE id = 1")
    row = await cursor.fetchone()
    await cursor.close()

    assert row is not None
    assert row["version"] == SQLiteSchemaManager.SCHEMA_VERSION


@pytest.mark.asyncio
async def test_schema_manager_idempotent(temp_db, schema_manager):
    """Test that schema manager can be run multiple times safely."""
    # Apply schema twice
    await schema_manager.apply_schema(temp_db)
    await schema_manager.apply_schema(temp_db)

    # Verify tables still exist and version is correct
    cursor = await temp_db.execute("SELECT version FROM schema_meta WHERE id = 1")
    row = await cursor.fetchone()
    await cursor.close()

    assert row is not None
    assert row["version"] == SQLiteSchemaManager.SCHEMA_VERSION


@pytest.mark.asyncio
async def test_schema_manager_artifacts_table_structure(temp_db, schema_manager):
    """Test that artifacts table has correct structure."""
    await schema_manager.apply_schema(temp_db)

    # Get table info
    cursor = await temp_db.execute("PRAGMA table_info(artifacts)")
    columns = {row["name"]: row for row in await cursor.fetchall()}
    await cursor.close()

    # Verify required columns exist
    required_columns = [
        "artifact_id",
        "type",
        "canonical_type",
        "produced_by",
        "payload",
        "version",
        "visibility",
        "tags",
        "correlation_id",
        "partition_key",
        "created_at",
    ]
    for col in required_columns:
        assert col in columns, f"Column {col} should exist in artifacts table"

    # Verify artifact_id is primary key
    assert columns["artifact_id"]["pk"] == 1


@pytest.mark.asyncio
async def test_schema_manager_consumptions_table_structure(temp_db, schema_manager):
    """Test that artifact_consumptions table has correct structure."""
    await schema_manager.apply_schema(temp_db)

    # Get table info
    cursor = await temp_db.execute("PRAGMA table_info(artifact_consumptions)")
    columns = {row["name"]: row for row in await cursor.fetchall()}
    await cursor.close()

    # Verify required columns exist
    required_columns = [
        "artifact_id",
        "consumer",
        "run_id",
        "correlation_id",
        "consumed_at",
    ]
    for col in required_columns:
        assert col in columns, (
            f"Column {col} should exist in artifact_consumptions table"
        )


@pytest.mark.asyncio
async def test_schema_manager_agent_snapshots_table_structure(temp_db, schema_manager):
    """Test that agent_snapshots table has correct structure."""
    await schema_manager.apply_schema(temp_db)

    # Get table info
    cursor = await temp_db.execute("PRAGMA table_info(agent_snapshots)")
    columns = {row["name"]: row for row in await cursor.fetchall()}
    await cursor.close()

    # Verify required columns exist
    required_columns = [
        "agent_name",
        "description",
        "subscriptions",
        "output_types",
        "labels",
        "first_seen",
        "last_seen",
        "signature",
    ]
    for col in required_columns:
        assert col in columns, f"Column {col} should exist in agent_snapshots table"

    # Verify agent_name is primary key
    assert columns["agent_name"]["pk"] == 1
