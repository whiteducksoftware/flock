"""Blackboard orchestrator and scheduling runtime."""

from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Task
from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from flock.components.orchestrator import (
    CollectionResult,
    OrchestratorComponent,
    ScheduleDecision,
)
from flock.core.agent import Agent, AgentBuilder
from flock.core.artifacts import Artifact
from flock.core.store import BlackboardStore, ConsumptionRecord
from flock.core.subscription import Subscription
from flock.core.visibility import PublicVisibility, Visibility
from flock.logging.auto_trace import AutoTracedMeta
from flock.mcp import (
    FlockMCPClientManager,
    FlockMCPConfiguration,
    ServerParameters,
)
from flock.orchestrator import (
    AgentScheduler,
    ArtifactManager,
    ComponentRunner,
    OrchestratorInitializer,
    ServerManager,
    TracingManager,
)
from flock.registry import type_registry


if TYPE_CHECKING:
    import builtins


class BoardHandle:
    """Handle exposed to components for publishing and inspection."""

    def __init__(self, orchestrator: Flock) -> None:
        self._orchestrator = orchestrator

    async def publish(self, artifact: Artifact) -> None:
        await self._orchestrator._persist_and_schedule(artifact)

    async def get(self, artifact_id) -> Artifact | None:
        return await self._orchestrator.store.get(artifact_id)

    async def list(self) -> builtins.list[Artifact]:
        return await self._orchestrator.store.list()


