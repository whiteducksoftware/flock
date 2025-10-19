"""Tests for SQLite query builder."""

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel

from flock.core.store import FilterConfig
from flock.registry import flock_type
from flock.storage.sqlite.query_builder import SQLiteQueryBuilder


@flock_type(name="TestTypeA")
class TestTypeA(BaseModel):
    """Test type A for query builder tests."""

    data: str


@pytest.fixture
def builder():
    """Create query builder instance."""
    return SQLiteQueryBuilder()


def test_build_filters_empty(builder):
    """Test building filters with no constraints."""
    filters = FilterConfig()
    where_clause, params = builder.build_filters(filters)

    assert where_clause == ""
    assert params == []


def test_build_filters_type_names(builder):
    """Test building filters with type names."""
    # Use registered type
    filters = FilterConfig(type_names={"TestTypeA"})
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "canonical_type IN" in where_clause
    assert len(params) == 1
    # Should resolve type name
    assert "TestTypeA" in params[0]


def test_build_filters_produced_by(builder):
    """Test building filters with producer filter."""
    filters = FilterConfig(produced_by={"agent1", "agent2"})
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "produced_by IN" in where_clause
    assert len(params) == 2
    assert "agent1" in params
    assert "agent2" in params


def test_build_filters_correlation_id(builder):
    """Test building filters with correlation ID."""
    filters = FilterConfig(correlation_id="corr-123")
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "correlation_id = ?" in where_clause
    assert params == ["corr-123"]


def test_build_filters_visibility(builder):
    """Test building filters with visibility filter."""
    filters = FilterConfig(visibility={"Public", "Private"})
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "json_extract" in where_clause
    assert "visibility" in where_clause
    assert len(params) == 2


def test_build_filters_date_range(builder):
    """Test building filters with date range."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    end = datetime(2025, 12, 31, tzinfo=UTC)

    filters = FilterConfig(start=start, end=end)
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "created_at >= ?" in where_clause
    assert "created_at <= ?" in where_clause
    assert len(params) == 2
    assert params[0] == start.isoformat()
    assert params[1] == end.isoformat()


def test_build_filters_tags(builder):
    """Test building filters with tags."""
    filters = FilterConfig(tags={"alpha", "beta"})
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "json_each" in where_clause
    assert len(params) == 2  # One param per tag
    assert "alpha" in params
    assert "beta" in params


def test_build_filters_combined(builder):
    """Test building filters with multiple constraints."""
    filters = FilterConfig(
        type_names={"TestTypeA"},
        produced_by={"agent1"},
        correlation_id="corr-456",
    )
    where_clause, params = builder.build_filters(filters)

    assert "WHERE" in where_clause
    assert "canonical_type IN" in where_clause
    assert "produced_by IN" in where_clause
    assert "correlation_id = ?" in where_clause
    # Should use AND to combine conditions
    assert where_clause.count(" AND ") == 2
    assert len(params) == 3  # One type, one producer, one correlation_id


def test_build_filters_with_table_alias(builder):
    """Test building filters with table alias."""
    filters = FilterConfig(type_names={"TestTypeA"})
    where_clause, params = builder.build_filters(filters, table_alias="a")

    assert "WHERE" in where_clause
    assert "a.canonical_type IN" in where_clause
    assert len(params) == 1


def test_build_filters_parameterized(builder):
    """Test that all values are parameterized (no SQL injection)."""
    # Try to inject SQL via various fields (using actual registered type for type_names)
    # For produced_by and correlation_id, any string is acceptable
    filters = FilterConfig(
        produced_by={"agent1'; DELETE FROM artifacts; --"},
        correlation_id="corr'; UPDATE artifacts SET type='hacked'; --",
    )
    where_clause, params = builder.build_filters(filters)

    # WHERE clause should only contain placeholders (?)
    # Count ? placeholders
    placeholder_count = where_clause.count("?")
    # Should have 2 placeholders (one for producer, one for correlation)
    assert placeholder_count == 2

    # All values should be in params list, not in WHERE clause
    assert "agent1'; DELETE FROM artifacts; --" in params
    assert "corr'; UPDATE artifacts SET type='hacked'; --" in params

    # The SQL injection strings should only appear in params, not in WHERE structure
    # The WHERE clause itself should be safe
    assert "DELETE" not in where_clause
    assert "UPDATE" not in where_clause
    assert "DROP" not in where_clause
