"""Tests for TypeResolutionHelper utility."""

import pytest

from flock.registry import TypeRegistry
from flock.utils.type_resolution import TypeResolutionHelper


def test_safe_resolve_existing_type():
    """Test resolving existing type returns canonical name."""
    from pydantic import BaseModel

    registry = TypeRegistry()

    # Register a type (TypeRegistry requires Pydantic models)
    class MyType(BaseModel):
        value: str

    canonical_name = registry.register(MyType, name="test_module.MyType")

    # Resolve should return canonical name
    result = TypeResolutionHelper.safe_resolve(registry, "test_module.MyType")
    assert result == canonical_name
    assert result == "test_module.MyType"


def test_safe_resolve_missing_type():
    """Test resolving missing type returns original name."""
    registry = TypeRegistry()

    # Try to resolve unknown type
    result = TypeResolutionHelper.safe_resolve(registry, "UnknownType")

    # Should return original name without raising error
    assert result == "UnknownType"


def test_safe_resolve_handles_key_error_gracefully():
    """Test that safe_resolve doesn't raise KeyError."""
    registry = TypeRegistry()

    # This should not raise KeyError
    try:
        result = TypeResolutionHelper.safe_resolve(registry, "NonExistent")
        assert result == "NonExistent"
    except KeyError:
        pytest.fail("safe_resolve should not raise KeyError")


def test_safe_resolve_with_empty_registry():
    """Test safe_resolve works with empty registry."""
    registry = TypeRegistry()

    result = TypeResolutionHelper.safe_resolve(registry, "AnyType")
    assert result == "AnyType"