class Flock(metaclass=AutoTracedMeta):
    """Main orchestrator for blackboard-based agent coordination.

    All public methods are automatically traced via OpenTelemetry.
    """

    def _patch_litellm_proxy_imports(self) -> None:
        """Stub litellm proxy_server to avoid optional proxy deps when not used.

        Some litellm versions import `litellm.proxy.proxy_server` during standard logging
        to read `general_settings`, which pulls in optional dependencies like `apscheduler`.
        We provide a stub so imports succeed but cold storage remains disabled.
        """
        try:
            import sys
            import types

            if "litellm.proxy.proxy_server" not in sys.modules:
                stub = types.ModuleType("litellm.proxy.proxy_server")
                # Minimal surface that cold_storage_handler accesses
                stub.general_settings = {}
                sys.modules["litellm.proxy.proxy_server"] = stub
        except Exception:  # nosec B110 - Safe to ignore; worst case litellm will log a warning
            # logger.debug(f"Failed to stub litellm proxy_server: {e}")
            pass

    def __init__(
        self,
        model: str | None = None,
        *,
        store: BlackboardStore | None = None,
        max_agent_iterations: int = 1000,
        context_provider: Any = None,
    ) -> None:
        """Initialize the Flock orchestrator for blackboard-based agent coordination.

        Phase 3: Simplified using OrchestratorInitializer module.

        Args:
            model: Default LLM model for agents
            store: Custom blackboard storage backend
            max_agent_iterations: Circuit breaker limit
            context_provider: Global context provider for all agents

        Examples:
            >>> flock = Flock("openai/gpt-4.1")
            >>> flock = Flock("openai/gpt-4o", store=CustomStore())
        """
        # Patch litellm imports and setup logger
        self._patch_litellm_proxy_imports()
        self._logger = logging.getLogger(__name__)
        self.model = model or os.getenv("DEFAULT_MODEL")

        # Phase 3: Initialize all components using OrchestratorInitializer
        components = OrchestratorInitializer.initialize_components(
            store=store,
            context_provider=context_provider,
            max_agent_iterations=max_agent_iterations,
            logger=self._logger,
            model=model,
        )

        # Assign basic state
        self.store = components["store"]
        self._agents = components["agents"]
        self._lock = components["lock"]
        self.metrics = components["metrics"]
        self._agent_iteration_count = components["agent_iteration_count"]
        self._default_context_provider = context_provider
        self.max_agent_iterations = max_agent_iterations
        self.is_dashboard = False

        # Assign engines
        self._artifact_collector = components["artifact_collector"]
        self._correlation_engine = components["correlation_engine"]
        self._batch_engine = components["batch_engine"]

        # Assign Phase 5A modules
        self._context_builder = components["context_builder"]
        self._event_emitter = components["event_emitter"]
        self._lifecycle_manager = components["lifecycle_manager"]

        # Assign Phase 3 modules
        self._mcp_manager_instance = components["mcp_manager_instance"]
        self._tracing_manager = components["tracing_manager"]
        self._auto_workflow_enabled = components["auto_workflow_enabled"]

        # WebSocket manager (set by serve())
        self.__websocket_manager = components["websocket_manager"]

        # Set batch timeout callback
        self._lifecycle_manager.set_batch_timeout_callback(self._check_batch_timeouts)

        # Background server task for non-blocking serve() (set by ServerManager.serve)
        self._server_task: Task[None] | None = None
        self._dashboard_launcher: Any = None

        # Initialize components list and built-in components
        self._components: list[OrchestratorComponent] = []
        runner_components = OrchestratorInitializer.initialize_components_and_runner(
            self._components, max_agent_iterations, self._logger
        )
        self._component_runner = runner_components["component_runner"]

        # Initialize scheduler and artifact manager
        self._scheduler = AgentScheduler(self, self._component_runner)
        self._artifact_manager = ArtifactManager(self, self.store, self._scheduler)

        # Log initialization
        self._logger.debug("Orchestrator initialized: components=[]")

    # Agent management -----------------------------------------------------

    def agent(self, name: str) -> AgentBuilder:
        """Create a new agent using the fluent builder API.

        Args:
            name: Unique identifier for the agent. Used for visibility controls and metrics.

        Returns:
            AgentBuilder for fluent configuration

        Raises:
            ValueError: If an agent with this name already exists

        Examples:
            >>> # Basic agent
            >>> pizza_agent = (
            ...     flock.agent("pizza_master")
            ...     .description("Creates delicious pizza recipes")
            ...     .consumes(DreamPizza)
            ...     .publishes(Pizza)
            ... )

            >>> # Advanced agent with filtering
            >>> critic = (
            ...     flock.agent("critic")
            ...     .consumes(Movie, where=lambda m: m.rating >= 8)
            ...     .publishes(Review)
            ...     .with_utilities(RateLimiter(max_calls=10))
            ... )
        """
        if name in self._agents:
            raise ValueError(f"Agent '{name}' already registered.")
        return AgentBuilder(self, name)

    def register_agent(self, agent: Agent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' already registered.")
        self._agents[agent.name] = agent

    def get_agent(self, name: str) -> Agent:
        return self._agents[name]

    @property
    def agents(self) -> list[Agent]:
        return list(self._agents.values())

    async def get_correlation_status(self, correlation_id: str) -> dict[str, Any]:
        """Get the status of a workflow by correlation ID.

        Args:
            correlation_id: The correlation ID to check

        Returns:
            Dictionary containing workflow status information:
            - state: "active" if work is pending, "completed" otherwise
            - has_pending_work: True if orchestrator has pending work for this correlation
            - artifact_count: Total number of artifacts with this correlation_id
            - error_count: Number of WorkflowError artifacts
            - started_at: Timestamp of first artifact (if any)
            - last_activity_at: Timestamp of most recent artifact (if any)
        """
        from uuid import UUID

        try:
            correlation_uuid = UUID(correlation_id)
        except ValueError as exc:
            raise ValueError(
                f"Invalid correlation_id format: {correlation_id}"
            ) from exc

        # Check if orchestrator has pending work for this correlation
        # 1. Check active tasks for this correlation_id
        has_active_tasks = (
            correlation_uuid in self._scheduler._correlation_tasks
            and bool(self._scheduler._correlation_tasks[correlation_uuid])
        )

        # 2. Check correlation groups (for agents with JoinSpec that haven't yielded yet)
        has_pending_groups = False
        for groups in self._correlation_engine.correlation_groups.values():
            for group_key, group in groups.items():
                # Check if this group belongs to our correlation
                for type_name, artifacts in group.waiting_artifacts.items():
                    if any(
                        artifact.correlation_id == correlation_uuid
                        for artifact in artifacts
                    ):
                        has_pending_groups = True
                        break
                if has_pending_groups:
                    break
            if has_pending_groups:
                break

        # Workflow has pending work if EITHER tasks are active OR groups are waiting
        has_pending_work = has_active_tasks or has_pending_groups

        # Query artifacts for this correlation
        from flock.core.store import FilterConfig

        filters = FilterConfig(correlation_id=correlation_id)
        artifacts, total = await self.store.query_artifacts(
            filters, limit=1000, offset=0
        )

        # Count errors - use registry to get correct type name after Phase 8 refactor
        from flock.models.system_artifacts import WorkflowError

        workflow_error_type = type_registry.name_for(WorkflowError)
        error_count = sum(
            1 for artifact in artifacts if artifact.type == workflow_error_type
        )

        # Get timestamps
        started_at = None
        last_activity_at = None
        if artifacts:
            timestamps = [artifact.created_at for artifact in artifacts]
            started_at = min(timestamps).isoformat()
            last_activity_at = max(timestamps).isoformat()

        # Determine state
        if has_pending_work:
            state = "active"
        elif total == 0:
            state = "not_found"
        elif error_count > 0 and total == error_count:
            state = "failed"  # Only error artifacts exist
        else:
            state = "completed"

        return {
            "correlation_id": correlation_id,
            "state": state,
            "has_pending_work": has_pending_work,
            "artifact_count": total,
            "error_count": error_count,
            "started_at": started_at,
            "last_activity_at": last_activity_at,
        }

    # Phase 5A: WebSocket manager property (auto-updates event emitter)

    @property
    def _websocket_manager(self) -> Any:
        """Get the WebSocket manager for dashboard events."""
        return self.__websocket_manager

    @_websocket_manager.setter
    def _websocket_manager(self, value: Any) -> None:
        """Set the WebSocket manager and propagate to EventEmitter."""
        self.__websocket_manager = value
        self._event_emitter.set_websocket_manager(value)

    # Component management -------------------------------------------------

    def add_component(self, component: OrchestratorComponent) -> Flock:
        """Add an OrchestratorComponent to this orchestrator.

        Components execute in priority order (lower priority number = earlier).
        Multiple components can have the same priority.

        Args:
            component: Component to add (must be an OrchestratorComponent instance)

        Returns:
            Self for method chaining

        Examples:
            >>> # Add single component
            >>> flock = Flock("openai/gpt-4.1")
            >>> flock.add_component(CircuitBreakerComponent(max_iterations=500))

            >>> # Method chaining
            >>> flock.add_component(CircuitBreakerComponent()) \\
            ...      .add_component(MetricsComponent()) \\
            ...      .add_component(DeduplicationComponent())

            >>> # Custom priority (lower = earlier)
            >>> flock.add_component(
            ...     CustomComponent(priority=5, name="early_component")
            ... )
        """
        self._components.append(component)
        self._components.sort(key=lambda c: c.priority)

        # Phase 3: Update ComponentRunner with new sorted components
        self._component_runner = ComponentRunner(self._components, self._logger)

        # Log component addition
        comp_name = component.name or component.__class__.__name__
        self._logger.info(
            f"Component added: name={comp_name}, "
            f"priority={component.priority}, total_components={len(self._components)}"
        )

        return self

    # MCP management - Phase 3 extracted to MCPManager -------------------------------------------------------

    def add_mcp(
        self,
        name: str,
        connection_params: ServerParameters,
        *,
        enable_tools_feature: bool = True,
        enable_prompts_feature: bool = True,
        enable_sampling_feature: bool = True,
        enable_roots_feature: bool = True,
        mount_points: list[str] | None = None,
        tool_whitelist: list[str] | None = None,
        read_timeout_seconds: float = 300,
        max_retries: int = 3,
        **kwargs,
    ) -> Flock:
        """Register an MCP server for use by agents.

        Architecture Decision: AD001 - Two-Level Architecture
        MCP servers are registered at orchestrator level and assigned to agents.

        Args:
            name: Unique identifier for this MCP server
            connection_params: Server connection parameters
            enable_tools_feature: Enable tool execution
            enable_prompts_feature: Enable prompt templates
            enable_sampling_feature: Enable LLM sampling requests
            enable_roots_feature: Enable filesystem roots
            tool_whitelist: Optional list of tool names to allow
            read_timeout_seconds: Timeout for server communications
            max_retries: Connection retry attempts

        Returns:
            self for method chaining

        Raises:
            ValueError: If server name already registered
        """
        # Phase 3: Delegate to MCPManager
        self._mcp_manager_instance.add_mcp(
            name,
            connection_params,
            enable_tools_feature=enable_tools_feature,
            enable_prompts_feature=enable_prompts_feature,
            enable_sampling_feature=enable_sampling_feature,
            enable_roots_feature=enable_roots_feature,
            mount_points=mount_points,
            tool_whitelist=tool_whitelist,
            read_timeout_seconds=read_timeout_seconds,
            max_retries=max_retries,
            **kwargs,
        )
        return self

    def get_mcp_manager(self) -> FlockMCPClientManager:
        """Get or create the MCP client manager.

        Architecture Decision: AD005 - Lazy Connection Establishment
        """
        # Phase 3: Delegate to MCPManager
        return self._mcp_manager_instance.get_mcp_manager()

    @property
    def _mcp_configs(self) -> dict[str, FlockMCPConfiguration]:
        """Get the dictionary of MCP configurations (Phase 3: delegated to MCPManager)."""
        return self._mcp_manager_instance.configs

    @property
    def _mcp_manager(self) -> FlockMCPClientManager | None:
        """Get the MCP manager instance."""
        return self._mcp_manager_instance._client_manager

    # Unified Tracing - Phase 3: Delegated to TracingManager --------------

    @property
    def _workflow_span(self) -> Any:
        """Get current workflow span (for backwards compatibility with tests)."""
        return self._tracing_manager.current_workflow_span

    @asynccontextmanager
    async def traced_run(self, name: str = "workflow") -> AsyncGenerator[Any, None]:
        """Context manager for wrapping an entire execution in a single unified trace.

        Phase 3: Delegates to TracingManager module.

        Args:
            name: Name for the workflow trace (default: "workflow")

        Yields:
            The workflow span for optional manual attribute setting

        Examples:
            async with flock.traced_run("pizza_workflow"):
                await flock.publish(pizza_idea)
                await flock.run_until_idle()
        """
        async with self._tracing_manager.traced_run(
            name=name, flock_id=str(id(self))
        ) as span:
            yield span

    @staticmethod
    def clear_traces(db_path: str = ".flock/traces.duckdb") -> dict[str, Any]:
        """Clear all traces from the DuckDB database.

        Phase 3: Delegates to TracingManager module.

        Args:
            db_path: Path to the DuckDB database file

        Returns:
            Dictionary with operation results (deleted_count, success, error)

        Examples:
            result = Flock.clear_traces()
            print(f"Deleted {result['deleted_count']} spans")
        """
        return TracingManager.clear_traces(db_path)

    # Runtime --------------------------------------------------------------

    async def run_until_idle(self, *, wait_for_input: bool = False) -> None:
        """Wait for all scheduled agent tasks to complete.

        This method blocks until the blackboard reaches a stable state where no
        agents are queued for execution. Essential for batch processing and ensuring
        all agent cascades complete before continuing.

        Args:
            wait_for_input: If True, waits for user input before returning (default: False).
                Useful for debugging or step-by-step execution.

        Note:
            Automatically resets circuit breaker counters and shuts down MCP connections
            when idle. Used with publish() for event-driven workflows.

        Examples:
            >>> # Event-driven workflow (recommended)
            >>> await flock.publish(task1)
            >>> await flock.publish(task2)
            >>> await flock.run_until_idle()  # Wait for all cascades
            >>> # All agents have finished processing

            >>> # Parallel batch processing
            >>> await flock.publish_many([task1, task2, task3])
            >>> await flock.run_until_idle()  # All tasks processed in parallel

            >>> # Step-by-step execution with user prompts
            >>> await flock.publish(task1)
            >>> await flock.run_until_idle(wait_for_input=True)  # Pauses for user input
            >>> await flock.publish(task2)
            >>> await flock.run_until_idle(wait_for_input=True)  # Pauses again

        See Also:
            - publish(): Event-driven artifact publishing
            - publish_many(): Batch publishing for parallel execution
            - invoke(): Direct agent invocation without cascade
        """
        while self._scheduler.pending_tasks:
            await asyncio.sleep(0.01)
            pending = {
                task for task in self._scheduler.pending_tasks if not task.done()
            }
            self._scheduler._tasks = pending

        # Phase 5A: Check for pending work using LifecycleManager properties
        pending_batches = self._lifecycle_manager.has_pending_batches
        pending_correlations = self._lifecycle_manager.has_pending_correlations

        # Ensure watchdog loops remain active while pending work exists.
        if pending_batches:
            await self._lifecycle_manager.start_batch_timeout_checker()

        if pending_correlations:
            await self._lifecycle_manager.start_correlation_cleanup()

        # If deferred work is still outstanding, consider the orchestrator quiescent for
        # now but leave watchdog tasks running to finish the job.
        if pending_batches or pending_correlations:
            self._agent_iteration_count.clear()
            return

        # Notify components that orchestrator reached idle state
        if self._component_runner.is_initialized:
            await self._component_runner.run_idle(self)

        # T068: Reset circuit breaker counters when idle
        self._agent_iteration_count.clear()

        # Automatically shutdown MCP connections when idle
        await self.shutdown(include_components=False)

        # Wait for user input if requested
        if wait_for_input:
            # Use asyncio.to_thread to avoid blocking the event loop
            # since input() is a blocking I/O operation
            await asyncio.to_thread(input, "Press any key to continue....")

    async def direct_invoke(
        self, agent: Agent, inputs: Sequence[BaseModel | Mapping[str, Any] | Artifact]
    ) -> list[Artifact]:
        artifacts = [
            self._normalize_input(value, produced_by="__direct__") for value in inputs
        ]
        for artifact in artifacts:
            self._mark_processed(artifact, agent)
            await self._persist_and_schedule(artifact)

        # Phase 5A: Use ContextBuilder to create execution context (consolidates duplicated pattern)
        # This implements the security boundary pattern (Phase 8 security fix)
        ctx = await self._context_builder.build_execution_context(
            agent=agent,
            artifacts=artifacts,
            correlation_id=artifacts[0].correlation_id
            if artifacts and artifacts[0].correlation_id
            else None,
            is_batch=False,
        )
        self._record_agent_run(agent)
        return await agent.execute(ctx, artifacts)

    async def arun(
        self, agent_builder: AgentBuilder, *inputs: BaseModel
    ) -> list[Artifact]:
        """Execute an agent with inputs and wait for all cascades to complete (async).

        Convenience method that combines direct agent invocation with run_until_idle().
        Useful for testing and synchronous request-response patterns.

        Args:
            agent_builder: Agent to execute (from flock.agent())
            *inputs: Input objects (BaseModel instances)

        Returns:
            Artifacts produced by the agent and any triggered cascades

        Examples:
            >>> # Test a single agent
            >>> flock = Flock("openai/gpt-4.1")
            >>> pizza_agent = flock.agent("pizza").consumes(Idea).publishes(Pizza)
            >>> results = await flock.arun(pizza_agent, Idea(topic="Margherita"))

            >>> # Multiple inputs
            >>> results = await flock.arun(
            ...     task_agent, Task(name="deploy"), Task(name="test")
            ... )

        Note:
            For event-driven workflows, prefer publish() + run_until_idle() for better
            control over execution timing and parallel processing.
        """
        artifacts = await self.direct_invoke(agent_builder.agent, list(inputs))
        await self.run_until_idle()
        return artifacts

    def run(self, agent_builder: AgentBuilder, *inputs: BaseModel) -> list[Artifact]:
        """Synchronous wrapper for arun() - executes agent and waits for completion.

        Args:
            agent_builder: Agent to execute (from flock.agent())
            *inputs: Input objects (BaseModel instances)

        Returns:
            Artifacts produced by the agent and any triggered cascades

        Examples:
            >>> # Synchronous execution (blocks until complete)
            >>> flock = Flock("openai/gpt-4o-mini")
            >>> agent = flock.agent("analyzer").consumes(Data).publishes(Report)
            >>> results = flock.run(agent, Data(value=42))

        Warning:
            Cannot be called from within an async context. Use arun() instead
            if already in an async function.
        """
        return asyncio.run(self.arun(agent_builder, *inputs))

    async def shutdown(self, *, include_components: bool = True) -> None:
        """Shutdown orchestrator and clean up resources.

        Args:
            include_components: Whether to invoke component shutdown hooks.
                Internal callers (e.g., run_until_idle) disable this to avoid
                tearing down component state between cascades.
        """
        if include_components and self._component_runner.is_initialized:
            await self._component_runner.run_shutdown(self)

        # Cancel background server task if running (non-blocking serve)
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
            # Note: _cleanup_server_callback will handle launcher.stop()

        # Phase 5A: Delegate lifecycle cleanup to LifecycleManager
        await self._lifecycle_manager.shutdown()

        # Phase 3: Delegate MCP cleanup to MCPManager
        await self._mcp_manager_instance.cleanup()

    def cli(self) -> Flock:
        # Placeholder for CLI wiring (rich UI in Step 3)
        return self

    async def serve(
        self,
        *,
        dashboard: bool = False,
        dashboard_v2: bool = False,
        host: str = "127.0.0.1",
        port: int = 8344,
        blocking: bool = True,
    ) -> Task[None] | None:
        """Start HTTP service for the orchestrator.

        Phase 3: Delegates to ServerManager module.

        Args:
            dashboard: Enable real-time dashboard with WebSocket support
            dashboard_v2: Launch the new dashboard v2 frontend (implies dashboard=True)
            host: Host to bind to (default: "127.0.0.1")
            port: Port to bind to (default: 8344)
            blocking: If True, blocks until server stops. If False, starts server
                in background and returns task handle (default: True)

        Returns:
            None if blocking=True, or Task handle if blocking=False

        Examples:
            await orchestrator.serve()
            await orchestrator.serve(dashboard=True)

            # Non-blocking mode
            task = await orchestrator.serve(dashboard=True, blocking=False)
            await orchestrator.publish(my_message)
            await orchestrator.run_until_idle()
        """
        return await ServerManager.serve(
            self,
            dashboard=dashboard,
            dashboard_v2=dashboard_v2,
            host=host,
            port=port,
            blocking=blocking,
        )

    # Scheduling -----------------------------------------------------------

    async def publish(
        self,
        obj: BaseModel | dict | Artifact,
        *,
        visibility: Visibility | None = None,
        correlation_id: str | None = None,
        partition_key: str | None = None,
        tags: set[str] | None = None,
        is_dashboard: bool = False,
        schedule_immediately: bool = True,
    ) -> Artifact:
        """Publish an artifact to the blackboard (event-driven).

        Delegates to ArtifactManager for normalization and persistence.
        """
        return await self._artifact_manager.publish(
            obj,
            visibility=visibility,
            correlation_id=correlation_id,
            partition_key=partition_key,
            tags=tags,
            is_dashboard=is_dashboard,
            schedule_immediately=schedule_immediately,
        )

    async def publish_many(
        self,
        objects: Iterable[BaseModel | dict | Artifact],
        schedule_immediately: bool = True,
        **kwargs: Any,
    ) -> list[Artifact]:
        """Publish multiple artifacts at once (event-driven).

        Delegates to ArtifactManager for batch publishing.
        """
        return await self._artifact_manager.publish_many(
            objects, schedule_immediately=schedule_immediately, **kwargs
        )

    # -----------------------------------------------------------------------------
    # NEW DIRECT INVOCATION API - Explicit Control
    # -----------------------------------------------------------------------------

    async def invoke(
        self,
        agent: Agent | AgentBuilder,
        obj: BaseModel,
        *,
        publish_outputs: bool = True,
        timeout: float | None = None,
    ) -> list[Artifact]:
        """Directly invoke a specific agent (bypasses subscription matching).

        This executes the agent immediately without checking subscriptions or
        predicates. Useful for testing or synchronous request-response patterns.

        Args:
            agent: Agent or AgentBuilder to invoke
            obj: Input object (BaseModel instance)
            publish_outputs: If True, publish outputs to blackboard for cascade
            timeout: Optional timeout in seconds

        Returns:
            Artifacts produced by the agent

        Warning:
            This bypasses subscription filters and predicates. For event-driven
            coordination, use publish() instead.

        Examples:
            >>> # Testing: Execute agent without triggering others
            >>> results = await orchestrator.invoke(
            ...     agent, Task(name="test", priority=5), publish_outputs=False
            ... )

            >>> # HTTP endpoint: Execute specific agent, allow cascade
            >>> results = await orchestrator.invoke(
            ...     movie_agent, Idea(topic="AI", genre="comedy"), publish_outputs=True
            ... )
            >>> await orchestrator.run_until_idle()
        """
        from asyncio import wait_for

        # Get Agent instance
        agent_obj = agent.agent if isinstance(agent, AgentBuilder) else agent

        # Create artifact (don't publish to blackboard yet)
        type_name = type_registry.name_for(type(obj))
        artifact = Artifact(
            type=type_name,
            payload=obj.model_dump(),
            produced_by="__direct__",
            visibility=PublicVisibility(),
        )

        # Phase 5A: Use ContextBuilder to create execution context (consolidates duplicated pattern)
        # This implements the security boundary pattern (Phase 8 security fix)
        ctx = await self._context_builder.build_execution_context(
            agent=agent_obj,
            artifacts=[artifact],
            correlation_id=artifact.correlation_id if artifact.correlation_id else None,
            is_batch=False,
        )
        self._record_agent_run(agent_obj)

        # Execute with optional timeout
        if timeout:
            execution = agent_obj.execute(ctx, [artifact])
            outputs = await wait_for(execution, timeout=timeout)
        else:
            outputs = await agent_obj.execute(ctx, [artifact])

        # Phase 6: Orchestrator publishes outputs (security fix)
        # Agents return artifacts, orchestrator validates and publishes
        if publish_outputs:
            for output in outputs:
                await self._persist_and_schedule(output)

        return outputs

    async def _persist_and_schedule(self, artifact: Artifact) -> None:
        """Delegate to ArtifactManager."""
        await self._artifact_manager.persist_and_schedule(artifact)

    # Component Hook Delegation ───

    async def _run_initialize(self) -> None:
        """Delegate to ComponentRunner module."""
        await self._component_runner.run_initialize(self)

    async def _run_artifact_published(self, artifact: Artifact) -> Artifact | None:
        """Delegate to ComponentRunner module."""
        return await self._component_runner.run_artifact_published(self, artifact)

    async def _run_before_schedule(
        self, artifact: Artifact, agent: Agent, subscription: Subscription
    ) -> ScheduleDecision:
        """Delegate to ComponentRunner module."""
        return await self._component_runner.run_before_schedule(
            self, artifact, agent, subscription
        )

    async def _run_collect_artifacts(
        self, artifact: Artifact, agent: Agent, subscription: Subscription
    ) -> CollectionResult:
        """Delegate to ComponentRunner module."""
        return await self._component_runner.run_collect_artifacts(
            self, artifact, agent, subscription
        )

    async def _run_before_agent_schedule(
        self, agent: Agent, artifacts: list[Artifact]
    ) -> list[Artifact] | None:
        """Delegate to ComponentRunner module."""
        return await self._component_runner.run_before_agent_schedule(
            self, agent, artifacts
        )

    async def _run_agent_scheduled(
        self, agent: Agent, artifacts: list[Artifact], task: Task[Any]
    ) -> None:
        """Delegate to ComponentRunner module."""
        await self._component_runner.run_agent_scheduled(self, agent, artifacts, task)

    async def _run_idle(self) -> None:
        """Delegate to ComponentRunner module."""
        await self._component_runner.run_idle(self)

    async def _run_shutdown(self) -> None:
        """Delegate to ComponentRunner module."""
        await self._component_runner.run_shutdown(self)

    @property
    def _components_initialized(self) -> bool:
        """Delegate to ComponentRunner module."""
        return self._component_runner.is_initialized

    # Scheduling ───────────────────────────────────────────────────

    async def _schedule_artifact(self, artifact: Artifact) -> None:
        """Delegate to AgentScheduler."""
        await self._scheduler.schedule_artifact(artifact)

    def _schedule_task(
        self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
    ) -> Task[Any]:
        """Delegate to AgentScheduler."""
        return self._scheduler.schedule_task(agent, artifacts, is_batch=is_batch)

    def _record_agent_run(self, agent: Agent) -> None:
        self._scheduler.record_agent_run(agent)

    def _mark_processed(self, artifact: Artifact, agent: Agent) -> None:
        self._scheduler.mark_processed(artifact, agent)

    def _seen_before(self, artifact: Artifact, agent: Agent) -> bool:
        return self._scheduler.seen_before(artifact, agent)

    async def _run_agent_task(
        self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
    ) -> None:
        correlation_id = artifacts[0].correlation_id if artifacts else None

        # Phase 5A: Use ContextBuilder to create execution context (consolidates duplicated pattern)
        # This implements the security boundary pattern (Phase 8 security fix)
        # COMPLEXITY REDUCTION: This reduces _run_agent_task from C(11) to likely B or A
        ctx = await self._context_builder.build_execution_context(
            agent=agent,
            artifacts=artifacts,
            correlation_id=correlation_id,
            is_batch=is_batch,
        )
        self._record_agent_run(agent)

        # Phase 6: Execute agent (returns artifacts, doesn't publish)
        # Wrap in try/catch to handle agent failures gracefully
        try:
            outputs = await agent.execute(ctx, artifacts)
        except asyncio.CancelledError:
            # Re-raise cancellations immediately (shutdown, user cancellation)
            # Do NOT treat these as errors - they're intentional interruptions
            self._logger.debug(
                f"Agent '{agent.name}' task cancelled (task={ctx.task_id})"
            )
            raise  # Propagate cancellation so task.cancelled() == True
        except Exception as exc:
            # Agent already called component.on_error hooks before re-raising
            # Now orchestrator publishes error artifact and continues workflow
            from flock.models.system_artifacts import WorkflowError

            error_artifact_data = WorkflowError(
                failed_agent=agent.name,
                error_type=type(exc).__name__,
                error_message=str(exc),
                timestamp=datetime.now(UTC),
                task_id=ctx.task_id,
            )

            # Build and publish error artifact with correlation_id
            from flock.core.artifacts import ArtifactSpec

            error_spec = ArtifactSpec.from_model(WorkflowError)
            error_artifact = error_spec.build(
                produced_by=f"orchestrator#{agent.name}",
                data=error_artifact_data.model_dump(),
                correlation_id=correlation_id,
            )

            await self._persist_and_schedule(error_artifact)

            # Log error but don't re-raise - workflow continues
            self._logger.error(
                f"Agent '{agent.name}' failed (task={ctx.task_id}): {exc}",
                exc_info=True,
            )
            return  # Exit early - no outputs to publish

        # Phase 6: Orchestrator publishes outputs (security fix)
        # This fixes Vulnerability #2 (WRITE Bypass) - agents can't bypass validation
        for output in outputs:
            await self._persist_and_schedule(output)

        if artifacts:
            try:
                timestamp = datetime.now(UTC)
                records = [
                    ConsumptionRecord(
                        artifact_id=artifact.id,
                        consumer=agent.name,
                        run_id=ctx.task_id,
                        correlation_id=str(correlation_id) if correlation_id else None,
                        consumed_at=timestamp,
                    )
                    for artifact in artifacts
                ]
                await self.store.record_consumptions(records)
            except NotImplementedError:
                pass
            except Exception as exc:  # pragma: no cover - defensive logging
                self._logger.exception("Failed to record artifact consumption: %s", exc)

    # Phase 1.2: Logic Operations Event Emission ----------------------------
    # Phase 5A: Delegated to EventEmitter module

    async def _emit_correlation_updated_event(
        self, *, agent_name: str, subscription_index: int, artifact: Artifact
    ) -> None:
        """Emit CorrelationGroupUpdatedEvent for real-time dashboard updates.

        Phase 5A: Delegates to EventEmitter module.

        Args:
            agent_name: Name of the agent with the JoinSpec subscription
            subscription_index: Index of the subscription in the agent's subscriptions list
            artifact: The artifact that triggered this update
        """
        await self._event_emitter.emit_correlation_updated(
            correlation_engine=self._correlation_engine,
            agent_name=agent_name,
            subscription_index=subscription_index,
            artifact=artifact,
        )

    async def _emit_batch_item_added_event(
        self,
        *,
        agent_name: str,
        subscription_index: int,
        subscription: Subscription,  # noqa: F821
        artifact: Artifact,
    ) -> None:
        """Emit BatchItemAddedEvent for real-time dashboard updates.

        Phase 5A: Delegates to EventEmitter module.

        Args:
            agent_name: Name of the agent with the BatchSpec subscription
            subscription_index: Index of the subscription in the agent's subscriptions list
            subscription: The subscription with BatchSpec configuration
            artifact: The artifact that triggered this update
        """
        await self._event_emitter.emit_batch_item_added(
            batch_engine=self._batch_engine,
            agent_name=agent_name,
            subscription_index=subscription_index,
            subscription=subscription,
            artifact=artifact,
        )

    # Batch Helpers --------------------------------------------------------
    # Phase 5A: Delegated to LifecycleManager module

    async def _check_batch_timeouts(self) -> None:
        """Check all batches for timeout expiry and flush expired batches.

        Phase 5A: Delegates to LifecycleManager module.
        """

        async def schedule_callback(
            agent_name: str, _subscription_index: int, artifacts: list[Artifact]
        ) -> None:
            """Callback to schedule agent task for expired batch."""
            agent = self._agents.get(agent_name)
            if agent is not None:
                self._schedule_task(agent, artifacts, is_batch=True)

        await self._lifecycle_manager.check_batch_timeouts(schedule_callback)

    async def _flush_all_batches(self) -> None:
        """Flush all partial batches (for shutdown - ensures zero data loss).

        Phase 5A: Delegates to LifecycleManager module.
        """

        async def schedule_callback(
            agent_name: str, _subscription_index: int, artifacts: list[Artifact]
        ) -> None:
            """Callback to schedule agent task for flushed batch."""
            agent = self._agents.get(agent_name)
            if agent is not None:
                self._schedule_task(agent, artifacts, is_batch=True)

        await self._lifecycle_manager.flush_all_batches(schedule_callback)
        # Wait for all scheduled tasks to complete
        await self.run_until_idle()

    # Helpers --------------------------------------------------------------

    def _normalize_input(
        self, value: BaseModel | Mapping[str, Any] | Artifact, *, produced_by: str
    ) -> Artifact:
        if isinstance(value, Artifact):
            return value
        if isinstance(value, BaseModel):
            model_cls = type(value)
            type_name = type_registry.register(model_cls)
            payload = value.model_dump()
        elif isinstance(value, Mapping):
            if "type" not in value:
                raise ValueError("Mapping input must contain 'type'.")
            type_name = value["type"]
            payload = value.get("payload", {})
        else:  # pragma: no cover - defensive
            raise TypeError("Unsupported input for direct invoke.")
        return Artifact(type=type_name, payload=payload, produced_by=produced_by)


@asynccontextmanager
async def start_orchestrator(orchestrator: Flock):  # pragma: no cover - CLI helper
    try:
        yield orchestrator
        await orchestrator.run_until_idle()
    finally:
        pass


__all__ = ["Flock", "start_orchestrator"]
