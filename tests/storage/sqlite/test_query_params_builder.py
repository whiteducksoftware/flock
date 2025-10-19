"""Tests for QueryParamsBuilder."""

import pytest

from flock.storage.sqlite.query_params_builder import QueryParamsBuilder


@pytest.fixture
def builder():
    """Create query params builder instance."""
    return QueryParamsBuilder()


def test_build_pagination_no_limit_no_offset(builder):
    """Test pagination with no limit and no offset."""
    base_params = ["param1", "param2"]
    clause, params = builder.build_pagination_params(base_params, limit=0, offset=0)

    assert clause == ""
    assert params == ("param1", "param2")


def test_build_pagination_no_limit_with_offset(builder):
    """Test pagination with no limit but with offset."""
    base_params = ["param1"]
    clause, params = builder.build_pagination_params(base_params, limit=0, offset=10)

    assert clause == " LIMIT -1 OFFSET ?"
    assert params == ("param1", 10)


def test_build_pagination_with_limit_no_offset(builder):
    """Test pagination with limit but no offset."""
    base_params = ["param1"]
    clause, params = builder.build_pagination_params(base_params, limit=50, offset=0)

    assert clause == " LIMIT ? OFFSET ?"
    assert params == ("param1", 50, 0)


def test_build_pagination_with_limit_and_offset(builder):
    """Test pagination with both limit and offset."""
    base_params = []
    clause, params = builder.build_pagination_params(base_params, limit=25, offset=100)

    assert clause == " LIMIT ? OFFSET ?"
    assert params == (25, 100)


def test_build_pagination_negative_limit(builder):
    """Test pagination with negative limit (treated as no limit)."""
    base_params = ["param1"]
    clause, params = builder.build_pagination_params(base_params, limit=-1, offset=0)

    assert clause == ""
    assert params == ("param1",)


def test_build_pagination_negative_offset_normalized(builder):
    """Test pagination with negative offset (normalized to 0)."""
    base_params = []
    clause, params = builder.build_pagination_params(base_params, limit=10, offset=-5)

    assert clause == " LIMIT ? OFFSET ?"
    assert params == (10, 0)  # Offset normalized to 0


def test_build_unlimited_params_no_offset(builder):
    """Test _build_unlimited_params with no offset."""
    base_params = ["a", "b"]
    clause, params = builder._build_unlimited_params(base_params, offset=0)

    assert clause == ""
    assert params == ("a", "b")


def test_build_unlimited_params_with_offset(builder):
    """Test _build_unlimited_params with offset."""
    base_params = ["x"]
    clause, params = builder._build_unlimited_params(base_params, offset=20)

    assert clause == " LIMIT -1 OFFSET ?"
    assert params == ("x", 20)


def test_build_limited_params_standard(builder):
    """Test _build_limited_params with standard values."""
    base_params = ["p1", "p2"]
    clause, params = builder._build_limited_params(base_params, limit=100, offset=50)

    assert clause == " LIMIT ? OFFSET ?"
    assert params == ("p1", "p2", 100, 50)


def test_build_limited_params_zero_offset(builder):
    """Test _build_limited_params with zero offset."""
    base_params = []
    clause, params = builder._build_limited_params(base_params, limit=5, offset=0)

    assert clause == " LIMIT ? OFFSET ?"
    assert params == (5, 0)


def test_build_pagination_empty_base_params(builder):
    """Test pagination with empty base params."""
    clause, params = builder.build_pagination_params([], limit=10, offset=5)

    assert clause == " LIMIT ? OFFSET ?"
    assert params == (10, 5)


def test_build_pagination_large_values(builder):
    """Test pagination with large limit and offset values."""
    base_params = ["param"]
    clause, params = builder.build_pagination_params(
        base_params, limit=10000, offset=5000
    )

    assert clause == " LIMIT ? OFFSET ?"
    assert params == ("param", 10000, 5000)


def test_build_pagination_clauses_have_space_prefix(builder):
    """Test that pagination clauses start with space for SQL concatenation."""
    base_params = []

    # With limit
    clause1, _ = builder.build_pagination_params(base_params, limit=10, offset=0)
    assert clause1.startswith(" ")

    # Without limit but with offset
    clause2, _ = builder.build_pagination_params(base_params, limit=0, offset=10)
    assert clause2.startswith(" ")

    # No pagination
    clause3, _ = builder.build_pagination_params(base_params, limit=0, offset=0)
    assert clause3 == ""  # No space needed


def test_build_pagination_preserves_param_order(builder):
    """Test that base params come before pagination params."""
    base_params = ["first", "second", "third"]
    clause, params = builder.build_pagination_params(base_params, limit=5, offset=10)

    # Should preserve order: base params, then limit, then offset
    assert params == ("first", "second", "third", 5, 10)
