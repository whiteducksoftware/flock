"""Tests for AgentHistoryQueries."""

from datetime import UTC, datetime
from uuid import uuid4

import aiosqlite
import pytest

from flock.core.store import FilterConfig
from flock.storage.sqlite.agent_history_queries import AgentHistoryQueries


@pytest.fixture
async def db_conn():
    """Create an in-memory SQLite connection for testing."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row

    # Create tables
    await conn.execute("""
        CREATE TABLE artifacts (
            artifact_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            canonical_type TEXT NOT NULL,
            produced_by TEXT NOT NULL,
            payload TEXT NOT NULL,
            version INTEGER NOT NULL,
            visibility TEXT NOT NULL,
            tags TEXT,
            correlation_id TEXT,
            partition_key TEXT,
            created_at TEXT NOT NULL
        )
    """)

    await conn.execute("""
        CREATE TABLE artifact_consumptions (
            artifact_id TEXT NOT NULL,
            consumer TEXT NOT NULL,
            consumed_at TEXT NOT NULL,
            FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
        )
    """)

    await conn.commit()

    yield conn

    await conn.close()


@pytest.fixture
def queries():
    """Create agent history queries instance."""
    return AgentHistoryQueries()


@pytest.fixture
def mock_build_filters():
    """Create a mock build_filters function."""

    def build_filters(filters, table_alias=None):
        """Simple filter builder that builds WHERE clause from FilterConfig."""
        clauses = []
        params = []

        # Handle produced_by filter
        if filters.produced_by:
            prefix = f"{table_alias}." if table_alias else ""
            placeholders = ",".join("?" * len(filters.produced_by))
            clauses.append(f"{prefix}produced_by IN ({placeholders})")
            params.extend(filters.produced_by)

        # Build WHERE clause
        if clauses:
            where_clause = " WHERE " + " AND ".join(clauses)
        else:
            where_clause = ""

        return where_clause, params

    return build_filters


async def insert_artifact(
    conn, artifact_id, canonical_type, produced_by, created_at=None
):
    """Helper to insert test artifact."""
    if created_at is None:
        created_at = datetime.now(UTC).isoformat()

    await conn.execute(
        """
        INSERT INTO artifacts (
            artifact_id, type, canonical_type, produced_by, payload,
            version, visibility, created_at
        ) VALUES (?, ?, ?, ?, '{}', 1, '{"kind":"Public"}', ?)
        """,
        (artifact_id, canonical_type, canonical_type, produced_by, created_at),
    )
    await conn.commit()


async def insert_consumption(conn, artifact_id, consumer, consumed_at=None):
    """Helper to insert test consumption."""
    if consumed_at is None:
        consumed_at = datetime.now(UTC).isoformat()

    await conn.execute(
        """
        INSERT INTO artifact_consumptions (artifact_id, consumer, consumed_at)
        VALUES (?, ?, ?)
        """,
        (artifact_id, consumer, consumed_at),
    )
    await conn.commit()


@pytest.mark.asyncio
async def test_query_produced_basic(db_conn, queries, mock_build_filters):
    """Test querying produced artifacts."""
    # Insert artifacts
    await insert_artifact(db_conn, str(uuid4()), "Result", "agent1")
    await insert_artifact(db_conn, str(uuid4()), "Result", "agent1")
    await insert_artifact(db_conn, str(uuid4()), "Message", "agent1")
    await insert_artifact(db_conn, str(uuid4()), "Result", "agent2")

    # Query agent1 production
    filters = FilterConfig()
    result = await queries.query_produced(
        db_conn, "agent1", filters, mock_build_filters
    )

    assert result["Result"] == 2
    assert result["Message"] == 1


@pytest.mark.asyncio
async def test_query_produced_no_results(db_conn, queries, mock_build_filters):
    """Test querying produced when agent produced nothing."""
    await insert_artifact(db_conn, str(uuid4()), "Result", "agent2")

    filters = FilterConfig()
    result = await queries.query_produced(
        db_conn, "agent1", filters, mock_build_filters
    )

    assert result == {}


@pytest.mark.asyncio
async def test_query_produced_excluded_by_filter(db_conn, queries, mock_build_filters):
    """Test query_produced returns empty when agent excluded by filter."""
    filters = FilterConfig(produced_by={"agent2"})  # Only agent2
    result = await queries.query_produced(
        db_conn, "agent1", filters, mock_build_filters
    )

    assert result == {}


@pytest.mark.asyncio
async def test_query_consumed_basic(db_conn, queries, mock_build_filters):
    """Test querying consumed artifacts."""
    # Insert artifacts
    artifact1_id = str(uuid4())
    artifact2_id = str(uuid4())
    artifact3_id = str(uuid4())

    await insert_artifact(db_conn, artifact1_id, "Result", "agent2")
    await insert_artifact(db_conn, artifact2_id, "Result", "agent2")
    await insert_artifact(db_conn, artifact3_id, "Message", "agent2")

    # Insert consumptions
    await insert_consumption(db_conn, artifact1_id, "agent1")
    await insert_consumption(db_conn, artifact2_id, "agent1")
    await insert_consumption(db_conn, artifact3_id, "agent1")

    # Query agent1 consumption
    filters = FilterConfig()
    result = await queries.query_consumed(
        db_conn, "agent1", filters, mock_build_filters
    )

    assert result["Result"] == 2
    assert result["Message"] == 1


@pytest.mark.asyncio
async def test_query_consumed_no_results(db_conn, queries, mock_build_filters):
    """Test querying consumed when agent consumed nothing."""
    artifact_id = str(uuid4())
    await insert_artifact(db_conn, artifact_id, "Result", "agent2")
    await insert_consumption(db_conn, artifact_id, "agent2")

    filters = FilterConfig()
    result = await queries.query_consumed(
        db_conn, "agent1", filters, mock_build_filters
    )

    assert result == {}


@pytest.mark.asyncio
async def test_query_consumed_multiple_same_type(db_conn, queries, mock_build_filters):
    """Test querying consumed with multiple artifacts of same type."""
    # Create 5 Results consumed by agent1
    for _ in range(5):
        artifact_id = str(uuid4())
        await insert_artifact(db_conn, artifact_id, "Result", "agent2")
        await insert_consumption(db_conn, artifact_id, "agent1")

    filters = FilterConfig()
    result = await queries.query_consumed(
        db_conn, "agent1", filters, mock_build_filters
    )

    assert result["Result"] == 5


def test_derive_produced_filter(queries):
    """Test deriving filter for specific agent production."""
    base_filters = FilterConfig(
        type_names={"Result", "Message"},
        correlation_id="corr-123",
        tags={"alpha", "beta"},
        visibility={"Public"},
        start=datetime(2025, 1, 1, tzinfo=UTC),
        end=datetime(2025, 12, 31, tzinfo=UTC),
    )

    derived = queries._derive_produced_filter(base_filters, "agent1")

    # Should have agent as producer
    assert derived.produced_by == {"agent1"}

    # Should preserve other filters
    assert derived.type_names == {"Result", "Message"}
    assert derived.correlation_id == "corr-123"
    assert derived.tags == {"alpha", "beta"}
    assert derived.visibility == {"Public"}
    assert derived.start == datetime(2025, 1, 1, tzinfo=UTC)
    assert derived.end == datetime(2025, 12, 31, tzinfo=UTC)


def test_derive_produced_filter_none_values(queries):
    """Test deriving filter when base has None values."""
    base_filters = FilterConfig()

    derived = queries._derive_produced_filter(base_filters, "agent1")

    assert derived.produced_by == {"agent1"}
    assert derived.type_names is None
    assert derived.correlation_id is None
    assert derived.tags is None
    assert derived.visibility is None
    assert derived.start is None
    assert derived.end is None


def test_derive_produced_filter_preserves_sets(queries):
    """Test that derived filter creates new set instances."""
    base_filters = FilterConfig(
        type_names={"Result"},
        tags={"tag1"},
        visibility={"Public"},
    )

    derived = queries._derive_produced_filter(base_filters, "agent1")

    # Should be new instances, not same references
    assert derived.type_names is not base_filters.type_names
    assert derived.tags is not base_filters.tags
    assert derived.visibility is not base_filters.visibility

    # But should have same values
    assert derived.type_names == base_filters.type_names
    assert derived.tags == base_filters.tags
    assert derived.visibility == base_filters.visibility


@pytest.mark.asyncio
async def test_query_produced_groups_by_canonical_type(
    db_conn, queries, mock_build_filters
):
    """Test that query_produced groups by canonical_type correctly."""
    # Insert multiple of same canonical type
    for i in range(3):
        await insert_artifact(db_conn, str(uuid4()), "Result", "agent1")

    for i in range(2):
        await insert_artifact(db_conn, str(uuid4()), "Message", "agent1")

    filters = FilterConfig()
    result = await queries.query_produced(
        db_conn, "agent1", filters, mock_build_filters
    )

    # Should group by canonical_type
    assert len(result) == 2
    assert result["Result"] == 3
    assert result["Message"] == 2


@pytest.mark.asyncio
async def test_query_consumed_groups_by_canonical_type(
    db_conn, queries, mock_build_filters
):
    """Test that query_consumed groups by canonical_type correctly."""
    # Create artifacts and consumptions
    for i in range(4):
        artifact_id = str(uuid4())
        await insert_artifact(db_conn, artifact_id, "Result", "agent2")
        await insert_consumption(db_conn, artifact_id, "agent1")

    for i in range(3):
        artifact_id = str(uuid4())
        await insert_artifact(db_conn, artifact_id, "Error", "agent2")
        await insert_consumption(db_conn, artifact_id, "agent1")

    filters = FilterConfig()
    result = await queries.query_consumed(
        db_conn, "agent1", filters, mock_build_filters
    )

    # Should group by canonical_type
    assert len(result) == 2
    assert result["Result"] == 4
    assert result["Error"] == 3
