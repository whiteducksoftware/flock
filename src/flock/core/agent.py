"""Agent definitions and fluent builder APIs."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import BaseModel

# Phase 5B: Import builder modules
from flock.agent.builder_helpers import Pipeline, PublishBuilder, RunHandle
from flock.agent.builder_validator import BuilderValidator
from flock.agent.component_lifecycle import ComponentLifecycle
from flock.agent.mcp_integration import MCPIntegration

# Phase 4: Import extracted modules
from flock.agent.output_processor import OutputProcessor
from flock.core.artifacts import Artifact, ArtifactSpec
from flock.core.subscription import BatchSpec, JoinSpec, Subscription
from flock.core.visibility import AgentIdentity, Visibility, ensure_visibility
from flock.logging.auto_trace import AutoTracedMeta
from flock.logging.logging import get_logger
from flock.registry import function_registry, type_registry
from flock.utils.runtime import Context, EvalInputs, EvalResult


logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from collections.abc import Callable, Iterable, Sequence

    from flock.components.agent import AgentComponent, EngineComponent
    from flock.core import Flock


class MCPServerConfig(TypedDict, total=False):
    """Configuration for MCP server assignment to an agent.

    All fields are optional. If omitted, no restrictions apply.

    Attributes:
        roots: Filesystem paths this server can access.
               Empty list or omitted = no mount restrictions.
        tool_whitelist: Tool names the agent can use from this server.
                       Empty list or omitted = all tools available.

    Examples:
        >>> # No restrictions
        >>> config: MCPServerConfig = {}

        >>> # Mount restrictions only
        >>> config: MCPServerConfig = {"roots": ["/workspace/data"]}

        >>> # Tool whitelist only
        >>> config: MCPServerConfig = {
        ...     "tool_whitelist": ["read_file", "write_file"]
        ... }

        >>> # Both restrictions
        >>> config: MCPServerConfig = {
        ...     "roots": ["/workspace/data"],
        ...     "tool_whitelist": ["read_file"],
        ... }
    """

    roots: list[str]
    tool_whitelist: list[str]


@dataclass
class AgentOutput:
    spec: ArtifactSpec
    default_visibility: Visibility
    count: int = 1  # Number of artifacts to generate (fan-out)
    filter_predicate: Callable[[BaseModel], bool] | None = None  # Where clause
    validate_predicate: (
        Callable[[BaseModel], bool] | list[tuple[Callable, str]] | None
    ) = None  # Validation logic
    group_description: str | None = None  # Group description override

    def __post_init__(self):
        """Validate field constraints."""
        if self.count < 1:
            raise ValueError(f"count must be >= 1, got {self.count}")

    def is_many(self) -> bool:
        """Return True if this output generates multiple artifacts (count > 1)."""
        return self.count > 1

    def apply(
        self,
        data: dict[str, Any],
        *,
        produced_by: str,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        metadata = metadata or {}
        return self.spec.build(
            produced_by=produced_by,
            data=data,
            visibility=metadata.get("visibility", self.default_visibility),
            correlation_id=metadata.get("correlation_id"),
            partition_key=metadata.get("partition_key"),
            tags=metadata.get("tags"),
            version=metadata.get("version", 1),
            artifact_id=metadata.get("artifact_id"),  # Phase 6: Preserve engine's ID
        )


@dataclass
class OutputGroup:
    """Represents one .publishes() call.

    Each OutputGroup triggers one engine execution that generates
    all artifacts in the group together.
    """

    outputs: list[AgentOutput]
    shared_visibility: Visibility | None = None
    group_description: str | None = None  # Group-level description override

    def is_single_call(self) -> bool:
        """True if this is one engine call generating multiple artifacts.

        Currently always returns True as each group = one engine call.
        Future: Could return False for parallel sub-groups.
        """
        return True


class Agent(metaclass=AutoTracedMeta):
    """Executable agent constructed via `AgentBuilder`.

    All public methods are automatically traced via OpenTelemetry.
    """

    # Phase 6+7: Class-level streaming coordination (SHARED across ALL agent instances)
    # These class variables enable all agents to coordinate CLI streaming behavior
    _streaming_counter: int = 0  # Global count of agents currently streaming to CLI
    _websocket_broadcast_global: Any = (
        None  # WebSocket broadcast wrapper (dashboard mode)
    )

    def __init__(self, name: str, *, orchestrator: Flock) -> None:
        self.name = name
        self.description: str | None = None
        self._orchestrator = orchestrator
        self.subscriptions: list[Subscription] = []
        self.output_groups: list[OutputGroup] = []
        self.utilities: list[AgentComponent] = []
        self.engines: list[EngineComponent] = []
        self.best_of_n: int = 1
        self.best_of_score: Callable[[EvalResult], float] | None = None
        self.max_concurrency: int = 2
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self.calls_func: Callable[..., Any] | None = None
        self.tools: set[Callable[..., Any]] = set()
        self.labels: set[str] = set()
        self.tenant_id: str | None = None
        self.model: str | None = None
        self.prevent_self_trigger: bool = True  # T065: Prevent infinite feedback loops
        # Phase 3: Per-agent context provider (security fix)
        self.context_provider: Any = None

        # Phase 4: Initialize extracted modules
        self._output_processor = OutputProcessor(name)
        self._mcp_integration = MCPIntegration(name, orchestrator)
        self._component_lifecycle = ComponentLifecycle(name)

    @property
    def outputs(self) -> list[AgentOutput]:
        """Return flat list of all outputs from all groups."""
        return [output for group in self.output_groups for output in group.outputs]

    # Phase 4: MCP properties - delegate to MCPIntegration
    @property
    def mcp_server_names(self) -> set[str]:
        """MCP server names assigned to this agent."""
        return self._mcp_integration.mcp_server_names

    @mcp_server_names.setter
    def mcp_server_names(self, value: set[str]) -> None:
        self._mcp_integration.mcp_server_names = value

    @property
    def mcp_server_mounts(self) -> dict[str, list[str]]:
        """Server-specific mount points."""
        return self._mcp_integration.mcp_server_mounts

    @mcp_server_mounts.setter
    def mcp_server_mounts(self, value: dict[str, list[str]]) -> None:
        self._mcp_integration.mcp_server_mounts = value

    @property
    def tool_whitelist(self) -> list[str] | None:
        """Tool whitelist for MCP servers."""
        return self._mcp_integration.tool_whitelist

    @tool_whitelist.setter
    def tool_whitelist(self, value: list[str] | None) -> None:
        self._mcp_integration.tool_whitelist = value

    @property
    def identity(self) -> AgentIdentity:
        return AgentIdentity(
            name=self.name, labels=self.labels, tenant_id=self.tenant_id
        )

    @staticmethod
    def _component_display_name(component: AgentComponent) -> str:
        return component.name or component.__class__.__name__

    def _sorted_utilities(self) -> list[AgentComponent]:
        if not self.utilities:
            return []
        return sorted(self.utilities, key=lambda comp: getattr(comp, "priority", 0))

    def _add_utilities(self, components: Sequence[AgentComponent]) -> None:
        if not components:
            return
        for component in components:
            self.utilities.append(component)
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.info(
                f"Agent {self.name}: utility added: component={comp_name}, priority={priority}, total_utilities={len(self.utilities)}"
            )
        self.utilities.sort(key=lambda comp: getattr(comp, "priority", 0))

    def set_max_concurrency(self, value: int) -> None:
        self.max_concurrency = max(1, value)
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

    async def run_direct(self, *inputs: BaseModel) -> list[Artifact]:
        return await self._orchestrator.direct_invoke(self, list(inputs))

    async def execute(self, ctx: Context, artifacts: list[Artifact]) -> list[Artifact]:
        async with self._semaphore:
            try:
                self._resolve_engines()
                self._resolve_utilities()
                await self._run_initialize(ctx)
                processed_inputs = await self._run_pre_consume(ctx, artifacts)
                eval_inputs = EvalInputs(
                    artifacts=processed_inputs, state=dict(ctx.state)
                )
                eval_inputs = await self._run_pre_evaluate(ctx, eval_inputs)

                # Phase 3: Call engine ONCE PER OutputGroup
                all_outputs: list[Artifact] = []

                if not self.output_groups:
                    # No output groups: Utility agents that don't publish
                    # Create empty OutputGroup for engines that may have side effects
                    empty_group = OutputGroup(outputs=[], group_description=None)
                    result = await self._run_engines(ctx, eval_inputs, empty_group)
                    # Run post_evaluate hooks for utility components (e.g., metrics)
                    result = await self._run_post_evaluate(ctx, eval_inputs, result)
                    # Utility agents return empty list (no outputs declared)
                    outputs = []
                else:
                    # Loop over each output group
                    for group_idx, output_group in enumerate(self.output_groups):
                        # Prepare group-specific context
                        group_ctx = self._prepare_group_context(
                            ctx, group_idx, output_group
                        )

                        # Phase 7: Single evaluation path with auto-detection
                        # Engine's evaluate() auto-detects batch/fan-out from ctx and output_group
                        result = await self._run_engines(
                            group_ctx, eval_inputs, output_group
                        )

                        result = await self._run_post_evaluate(
                            group_ctx, eval_inputs, result
                        )

                        # Extract outputs for THIS group only
                        group_outputs = await self._make_outputs_for_group(
                            group_ctx, result, output_group
                        )

                        all_outputs.extend(group_outputs)

                    outputs = all_outputs

                await self._run_post_publish(ctx, outputs)
                if self.calls_func:
                    await self._invoke_call(ctx, outputs or processed_inputs)
                return outputs
            except Exception as exc:
                await self._run_error(ctx, exc)
                raise
            finally:
                await self._run_terminate(ctx)

    async def _get_mcp_tools(self, ctx: Context) -> list[Callable]:
        """Delegate to MCPIntegration module."""
        return await self._mcp_integration.get_mcp_tools(ctx)

    async def _run_initialize(self, ctx: Context) -> None:
        """Delegate to ComponentLifecycle module."""
        await self._component_lifecycle.run_initialize(
            self, ctx, self._sorted_utilities(), self.engines
        )

    async def _run_pre_consume(
        self, ctx: Context, inputs: list[Artifact]
    ) -> list[Artifact]:
        """Delegate to ComponentLifecycle module."""
        return await self._component_lifecycle.run_pre_consume(
            self, ctx, inputs, self._sorted_utilities()
        )

    async def _run_pre_evaluate(self, ctx: Context, inputs: EvalInputs) -> EvalInputs:
        """Delegate to ComponentLifecycle module."""
        return await self._component_lifecycle.run_pre_evaluate(
            self, ctx, inputs, self._sorted_utilities()
        )

    async def _run_engines(
        self, ctx: Context, inputs: EvalInputs, output_group: OutputGroup
    ) -> EvalResult:
        """Execute engines for a specific OutputGroup.

        Args:
            ctx: Execution context
            inputs: EvalInputs with input artifacts
            output_group: The OutputGroup defining what artifacts to produce

        Returns:
            EvalResult with artifacts matching output_group specifications
        """
        engines = self._resolve_engines()
        if not engines:
            return EvalResult(artifacts=inputs.artifacts, state=inputs.state)

        async def run_chain() -> EvalResult:
            current_inputs = inputs
            accumulated_logs: list[str] = []
            accumulated_metrics: dict[str, float] = {}
            for engine in engines:
                current_inputs = await engine.on_pre_evaluate(self, ctx, current_inputs)

                # Phase 7: Single evaluation path with auto-detection
                # Engine's evaluate() auto-detects batching via ctx.is_batch
                result = await engine.evaluate(self, ctx, current_inputs, output_group)

                # AUTO-WRAP: If engine returns BaseModel instead of EvalResult, wrap it
                from flock.utils.runtime import EvalResult as ER

                if isinstance(result, BaseModel) and not isinstance(result, ER):
                    result = ER.from_object(result, agent=self)

                artifacts = result.artifacts
                for artifact in artifacts:
                    artifact.correlation_id = ctx.correlation_id

                result = await engine.on_post_evaluate(
                    self, ctx, current_inputs, result
                )
                accumulated_logs.extend(result.logs)
                accumulated_metrics.update(result.metrics)
                merged_state = dict(current_inputs.state)
                merged_state.update(result.state)
                current_inputs = EvalInputs(
                    artifacts=result.artifacts or current_inputs.artifacts,
                    state=merged_state,
                )
            return EvalResult(
                artifacts=current_inputs.artifacts,
                state=current_inputs.state,
                metrics=accumulated_metrics,
                logs=accumulated_logs,
            )

        if self.best_of_n <= 1:
            return await run_chain()

        async with asyncio.TaskGroup() as tg:  # Python 3.12
            tasks: list[asyncio.Task[EvalResult]] = []
            for _ in range(self.best_of_n):
                tasks.append(tg.create_task(run_chain()))
        results = [task.result() for task in tasks]
        if not results:
            return EvalResult(artifacts=[], state={})
        if self.best_of_score is None:
            return results[0]
        return max(results, key=self.best_of_score)

    async def _run_post_evaluate(
        self, ctx: Context, inputs: EvalInputs, result: EvalResult
    ) -> EvalResult:
        """Delegate to ComponentLifecycle module."""
        return await self._component_lifecycle.run_post_evaluate(
            self, ctx, inputs, result, self._sorted_utilities()
        )

    async def _make_outputs(self, ctx: Context, result: EvalResult) -> list[Artifact]:
        """Delegate to OutputProcessor module."""
        return await self._output_processor.make_outputs(
            ctx, result, self.output_groups
        )

    def _prepare_group_context(
        self, ctx: Context, group_idx: int, output_group: OutputGroup
    ) -> Context:
        """Delegate to OutputProcessor module."""
        return self._output_processor.prepare_group_context(
            ctx, group_idx, output_group
        )

    async def _make_outputs_for_group(
        self, ctx: Context, result: EvalResult, output_group: OutputGroup
    ) -> list[Artifact]:
        """Delegate to OutputProcessor module."""
        return await self._output_processor.make_outputs_for_group(
            ctx, result, output_group
        )

    async def _run_post_publish(
        self, ctx: Context, artifacts: Sequence[Artifact]
    ) -> None:
        """Delegate to ComponentLifecycle module."""
        await self._component_lifecycle.run_post_publish(
            self, ctx, artifacts, self._sorted_utilities()
        )

    async def _invoke_call(self, ctx: Context, artifacts: Sequence[Artifact]) -> None:
        func = self.calls_func
        if func is None:
            return
        if not artifacts:
            return
        first = artifacts[0]
        model_cls = type_registry.resolve(first.type)
        payload = model_cls(**first.payload)
        maybe_coro = func(payload)
        if asyncio.iscoroutine(maybe_coro):  # pragma: no cover - optional async support
            await maybe_coro

    async def _run_error(self, ctx: Context, error: Exception) -> None:
        """Delegate to ComponentLifecycle module."""
        await self._component_lifecycle.run_error(
            self, ctx, error, self._sorted_utilities(), self.engines
        )

    async def _run_terminate(self, ctx: Context) -> None:
        """Delegate to ComponentLifecycle module."""
        await self._component_lifecycle.run_terminate(
            self, ctx, self._sorted_utilities(), self.engines
        )

    def _resolve_engines(self) -> list[EngineComponent]:
        if self.engines:
            return self.engines
        try:
            from flock.engines import DSPyEngine
        except Exception:  # pragma: no cover - optional dependency issues
            return []

        default_engine = DSPyEngine(
            model=self._orchestrator.model
            or os.getenv("DEFAULT_MODEL", "openai/gpt-4.1"),
            instructions=self.description,
        )
        self.engines = [default_engine]
        return self.engines

    def _resolve_utilities(self) -> list[AgentComponent]:
        if self.utilities:
            return self.utilities
        try:
            from flock.components.agent import (
                OutputUtilityComponent,
            )
        except Exception:  # pragma: no cover - optional dependency issues
            return []

        default_component = OutputUtilityComponent()
        self._add_utilities([default_component])
        return self.utilities

    def _find_matching_artifact(
        self, output_decl: AgentOutput, result: EvalResult
    ) -> Artifact | None:
        """Delegate to OutputProcessor module."""
        return self._output_processor.find_matching_artifact(output_decl, result)

    def _select_payload(
        self, output_decl: AgentOutput, result: EvalResult
    ) -> dict[str, Any] | None:
        """Delegate to OutputProcessor module."""
        return self._output_processor.select_payload(output_decl, result)


class AgentBuilder:
    """Fluent builder that also acts as the runtime agent handle."""

    def __init__(self, orchestrator: Flock, name: str) -> None:
        self._orchestrator = orchestrator
        self._agent = Agent(name, orchestrator=orchestrator)
        self._agent.model = orchestrator.model
        orchestrator.register_agent(self._agent)

    # Fluent configuration -------------------------------------------------

    def description(self, text: str) -> AgentBuilder:
        """Set the agent's description for documentation and tracing.

        Args:
            text: Human-readable description of what the agent does

        Returns:
            self for method chaining

        Example:
            >>> agent = (
            ...     flock.agent("pizza_chef")
            ...     .description("Creates authentic Italian pizza recipes")
            ...     .consumes(Idea)
            ...     .publishes(Recipe)
            ... )
        """
        self._agent.description = text
        return self

    def consumes(
        self,
        *types: type[BaseModel],
        where: Callable[[BaseModel], bool]
        | Sequence[Callable[[BaseModel], bool]]
        | None = None,
        semantic_match: str
        | list[str]
        | list[dict[str, Any]]
        | dict[str, Any]
        | None = None,
        semantic_threshold: float = 0.0,
        from_agents: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        join: dict | JoinSpec | None = None,
        batch: dict | BatchSpec | None = None,
        mode: str = "both",
        priority: int = 0,
    ) -> AgentBuilder:
        """Declare which artifact types this agent processes.

        Sets up subscription rules that determine when the agent executes.
        Supports type-based matching, conditional filters, batching, and joins.

        Args:
            *types: Artifact types (Pydantic models) to consume
            where: Optional filter predicate(s). Agent only executes if predicate returns True.
                Can be a single callable or sequence of callables (all must pass).
            semantic_match: Optional semantic similarity filter. Matches artifacts based on
                meaning rather than keywords. Can be:
                - str: Single query (e.g., "security vulnerability")
                - list[str]: Multiple queries, all must match (AND logic)
                - dict: Advanced config with "query", "threshold", "field"
                - list[dict]: Multiple queries with individual thresholds
            semantic_threshold: Minimum similarity threshold for semantic matching (0.0-1.0).
                Applied to all queries when semantic_match is a string or list of strings.
                Ignored if semantic_match is a dict/list of dicts with explicit "threshold".
                Default: 0.0 (uses default 0.4 when not specified)
            from_agents: Only consume artifacts from specific agents
            tags: Only consume artifacts with matching tags
            join: Join specification for coordinating multiple artifact types
            batch: Batch specification for processing multiple artifacts together
            mode: Processing mode - "both", "direct", or "events"
            priority: Execution priority (higher = executes first)

        Returns:
            self for method chaining

        Examples:
            >>> # Basic type subscription
            >>> agent.consumes(Task)

            >>> # Multiple types
            >>> agent.consumes(Task, Event, Command)

            >>> # Conditional consumption (filtering)
            >>> agent.consumes(Review, where=lambda r: r.score >= 8)

            >>> # Multiple predicates (all must pass)
            >>> agent.consumes(
            ...     Order,
            ...     where=[lambda o: o.total > 100, lambda o: o.status == "pending"],
            ... )

            >>> # Semantic matching
            >>> agent.consumes(Ticket, semantic_match="security vulnerability")

            >>> # Semantic matching with custom threshold
            >>> agent.consumes(Ticket, semantic_match="urgent", semantic_threshold=0.6)

            >>> # Consume from specific agents
            >>> agent.consumes(Report, from_agents=["analyzer", "validator"])

            >>> # Channel-based routing
            >>> agent.consumes(Alert, tags={"critical", "security"})

            >>> # Batch processing
            >>> agent.consumes(Email, batch={"size": 10, "timeout": 5.0})
        """
        predicates: Sequence[Callable[[BaseModel], bool]] | None
        if where is None:
            predicates = None
        elif callable(where):
            predicates = [where]
        else:
            predicates = list(where)

        # Phase 5B: Use BuilderValidator for normalization
        join_spec = BuilderValidator.normalize_join(join)
        batch_spec = BuilderValidator.normalize_batch(batch)

        # Handle semantic_threshold parameter to control semantic matching threshold
        # If semantic_threshold is provided and semantic_match is simple, convert to dict
        semantic_param: (
            str | list[str] | list[dict[str, Any]] | dict[str, Any] | None
        ) = semantic_match
        if semantic_match is not None and semantic_threshold > 0.0:
            if isinstance(semantic_match, str):
                # Simple string: create dict with semantic_threshold as threshold
                semantic_param = {
                    "query": semantic_match,
                    "threshold": semantic_threshold,
                }
            elif isinstance(semantic_match, list):
                # List of strings: convert to list of dicts with semantic_threshold
                semantic_param = [
                    {"query": q, "threshold": semantic_threshold}
                    for q in semantic_match
                ]
            elif isinstance(semantic_match, dict) and "threshold" not in semantic_match:
                # Dict without explicit threshold: add semantic_threshold
                semantic_param = {**semantic_match, "threshold": semantic_threshold}

        # Semantic matching: pass semantic_match parameter to Subscription
        # which will parse it into TextPredicate objects
        subscription = Subscription(
            agent_name=self._agent.name,
            types=types,
            where=predicates,
            semantic_match=semantic_param,  # Let Subscription handle conversion
            from_agents=from_agents,
            tags=tags,
            join=join_spec,
            batch=batch_spec,
            mode=mode,
            priority=priority,
        )
        self._agent.subscriptions.append(subscription)
        return self

    def publishes(
        self,
        *types: type[BaseModel],
        visibility: Visibility | Callable[[BaseModel], Visibility] | None = None,
        fan_out: int | None = None,
        where: Callable[[BaseModel], bool] | None = None,
        validate: Callable[[BaseModel], bool]
        | list[tuple[Callable, str]]
        | None = None,
        description: str | None = None,
    ) -> PublishBuilder:
        """Declare which artifact types this agent produces.

        Args:
            *types: Artifact types (Pydantic models) to publish
            visibility: Default visibility control OR callable for dynamic visibility
            fan_out: Number of artifacts to publish (applies to ALL types)
            where: Filter predicate for output artifacts
            validate: Validation predicate(s) - callable or list of (callable, error_msg) tuples
            description: Group-level description override

        Returns:
            PublishBuilder for conditional publishing configuration

        Examples:
            >>> agent.publishes(Report)  # Publish 1 Report
            >>> agent.publishes(
            ...     Task, Task, Task
            ... )  # Publish 3 Tasks (duplicate counting)
            >>> agent.publishes(Task, fan_out=3)  # Same as above (sugar syntax)
            >>> agent.publishes(Task, where=lambda t: t.priority > 5)  # With filtering
            >>> agent.publishes(
            ...     Report, validate=lambda r: r.score > 0
            ... )  # With validation
            >>> agent.publishes(
            ...     Task, description="Special instructions"
            ... )  # With description

        See Also:
            - PublicVisibility: Default, visible to all agents
            - PrivateVisibility: Allowlist-based access control
            - TenantVisibility: Multi-tenant isolation
            - LabelledVisibility: Role-based access control
        """
        # Validate fan_out if provided
        if fan_out is not None and fan_out < 1:
            raise ValueError(f"fan_out must be >= 1, got {fan_out}")

        # Resolve visibility
        resolved_visibility = (
            ensure_visibility(visibility) if not callable(visibility) else visibility
        )

        # Create AgentOutput objects for this group
        outputs: list[AgentOutput] = []

        if fan_out is not None:
            # Apply fan_out to ALL types
            for model in types:
                spec = ArtifactSpec.from_model(model)
                output = AgentOutput(
                    spec=spec,
                    default_visibility=resolved_visibility,
                    count=fan_out,
                    filter_predicate=where,
                    validate_predicate=validate,
                    group_description=description,
                )
                outputs.append(output)
        else:
            # Create separate AgentOutput for each type (including duplicates)
            # This preserves order: .publishes(A, B, A) → [A, B, A] (3 outputs)
            for model in types:
                spec = ArtifactSpec.from_model(model)
                output = AgentOutput(
                    spec=spec,
                    default_visibility=resolved_visibility,
                    count=1,
                    filter_predicate=where,
                    validate_predicate=validate,
                    group_description=description,
                )
                outputs.append(output)

        # Create OutputGroup from outputs
        group = OutputGroup(
            outputs=outputs,
            shared_visibility=resolved_visibility
            if not callable(resolved_visibility)
            else None,
            group_description=description,
        )

        # Append to agent's output_groups
        self._agent.output_groups.append(group)

        # Phase 5B: Use BuilderValidator for validation
        BuilderValidator.validate_self_trigger_risk(self._agent)

        return PublishBuilder(self, outputs)

    def with_utilities(self, *components: AgentComponent) -> AgentBuilder:
        """Add utility components to customize agent lifecycle and behavior.

        Components are hooks that run at specific points in the agent execution
        lifecycle. Common uses include rate limiting, budgets, metrics, caching,
        and custom preprocessing/postprocessing.

        Args:
            *components: AgentComponent instances with lifecycle hooks

        Returns:
            self for method chaining

        Examples:
            >>> # Rate limiting
            >>> agent.with_utilities(RateLimiter(max_calls=10, window=60))

            >>> # Budget control
            >>> agent.with_utilities(TokenBudget(max_tokens=10000))

            >>> # Multiple components (executed in order)
            >>> agent.with_utilities(
            ...     RateLimiter(max_calls=5), MetricsCollector(), CacheLayer(ttl=3600)
            ... )

        See Also:
            - AgentComponent: Base class for custom components
            - Lifecycle hooks: on_initialize, on_pre_consume, on_post_publish, etc.
        """
        if components:
            self._agent._add_utilities(list(components))
        return self

    def with_engines(self, *engines: EngineComponent) -> AgentBuilder:
        """Configure LLM engines for agent evaluation.

        Engines determine how agents process inputs. Default is DSPy with the
        orchestrator's model. Custom engines enable different LLM backends,
        non-LLM logic, or hybrid approaches.

        Args:
            *engines: EngineComponent instances for evaluation

        Returns:
            self for method chaining

        Examples:
            >>> # DSPy engine with specific model
            >>> agent.with_engines(DSPyEngine(model="openai/gpt-4o"))

            >>> # Custom non-LLM engine
            >>> agent.with_engines(RuleBasedEngine(rules=my_rules))

            >>> # Hybrid approach (multiple engines)
            >>> agent.with_engines(
            ...     DSPyEngine(model="openai/gpt-4o-mini"), FallbackEngine()
            ... )

        Note:
            If no engines specified, agent uses DSPy with the orchestrator's default model.

        See Also:
            - DSPyEngine: Default LLM-based evaluation
            - EngineComponent: Base class for custom engines
        """
        self._agent.engines.extend(engines)
        return self

    def best_of(self, n: int, score: Callable[[EvalResult], float]) -> AgentBuilder:
        self._agent.best_of_n = max(1, n)
        self._agent.best_of_score = score
        # Phase 5B: Use BuilderValidator for validation
        BuilderValidator.validate_best_of(self._agent.name, n)
        return self

    def max_concurrency(self, n: int) -> AgentBuilder:
        self._agent.set_max_concurrency(n)
        # Phase 5B: Use BuilderValidator for validation
        BuilderValidator.validate_concurrency(self._agent.name, n)
        return self

    def calls(self, func: Callable[..., Any]) -> AgentBuilder:
        function_registry.register(func)
        self._agent.calls_func = func
        return self

    def with_tools(self, funcs: Iterable[Callable[..., Any]]) -> AgentBuilder:
        self._agent.tools.update(funcs)
        return self

    def with_context(self, provider: Any) -> AgentBuilder:
        """Configure a custom context provider for this agent (Phase 3 security fix).

        Context providers control what artifacts an agent can see, enforcing
        visibility filtering at the security boundary layer.

        Args:
            provider: ContextProvider instance for this agent

        Returns:
            self for method chaining

        Examples:
            >>> # Use custom provider for this agent
            >>> agent.with_context(MyCustomProvider())

            >>> # Use FilteredContextProvider for declarative filtering
            >>> agent.with_context(
            ...     FilteredContextProvider(FilterConfig(tags={"important"}))
            ... )

        Note:
            Per-agent provider takes precedence over global provider configured
            on Flock(context_provider=...). If neither is set, DefaultContextProvider
            is used automatically.

        See Also:
            - DefaultContextProvider: Default security boundary with visibility enforcement
            - FilteredContextProvider: Declarative filtering with FilterConfig
        """
        self._agent.context_provider = provider
        return self

    def with_mcps(
        self,
        servers: (Iterable[str] | dict[str, MCPServerConfig]),
    ) -> AgentBuilder:
        """Assign MCP servers to this agent with optional server-specific mount points.

        Architecture Decision: AD001 - Two-Level Architecture
        Agents reference servers registered at orchestrator level.

        Args:
            servers: One of:
                - List of server names (strings) - no specific mounts
                - Dict mapping server names to MCPServerConfig

        Returns:
            self for method chaining

        Raises:
            ValueError: If any server name is not registered with orchestrator

        Examples:
            >>> # Simple: no mount restrictions
            >>> agent.with_mcps(["filesystem", "github"])

            >>> # Server-specific config with roots and tool whitelist
            >>> agent.with_mcps({
            ...     "filesystem": {
            ...         "roots": ["/workspace/dir/data"],
            ...         "tool_whitelist": ["read_file"],
            ...     },
            ...     "github": {},  # No restrictions for github
            ... })
        """
        # Delegate to MCPIntegration module
        registered_servers = set(self._orchestrator._mcp_configs.keys())
        self._agent._mcp_integration.configure_servers(servers, registered_servers)
        return self

    def labels(self, *labels: str) -> AgentBuilder:
        self._agent.labels.update(labels)
        return self

    def tenant(self, tenant_id: str) -> AgentBuilder:
        self._agent.tenant_id = tenant_id
        return self

    def prevent_self_trigger(self, enabled: bool = True) -> AgentBuilder:
        """Prevent agent from being triggered by its own outputs.

        When enabled (default), the orchestrator will skip scheduling this agent
        for artifacts it produced itself. This prevents infinite feedback loops
        when an agent consumes and publishes the same type.

        Args:
            enabled: True to prevent self-triggering (safe default),
                    False to allow feedback loops (advanced use case)

        Returns:
            AgentBuilder for method chaining

        Example:
            # Safe by default (recommended)
            agent.consumes(Document).publishes(Document)
            # Won't trigger on own outputs ✅

            # Explicit feedback loop (use with caution!)
            agent.consumes(Data, where=lambda d: d.depth < 10)
                 .publishes(Data)
                 .prevent_self_trigger(False)  # Acknowledge risk
        """
        self._agent.prevent_self_trigger = enabled
        return self

    # Runtime helpers ------------------------------------------------------

    def run(self, *inputs: BaseModel) -> RunHandle:
        return RunHandle(self._agent, list(inputs))

    def then(self, other: AgentBuilder) -> Pipeline:
        return Pipeline([self, other])

    # Phase 5B: Validation and normalization moved to BuilderValidator module

    # Properties -----------------------------------------------------------

    @property
    def name(self) -> str:
        return self._agent.name

    @property
    def agent(self) -> Agent:
        return self._agent


# Phase 5B: Helper classes moved to builder_helpers module


__all__ = [
    "Agent",
    "AgentBuilder",
    "AgentOutput",
    "OutputGroup",
]
