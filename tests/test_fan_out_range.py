"""Tests for dynamic fan-out core types and normalization."""

from __future__ import annotations

import pytest

from flock.core.fan_out import FanOutRange, normalize_fan_out


def test_normalize_fan_out_with_int_returns_fixed_range():
    """normalize_fan_out(int>1) returns fixed FanOutRange."""
    result = normalize_fan_out(5)
    assert isinstance(result, FanOutRange)
    assert result.min == 5
    assert result.max == 5
    assert result.is_fixed() is True
    assert result.fixed_count() == 5


def test_normalize_fan_out_one_returns_none():
    """normalize_fan_out(1) returns None (same as default)."""
    result = normalize_fan_out(1)
    assert result is None


def test_normalize_fan_out_with_tuple_returns_range():
    """normalize_fan_out(tuple) returns FanOutRange with min/max."""
    result = normalize_fan_out((3, 10))
    assert isinstance(result, FanOutRange)
    assert result.min == 3
    assert result.max == 10
    assert result.is_fixed() is False
    assert result.fixed_count() is None


def test_normalize_fan_out_with_fan_out_range_passthrough():
    """normalize_fan_out(FanOutRange) returns same instance."""
    spec = FanOutRange(min=2, max=8)
    result = normalize_fan_out(spec)
    assert result is spec


@pytest.mark.parametrize("value", [0, -1])
def test_normalize_fan_out_with_invalid_min_raises(value: int):
    """normalize_fan_out enforces min >= 1."""
    with pytest.raises(ValueError) as exc:
        normalize_fan_out((value, 10))
    assert "fan_out min must be >= 1" in str(exc.value)


def test_normalize_fan_out_with_max_less_than_min_raises():
    """normalize_fan_out enforces max >= min."""
    with pytest.raises(ValueError) as exc:
        normalize_fan_out((10, 5))
    message = str(exc.value)
    assert "fan_out max" in message and "must be >= min" in message


@pytest.mark.parametrize("spec", ["5", [1, 2], range(3, 11)])
def test_normalize_fan_out_with_invalid_type_raises_type_error(spec):
    """normalize_fan_out rejects unsupported spec types."""
    with pytest.raises(TypeError) as exc:
        normalize_fan_out(spec)  # type: ignore[arg-type]
    message = str(exc.value)
    assert "fan_out must be int, tuple[int, int], or FanOutRange" in message


def test_fan_out_range_is_fixed_and_fixed_count_logic():
    """FanOutRange.is_fixed and fixed_count behave as expected."""
    fixed = FanOutRange(min=5, max=5)
    dynamic = FanOutRange(min=3, max=10)

    assert fixed.is_fixed() is True
    assert fixed.fixed_count() == 5

    assert dynamic.is_fixed() is False
    assert dynamic.fixed_count() is None


def test_fan_out_range_invalid_min_raises_value_error():
    """FanOutRange enforces min >= 1."""
    with pytest.raises(ValueError) as exc:
        FanOutRange(min=0, max=1)
    assert "fan_out min must be >= 1" in str(exc.value)


def test_fan_out_range_max_less_than_min_raises_value_error():
    """FanOutRange enforces max >= min."""
    with pytest.raises(ValueError) as exc:
        FanOutRange(min=5, max=3)
    message = str(exc.value)
    assert "fan_out max" in message and "must be >= min" in message
