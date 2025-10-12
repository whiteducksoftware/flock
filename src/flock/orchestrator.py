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
from flock.artifacts import Artifact
from flock.helper.cli_helper import init_console
from flock.logging.auto_trace import AutoTracedMeta
from flock.mcp import (
    FlockMCPClientManager,
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
    FlockMCPFeatureConfiguration,
    ServerParameters,
)
from flock.registry import type_registry
from flock.runtime import Context
from flock.store import BlackboardStore, ConsumptionRecord, InMemoryBlackboardStore
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
        # Unified tracing support
        self._workflow_span = None
        self._auto_workflow_enabled = os.getenv("FLOCK_AUTO_WORKFLOW_TRACE", "false").lower() in {
            "true",
            "1",
            "yes",
            "on",
        }
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
        # T068: Reset circuit breaker counters when idle
        self._agent_iteration_count.clear()

        # Automatically shutdown MCP connections when idle
        await self.shutdown()

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

    async def shutdown(self) -> None:
        """Shutdown orchestrator and clean up resources."""
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

        # Inject event collector into all existing agents
        for agent in self._agents.values():
            # Insert at beginning of utilities list (highest priority)
            agent.utilities.insert(0, event_collector)

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
            init_console(clear_screen=True, show_banner=True, model=self.model)
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

    # Keep publish_external as deprecated alias
    async def publish_external(
        self,
        type_name: str,
        payload: dict[str, Any],
        *,
        visibility: Visibility | None = None,
        correlation_id: str | None = None,
        partition_key: str | None = None,
        tags: set[str] | None = None,
    ) -> Artifact:
        """Deprecated: Use publish() instead.

        This method will be removed in v2.0.
        """
        import warnings

        warnings.warn(
            "publish_external() is deprecated. Use publish(obj) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self.publish(
            {"type": type_name, "payload": payload},
            visibility=visibility,
            correlation_id=correlation_id,
            partition_key=partition_key,
            tags=tags,
        )

    async def _persist_and_schedule(self, artifact: Artifact) -> None:
        await self.store.publish(artifact)
        self.metrics["artifacts_published"] += 1
        await self._schedule_artifact(artifact)

    async def _schedule_artifact(self, artifact: Artifact) -> None:
        for agent in self.agents:
            identity = agent.identity
            for subscription in agent.subscriptions:
                if not subscription.accepts_events():
                    continue
                # T066: Check prevent_self_trigger
                if agent.prevent_self_trigger and artifact.produced_by == agent.name:
                    continue  # Skip - agent produced this artifact (prevents feedback loops)
                # T068: Circuit breaker - check iteration limit
                iteration_count = self._agent_iteration_count.get(agent.name, 0)
                if iteration_count >= self.max_agent_iterations:
                    # Agent hit iteration limit - possible infinite loop
                    continue
                if not self._check_visibility(artifact, identity):
                    continue
                if not subscription.matches(artifact):
                    continue
                if self._seen_before(artifact, agent):
                    continue
                # T068: Increment iteration counter
                self._agent_iteration_count[agent.name] = iteration_count + 1
                self._mark_processed(artifact, agent)
                self._schedule_task(agent, [artifact])

    def _schedule_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
        task = asyncio.create_task(self._run_agent_task(agent, artifacts))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _record_agent_run(self, agent: Agent) -> None:
        self.metrics["agent_runs"] += 1

    def _mark_processed(self, artifact: Artifact, agent: Agent) -> None:
        key = (str(artifact.id), agent.name)
        self._processed.add(key)

    def _seen_before(self, artifact: Artifact, agent: Agent) -> bool:
        key = (str(artifact.id), agent.name)
        return key in self._processed

    async def _run_agent_task(self, agent: Agent, artifacts: list[Artifact]) -> None:
        correlation_id = artifacts[0].correlation_id if artifacts else uuid4()

        ctx = Context(
            board=BoardHandle(self),
            orchestrator=self,
            task_id=str(uuid4()),
            correlation_id=correlation_id,  # NEW!
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
