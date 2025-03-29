"""Base classes and implementations for Flock evaluators."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, Field, create_model

T = TypeVar("T", bound="FlockEvaluatorConfig")


class FlockEvaluatorConfig(BaseModel):
    """Base configuration class for Flock modules.

    This class serves as the base for all module-specific configurations.
    Each module should define its own config class inheriting from this one.

    Example:
        class MemoryModuleConfig(FlockModuleConfig):
            file_path: str = Field(default="memory.json")
            save_after_update: bool = Field(default=True)
    """

    model: str = Field(
        default="", description="The model to use for evaluation"
    )

    @classmethod
    def with_fields(cls: type[T], **field_definitions) -> type[T]:
        """Create a new config class with additional fields."""
        return create_model(
            f"Dynamic{cls.__name__}", __base__=cls, **field_definitions
        )


class FlockEvaluator(ABC, BaseModel):
    """Base class for all evaluators in Flock.

    An evaluator is responsible for taking inputs and producing outputs using
    some evaluation strategy (e.g., DSPy, natural language, etc.).
    """

    name: str = Field(..., description="Unique identifier for this evaluator")
    config: FlockEvaluatorConfig = Field(
        default_factory=FlockEvaluatorConfig,
        description="Evaluator configuration",
    )

    @abstractmethod
    async def evaluate(
        self, agent: Any, inputs: dict[str, Any], tools: list[Any]
    ) -> dict[str, Any]:
        """Evaluate inputs to produce outputs."""
        pass
