"""Agent component base classes and configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from typing_extensions import TypeVar

from flock.logging.auto_trace import AutoTracedMeta


if TYPE_CHECKING:  # pragma: no cover - type checking only
    from flock.agent import Agent, OutputGroup
    from flock.core.artifacts import Artifact
    from flock.utils.runtime import Context, EvalInputs, EvalResult

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
    priority: int = Field(
        default=0,
        description="Execution priority (lower numbers run earlier; default preserves add order).",
    )

    async def on_initialize(
        self, agent: Agent, ctx: Context
    ) -> None:  # pragma: no cover - default no-op
        return None

    async def on_pre_consume(
        self, agent: Agent, ctx: Context, inputs: list[Artifact]
    ) -> list[Artifact]:
        return inputs

    async def on_pre_evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs
    ) -> EvalInputs:
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

    async def on_terminate(
        self, agent: Agent, ctx: Context
    ) -> None:  # pragma: no cover - default
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

    async def evaluate(
        self, agent: Agent, ctx: Context, inputs: EvalInputs, output_group: OutputGroup
    ) -> EvalResult:
        """Universal evaluation method with auto-detection of batch and fan-out modes.

        This single method handles ALL evaluation scenarios:
        - Single artifact → single output
        - Batch processing (ctx.is_batch=True) → list[Type] signatures
        - Fan-out (output_group.outputs[*].count > 1) → multiple artifacts
        - Multi-output (len(output_group.outputs) > 1) → multiple types

        Auto-detection happens automatically:
        - Batching: Detected via ctx.is_batch flag
        - Fan-out: Detected via output_group.outputs[*].count
        - Multi-input: Detected via len(inputs.artifacts)
        - Multi-output: Detected via len(output_group.outputs)

        Args:
            agent: Agent instance executing this engine
            ctx: Execution context (check ctx.is_batch for batch mode)
            inputs: EvalInputs with input artifacts
            output_group: OutputGroup defining what artifacts to produce
                         (inspect outputs[*].count for fan-out detection)

        Returns:
            EvalResult with artifacts matching output_group specifications

        Implementation Guide:
            >>> async def evaluate(self, agent, ctx, inputs, output_group):
            ...     # Auto-detect batching from context
            ...     batched = bool(getattr(ctx, "is_batch", False))
            ...
            ...     # Fan-out is auto-detected from output_group
            ...     # Your signature building should check:
            ...     # - output_group.outputs[i].count > 1 for fan-out
            ...     # - len(output_group.outputs) > 1 for multi-output
            ...
            ...     # Build signature adapting to all modes
            ...     signature = self._build_signature(inputs, output_group, batched)
            ...     result = await self._execute(signature, inputs)
            ...     return EvalResult.from_objects(*result, agent=agent)
        """
        raise NotImplementedError

    def get_conversation_context(
        self,
        ctx: Context,
        max_artifacts: int | None = None,
    ) -> list[Artifact]:
        """Get conversation context from Context (read-only helper).

        Phase 8 Security Fix: This method now simply reads pre-filtered artifacts from
        Context. The orchestrator evaluates context BEFORE creating Context, so engines
        can no longer query arbitrary data.

        REMOVED METHODS (Security Fix):
        - fetch_conversation_context() - REMOVED (engines can't query anymore)
        - get_latest_artifact_of_type() - REMOVED (engines can't query anymore)

        Migration Guide:
            Old (vulnerable): context = await self.fetch_conversation_context(ctx, agent, exclude_ids)
            New (secure): context = ctx.artifacts  # Pre-filtered by orchestrator!

        Args:
            ctx: Execution context with pre-filtered artifacts
            max_artifacts: Optional limit (applies to already-filtered list)

        Returns:
            List of Artifact objects (pre-filtered by orchestrator via context provider)
            with full metadata (type, payload, produced_by, created_at, tags, etc.)
        """
        if not self.enable_context or not ctx:
            return []

        context_items = list(ctx.artifacts)  # Copy to avoid mutation

        # Apply engine-level filtering (type exclusions)
        if self.context_exclude_types:
            context_items = [
                item
                for item in context_items
                if item.type not in self.context_exclude_types
            ]

        # Apply max artifacts limit
        max_limit = (
            max_artifacts if max_artifacts is not None else self.context_max_artifacts
        )
        if max_limit is not None and max_limit > 0:
            context_items = context_items[-max_limit:]

        return context_items

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
    "TracedModelMeta",
]
