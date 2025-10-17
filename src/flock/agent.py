"""Agent definitions and fluent builder APIs."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import BaseModel

from flock.artifacts import Artifact, ArtifactSpec
from flock.logging.auto_trace import AutoTracedMeta
from flock.logging.logging import get_logger
from flock.registry import function_registry, type_registry
from flock.runtime import Context, EvalInputs, EvalResult
from flock.subscription import BatchSpec, JoinSpec, Subscription, TextPredicate
from flock.visibility import AgentIdentity, Visibility, ensure_visibility, only_for


logger = get_logger(__name__)

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from collections.abc import Callable, Iterable, Sequence

    from flock.components import AgentComponent, EngineComponent
    from flock.orchestrator import Flock


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
        # MCP integration
        self.mcp_server_names: set[str] = set()
        self.mcp_mount_points: list[
            str
        ] = []  # Deprecated: Use mcp_server_mounts instead
        self.mcp_server_mounts: dict[
            str, list[str]
        ] = {}  # Server-specific mount points
        self.tool_whitelist: list[str] | None = None

    @property
    def outputs(self) -> list[AgentOutput]:
        """Backwards compatibility: return flat list of all outputs from all groups."""
        return [output for group in self.output_groups for output in group.outputs]

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
                "Agent %s: utility added: component=%s, priority=%s, total_utilities=%s",
                self.name,
                comp_name,
                priority,
                len(self.utilities),
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
        """Lazy-load MCP tools from assigned servers.

        Architecture Decision: AD001 - Two-Level Architecture
        Agents fetch tools from servers registered at orchestrator level.

        Architecture Decision: AD003 - Tool Namespacing
        All tools are namespaced as {server}__{tool}.

        Architecture Decision: AD007 - Graceful Degradation
        If MCP loading fails, returns empty list so agent continues with native tools.

        Args:
            ctx: Current execution context with agent_id and run_id

        Returns:
            List of DSPy-compatible tool callables
        """
        if not self.mcp_server_names:
            # No MCP servers assigned to this agent
            return []

        try:
            # Get the MCP manager from orchestrator
            manager = self._orchestrator.get_mcp_manager()

            # Fetch tools from all assigned servers
            tools_dict = await manager.get_tools_for_agent(
                agent_id=self.name,
                run_id=ctx.task_id,
                server_names=self.mcp_server_names,
                server_mounts=self.mcp_server_mounts,  # Pass server-specific mounts
            )

            # Whitelisting logic
            tool_whitelist = self.tool_whitelist
            if (
                tool_whitelist is not None
                and isinstance(tool_whitelist, list)
                and len(tool_whitelist) > 0
            ):
                filtered_tools: dict[str, Any] = {}
                for tool_key, tool_entry in tools_dict.items():
                    if isinstance(tool_entry, dict):
                        original_name = tool_entry.get("original_name", None)
                        if (
                            original_name is not None
                            and original_name in tool_whitelist
                        ):
                            filtered_tools[tool_key] = tool_entry

                tools_dict = filtered_tools

            # Convert to DSPy tool callables
            dspy_tools = []
            for namespaced_name, tool_info in tools_dict.items():
                tool_info["server_name"]
                flock_tool = tool_info["tool"]  # Already a FlockMCPTool
                client = tool_info["client"]

                # Convert to DSPy tool
                dspy_tool = flock_tool.as_dspy_tool(server=client)

                # Update name to include namespace
                dspy_tool.name = namespaced_name

                dspy_tools.append(dspy_tool)

            return dspy_tools

        except Exception as e:
            # Architecture Decision: AD007 - Graceful Degradation
            # Agent continues with native tools only
            logger.error(
                f"Failed to load MCP tools for agent {self.name}: {e}", exc_info=True
            )
            return []

    async def _run_initialize(self, ctx: Context) -> None:
        for component in self._sorted_utilities():
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent initialize: agent={self.name}, component={comp_name}, priority={priority}"
            )
            try:
                await component.on_initialize(self, ctx)
            except Exception as exc:
                logger.exception(
                    f"Agent initialize failed: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        for engine in self.engines:
            await engine.on_initialize(self, ctx)

    async def _run_pre_consume(
        self, ctx: Context, inputs: list[Artifact]
    ) -> list[Artifact]:
        current = inputs
        for component in self._sorted_utilities():
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent pre_consume: agent={self.name}, component={comp_name}, "
                f"priority={priority}, input_count={len(current)}"
            )
            try:
                current = await component.on_pre_consume(self, ctx, current)
            except Exception as exc:
                logger.exception(
                    f"Agent pre_consume failed: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        return current

    async def _run_pre_evaluate(self, ctx: Context, inputs: EvalInputs) -> EvalInputs:
        current = inputs
        for component in self._sorted_utilities():
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent pre_evaluate: agent={self.name}, component={comp_name}, "
                f"priority={priority}, artifact_count={len(current.artifacts)}"
            )
            try:
                current = await component.on_pre_evaluate(self, ctx, current)
            except Exception as exc:
                logger.exception(
                    f"Agent pre_evaluate failed: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        return current

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
                from flock.runtime import EvalResult as ER

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
        current = result
        for component in self._sorted_utilities():
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent post_evaluate: agent={self.name}, component={comp_name}, "
                f"priority={priority}, artifact_count={len(current.artifacts)}"
            )
            try:
                current = await component.on_post_evaluate(self, ctx, inputs, current)
            except Exception as exc:
                logger.exception(
                    f"Agent post_evaluate failed: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        return current

    async def _make_outputs(self, ctx: Context, result: EvalResult) -> list[Artifact]:
        if not self.output_groups:
            # Utility agents may not publish anything
            return list(result.artifacts)

        produced: list[Artifact] = []

        # For Phase 2: Iterate ALL output_groups (even though we only have 1 engine call)
        # Phase 3 will modify this to call engine once PER group
        for output_group in self.output_groups:
            for output_decl in output_group.outputs:
                # Phase 6: Find the matching artifact from engine result to preserve its ID
                matching_artifact = self._find_matching_artifact(output_decl, result)

                payload = self._select_payload(output_decl, result)
                if payload is None:
                    continue
                metadata = {
                    "correlation_id": ctx.correlation_id,
                }

                # Phase 6: Preserve artifact ID from engine (for streaming message preview)
                if matching_artifact:
                    metadata["artifact_id"] = matching_artifact.id

                artifact = output_decl.apply(
                    payload, produced_by=self.name, metadata=metadata
                )
                produced.append(artifact)
                # Phase 6: REMOVED publishing - orchestrator now handles it
                # await ctx.board.publish(artifact)

        return produced

    def _prepare_group_context(
        self, ctx: Context, group_idx: int, output_group: OutputGroup
    ) -> Context:
        """Phase 3: Prepare context specific to this OutputGroup.

        Creates a modified context for this group's engine call, potentially
        with group-specific instructions or metadata.

        Args:
            ctx: Base context
            group_idx: Index of this group (0-based)
            output_group: The OutputGroup being processed

        Returns:
            Context for this group (may be the same instance or modified)
        """
        # For now, return the same context
        # Phase 4 will add group-specific system prompts here
        # Future: ctx.clone() and add group_description to system prompt
        return ctx

    async def _make_outputs_for_group(
        self, ctx: Context, result: EvalResult, output_group: OutputGroup
    ) -> list[Artifact]:
        """Phase 3/5: Validate, filter, and publish artifacts for specific OutputGroup.

        This function:
        1. Validates that the engine fulfilled its contract (produced expected count)
        2. Applies WHERE filtering (reduces artifacts, no error)
        3. Applies VALIDATE checks (raises ValueError if validation fails)
        4. Applies visibility (static or dynamic)
        5. Publishes artifacts to the board

        Args:
            ctx: Context for this group
            result: EvalResult from engine for THIS group
            output_group: OutputGroup defining expected outputs

        Returns:
            List of artifacts matching this group's outputs

        Raises:
            ValueError: If engine violated contract or validation failed
        """
        produced: list[Artifact] = []

        for output_decl in output_group.outputs:
            # 1. Find ALL matching artifacts for this type
            from flock.registry import type_registry

            expected_canonical = type_registry.resolve_name(output_decl.spec.type_name)

            matching_artifacts: list[Artifact] = []
            for artifact in result.artifacts:
                try:
                    artifact_canonical = type_registry.resolve_name(artifact.type)
                    if artifact_canonical == expected_canonical:
                        matching_artifacts.append(artifact)
                except Exception:
                    if artifact.type == output_decl.spec.type_name:
                        matching_artifacts.append(artifact)

            # 2. STRICT VALIDATION: Engine must produce exactly what was promised
            # (This happens BEFORE filtering so engine contract is validated first)
            expected_count = output_decl.count
            actual_count = len(matching_artifacts)

            if actual_count != expected_count:
                raise ValueError(
                    f"Engine contract violation in agent '{self.name}': "
                    f"Expected {expected_count} artifact(s) of type '{output_decl.spec.type_name}', "
                    f"but engine produced {actual_count}. "
                    f"Check your engine implementation to ensure it generates the correct number of outputs."
                )

            # 3. Apply WHERE filtering (Phase 5)
            # Filtering reduces the number of published artifacts (this is intentional)
            # NOTE: Predicates expect Pydantic model instances, not dicts
            model_cls = type_registry.resolve(output_decl.spec.type_name)

            if output_decl.filter_predicate:
                original_count = len(matching_artifacts)
                filtered = []
                for a in matching_artifacts:
                    # Reconstruct Pydantic model from payload dict
                    model_instance = model_cls(**a.payload)
                    if output_decl.filter_predicate(model_instance):
                        filtered.append(a)
                matching_artifacts = filtered
                logger.debug(
                    f"Agent {self.name}: WHERE filter reduced artifacts from "
                    f"{original_count} to {len(matching_artifacts)} for type {output_decl.spec.type_name}"
                )

            # 4. Apply VALIDATE checks (Phase 5)
            # Validation failures raise errors (fail-fast)
            if output_decl.validate_predicate:
                if callable(output_decl.validate_predicate):
                    # Single predicate
                    for artifact in matching_artifacts:
                        # Reconstruct Pydantic model from payload dict
                        model_instance = model_cls(**artifact.payload)
                        if not output_decl.validate_predicate(model_instance):
                            raise ValueError(
                                f"Validation failed for {output_decl.spec.type_name} "
                                f"in agent '{self.name}'"
                            )
                elif isinstance(output_decl.validate_predicate, list):
                    # List of (callable, error_msg) tuples
                    for artifact in matching_artifacts:
                        # Reconstruct Pydantic model from payload dict
                        model_instance = model_cls(**artifact.payload)
                        for check, error_msg in output_decl.validate_predicate:
                            if not check(model_instance):
                                raise ValueError(
                                    f"{error_msg}: {output_decl.spec.type_name}"
                                )

            # 5. Apply visibility and publish artifacts (Phase 5)
            for artifact_from_engine in matching_artifacts:
                metadata = {
                    "correlation_id": ctx.correlation_id,
                    "artifact_id": artifact_from_engine.id,  # Preserve engine's ID
                }

                # Determine visibility (static or dynamic)
                visibility = output_decl.default_visibility
                if callable(visibility):
                    # Dynamic visibility based on artifact content
                    # Reconstruct Pydantic model from payload dict
                    model_instance = model_cls(**artifact_from_engine.payload)
                    visibility = visibility(model_instance)

                # Override metadata visibility
                metadata["visibility"] = visibility

                # Re-wrap the artifact with agent metadata
                artifact = output_decl.apply(
                    artifact_from_engine.payload,
                    produced_by=self.name,
                    metadata=metadata,
                )
                produced.append(artifact)
                # Phase 6 SECURITY FIX: REMOVED publishing - orchestrator now handles it
                # This fixes Vulnerability #2 (WRITE Bypass) - agents can no longer publish directly
                # await ctx.board.publish(artifact)

        return produced

    async def _run_post_publish(
        self, ctx: Context, artifacts: Sequence[Artifact]
    ) -> None:
        components = self._sorted_utilities()
        for artifact in artifacts:
            for component in components:
                comp_name = self._component_display_name(component)
                priority = getattr(component, "priority", 0)
                logger.debug(
                    f"Agent post_publish: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, artifact_id={artifact.id}"
                )
                try:
                    await component.on_post_publish(self, ctx, artifact)
                except Exception as exc:
                    logger.exception(
                        f"Agent post_publish failed: agent={self.name}, component={comp_name}, "
                        f"priority={priority}, artifact_id={artifact.id}, error={exc!s}"
                    )
                    raise

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
        for component in self._sorted_utilities():
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)

            # Python 3.12+ TaskGroup raises BaseExceptionGroup - extract sub-exceptions
            error_detail = str(error)
            if isinstance(error, BaseExceptionGroup):
                sub_exceptions = [f"{type(e).__name__}: {e}" for e in error.exceptions]
                error_detail = f"{error!s} - Sub-exceptions: {sub_exceptions}"

            logger.debug(
                f"Agent error hook: agent={self.name}, component={comp_name}, "
                f"priority={priority}, error={error_detail}"
            )
            try:
                await component.on_error(self, ctx, error)
            except Exception as exc:
                logger.exception(
                    f"Agent error hook failed: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, original_error={error!s}, hook_error={exc!s}"
                )
                raise
        for engine in self.engines:
            await engine.on_error(self, ctx, error)

    async def _run_terminate(self, ctx: Context) -> None:
        for component in self._sorted_utilities():
            comp_name = self._component_display_name(component)
            priority = getattr(component, "priority", 0)
            logger.debug(
                f"Agent terminate: agent={self.name}, component={comp_name}, priority={priority}"
            )
            try:
                await component.on_terminate(self, ctx)
            except Exception as exc:
                logger.exception(
                    f"Agent terminate failed: agent={self.name}, component={comp_name}, "
                    f"priority={priority}, error={exc!s}"
                )
                raise
        for engine in self.engines:
            await engine.on_terminate(self, ctx)

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
            from flock.utility.output_utility_component import (
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
        """Phase 6: Find artifact from engine result that matches this output declaration.

        Returns the artifact object (with its ID) so we can preserve it when creating
        the final published artifact. This ensures streaming events use the same ID.
        """
        from flock.registry import type_registry

        if not result.artifacts:
            return None

        # Normalize the expected type name to canonical form
        expected_canonical = type_registry.resolve_name(output_decl.spec.type_name)

        for artifact in result.artifacts:
            # Normalize artifact type name to canonical form for comparison
            try:
                artifact_canonical = type_registry.resolve_name(artifact.type)
                if artifact_canonical == expected_canonical:
                    return artifact
            except Exception:
                # If normalization fails, fall back to direct comparison
                if artifact.type == output_decl.spec.type_name:
                    return artifact

        return None

    def _select_payload(
        self, output_decl: AgentOutput, result: EvalResult
    ) -> dict[str, Any] | None:
        from flock.registry import type_registry

        if not result.artifacts:
            return None

        # Normalize the expected type name to canonical form
        expected_canonical = type_registry.resolve_name(output_decl.spec.type_name)

        for artifact in result.artifacts:
            # Normalize artifact type name to canonical form for comparison
            try:
                artifact_canonical = type_registry.resolve_name(artifact.type)
                if artifact_canonical == expected_canonical:
                    return artifact.payload
            except Exception:
                # If normalization fails, fall back to direct comparison
                if artifact.type == output_decl.spec.type_name:
                    return artifact.payload

        # Fallback to state entries keyed by type name
        maybe_data = result.state.get(output_decl.spec.type_name)
        if isinstance(maybe_data, dict):
            return maybe_data
        return None


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
        text: str | None = None,
        min_p: float = 0.0,
        from_agents: Iterable[str] | None = None,
        tags: Iterable[str] | None = None,
        join: dict | JoinSpec | None = None,
        batch: dict | BatchSpec | None = None,
        delivery: str = "exclusive",
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
            text: Optional semantic text filter using embedding similarity
            min_p: Minimum probability threshold for text similarity (0.0-1.0)
            from_agents: Only consume artifacts from specific agents
            tags: Only consume artifacts with matching tags
            join: Join specification for coordinating multiple artifact types
            batch: Batch specification for processing multiple artifacts together
            delivery: Delivery mode - "exclusive" (one agent) or "broadcast" (all matching)
            mode: Processing mode - "both", "streaming", or "batch"
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

        join_spec = self._normalize_join(join)
        batch_spec = self._normalize_batch(batch)
        text_predicates = [TextPredicate(text=text, min_p=min_p)] if text else []
        subscription = Subscription(
            agent_name=self._agent.name,
            types=types,
            where=predicates,
            text_predicates=text_predicates,
            from_agents=from_agents,
            tags=tags,
            join=join_spec,
            batch=batch_spec,
            delivery=delivery,
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

        # Validate configuration
        self._validate_self_trigger_risk()

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
        # T074: Validate best_of value
        self._validate_best_of(n)
        return self

    def max_concurrency(self, n: int) -> AgentBuilder:
        self._agent.set_max_concurrency(n)
        # T074: Validate concurrency value
        self._validate_concurrency(n)
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
        servers: (
            Iterable[str]
            | dict[str, MCPServerConfig | list[str]]  # Support both new and old format
            | list[str | dict[str, MCPServerConfig | list[str]]]
        ),
    ) -> AgentBuilder:
        """Assign MCP servers to this agent with optional server-specific mount points.

                Architecture Decision: AD001 - Two-Level Architecture
                Agents reference servers registered at orchestrator level.

                Args:
                    servers: One of:
                        - List of server names (strings) - no specific mounts
                        - Dict mapping server names to MCPServerConfig or list[str] (backward compatible)
                        - Mixed list of strings and dicts for flexibility

                Returns:
                    self for method chaining

                Raises:
                    ValueError: If any server name is not registered with orchestrator

                Examples:
                    >>> # Simple: no mount restrictions
                    >>> agent.with_mcps(["filesystem", "github"])

                    >>> # New format: Server-specific config with roots and tool whitelist
                    >>> agent.with_mcps({
                    ...     "filesystem": {
                    ...         "roots": ["/workspace/dir/data"],
                    ...         "tool_whitelist": ["read_file"],
                    ...     },
                    ...     "github": {},  # No restrictions for github
                    ... })

                    >>> # Old format: Direct list (backward compatible)
                    >>> agent.with_mcps({
                    ...     "filesystem": ["/workspace/dir/data"],  # Old format still works
                    ... })

                    >>> # Mixed: backward compatible
                    >>> agent.with_mcps([
                    ...     "github",  # No mounts
                    ...     {"filesystem": {"roots": ["mount1", "mount2"] } }
        ```
                    ... ])
        """
        # Parse input into server_names and mounts
        server_set: set[str] = set()
        server_mounts: dict[str, list[str]] = {}
        whitelist = None

        if isinstance(servers, dict):
            # Dict format: supports both old and new formats
            # Old: {"server": ["/path1", "/path2"]}
            # New: {"server": {"roots": ["/path1"], "tool_whitelist": ["tool1"]}}
            for server_name, server_config in servers.items():
                server_set.add(server_name)

                # Check if it's the old format (direct list) or new format (MCPServerConfig dict)
                if isinstance(server_config, list):
                    # Old format: direct list of paths (backward compatibility)
                    if len(server_config) > 0:
                        server_mounts[server_name] = list(server_config)
                elif isinstance(server_config, dict):
                    # New format: MCPServerConfig with optional roots and tool_whitelist
                    mounts = server_config.get("roots", None)
                    if (
                        mounts is not None
                        and isinstance(mounts, list)
                        and len(mounts) > 0
                    ):
                        server_mounts[server_name] = list(mounts)

                    config_whitelist = server_config.get("tool_whitelist", None)
                    if (
                        config_whitelist is not None
                        and isinstance(config_whitelist, list)
                        and len(config_whitelist) > 0
                    ):
                        whitelist = config_whitelist
        elif isinstance(servers, list):
            # List format: can be mixed
            for item in servers:
                if isinstance(item, str):
                    # Simple server name
                    server_set.add(item)
                elif isinstance(item, dict):
                    # Dict with mounts
                    for server_name, mounts in item.items():
                        server_set.add(server_name)
                        if mounts:
                            server_mounts[server_name] = list(mounts)
                else:
                    raise TypeError(
                        f"Invalid server specification: {item}. "
                        f"Expected string or dict, got {type(item).__name__}"
                    )
        else:
            # Assume it's an iterable of strings (backward compatibility)
            server_set = set(servers)

        # Validate all servers exist in orchestrator
        registered_servers = set(self._orchestrator._mcp_configs.keys())
        invalid_servers = server_set - registered_servers

        if invalid_servers:
            available = list(registered_servers) if registered_servers else ["none"]
            raise ValueError(
                f"MCP servers not registered: {invalid_servers}. "
                f"Available servers: {available}. "
                f"Register servers using orchestrator.add_mcp() first."
            )

        # Store in agent
        self._agent.mcp_server_names = server_set
        self._agent.mcp_server_mounts = server_mounts
        self._agent.tool_whitelist = whitelist

        return self

    def mount(self, paths: str | list[str], *, validate: bool = False) -> AgentBuilder:
        """Mount agent in specific directories for MCP root access.

        .. deprecated:: 0.2.0
            Use `.with_mcps({"server_name": ["/path"]})` instead for server-specific mounts.
            This method applies mounts globally to all MCP servers.

        This sets the filesystem roots that MCP servers will operate under for this agent.
        Paths are cumulative across multiple calls.

        Args:
            paths: Single path or list of paths to mount
            validate: If True, validate that paths exist (default: False)

        Returns:
            AgentBuilder for method chaining

        Example:
            >>> # Old way (deprecated)
            >>> agent.with_mcps(["filesystem"]).mount("/workspace/src")
            >>>
            >>> # New way (recommended)
            >>> agent.with_mcps({"filesystem": ["/workspace/src"]})
        """
        import warnings

        warnings.warn(
            "Agent.mount() is deprecated. Use .with_mcps({'server': ['/path']}) "
            "for server-specific mounts instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        if isinstance(paths, str):
            paths = [paths]
        if validate:
            from pathlib import Path

            for path in paths:
                if not Path(path).exists():
                    raise ValueError(f"Mount path does not exist: {path}")

        # Add to agent's mount points (cumulative) - for backward compatibility
        self._agent.mcp_mount_points.extend(paths)

        # Also add to all configured servers for backward compatibility
        for server_name in self._agent.mcp_server_names:
            if server_name not in self._agent.mcp_server_mounts:
                self._agent.mcp_server_mounts[server_name] = []
            self._agent.mcp_server_mounts[server_name].extend(paths)

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

    # Validation -----------------------------------------------------------

    def _validate_self_trigger_risk(self) -> None:
        """T074: Warn if agent consumes and publishes same type (feedback loop risk)."""
        from flock.logging.logging import get_logger

        logger = get_logger(__name__)

        # Get types agent consumes
        consuming_types = set()
        for sub in self._agent.subscriptions:
            consuming_types.update(sub.type_names)

        # Get types agent publishes
        publishing_types = {
            output.spec.type_name
            for group in self._agent.output_groups
            for output in group.outputs
        }

        # Check for overlap
        overlap = consuming_types.intersection(publishing_types)
        if overlap and self._agent.prevent_self_trigger:
            logger.warning(
                f"Agent '{self._agent.name}' consumes and publishes {overlap}. "
                f"Feedback loop risk detected. Agent has prevent_self_trigger=True (safe), "
                f"but consider adding filtering: .consumes(Type, where=lambda x: ...) "
                f"or use .prevent_self_trigger(False) for intentional feedback."
            )

    def _validate_best_of(self, n: int) -> None:
        """T074: Warn if best_of value is excessively high."""
        from flock.logging.logging import get_logger

        logger = get_logger(__name__)

        if n > 100:
            logger.warning(
                f"Agent '{self._agent.name}' has best_of({n}) which is very high. "
                f"Typical values are 3-10. High values increase cost and latency. "
                f"Consider reducing unless you have specific requirements."
            )

    def _validate_concurrency(self, n: int) -> None:
        """T074: Warn if max_concurrency is excessively high."""
        from flock.logging.logging import get_logger

        logger = get_logger(__name__)

        if n > 1000:
            logger.warning(
                f"Agent '{self._agent.name}' has max_concurrency({n}) which is very high. "
                f"Typical values are 1-50. Excessive concurrency may cause resource issues. "
                f"Consider reducing unless you have specific infrastructure."
            )

    # Utility --------------------------------------------------------------

    def _normalize_join(self, value: dict | JoinSpec | None) -> JoinSpec | None:
        if value is None or isinstance(value, JoinSpec):
            return value
        # Phase 2: New JoinSpec API with 'by' and 'within' (time OR count)
        from datetime import timedelta

        within_value = value.get("within")
        if isinstance(within_value, (int, float)):
            # Count window or seconds as float - keep as is
            within = (
                int(within_value)
                if isinstance(within_value, int)
                else timedelta(seconds=within_value)
            )
        else:
            # Default to 1 minute time window
            within = timedelta(minutes=1)
        return JoinSpec(
            by=value["by"],  # Required
            within=within,
        )

    def _normalize_batch(self, value: dict | BatchSpec | None) -> BatchSpec | None:
        if value is None or isinstance(value, BatchSpec):
            return value
        return BatchSpec(
            size=int(value.get("size", 1)),
            within=float(value.get("within", 0.0)),
            by=value.get("by"),
        )

    # Properties -----------------------------------------------------------

    @property
    def name(self) -> str:
        return self._agent.name

    @property
    def agent(self) -> Agent:
        return self._agent


class PublishBuilder:
    """Helper returned by `.publishes(...)` to support `.only_for` sugar."""

    def __init__(self, parent: AgentBuilder, outputs: Sequence[AgentOutput]) -> None:
        self._parent = parent
        self._outputs = list(outputs)

    def only_for(self, *agent_names: str) -> AgentBuilder:
        visibility = only_for(*agent_names)
        for output in self._outputs:
            output.default_visibility = visibility
        return self._parent

    def visibility(self, value: Visibility) -> AgentBuilder:
        for output in self._outputs:
            output.default_visibility = value
        return self._parent

    def __getattr__(self, item):
        return getattr(self._parent, item)


class RunHandle:
    """Represents a chained run starting from a given agent."""

    def __init__(self, agent: Agent, inputs: list[BaseModel]) -> None:
        self.agent = agent
        self.inputs = inputs
        self._chain: list[Agent] = [agent]

    def then(self, builder: AgentBuilder) -> RunHandle:
        self._chain.append(builder.agent)
        return self

    async def execute(self) -> list[Artifact]:
        orchestrator = self.agent._orchestrator
        artifacts = await orchestrator.direct_invoke(self.agent, self.inputs)
        for agent in self._chain[1:]:
            artifacts = await orchestrator.direct_invoke(agent, artifacts)
        return artifacts


class Pipeline:
    def __init__(self, builders: Sequence[AgentBuilder]) -> None:
        self.builders = list(builders)

    def then(self, builder: AgentBuilder) -> Pipeline:
        self.builders.append(builder)
        return self

    async def execute(self) -> list[Artifact]:
        orchestrator = self.builders[0].agent._orchestrator
        artifacts: list[Artifact] = []
        for builder in self.builders:
            inputs = artifacts if artifacts else []
            artifacts = await orchestrator.direct_invoke(builder.agent, inputs)
        return artifacts


__all__ = [
    "Agent",
    "AgentBuilder",
    "AgentOutput",
    "OutputGroup",
]
