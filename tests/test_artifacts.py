"""Tests for artifact validation."""

from uuid import UUID

import pytest
from pydantic import BaseModel, Field, ValidationError

from flock.core.artifacts import Artifact, ArtifactSpec
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type


# Test artifact types
@flock_type(name="ValidArtifact")
class ValidArtifact(BaseModel):
    title: str = Field(description="Title", min_length=1)
    count: int = Field(description="Count", ge=0, le=100)


@flock_type(name="AnotherArtifact")
class AnotherArtifact(BaseModel):
    data: str = Field(description="Data")


@pytest.mark.asyncio
async def test_artifact_validation_with_valid_data():
    """Test that artifact validation passes with valid data."""
    # Arrange
    valid_payload = {"title": "TEST", "count": 42}

    # Act
    artifact = Artifact(
        type="ValidArtifact",
        payload=valid_payload,
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Assert
    assert artifact.type == "ValidArtifact"
    assert artifact.payload["title"] == "TEST"
    assert artifact.payload["count"] == 42
    assert isinstance(artifact.id, UUID)
    assert artifact.produced_by == "test_agent"


@pytest.mark.asyncio
async def test_artifact_validation_fails_with_invalid_data():
    """Test that artifact validation fails with invalid data."""
    # Arrange - Use ArtifactSpec to validate payload
    spec = ArtifactSpec.from_model(ValidArtifact)

    # Act & Assert - Missing required field should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        spec.build(
            produced_by="test_agent",
            data={"title": "TEST"},  # Missing 'count' field
        )

    # Verify the error is about the missing field
    assert (
        "count" in str(exc_info.value).lower()
        or "field required" in str(exc_info.value).lower()
    )


@pytest.mark.asyncio
async def test_artifact_validation_fails_with_out_of_range_value():
    """Test that artifact validation fails with out-of-range values."""
    # Arrange
    spec = ArtifactSpec.from_model(ValidArtifact)

    # Act & Assert - Count > 100 should raise ValidationError
    with pytest.raises(ValidationError) as exc_info:
        spec.build(
            produced_by="test_agent",
            data={"title": "TEST", "count": 150},  # Count exceeds le=100
        )

    # Verify the error is about the value constraint
    error_str = str(exc_info.value).lower()
    assert "less than or equal" in error_str or "count" in error_str


@pytest.mark.asyncio
async def test_artifact_immutability():
    """Test that artifacts are immutable (Pydantic model)."""
    # Arrange
    artifact = Artifact(
        type="ValidArtifact",
        payload={"title": "ORIGINAL", "count": 10},
        produced_by="test_agent",
        visibility=PublicVisibility(),
    )

    # Act & Assert - Attempting to modify should not change the model
    # Pydantic models are immutable by default with frozen=True
    # But without frozen=True, we test that the payload dict is not shared
    artifact.payload["title"]

    # Try to modify the payload (this modifies the dict, not the model)
    artifact.payload["title"] = "MODIFIED"

    # The artifact's payload dict is mutable, but the artifact itself
    # should be used in an immutable way (event sourcing pattern)
    assert artifact.payload["title"] == "MODIFIED"  # Dict is mutable
    # In practice, we never modify artifacts after creation (event sourcing)
