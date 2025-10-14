"""Blackboard orchestrator and scheduling runtime."""

from __future__ import annotations

import asyncio
import logging
import os
from asyncio import Task
from collections.abc import AsyncGenerator, Iterable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from pydantic import BaseModel

from flock.agent import Agent, AgentBuilder
from flock.artifact_collector import ArtifactCollector
from flock.artifacts import Artifact
from flock.batch_accumulator import BatchEngine
from flock.correlation_engine import CorrelationEngine
from flock.helper.cli_helper import init_console
from flock.logging.auto_trace import AutoTracedMeta
from flock.mcp import (
    FlockMCPClientManager,
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
    FlockMCPFeatureConfiguration,
    ServerParameters,
)
from flock.orchestrator_component import (
    CollectionResult,
    OrchestratorComponent,
    ScheduleDecision,
)
from flock.registry import type_registry
from flock.runtime import Context
from flock.store import BlackboardStore, ConsumptionRecord, InMemoryBlackboardStore
from flock.subscription import Subscription
from flock.visibility import AgentIdentity, PublicVisibility, Visibility


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
    ) -> None:
        """Initialize the Flock orchestrator for blackboard-based agent coordination.

        Args:
            model: Default LLM model for agents (e.g., "openai/gpt-4.1").
                Can be overridden per-agent. If None, uses DEFAULT_MODEL env var.
            store: Custom blackboard storage backend. Defaults to InMemoryBlackboardStore.
            max_agent_iterations: Circuit breaker limit to prevent runaway agent loops.
                Defaults to 1000 iterations per agent before reset.

        Examples:
            >>> # Basic initialization with default model
            >>> flock = Flock("openai/gpt-4.1")

            >>> # Custom storage backend
            >>> flock = Flock(
            ...     "openai/gpt-4o",
            ...     store=CustomBlackboardStore()
            ... )

            >>> # Circuit breaker configuration
            >>> flock = Flock(
            ...     "openai/gpt-4.1",
            ...     max_agent_iterations=500
            ... )
        """
        self._patch_litellm_proxy_imports()
        self._logger = logging.getLogger(__name__)
        self.model = model
        self.store: BlackboardStore = store or InMemoryBlackboardStore()
        self._agents: dict[str, Agent] = {}
        self._tasks: set[Task[Any]] = set()
        self._processed: set[tuple[str, str]] = set()
        self._lock = asyncio.Lock()
        self.metrics: dict[str, float] = {"artifacts_published": 0, "agent_runs": 0}
        # MCP integration
        self._mcp_configs: dict[str, FlockMCPConfiguration] = {}
        self._mcp_manager: FlockMCPClientManager | None = None
        # T068: Circuit breaker for runaway agents
        self.max_agent_iterations: int = max_agent_iterations
        self._agent_iteration_count: dict[str, int] = {}
        self.is_dashboard: bool = False
        # AND gate logic: Artifact collection for multi-type subscriptions
        self._artifact_collector = ArtifactCollector()
        # JoinSpec logic: Correlation engine for correlated AND gates
        self._correlation_engine = CorrelationEngine()
        # Background task for checking correlation expiry (time-based JoinSpec)
        self._correlation_cleanup_task: Task[Any] | None = None
        self._correlation_cleanup_interval: float = 0.1  # Check every 100ms
        # BatchSpec logic: Batch accumulator for size/timeout batching
        self._batch_engine = BatchEngine()
        # Background task for checking batch timeouts
        self._batch_timeout_task: Task[Any] | None = None
        self._batch_timeout_interval: float = 0.1  # Check every 100ms
        # Phase 1.2: WebSocket manager for real-time dashboard events (set by serve())
        self._websocket_manager: Any = None
        # Unified tracing support
        self._workflow_span = None
        self._auto_workflow_enabled = os.getenv("FLOCK_AUTO_WORKFLOW_TRACE", "false").lower() in {
            "true",
            "1",
            "yes",
            "on",
        }

        # Phase 2: OrchestratorComponent system
        self._components: list[OrchestratorComponent] = []
        self._components_initialized: bool = False

        # Auto-add built-in components
        from flock.orchestrator_component import (
            BuiltinCollectionComponent,
            CircuitBreakerComponent,
            DeduplicationComponent,
        )

        self.add_component(CircuitBreakerComponent(max_iterations=max_agent_iterations))
        self.add_component(DeduplicationComponent())
        self.add_component(BuiltinCollectionComponent())

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

        # Log component addition
        comp_name = component.name or component.__class__.__name__
        self._logger.info(
            f"Component added: name={comp_name}, "
            f"priority={component.priority}, total_components={len(self._components)}"
        )

        return self

    # MCP management -------------------------------------------------------

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
        if name in self._mcp_configs:
            raise ValueError(f"MCP server '{name}' is already registered.")

        # Detect transport type
        from flock.mcp.types import (
            SseServerParameters,
            StdioServerParameters,
            StreamableHttpServerParameters,
            WebsocketServerParameters,
        )

        if isinstance(connection_params, StdioServerParameters):
            transport_type = "stdio"
        elif isinstance(connection_params, WebsocketServerParameters):
            transport_type = "websockets"
        elif isinstance(connection_params, SseServerParameters):
            transport_type = "sse"
        elif isinstance(connection_params, StreamableHttpServerParameters):
            transport_type = "streamable_http"
        else:
            transport_type = "custom"

        mcp_roots = None
        if mount_points:
            from pathlib import Path as PathLib

            from flock.mcp.types import MCPRoot

            mcp_roots = []
            for path in mount_points:
                # Normalize the path
                if path.startswith("file://"):
                    # Already a file URI
                    uri = path
                    # Extract path from URI for name
                    path_str = path.replace("file://", "")
                # the test:// path-prefix is used by testing servers such as the mcp-everything server.
                elif path.startswith("test://"):
                    # Already a test URI
                    uri = path
                    # Extract path from URI for name
                    path_str = path.replace("test://", "")
                else:
                    # Convert to absolute path and create URI
                    abs_path = PathLib(path).resolve()
                    uri = f"file://{abs_path}"
                    path_str = str(abs_path)

                # Extract a meaningful name (last component of path)
                name = PathLib(path_str).name or path_str.rstrip("/").split("/")[-1] or "root"
                mcp_roots.append(MCPRoot(uri=uri, name=name))

        # Build configuration
        connection_config = FlockMCPConnectionConfiguration(
            max_retries=max_retries,
            connection_parameters=connection_params,
            transport_type=transport_type,
            read_timeout_seconds=read_timeout_seconds,
            mount_points=mcp_roots,
        )

        feature_config = FlockMCPFeatureConfiguration(
            tools_enabled=enable_tools_feature,
            prompts_enabled=enable_prompts_feature,
            sampling_enabled=enable_sampling_feature,
            roots_enabled=enable_roots_feature,
            tool_whitelist=tool_whitelist,
        )

        mcp_config = FlockMCPConfiguration(
            name=name,
            connection_config=connection_config,
            feature_config=feature_config,
        )

        self._mcp_configs[name] = mcp_config
        return self

    def get_mcp_manager(self) -> FlockMCPClientManager:
        """Get or create the MCP client manager.

        Architecture Decision: AD005 - Lazy Connection Establishment
        """
        if not self._mcp_configs:
            raise RuntimeError("No MCP servers registered. Call add_mcp() first.")

        if self._mcp_manager is None:
            self._mcp_manager = FlockMCPClientManager(self._mcp_configs)

        return self._mcp_manager

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
        while self._tasks:
            await asyncio.sleep(0.01)
            pending = {task for task in self._tasks if not task.done()}
            self._tasks = pending

        # Determine whether any deferred work (timeouts/cleanup) is still pending.
        pending_batches = any(
            accumulator.artifacts for accumulator in self._batch_engine.batches.values()
        )
        pending_correlations = any(
            groups and any(group.waiting_artifacts for group in groups.values())
            for groups in self._correlation_engine.correlation_groups.values()
        )

        # Ensure watchdog loops remain active while pending work exists.
        if pending_batches and (
            self._batch_timeout_task is None or self._batch_timeout_task.done()
        ):
            self._batch_timeout_task = asyncio.create_task(self._batch_timeout_checker_loop())

        if pending_correlations and (
            self._correlation_cleanup_task is None or self._correlation_cleanup_task.done()
        ):
            self._correlation_cleanup_task = asyncio.create_task(self._correlation_cleanup_loop())

        # If deferred work is still outstanding, consider the orchestrator quiescent for
        # now but leave watchdog tasks running to finish the job.
        if pending_batches or pending_correlations:
            self._agent_iteration_count.clear()
            return

        # Notify components that orchestrator reached idle state
        if self._components_initialized:
            await self._run_idle()

        # T068: Reset circuit breaker counters when idle
        self._agent_iteration_count.clear()

        # Automatically shutdown MCP connections when idle
        await self.shutdown(include_components=False)

    async def direct_invoke(
        self, agent: Agent, inputs: Sequence[BaseModel | Mapping[str, Any] | Artifact]
    ) -> list[Artifact]:
        artifacts = [self._normalize_input(value, produced_by="__direct__") for value in inputs]
        for artifact in artifacts:
            self._mark_processed(artifact, agent)
            await self._persist_and_schedule(artifact)
        ctx = Context(board=BoardHandle(self), orchestrator=self, task_id=str(uuid4()))
        self._record_agent_run(agent)
        return await agent.execute(ctx, artifacts)

    async def arun(self, agent_builder: AgentBuilder, *inputs: BaseModel) -> list[Artifact]:
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
            ...     task_agent,
            ...     Task(name="deploy"),
            ...     Task(name="test")
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
        if include_components and self._components_initialized:
            await self._run_shutdown()

        # Cancel correlation cleanup task if running
        if self._correlation_cleanup_task and not self._correlation_cleanup_task.done():
            self._correlation_cleanup_task.cancel()
            try:
                await self._correlation_cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel batch timeout checker if running
        if self._batch_timeout_task and not self._batch_timeout_task.done():
            self._batch_timeout_task.cancel()
            try:
                await self._batch_timeout_task
            except asyncio.CancelledError:
                pass

        if self._mcp_manager is not None:
            await self._mcp_manager.cleanup_all()
            self._mcp_manager = None

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

        All agents with matching subscriptions will be triggered according to
        their filters (type, predicates, visibility, etc).

        Args:
            obj: Object to publish (BaseModel instance, dict, or Artifact)
            visibility: Access control (defaults to PublicVisibility)
            correlation_id: Optional correlation ID for request tracing
            partition_key: Optional partition key for sharding
            tags: Optional tags for channel-based routing

        Returns:
            The published Artifact

        Examples:
            >>> # Publish a model instance (recommended)
            >>> task = Task(name="Deploy", priority=5)
            >>> await orchestrator.publish(task)

            >>> # Publish with custom visibility
            >>> await orchestrator.publish(
            ...     task,
            ...     visibility=PrivateVisibility(agents={"admin"})
            ... )

            >>> # Publish with tags for channel routing
            >>> await orchestrator.publish(task, tags={"urgent", "backend"})
        """
        self.is_dashboard = is_dashboard
        # Only show banner in CLI mode, not dashboard mode
        if not self.is_dashboard:
            try:
                init_console(clear_screen=True, show_banner=True, model=self.model)
            except (UnicodeEncodeError, UnicodeDecodeError):
                # Skip banner on Windows consoles with encoding issues (e.g., tests, CI)
                pass
        # Handle different input types
        if isinstance(obj, Artifact):
            # Already an artifact - publish as-is
            artifact = obj
        elif isinstance(obj, BaseModel):
            # BaseModel instance - get type from registry
            type_name = type_registry.name_for(type(obj))
            artifact = Artifact(
                type=type_name,
                payload=obj.model_dump(),
                produced_by="external",
                visibility=visibility or PublicVisibility(),
                correlation_id=correlation_id or uuid4(),
                partition_key=partition_key,
                tags=tags or set(),
            )
        elif isinstance(obj, dict):
            # Dict must have 'type' key
            if "type" not in obj:
                raise ValueError(
                    "Dict input must contain 'type' key. "
                    "Example: {'type': 'Task', 'name': 'foo', 'priority': 5}"
                )
            # Support both {'type': 'X', 'payload': {...}} and {'type': 'X', ...}
            type_name = obj["type"]
            if "payload" in obj:
                payload = obj["payload"]
            else:
                payload = {k: v for k, v in obj.items() if k != "type"}

            artifact = Artifact(
                type=type_name,
                payload=payload,
                produced_by="external",
                visibility=visibility or PublicVisibility(),
                correlation_id=correlation_id,
                partition_key=partition_key,
                tags=tags or set(),
            )
        else:
            raise TypeError(
                f"Cannot publish object of type {type(obj).__name__}. "
                "Expected BaseModel, dict, or Artifact."
            )

        # Persist and schedule matching agents
        await self._persist_and_schedule(artifact)
        return artifact

    async def publish_many(
        self, objects: Iterable[BaseModel | dict | Artifact], **kwargs: Any
    ) -> list[Artifact]:
        """Publish multiple artifacts at once (event-driven).

        Args:
            objects: Iterable of objects to publish
            **kwargs: Passed to each publish() call (visibility, tags, etc)

        Returns:
            List of published Artifacts

        Example:
            >>> tasks = [
            ...     Task(name="Deploy", priority=5),
            ...     Task(name="Test", priority=3),
            ...     Task(name="Document", priority=1),
            ... ]
            >>> await orchestrator.publish_many(tasks, tags={"sprint-3"})
        """
        artifacts = []
        for obj in objects:
            artifact = await self.publish(obj, **kwargs)
            artifacts.append(artifact)
        return artifacts

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
            ...     agent,
            ...     Task(name="test", priority=5),
            ...     publish_outputs=False
            ... )

            >>> # HTTP endpoint: Execute specific agent, allow cascade
            >>> results = await orchestrator.invoke(
            ...     movie_agent,
            ...     Idea(topic="AI", genre="comedy"),
            ...     publish_outputs=True
            ... )
            >>> await orchestrator.run_until_idle()
        """
        from asyncio import wait_for
        from uuid import uuid4

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

        # Execute agent directly
        ctx = Context(board=BoardHandle(self), orchestrator=self, task_id=str(uuid4()))
        self._record_agent_run(agent_obj)

        # Execute with optional timeout
        if timeout:
            execution = agent_obj.execute(ctx, [artifact])
            outputs = await wait_for(execution, timeout=timeout)
        else:
            outputs = await agent_obj.execute(ctx, [artifact])

        # Optionally publish outputs to blackboard
        if publish_outputs:
            for output in outputs:
                await self._persist_and_schedule(output)

        return outputs

    async def _persist_and_schedule(self, artifact: Artifact) -> None:
        await self.store.publish(artifact)
        self.metrics["artifacts_published"] += 1
        await self._schedule_artifact(artifact)

    # Component Hook Runners ───────────────────────────────────────

    async def _run_initialize(self) -> None:
        """Initialize all components in priority order (called once).

        Executes on_initialize hook for each component. Sets _components_initialized
        flag to prevent multiple initializations.
        """
        if self._components_initialized:
            return

        self._logger.info(f"Initializing {len(self._components)} orchestrator components")

        for component in self._components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(
                f"Initializing component: name={comp_name}, priority={component.priority}"
            )

            try:
                await component.on_initialize(self)
            except Exception as e:
                self._logger.exception(
                    f"Component initialization failed: name={comp_name}, error={e!s}"
                )
                raise

        self._components_initialized = True
        self._logger.info(f"All components initialized: count={len(self._components)}")

    async def _run_artifact_published(self, artifact: Artifact) -> Artifact | None:
        """Run on_artifact_published hooks (returns modified artifact or None to block).

        Components execute in priority order, each receiving the artifact from the
        previous component (chaining). If any component returns None, the artifact
        is blocked and scheduling stops.
        """
        current_artifact = artifact

        for component in self._components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(
                f"Running on_artifact_published: component={comp_name}, "
                f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
            )

            try:
                result = await component.on_artifact_published(self, current_artifact)

                if result is None:
                    self._logger.info(
                        f"Artifact blocked by component: component={comp_name}, "
                        f"artifact_type={current_artifact.type}, artifact_id={current_artifact.id}"
                    )
                    return None

                current_artifact = result
            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_artifact_published, error={e!s}"
                )
                raise

        return current_artifact

    async def _run_before_schedule(
        self, artifact: Artifact, agent: Agent, subscription: Subscription
    ) -> ScheduleDecision:
        """Run on_before_schedule hooks (returns CONTINUE, SKIP, or DEFER).

        Components execute in priority order. First component to return SKIP or
        DEFER stops execution and returns that decision.
        """
        from flock.orchestrator_component import ScheduleDecision

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_before_schedule: component={comp_name}, "
                f"agent={agent.name}, artifact_type={artifact.type}"
            )

            try:
                decision = await component.on_before_schedule(self, artifact, agent, subscription)

                if decision == ScheduleDecision.SKIP:
                    self._logger.info(
                        f"Scheduling skipped by component: component={comp_name}, "
                        f"agent={agent.name}, artifact_type={artifact.type}, decision=SKIP"
                    )
                    return ScheduleDecision.SKIP

                if decision == ScheduleDecision.DEFER:
                    self._logger.debug(
                        f"Scheduling deferred by component: component={comp_name}, "
                        f"agent={agent.name}, decision=DEFER"
                    )
                    return ScheduleDecision.DEFER

            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_before_schedule, error={e!s}"
                )
                raise

        return ScheduleDecision.CONTINUE

    async def _run_collect_artifacts(
        self, artifact: Artifact, agent: Agent, subscription: Subscription
    ) -> CollectionResult:
        """Run on_collect_artifacts hooks (returns first non-None result).

        Components execute in priority order. First component to return non-None
        wins (short-circuit). If all return None, default is immediate scheduling.
        """
        from flock.orchestrator_component import CollectionResult

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_collect_artifacts: component={comp_name}, "
                f"agent={agent.name}, artifact_type={artifact.type}"
            )

            try:
                result = await component.on_collect_artifacts(self, artifact, agent, subscription)

                if result is not None:
                    self._logger.debug(
                        f"Collection handled by component: component={comp_name}, "
                        f"complete={result.complete}, artifact_count={len(result.artifacts)}"
                    )
                    return result
            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_collect_artifacts, error={e!s}"
                )
                raise

        # Default: immediate scheduling with single artifact
        self._logger.debug(
            f"No component handled collection, using default: "
            f"agent={agent.name}, artifact_type={artifact.type}"
        )
        return CollectionResult.immediate([artifact])

    async def _run_before_agent_schedule(
        self, agent: Agent, artifacts: list[Artifact]
    ) -> list[Artifact] | None:
        """Run on_before_agent_schedule hooks (returns modified artifacts or None to block).

        Components execute in priority order, each receiving artifacts from the
        previous component (chaining). If any component returns None, scheduling
        is blocked.
        """
        current_artifacts = artifacts

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_before_agent_schedule: component={comp_name}, "
                f"agent={agent.name}, artifact_count={len(current_artifacts)}"
            )

            try:
                result = await component.on_before_agent_schedule(self, agent, current_artifacts)

                if result is None:
                    self._logger.info(
                        f"Agent scheduling blocked by component: component={comp_name}, "
                        f"agent={agent.name}"
                    )
                    return None

                current_artifacts = result
            except Exception as e:
                self._logger.exception(
                    f"Component hook failed: component={comp_name}, "
                    f"hook=on_before_agent_schedule, error={e!s}"
                )
                raise

        return current_artifacts

    async def _run_agent_scheduled(
        self, agent: Agent, artifacts: list[Artifact], task: Task[Any]
    ) -> None:
        """Run on_agent_scheduled hooks (notification only, non-blocking).

        Components execute in priority order. Exceptions are logged but don't
        prevent other components from executing or block scheduling.
        """
        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            self._logger.debug(
                f"Running on_agent_scheduled: component={comp_name}, "
                f"agent={agent.name}, artifact_count={len(artifacts)}"
            )

            try:
                await component.on_agent_scheduled(self, agent, artifacts, task)
            except Exception as e:
                self._logger.warning(
                    f"Component notification hook failed (non-critical): "
                    f"component={comp_name}, hook=on_agent_scheduled, error={e!s}"
                )
                # Don't propagate - this is a notification hook

    async def _run_idle(self) -> None:
        """Run on_orchestrator_idle hooks when orchestrator becomes idle.

        Components execute in priority order. Exceptions are logged but don't
        prevent other components from executing.
        """
        self._logger.debug(
            f"Running on_orchestrator_idle hooks: component_count={len(self._components)}"
        )

        for component in self._components:
            comp_name = component.name or component.__class__.__name__

            try:
                await component.on_orchestrator_idle(self)
            except Exception as e:
                self._logger.warning(
                    f"Component idle hook failed (non-critical): "
                    f"component={comp_name}, hook=on_orchestrator_idle, error={e!s}"
                )

    async def _run_shutdown(self) -> None:
        """Run on_shutdown hooks when orchestrator shuts down.

        Components execute in priority order. Exceptions are logged but don't
        prevent shutdown of other components (best-effort cleanup).
        """
        self._logger.info(f"Shutting down {len(self._components)} orchestrator components")

        for component in self._components:
            comp_name = component.name or component.__class__.__name__
            self._logger.debug(f"Shutting down component: name={comp_name}")

            try:
                await component.on_shutdown(self)
            except Exception as e:
                self._logger.exception(
                    f"Component shutdown failed: component={comp_name}, "
                    f"hook=on_shutdown, error={e!s}"
                )
                # Continue shutting down other components

    # Scheduling ───────────────────────────────────────────────────

    async def _schedule_artifact(self, artifact: Artifact) -> None:
        """Schedule agents for an artifact using component hooks.

        Refactored to use OrchestratorComponent hook system for extensibility.
        Components can modify artifact, control scheduling, and handle collection.
        """
        # Phase 3: Initialize components on first artifact
        if not self._components_initialized:
            await self._run_initialize()

        # Phase 3: Component hook - artifact published (can transform or block)
        artifact = await self._run_artifact_published(artifact)
        if artifact is None:
            return  # Artifact blocked by component

        for agent in self.agents:
            identity = agent.identity
            for subscription in agent.subscriptions:
                if not subscription.accepts_events():
                    continue

                # T066: Check prevent_self_trigger
                if agent.prevent_self_trigger and artifact.produced_by == agent.name:
                    continue  # Skip - agent produced this artifact (prevents feedback loops)

                # Visibility check
                if not self._check_visibility(artifact, identity):
                    continue

                # Subscription match check
                if not subscription.matches(artifact):
                    continue

                # Phase 3: Component hook - before schedule (circuit breaker, deduplication, etc.)
                from flock.orchestrator_component import ScheduleDecision

                decision = await self._run_before_schedule(artifact, agent, subscription)
                if decision == ScheduleDecision.SKIP:
                    continue  # Skip this subscription
                if decision == ScheduleDecision.DEFER:
                    continue  # Defer for later (batching/correlation)

                # Phase 3: Component hook - collect artifacts (handles AND gates, correlation, batching)
                collection = await self._run_collect_artifacts(artifact, agent, subscription)
                if not collection.complete:
                    continue  # Still collecting (AND gate, correlation, or batch incomplete)

                artifacts = collection.artifacts

                # Phase 3: Component hook - before agent schedule (final validation/transformation)
                artifacts = await self._run_before_agent_schedule(agent, artifacts)
                if artifacts is None:
                    continue  # Scheduling blocked by component

                # Complete! Schedule agent with collected artifacts
                # Schedule agent task
                is_batch_execution = subscription.batch is not None
                task = self._schedule_task(agent, artifacts, is_batch=is_batch_execution)

                # Phase 3: Component hook - agent scheduled (notification)
                await self._run_agent_scheduled(agent, artifacts, task)

    def _schedule_task(
        self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
    ) -> Task[Any]:
        """Schedule agent task and return the task handle."""
        task = asyncio.create_task(self._run_agent_task(agent, artifacts, is_batch=is_batch))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    def _record_agent_run(self, agent: Agent) -> None:
        self.metrics["agent_runs"] += 1

    def _mark_processed(self, artifact: Artifact, agent: Agent) -> None:
        key = (str(artifact.id), agent.name)
        self._processed.add(key)

    def _seen_before(self, artifact: Artifact, agent: Agent) -> bool:
        key = (str(artifact.id), agent.name)
        return key in self._processed

    async def _run_agent_task(
        self, agent: Agent, artifacts: list[Artifact], is_batch: bool = False
    ) -> None:
        correlation_id = artifacts[0].correlation_id if artifacts else uuid4()

        ctx = Context(
            board=BoardHandle(self),
            orchestrator=self,
            task_id=str(uuid4()),
            correlation_id=correlation_id,
            is_batch=is_batch,  # NEW!
        )
        self._record_agent_run(agent)
        await agent.execute(ctx, artifacts)

        if artifacts:
            try:
                timestamp = datetime.now(timezone.utc)
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

    async def _emit_correlation_updated_event(
        self, *, agent_name: str, subscription_index: int, artifact: Artifact
    ) -> None:
        """Emit CorrelationGroupUpdatedEvent for real-time dashboard updates.

        Called when an artifact is added to a correlation group that is not yet complete.

        Args:
            agent_name: Name of the agent with the JoinSpec subscription
            subscription_index: Index of the subscription in the agent's subscriptions list
            artifact: The artifact that triggered this update
        """
        # Only emit if dashboard is enabled
        if self._websocket_manager is None:
            return

        # Import _get_correlation_groups helper from dashboard service
        from flock.dashboard.service import _get_correlation_groups

        # Get current correlation groups state from engine
        groups = _get_correlation_groups(self._correlation_engine, agent_name, subscription_index)

        if not groups:
            return  # No groups to report (shouldn't happen, but defensive)

        # Find the group that was just updated (match by last updated time or artifact ID)
        # For now, we'll emit an event for the FIRST group that's still waiting
        # In practice, the artifact we just added should be in one of these groups
        for group_state in groups:
            if not group_state["is_complete"]:
                # Import CorrelationGroupUpdatedEvent
                from flock.dashboard.events import CorrelationGroupUpdatedEvent

                # Build and emit event
                event = CorrelationGroupUpdatedEvent(
                    agent_name=agent_name,
                    subscription_index=subscription_index,
                    correlation_key=group_state["correlation_key"],
                    collected_types=group_state["collected_types"],
                    required_types=group_state["required_types"],
                    waiting_for=group_state["waiting_for"],
                    elapsed_seconds=group_state["elapsed_seconds"],
                    expires_in_seconds=group_state["expires_in_seconds"],
                    expires_in_artifacts=group_state["expires_in_artifacts"],
                    artifact_id=str(artifact.id),
                    artifact_type=artifact.type,
                    is_complete=group_state["is_complete"],
                )

                # Broadcast via WebSocket
                await self._websocket_manager.broadcast(event)
                break  # Only emit one event per artifact addition

    async def _emit_batch_item_added_event(
        self,
        *,
        agent_name: str,
        subscription_index: int,
        subscription: Subscription,  # noqa: F821
        artifact: Artifact,
    ) -> None:
        """Emit BatchItemAddedEvent for real-time dashboard updates.

        Called when an artifact is added to a batch that hasn't reached flush threshold.

        Args:
            agent_name: Name of the agent with the BatchSpec subscription
            subscription_index: Index of the subscription in the agent's subscriptions list
            subscription: The subscription with BatchSpec configuration
            artifact: The artifact that triggered this update
        """
        # Only emit if dashboard is enabled
        if self._websocket_manager is None:
            return

        # Import _get_batch_state helper from dashboard service
        from flock.dashboard.service import _get_batch_state

        # Get current batch state from engine
        batch_state = _get_batch_state(
            self._batch_engine, agent_name, subscription_index, subscription.batch
        )

        if not batch_state:
            return  # No batch to report (shouldn't happen, but defensive)

        # Import BatchItemAddedEvent
        from flock.dashboard.events import BatchItemAddedEvent

        # Build and emit event
        event = BatchItemAddedEvent(
            agent_name=agent_name,
            subscription_index=subscription_index,
            items_collected=batch_state["items_collected"],
            items_target=batch_state.get("items_target"),
            items_remaining=batch_state.get("items_remaining"),
            elapsed_seconds=batch_state["elapsed_seconds"],
            timeout_seconds=batch_state.get("timeout_seconds"),
            timeout_remaining_seconds=batch_state.get("timeout_remaining_seconds"),
            will_flush=batch_state["will_flush"],
            artifact_id=str(artifact.id),
            artifact_type=artifact.type,
        )

        # Broadcast via WebSocket
        await self._websocket_manager.broadcast(event)

    # Batch Helpers --------------------------------------------------------

    async def _correlation_cleanup_loop(self) -> None:
        """Background task that periodically cleans up expired correlation groups.

        Runs continuously until all correlation groups are cleared or orchestrator shuts down.
        Checks every 100ms for time-based expired correlations and discards them.
        """
        try:
            while True:
                await asyncio.sleep(self._correlation_cleanup_interval)
                self._cleanup_expired_correlations()

                # Stop if no correlation groups remain
                if not self._correlation_engine.correlation_groups:
                    self._correlation_cleanup_task = None
                    break
        except asyncio.CancelledError:
            # Clean shutdown
            self._correlation_cleanup_task = None
            raise

    def _cleanup_expired_correlations(self) -> None:
        """Clean up all expired correlation groups across all subscriptions.

        Called periodically by background task to enforce time-based correlation windows.
        Discards incomplete correlations that have exceeded their time window.
        """
        # Get all active subscription keys
        for agent_name, subscription_index in list(
            self._correlation_engine.correlation_groups.keys()
        ):
            self._correlation_engine.cleanup_expired(agent_name, subscription_index)

    async def _batch_timeout_checker_loop(self) -> None:
        """Background task that periodically checks for batch timeouts.

        Runs continuously until all batches are cleared or orchestrator shuts down.
        Checks every 100ms for expired batches and flushes them.
        """
        try:
            while True:
                await asyncio.sleep(self._batch_timeout_interval)
                await self._check_batch_timeouts()

                # Stop if no batches remain
                if not self._batch_engine.batches:
                    self._batch_timeout_task = None
                    break
        except asyncio.CancelledError:
            # Clean shutdown
            self._batch_timeout_task = None
            raise

    async def _check_batch_timeouts(self) -> None:
        """Check all batches for timeout expiry and flush expired batches.

        This method is called periodically by the background timeout checker
        or manually (in tests) to enforce timeout-based batching.
        """
        expired_batches = self._batch_engine.check_timeouts()

        for agent_name, subscription_index in expired_batches:
            # Flush the expired batch
            artifacts = self._batch_engine.flush_batch(agent_name, subscription_index)

            if artifacts is None:
                continue

            # Get the agent
            agent = self._agents.get(agent_name)
            if agent is None:
                continue

            # Schedule agent with batched artifacts (timeout flush)
            self._schedule_task(agent, artifacts, is_batch=True)

    async def _flush_all_batches(self) -> None:
        """Flush all partial batches (for shutdown - ensures zero data loss)."""
        all_batches = self._batch_engine.flush_all()

        for agent_name, _subscription_index, artifacts in all_batches:
            # Get the agent
            agent = self._agents.get(agent_name)
            if agent is None:
                continue

            # Schedule agent with partial batch (shutdown flush)
            self._schedule_task(agent, artifacts, is_batch=True)

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

    def _check_visibility(self, artifact: Artifact, identity: AgentIdentity) -> bool:
        try:
            return artifact.visibility.allows(identity)
        except AttributeError:  # pragma: no cover - fallback for dict vis
            return True


@asynccontextmanager
async def start_orchestrator(orchestrator: Flock):  # pragma: no cover - CLI helper
    try:
        yield orchestrator
        await orchestrator.run_until_idle()
    finally:
        pass


__all__ = ["Flock", "start_orchestrator"]
