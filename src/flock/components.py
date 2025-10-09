"""Agent component abstractions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from typing_extensions import Self, TypeVar

from flock.logging.auto_trace import AutoTracedMeta


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from uuid import UUID

    from flock.agent import Agent
    from flock.artifacts import Artifact
    from flock.runtime import Context, EvalInputs, EvalResult

T = TypeVar("T", bound="AgentComponentConfig")


class TracedModelMeta(ModelMetaclass, AutoTracedMeta):
    """Combined metaclass for Pydantic models with auto-tracing.

    This metaclass combines Pydantic's ModelMetaclass with AutoTracedMeta
    to enable both Pydantic functionality and automatic method tracing.
    """


class AgentComponentConfig(BaseModel):
    enabled: bool = True
    model: str | None = None

    @classmethod
    def with_fields(cls, **field_definitions) -> type[Self]:
        """Create a new config class with additional fields.

        This allows dynamic config creation for components with custom configuration needs.

        Example:
            CustomConfig = AgentComponentConfig.with_fields(
                temperature=Field(default=0.7, description="LLM temperature"),
                max_tokens=Field(default=1000, description="Max tokens to generate")
            )
        """
        return create_model(f"Dynamic{cls.__name__}", __base__=cls, **field_definitions)


class AgentComponent(BaseModel, metaclass=TracedModelMeta):
    """Base class for agent components with lifecycle hooks.

    All public methods are automatically traced via OpenTelemetry.
    """

    name: str | None = None
    config: AgentComponentConfig = Field(default_factory=AgentComponentConfig)

    async def on_initialize(
        self, agent: Agent, ctx: Context
    ) -> None:  # pragma: no cover - default no-op
        return None

    async def on_pre_consume(
        self, agent: Agent, ctx: Context, inputs: list[Artifact]
    ) -> list[Artifact]:
        return inputs

    async def on_pre_evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalInputs:
        return inputs

    async def on_post_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        return result

    async def on_post_publish(
        self, agent: Agent, ctx: Context, artifact: Artifact
    ) -> None:  # pragma: no cover - default
        return None

    async def on_error(
        self, agent: Agent, ctx: Context, error: Exception
    ) -> None:  # pragma: no cover - default
        return None

    async def on_terminate(self, agent: Agent, ctx: Context) -> None:  # pragma: no cover - default
        return None


class EngineComponent(AgentComponent):
    """Base class for engine components with built-in conversation context support."""

    # Configuration for context fetching
    enable_context: bool = Field(
        default=True,
        description="Whether to automatically fetch conversation context based on correlation_id",
    )
    context_max_artifacts: int | None = Field(
        default=None,
        description="Maximum number of artifacts to include in context (None = unlimited)",
    )
    context_exclude_types: set[str] = Field(
        default_factory=set, description="Artifact types to exclude from context"
    )

    async def evaluate(self, agent: Agent, ctx: Context, inputs: EvalInputs) -> EvalResult:
        """Override this method in your engine implementation."""
        raise NotImplementedError

    async def fetch_conversation_context(
        self,
        ctx: Context,
        correlation_id: UUID | None = None,
        max_artifacts: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all artifacts with the same correlation_id for conversation context."""
        if not self.enable_context or not ctx:
            return []

        target_correlation_id = correlation_id or getattr(ctx, "correlation_id", None)
        if not target_correlation_id:
            return []

        try:
            all_artifacts = await ctx.board.list()

            context_artifacts = [
                a
                for a in all_artifacts
                if (
                    a.correlation_id == target_correlation_id
                    and a.type not in self.context_exclude_types
                )
            ]

            context_artifacts.sort(key=lambda a: a.created_at)

            max_limit = max_artifacts if max_artifacts is not None else self.context_max_artifacts
            if max_limit is not None and max_limit > 0:
                context_artifacts = context_artifacts[-max_limit:]

            context = []
            i = 0
            for artifact in context_artifacts:
                context.append(
                    {
                        "type": artifact.type,
                        "payload": artifact.payload,
                        "produced_by": artifact.produced_by,
                        "event_number": i,
                        # "created_at": artifact.created_at.isoformat(),
                    }
                )
                i += 1

            return context

        except Exception:
            return []

    async def get_latest_artifact_of_type(
        self,
        ctx: Context,
        artifact_type: str,
        correlation_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Get the most recent artifact of a specific type in the conversation."""
        context = await self.fetch_conversation_context(ctx, correlation_id)
        matching = [a for a in context if a["type"].endswith(artifact_type)]
        return matching[-1] if matching else None

    def should_use_context(self, inputs: EvalInputs) -> bool:
        """Determine if context should be included based on the current inputs."""
        if not self.enable_context:
            return False

        if inputs.artifacts:
            return inputs.artifacts[0].correlation_id is not None

        return False


__all__ = [
    "AgentComponent",
    "AgentComponentConfig",
    "EngineComponent",
]
