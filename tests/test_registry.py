"""Tests for type registry."""

import pytest
from pydantic import BaseModel, Field

from flock.registry import RegistryError, flock_type, type_registry


# Test artifact types
@flock_type(name="RegisteredType")
class RegisteredType(BaseModel):
    value: str = Field(description="Value")


@flock_type(name="AnotherRegisteredType")
class AnotherRegisteredType(BaseModel):
    count: int = Field(description="Count")


@pytest.mark.asyncio
async def test_type_registry_resolves_registered_types():
    """Test that type registry resolves registered types."""
    # Arrange - types already registered via @flock_type decorator
    type_name = "RegisteredType"

    # Act
    resolved_model = type_registry.resolve(type_name)

    # Assert
    assert resolved_model is RegisteredType
    assert issubclass(resolved_model, BaseModel)


@pytest.mark.asyncio
async def test_type_registry_raises_on_unknown_type():
    """Test that type registry raises error for unknown types."""
    # Arrange
    unknown_type_name = "CompletelyUnknownType12345"

    # Act & Assert
    with pytest.raises(RegistryError) as exc_info:
        type_registry.resolve(unknown_type_name)

    # Verify the error message mentions the unknown type
    assert unknown_type_name in str(exc_info.value)


@pytest.mark.asyncio
async def test_type_registry_name_for_returns_name():
    """Test that type registry returns name for registered model."""
    # Arrange
    model = RegisteredType

    # Act
    name = type_registry.name_for(model)

    # Assert
    assert name == "RegisteredType"


@pytest.mark.asyncio
async def test_type_registry_registers_new_type():
    """Test that type registry can register a new type."""

    # Arrange
    class NewType(BaseModel):
        data: str = Field(description="Data")

    # Act
    registered_name = type_registry.register(NewType, name="NewlyRegisteredType")

    # Assert
    assert registered_name == "NewlyRegisteredType"
    resolved = type_registry.resolve("NewlyRegisteredType")
    assert resolved is NewType


@pytest.mark.asyncio
async def test_flock_type_decorator_registers_type():
    """Test that @flock_type decorator registers type."""

    # Arrange & Act
    @flock_type(name="DecoratedType")
    class DecoratedType(BaseModel):
        field: str = Field(description="Field")

    # Assert
    assert type_registry.resolve("DecoratedType") is DecoratedType
    assert type_registry.name_for(DecoratedType) == "DecoratedType"
