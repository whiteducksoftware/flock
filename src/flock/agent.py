"""Agent definitions and fluent builder APIs."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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


@dataclass
class AgentOutput:
    spec: ArtifactSpec
    default_visibility: Visibility

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
        )


class Agent(metaclass=AutoTracedMeta):
    """Executable agent constructed via `AgentBuilder`.

    All public methods are automatically traced via OpenTelemetry.
    """

    def __init__(self, name: str, *, orchestrator: Flock) -> None:
        self.name = name
        self.description: str | None = None
        self._orchestrator = orchestrator
        self.subscriptions: list[Subscription] = []
        self.outputs: list[AgentOutput] = []
        self.utilities: list[AgentComponent] = []
        self.engines: list[EngineComponent] = []
        self.best_of_n: int = 1
        self.best_of_score: Callable[[EvalResult], float] | None = None
        self.max_concurrency: int = 1
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self.calls_func: Callable[..., Any] | None = None
        self.tools: set[Callable[..., Any]] = set()
        self.labels: set[str] = set()
        self.tenant_id: str | None = None
        self.model: str | None = None
        self.prevent_self_trigger: bool = True  # T065: Prevent infinite feedback loops
        # MCP integration
        self.mcp_server_names: set[str] = set()

    @property
    def identity(self) -> AgentIdentity:
        return AgentIdentity(name=self.name, labels=self.labels, tenant_id=self.tenant_id)

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
                eval_inputs = EvalInputs(artifacts=processed_inputs, state=dict(ctx.state))
                eval_inputs = await self._run_pre_evaluate(ctx, eval_inputs)
                result = await self._run_engines(ctx, eval_inputs)
                result = await self._run_post_evaluate(ctx, eval_inputs, result)
                outputs = await self._make_outputs(ctx, result)
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

            # Import tool wrapper

            # Fetch tools from all assigned servers
            tools_dict = await manager.get_tools_for_agent(
                agent_id=self.name,
                run_id=ctx.task_id,
                server_names=self.mcp_server_names,
            )

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
            logger.error(f"Failed to load MCP tools for agent {self.name}: {e}", exc_info=True)
            return []

    async def _run_initialize(self, ctx: Context) -> None:
        for component in self.utilities:
            await component.on_initialize(self, ctx)
        for engine in self.engines:
            await engine.on_initialize(self, ctx)

    async def _run_pre_consume(self, ctx: Context, inputs: list[Artifact]) -> list[Artifact]:
        current = inputs
        for component in self.utilities:
            current = await component.on_pre_consume(self, ctx, current)
        return current

    async def _run_pre_evaluate(self, ctx: Context, inputs: EvalInputs) -> EvalInputs:
        current = inputs
        for component in self.utilities:
            current = await component.on_pre_evaluate(self, ctx, current)
        return current

    async def _run_engines(self, ctx: Context, inputs: EvalInputs) -> EvalResult:
        engines = self._resolve_engines()
        if not engines:
            return EvalResult(artifacts=inputs.artifacts, state=inputs.state)

        async def run_chain() -> EvalResult:
            current_inputs = inputs
            accumulated_logs: list[str] = []
            accumulated_metrics: dict[str, float] = {}
            for engine in engines:
                current_inputs = await engine.on_pre_evaluate(self, ctx, current_inputs)
                result = await engine.evaluate(self, ctx, current_inputs)

                # AUTO-WRAP: If engine returns BaseModel instead of EvalResult, wrap it
                from flock.runtime import EvalResult as ER

                if isinstance(result, BaseModel) and not isinstance(result, ER):
                    result = ER.from_object(result, agent=self)

                result = await engine.on_post_evaluate(self, ctx, current_inputs, result)
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
        for component in self.utilities:
            current = await component.on_post_evaluate(self, ctx, inputs, current)
        return current

    async def _make_outputs(self, ctx: Context, result: EvalResult) -> list[Artifact]:
        if not self.outputs:
            # Utility agents may not publish anything
            return list(result.artifacts)

        produced: list[Artifact] = []
        for output_decl in self.outputs:
            payload = self._select_payload(output_decl, result)
            if payload is None:
                continue
            metadata = {
                "correlation_id": ctx.correlation_id  # Need to add this to Context!
            }
            artifact = output_decl.apply(payload, produced_by=self.name, metadata=metadata)
            produced.append(artifact)
            await ctx.board.publish(artifact)
        return produced

    async def _run_post_publish(self, ctx: Context, artifacts: Sequence[Artifact]) -> None:
        for artifact in artifacts:
            for component in self.utilities:
                await component.on_post_publish(self, ctx, artifact)

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
        for component in self.utilities:
            await component.on_error(self, ctx, error)
        for engine in self.engines:
            await engine.on_error(self, ctx, error)

    async def _run_terminate(self, ctx: Context) -> None:
        for component in self.utilities:
            await component.on_terminate(self, ctx)
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
            model=self._orchestrator.model or os.getenv("DEFAULT_MODEL", "openai/gpt-4o-mini"),
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
        self.utilities = [default_component]
        return self.utilities

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
        self._agent.description = text
        return self

    def consumes(
        self,
        *types: type[BaseModel],
        where: Callable[[BaseModel], bool] | Sequence[Callable[[BaseModel], bool]] | None = None,
        text: str | None = None,
        min_p: float = 0.0,
        from_agents: Iterable[str] | None = None,
        channels: Iterable[str] | None = None,
        join: dict | JoinSpec | None = None,
        batch: dict | BatchSpec | None = None,
        delivery: str = "exclusive",
        mode: str = "both",
        priority: int = 0,
    ) -> AgentBuilder:
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
            channels=channels,
            join=join_spec,
            batch=batch_spec,
            delivery=delivery,
            mode=mode,
            priority=priority,
        )
        self._agent.subscriptions.append(subscription)
        return self

    def publishes(
        self, *types: type[BaseModel], visibility: Visibility | None = None
    ) -> PublishBuilder:
        outputs = []
        for model in types:
            spec = ArtifactSpec.from_model(model)
            output = AgentOutput(spec=spec, default_visibility=ensure_visibility(visibility))
            self._agent.outputs.append(output)
            outputs.append(output)
        # T074: Validate configuration after adding outputs
        self._validate_self_trigger_risk()
        return PublishBuilder(self, outputs)

    def with_utilities(self, *components: AgentComponent) -> AgentBuilder:
        self._agent.utilities.extend(components)
        return self

    def with_engines(self, *engines: EngineComponent) -> AgentBuilder:
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

    def with_mcps(self, server_names: Iterable[str]) -> AgentBuilder:
        """Assign MCP servers to this agent.

        Architecture Decision: AD001 - Two-Level Architecture
        Agents reference servers registered at orchestrator level.

        Args:
            server_names: Names of MCP servers this agent should use

        Returns:
            self for method chaining

        Raises:
            ValueError: If any server name is not registered with orchestrator

        Example:
            >>> agent = (
            ...     orchestrator.agent("file_agent")
            ...     .with_mcps(["filesystem", "github"])
            ...     .build()
            ... )
        """
        # Convert to set for efficient lookup
        server_set = set(server_names)

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
        publishing_types = {output.spec.type_name for output in self._agent.outputs}

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
        return JoinSpec(
            kind=value.get("kind", "all_of"),
            window=float(value.get("window", 0.0)),
            by=value.get("by"),
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
]
