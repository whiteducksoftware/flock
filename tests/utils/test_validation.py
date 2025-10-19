"""Tests for ArtifactValidator utility."""

import pytest
from pydantic import BaseModel, Field, ValidationError

from flock.utils.validation import ArtifactValidator


class SimpleModel(BaseModel):
    """Simple test model."""

    name: str
    age: int


class ComplexModel(BaseModel):
    """Complex test model with validation."""

    id: int = Field(gt=0)
    email: str
    score: float = Field(ge=0, le=100)


class TestArtifactValidator:
    """Tests for ArtifactValidator."""

    def test_validate_artifact_success(self):
        """Test successful artifact validation."""

        class MockArtifact:
            payload = {"name": "Alice", "age": 30}

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel
        )

        assert is_valid is True
        assert model is not None
        assert model.name == "Alice"
        assert model.age == 30
        assert error is None

    def test_validate_artifact_with_predicate_success(self):
        """Test validation with predicate that passes."""

        class MockArtifact:
            payload = {"name": "Alice", "age": 30}

        artifact = MockArtifact()

        # Predicate: age must be >= 18
        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel, lambda m: m.age >= 18
        )

        assert is_valid is True
        assert model is not None
        assert error is None

    def test_validate_artifact_with_predicate_failure(self):
        """Test validation with predicate that fails."""

        class MockArtifact:
            payload = {"name": "Bob", "age": 15}

        artifact = MockArtifact()

        # Predicate: age must be >= 18
        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel, lambda m: m.age >= 18
        )

        assert is_valid is False
        assert model is not None  # Model is created but predicate fails
        assert error == "Predicate validation failed"

    def test_validate_artifact_missing_field(self):
        """Test validation with missing required field."""

        class MockArtifact:
            payload = {"name": "Charlie"}  # Missing 'age'

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel
        )

        assert is_valid is False
        assert model is None
        assert error is not None
        assert "age" in error.lower() or "field required" in error.lower()

    def test_validate_artifact_wrong_type(self):
        """Test validation with wrong field type."""

        class MockArtifact:
            payload = {"name": "David", "age": "not-a-number"}

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel
        )

        assert is_valid is False
        assert model is None
        assert error is not None

    def test_validate_artifact_complex_model(self):
        """Test validation with complex model constraints."""

        class MockArtifact:
            payload = {"id": 1, "email": "test@example.com", "score": 95.5}

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, ComplexModel
        )

        assert is_valid is True
        assert model is not None
        assert model.id == 1
        assert model.score == 95.5

    def test_validate_artifact_complex_model_constraint_violation(self):
        """Test validation with constraint violation."""

        class MockArtifact:
            payload = {"id": -1, "email": "test@example.com", "score": 50}

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, ComplexModel
        )

        assert is_valid is False
        assert model is None
        assert error is not None

    def test_validate_artifact_extra_fields_ignored(self):
        """Test that extra fields are handled according to model config."""

        class MockArtifact:
            payload = {
                "name": "Eve",
                "age": 25,
                "extra_field": "ignored",
            }

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel
        )

        # Pydantic ignores extra fields by default
        assert is_valid is True
        assert model is not None
        assert model.name == "Eve"

    def test_validate_artifact_with_none_predicate(self):
        """Test validation with None predicate (should skip predicate check)."""

        class MockArtifact:
            payload = {"name": "Frank", "age": 40}

        artifact = MockArtifact()

        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel, None
        )

        assert is_valid is True
        assert model is not None
        assert error is None

    def test_validate_artifact_predicate_with_exception(self):
        """Test predicate that raises exception."""

        class MockArtifact:
            payload = {"name": "Grace", "age": 28}

        artifact = MockArtifact()

        def failing_predicate(m):
            raise RuntimeError("Predicate error")

        # Should catch exception and return validation failure
        is_valid, model, error = ArtifactValidator.validate_artifact(
            artifact, SimpleModel, failing_predicate
        )

        assert is_valid is False
        assert error is not None
