"""Runtime envelopes exchanged between orchestrator and components."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from flock.artifacts import Artifact


class EvalInputs(BaseModel):
    artifacts: list[Artifact] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

    def first_as(self, model_cls: type[BaseModel]) -> BaseModel | None:
        """Extract first artifact as model instance.

        Convenience method to deserialize the first artifact's payload
        into a typed Pydantic model.

        Args:
            model_cls: Pydantic model class to deserialize to

        Returns:
            Model instance or None if no artifacts

        Example:
            >>> class TaskProcessor(EngineComponent):
            ...     async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            ...         task = inputs.first_as(Task)
            ...         if not task:
            ...             return EvalResult.empty()
            ...         # Process task...
        """
        if not self.artifacts:
            return None
        return model_cls(**self.artifacts[0].payload)

    def all_as(self, model_cls: type[BaseModel]) -> list[BaseModel]:
        """Extract all artifacts as model instances.

        Args:
            model_cls: Pydantic model class to deserialize to

        Returns:
            List of model instances (empty if no artifacts)

        Example:
            >>> tasks = inputs.all_as(Task)
            >>> for task in tasks:
            ...     # Process each task
        """
        return [model_cls(**artifact.payload) for artifact in self.artifacts]


class EvalResult(BaseModel):
    artifacts: list[Artifact] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)

    @classmethod
    def from_object(
        cls,
        obj: BaseModel,
        *,
        agent: Any,
        state: dict | None = None,
        metrics: dict | None = None,
        errors: list[str] | None = None,
    ) -> EvalResult:
        """Create EvalResult from a single model instance.

        Automatically constructs an Artifact from the model instance,
        handling type registry lookup and payload serialization.

        Args:
            obj: Pydantic model instance to publish as artifact
            agent: Agent producing the artifact (for produced_by field)
            state: Optional state dict to include in result
            metrics: Optional metrics dict (e.g., {"confidence": 0.95})
            errors: Optional list of error messages

        Returns:
            EvalResult with single artifact

        Example:
            >>> class TaskProcessor(EngineComponent):
            ...     async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            ...         task = inputs.first_as(Task)
            ...         processed = Task(name=f"Done: {task.name}", priority=task.priority)
            ...         return EvalResult.from_object(processed, agent=agent)
        """
        from flock.artifacts import Artifact
        from flock.registry import type_registry

        type_name = type_registry.name_for(type(obj))
        artifact = Artifact(
            type=type_name,
            payload=obj.model_dump(),
            produced_by=agent.name,
        )

        return cls(
            artifacts=[artifact],
            state=state or {},
            metrics=metrics or {},
            errors=errors or [],
        )

    @classmethod
    def from_objects(
        cls,
        *objs: BaseModel,
        agent: Any,
        state: dict | None = None,
        metrics: dict | None = None,
        errors: list[str] | None = None,
    ) -> EvalResult:
        """Create EvalResult from multiple model instances.

        Automatically constructs Artifacts from all model instances.
        Useful when an agent produces multiple outputs in one evaluation.

        Args:
            *objs: Pydantic model instances to publish as artifacts
            agent: Agent producing the artifacts
            state: Optional state dict
            metrics: Optional metrics dict
            errors: Optional list of error messages

        Returns:
            EvalResult with multiple artifacts

        Example:
            >>> class MovieEngine(EngineComponent):
            ...     async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            ...         idea = inputs.first_as(Idea)
            ...         movie = Movie(title=idea.topic.upper(), runtime=240, synopsis="...")
            ...         tagline = Tagline(line="Don't miss it!")
            ...         return EvalResult.from_objects(
            ...             movie, tagline,
            ...             agent=agent,
            ...             metrics={"confidence": 0.9}
            ...         )
        """
        from flock.artifacts import Artifact
        from flock.registry import type_registry

        artifacts = []
        for obj in objs:
            type_name = type_registry.name_for(type(obj))
            artifact = Artifact(
                type=type_name,
                payload=obj.model_dump(),
                produced_by=agent.name,
            )
            artifacts.append(artifact)

        return cls(
            artifacts=artifacts,
            state=state or {},
            metrics=metrics or {},
            errors=errors or [],
        )

    @classmethod
    def empty(
        cls,
        state: dict | None = None,
        metrics: dict | None = None,
        errors: list[str] | None = None,
    ) -> EvalResult:
        """Return empty result with no artifacts.

        Useful when:
        - Conditions aren't met for processing
        - Agent only updates state without producing output
        - Processing failed (use errors parameter)

        Args:
            state: Optional state dict
            metrics: Optional metrics dict
            errors: Optional list of error messages

        Returns:
            EvalResult with empty artifacts list

        Example:
            >>> class ConditionalProcessor(EngineComponent):
            ...     async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            ...         task = inputs.first_as(Task)
            ...         if task.priority < 3:
            ...             return EvalResult.empty()  # Skip low priority
            ...         # Process high priority tasks...

            >>> # With error reporting
            >>> return EvalResult.empty(errors=["Validation failed: missing field"])
        """
        return cls(
            artifacts=[],
            state=state or {},
            metrics=metrics or {},
            errors=errors or [],
        )

    @classmethod
    def with_state(
        cls,
        state: dict,
        *,
        metrics: dict | None = None,
        errors: list[str] | None = None,
    ) -> EvalResult:
        """Return result with only state updates (no artifacts).

        Useful for agents that only update context without producing outputs,
        such as validation or enrichment agents.

        Args:
            state: State dict to pass to downstream agents
            metrics: Optional metrics dict
            errors: Optional list of error messages

        Returns:
            EvalResult with state but no artifacts

        Example:
            >>> class ValidationAgent(EngineComponent):
            ...     async def evaluate(self, agent, ctx, inputs: EvalInputs) -> EvalResult:
            ...         task = inputs.first_as(Task)
            ...         is_valid = task.priority >= 1
            ...         return EvalResult.with_state(
            ...             {"validation_passed": is_valid, "validator": "priority_check"}
            ...         )
        """
        return cls(
            artifacts=[],
            state=state,
            metrics=metrics or {},
            errors=errors or [],
        )


class Context(BaseModel):
    board: Any
    orchestrator: Any
    correlation_id: UUID | None = None  # NEW!
    task_id: str
    state: dict[str, Any] = Field(default_factory=dict)

    def get_variable(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)


__all__ = [
    "Context",
    "EvalInputs",
    "EvalResult",
]
