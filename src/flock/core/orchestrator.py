"""Blackboard orchestrator and scheduling runtime."""

from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Task
from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

from flock.artifact_collector import ArtifactCollector
from flock.artifacts import Artifact
from flock.batch_accumulator import BatchEngine
from flock.components.orchestrator import (
    CollectionResult,
    OrchestratorComponent,
    ScheduleDecision,
)
from flock.core.agent import Agent, AgentBuilder
from flock.correlation_engine import CorrelationEngine
from flock.helper.cli_helper import init_console
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
    ContextBuilder,
    EventEmitter,
    LifecycleManager,
    MCPManager,
)
from flock.registry import type_registry
from flock.store import BlackboardStore, ConsumptionRecord, InMemoryBlackboardStore
from flock.subscription import Subscription
from flock.visibility import PublicVisibility, Visibility


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

        Args:
            model: Default LLM model for agents (e.g., "openai/gpt-4.1").
                Can be overridden per-agent. If None, uses DEFAULT_MODEL env var.
            store: Custom blackboard storage backend. Defaults to InMemoryBlackboardStore.
            max_agent_iterations: Circuit breaker limit to prevent runaway agent loops.
                Defaults to 1000 iterations per agent before reset.
            context_provider: Global context provider for all agents (Phase 3 security fix).
                If None, agents use DefaultContextProvider. Can be overridden per-agent.

        Examples:
            >>> # Basic initialization with default model
            >>> flock = Flock("openai/gpt-4.1")

            >>> # Custom storage backend
            >>> flock = Flock("openai/gpt-4o", store=CustomBlackboardStore())

            >>> # Circuit breaker configuration
            >>> flock = Flock("openai/gpt-4.1", max_agent_iterations=500)

            >>> # Global context provider (Phase 3 security fix)
            >>> from flock.context_provider import DefaultContextProvider
            >>> flock = Flock(
            ...     "openai/gpt-4.1", context_provider=DefaultContextProvider()
            ... )
        """
        self._patch_litellm_proxy_imports()
        self._logger = logging.getLogger(__name__)
        self.model = model

        try:
            init_console(clear_screen=True, show_banner=True, model=self.model)
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Skip banner on Windows consoles with encoding issues (e.g., tests, CI)
            pass

        self.store: BlackboardStore = store or InMemoryBlackboardStore()
        self._agents: dict[str, Agent] = {}
        self._lock = asyncio.Lock()
        self.metrics: dict[str, float] = {"artifacts_published": 0, "agent_runs": 0}
        # Phase 3: Global context provider (security fix)
        self._default_context_provider = context_provider
        # MCP integration - Phase 3 extracted to MCPManager
        self._mcp_manager_instance = MCPManager()
        # T068: Circuit breaker for runaway agents
        self.max_agent_iterations: int = max_agent_iterations
        self._agent_iteration_count: dict[str, int] = {}
        self.is_dashboard: bool = False
        # AND gate logic: Artifact collection for multi-type subscriptions
        self._artifact_collector = ArtifactCollector()
        # JoinSpec logic: Correlation engine for correlated AND gates
        self._correlation_engine = CorrelationEngine()
        # BatchSpec logic: Batch accumulator for size/timeout batching
        self._batch_engine = BatchEngine()
        # Phase 1.2: WebSocket manager for real-time dashboard events (set by serve())
        self.__websocket_manager: Any = None  # Private storage, use property

        # Phase 5A: Initialize extracted modules for orchestration
        self._context_builder = ContextBuilder(
            store=self.store,
            default_context_provider=context_provider,
        )
        self._event_emitter = EventEmitter(websocket_manager=None)
        self._lifecycle_manager = LifecycleManager(
            correlation_engine=self._correlation_engine,
            batch_engine=self._batch_engine,
            cleanup_interval=0.1,
        )
        # Set batch timeout callback so lifecycle manager can trigger batch flushing
        self._lifecycle_manager.set_batch_timeout_callback(self._check_batch_timeouts)

        # Unified tracing support
        self._workflow_span = None
        self._auto_workflow_enabled = os.getenv(
            "FLOCK_AUTO_WORKFLOW_TRACE", "false"
        ).lower() in {
            "true",
            "1",
            "yes",
            "on",
        }

        # Phase 2: OrchestratorComponent system - Phase 3 extracted to ComponentRunner
        self._components: list[OrchestratorComponent] = []

        # Auto-add built-in components
        from flock.components.orchestrator import (
            BuiltinCollectionComponent,
            CircuitBreakerComponent,
            DeduplicationComponent,
        )

        self.add_component(CircuitBreakerComponent(max_iterations=max_agent_iterations))
        self.add_component(DeduplicationComponent())
        self.add_component(BuiltinCollectionComponent())

        # Phase 3: Initialize ComponentRunner with sorted components
        self._component_runner = ComponentRunner(self._components, self._logger)

        # Phase 3 (Complete): Initialize AgentScheduler and ArtifactManager
        self._scheduler = AgentScheduler(self, self._component_runner)
        self._artifact_manager = ArtifactManager(self, self.store, self._scheduler)

        # Log orchestrator initialization
        self._logger.debug("Orchestrator initialized: components=[]")

        if not model:
            self.model = os.getenv("DEFAULT_MODEL")

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

    # Unified Tracing ------------------------------------------------------

    @asynccontextmanager
    async def traced_run(self, name: str = "workflow") -> AsyncGenerator[Any, None]:
        """Context manager for wrapping an entire execution in a single unified trace.

        This creates a parent span that encompasses all operations (publish, run_until_idle, etc.)
        within the context, ensuring they all belong to the same trace_id for better observability.

        Args:
            name: Name for the workflow trace (default: "workflow")

        Yields:
            The workflow span for optional manual attribute setting

        Examples:
            # Explicit workflow tracing (recommended)
            async with flock.traced_run("pizza_workflow"):
                await flock.publish(pizza_idea)
                await flock.run_until_idle()
                # All operations now share the same trace_id!

            # Custom attributes
            async with flock.traced_run("data_pipeline") as span:
                span.set_attribute("pipeline.version", "2.0")
                await flock.publish(data)
                await flock.run_until_idle()
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(name) as span:
            # Set workflow-level attributes
            span.set_attribute("flock.workflow", True)
            span.set_attribute("workflow.name", name)
            span.set_attribute("workflow.flock_id", str(id(self)))

            # Store span for nested operations to use
            prev_workflow_span = self._workflow_span
            self._workflow_span = span

            try:
                yield span
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
            finally:
                # Restore previous workflow span
                self._workflow_span = prev_workflow_span

    @staticmethod
    def clear_traces(db_path: str = ".flock/traces.duckdb") -> dict[str, Any]:
        """Clear all traces from the DuckDB database.

        Useful for resetting debug sessions or cleaning up test data.

        Args:
            db_path: Path to the DuckDB database file (default: ".flock/traces.duckdb")

        Returns:
            Dictionary with operation results:
                - deleted_count: Number of spans deleted
                - success: Whether operation succeeded
                - error: Error message if failed

        Examples:
            # Clear all traces
            result = Flock.clear_traces()
            print(f"Deleted {result['deleted_count']} spans")

            # Custom database path
            result = Flock.clear_traces(".flock/custom_traces.duckdb")

            # Check if operation succeeded
            if result['success']:
                print("Traces cleared successfully!")
            else:
                print(f"Error: {result['error']}")
        """
        try:
            from pathlib import Path

            import duckdb

            db_file = Path(db_path)
            if not db_file.exists():
                return {
                    "success": False,
                    "deleted_count": 0,
                    "error": f"Database file not found: {db_path}",
                }

            # Connect and clear
            conn = duckdb.connect(str(db_file))
            try:
                # Get count before deletion
                count_result = conn.execute("SELECT COUNT(*) FROM spans").fetchone()
                deleted_count = count_result[0] if count_result else 0

                # Delete all spans
                conn.execute("DELETE FROM spans")

                # Vacuum to reclaim space
                conn.execute("VACUUM")

                return {"success": True, "deleted_count": deleted_count, "error": None}

            finally:
                conn.close()

        except Exception as e:
            return {"success": False, "deleted_count": 0, "error": str(e)}

    # Runtime --------------------------------------------------------------

    async def run_until_idle(self) -> None:
        """Wait for all scheduled agent tasks to complete.

        This method blocks until the blackboard reaches a stable state where no
        agents are queued for execution. Essential for batch processing and ensuring
        all agent cascades complete before continuing.

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
    ) -> None:
        """Start HTTP service for the orchestrator (blocking).

        Args:
            dashboard: Enable real-time dashboard with WebSocket support (default: False)
            dashboard_v2: Launch the new dashboard v2 frontend (implies dashboard=True)
            host: Host to bind to (default: "127.0.0.1")
            port: Port to bind to (default: 8344)

        Examples:
            # Basic HTTP API (no dashboard) - runs until interrupted
            await orchestrator.serve()

            # With dashboard (WebSocket + browser launch) - runs until interrupted
            await orchestrator.serve(dashboard=True)
        """
        if dashboard_v2:
            dashboard = True

        if not dashboard:
            # Standard service without dashboard
            from flock.service import BlackboardHTTPService

            service = BlackboardHTTPService(self)
            await service.run_async(host=host, port=port)
            return

        # Dashboard mode: integrate event collection and WebSocket
        from flock.dashboard.collector import DashboardEventCollector
        from flock.dashboard.launcher import DashboardLauncher
        from flock.dashboard.service import DashboardHTTPService
        from flock.dashboard.websocket import WebSocketManager

        # Create dashboard components
        websocket_manager = WebSocketManager()
        event_collector = DashboardEventCollector(store=self.store)
        event_collector.set_websocket_manager(websocket_manager)
        await event_collector.load_persistent_snapshots()

        # Store collector reference for agents added later
        self._dashboard_collector = event_collector
        # Store websocket manager for real-time event emission (Phase 1.2)
        self._websocket_manager = websocket_manager
        # Phase 5A: Set websocket manager on EventEmitter for dashboard updates
        self._event_emitter.set_websocket_manager(websocket_manager)

        # Phase 6+7: Set class-level WebSocket broadcast wrapper (dashboard mode)
        async def _broadcast_wrapper(event):
            """Isolated broadcast wrapper - no reference chain to orchestrator."""
            return await websocket_manager.broadcast(event)

        from flock.core import Agent

        Agent._websocket_broadcast_global = _broadcast_wrapper

        # Inject event collector into all existing agents
        for agent in self._agents.values():
            # Add dashboard collector with priority ordering handled by agent
            agent._add_utilities([event_collector])

        # Start dashboard launcher (npm process + browser)
        launcher_kwargs: dict[str, Any] = {"port": port}
        if dashboard_v2:
            dashboard_pkg_dir = Path(__file__).parent / "dashboard"
            launcher_kwargs["frontend_dir"] = dashboard_pkg_dir.parent / "frontend_v2"
            launcher_kwargs["static_dir"] = dashboard_pkg_dir / "static_v2"

        launcher = DashboardLauncher(**launcher_kwargs)
        launcher.start()

        # Create dashboard HTTP service
        service = DashboardHTTPService(
            orchestrator=self,
            websocket_manager=websocket_manager,
            event_collector=event_collector,
            use_v2=dashboard_v2,
        )

        # Store launcher for cleanup
        self._dashboard_launcher = launcher

        # Run service (blocking call)
        try:
            await service.run_async(host=host, port=port)
        finally:
            # Cleanup on exit
            launcher.stop()

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
        )

    async def publish_many(
        self, objects: Iterable[BaseModel | dict | Artifact], **kwargs: Any
    ) -> list[Artifact]:
        """Publish multiple artifacts at once (event-driven).

        Delegates to ArtifactManager for batch publishing.
        """
        return await self._artifact_manager.publish_many(objects, **kwargs)

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
        outputs = await agent.execute(ctx, artifacts)

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
