"""Common validation utilities."""

from typing import Any, Callable

from pydantic import BaseModel, ValidationError


class ArtifactValidator:
    """Validates artifacts against predicates.

    This utility consolidates artifact validation patterns
    used across agent.py for output validation.
    """

    @staticmethod
    def validate_artifact(
        artifact: Any,
        model_cls: type[BaseModel],
        predicate: Callable[[BaseModel], bool] | None = None,
    ) -> tuple[bool, BaseModel | None, str | None]:
        """
        Validate artifact payload against model and optional predicate.

        Args:
            artifact: Artifact to validate
            model_cls: Pydantic model class
            predicate: Optional validation predicate

        Returns:
            Tuple of (is_valid, model_instance, error_message)

        Example:
            >>> from pydantic import BaseModel
            >>> class MyModel(BaseModel):
            ...     name: str
            ...     age: int
            >>> artifact = type("obj", (), {"payload": {"name": "Alice", "age": 30}})()
            >>> is_valid, model, error = ArtifactValidator.validate_artifact(
            ...     artifact, MyModel, lambda m: m.age >= 18
            ... )
            >>> assert is_valid
            >>> assert model.name == "Alice"
        """
        try:
            # Validate against model
            model_instance = model_cls(**artifact.payload)

            # Apply predicate if provided
            if predicate and not predicate(model_instance):
                return False, model_instance, "Predicate validation failed"

            return True, model_instance, None

        except ValidationError as e:
            return False, None, str(e)
        except Exception as e:
            return False, None, f"Validation error: {e}"
