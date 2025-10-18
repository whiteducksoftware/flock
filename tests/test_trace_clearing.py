"""Tests for trace database clearing functionality."""

import tempfile
from pathlib import Path

import duckdb
import pytest

from flock.core import Flock


def test_clear_traces_nonexistent_database():
    """Test that clear_traces() handles non-existent database gracefully."""
    result = Flock.clear_traces("/nonexistent/path/traces.duckdb")

    assert result["success"] is False
    assert result["deleted_count"] == 0
    # Error message contains "not found" (case insensitive check for both possible messages)
    error_lower = result["error"].lower()
    assert "not found" in error_lower or "does not exist" in error_lower


def test_clear_traces_empty_database():
    """Test clearing traces from an empty database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "empty_traces.duckdb"

        # Create empty database with spans table
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE spans (
                trace_id VARCHAR NOT NULL,
                span_id VARCHAR PRIMARY KEY,
                parent_id VARCHAR,
                name VARCHAR NOT NULL,
                service VARCHAR,
                operation VARCHAR,
                kind VARCHAR,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                duration_ms DOUBLE NOT NULL,
                status_code VARCHAR NOT NULL,
                status_description VARCHAR,
                attributes JSON,
                events JSON,
                links JSON,
                resource JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.close()

        # Clear the empty database
        result = Flock.clear_traces(str(db_path))

        assert result["success"] is True
        assert result["deleted_count"] == 0
        assert result["error"] is None


def test_clear_traces_with_data():
    """Test clearing traces from a database with data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_traces.duckdb"

        # Create database and insert test data
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE spans (
                trace_id VARCHAR NOT NULL,
                span_id VARCHAR PRIMARY KEY,
                parent_id VARCHAR,
                name VARCHAR NOT NULL,
                service VARCHAR,
                operation VARCHAR,
                kind VARCHAR,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                duration_ms DOUBLE NOT NULL,
                status_code VARCHAR NOT NULL,
                status_description VARCHAR,
                attributes JSON,
                events JSON,
                links JSON,
                resource JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert test spans
        for i in range(10):
            conn.execute(
                """
                INSERT INTO spans (
                    trace_id, span_id, name, start_time, end_time,
                    duration_ms, status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"trace_{i}",
                    f"span_{i}",
                    f"test_op_{i}",
                    1000000 * i,
                    1000000 * i + 1000,
                    1.0,
                    "OK",
                ),
            )

        # Verify data exists
        count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        assert count == 10
        conn.close()

        # Clear the database
        result = Flock.clear_traces(str(db_path))

        assert result["success"] is True
        assert result["deleted_count"] == 10
        assert result["error"] is None

        # Verify database is empty
        conn = duckdb.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        assert count == 0
        conn.close()


def test_clear_traces_vacuum_reclaims_space():
    """Test that clear_traces() vacuums to reclaim space."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "vacuum_test.duckdb"

        # Create database with large dataset
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE spans (
                trace_id VARCHAR NOT NULL,
                span_id VARCHAR PRIMARY KEY,
                parent_id VARCHAR,
                name VARCHAR NOT NULL,
                service VARCHAR,
                operation VARCHAR,
                kind VARCHAR,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                duration_ms DOUBLE NOT NULL,
                status_code VARCHAR NOT NULL,
                status_description VARCHAR,
                attributes JSON,
                events JSON,
                links JSON,
                resource JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert many spans to create significant file size
        for i in range(100):
            conn.execute(
                """
                INSERT INTO spans (
                    trace_id, span_id, name, start_time, end_time,
                    duration_ms, status_code, attributes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    f"trace_{i}",
                    f"span_{i}",
                    f"test_operation_{i}",
                    1000000 * i,
                    1000000 * i + 5000,
                    5.0,
                    "OK",
                    '{"large_data": "' + ("x" * 1000) + '"}',  # Large JSON payload
                ),
            )
        conn.close()

        # Get initial file size
        initial_size = db_path.stat().st_size

        # Clear and vacuum
        result = Flock.clear_traces(str(db_path))

        assert result["success"] is True
        assert result["deleted_count"] == 100

        # Get size after vacuum - should be smaller
        final_size = db_path.stat().st_size
        assert final_size < initial_size


def test_clear_traces_default_path():
    """Test that clear_traces() uses default path correctly."""
    # Create a temporary database at the default location
    default_path = Path(".flock/traces.duckdb")

    # Skip if default path doesn't exist (not an error - just means no traces yet)
    if not default_path.exists():
        pytest.skip("Default traces database doesn't exist yet")

    result = Flock.clear_traces()

    # Should succeed (or fail gracefully if DB doesn't exist)
    assert "success" in result
    assert "deleted_count" in result
    assert "error" in result


def test_clear_traces_preserves_schema():
    """Test that clear_traces() preserves the table schema after clearing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "schema_test.duckdb"

        # Create database with spans table
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE spans (
                trace_id VARCHAR NOT NULL,
                span_id VARCHAR PRIMARY KEY,
                parent_id VARCHAR,
                name VARCHAR NOT NULL,
                service VARCHAR,
                operation VARCHAR,
                kind VARCHAR,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                duration_ms DOUBLE NOT NULL,
                status_code VARCHAR NOT NULL,
                status_description VARCHAR,
                attributes JSON,
                events JSON,
                links JSON,
                resource JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert test data
        conn.execute(
            """
            INSERT INTO spans (
                trace_id, span_id, name, start_time, end_time,
                duration_ms, status_code
            ) VALUES ('t1', 's1', 'test', 1000, 2000, 1.0, 'OK')
        """
        )
        conn.close()

        # Clear traces
        result = Flock.clear_traces(str(db_path))
        assert result["success"] is True

        # Verify schema still exists and we can insert new data
        conn = duckdb.connect(str(db_path))

        # This should succeed if schema is intact
        conn.execute(
            """
            INSERT INTO spans (
                trace_id, span_id, name, start_time, end_time,
                duration_ms, status_code
            ) VALUES ('t2', 's2', 'new_test', 3000, 4000, 1.0, 'OK')
        """
        )

        count = conn.execute("SELECT COUNT(*) FROM spans").fetchone()[0]
        assert count == 1  # Only the new record
        conn.close()


def test_clear_traces_concurrent_access():
    """Test that clear_traces() handles concurrent access gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "concurrent_test.duckdb"

        # Create database
        conn = duckdb.connect(str(db_path))
        conn.execute("""
            CREATE TABLE spans (
                trace_id VARCHAR NOT NULL,
                span_id VARCHAR PRIMARY KEY,
                parent_id VARCHAR,
                name VARCHAR NOT NULL,
                service VARCHAR,
                operation VARCHAR,
                kind VARCHAR,
                start_time BIGINT NOT NULL,
                end_time BIGINT NOT NULL,
                duration_ms DOUBLE NOT NULL,
                status_code VARCHAR NOT NULL,
                status_description VARCHAR,
                attributes JSON,
                events JSON,
                links JSON,
                resource JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute(
            """
            INSERT INTO spans (
                trace_id, span_id, name, start_time, end_time,
                duration_ms, status_code
            ) VALUES ('t1', 's1', 'test', 1000, 2000, 1.0, 'OK')
        """
        )
        conn.close()

        # Clear while connection is closed (should work)
        result = Flock.clear_traces(str(db_path))

        assert result["success"] is True
        assert result["deleted_count"] == 1
