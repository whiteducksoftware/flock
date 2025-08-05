# src/flock/core/orchestration/flock_execution.py
"""Execution management functionality for Flock orchestrator."""

import asyncio
import contextvars
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, TypeVar

from box import Box
from opentelemetry import trace
from opentelemetry.baggage import set_baggage

from flock.config import DEFAULT_MODEL
from flock.core.context.context import FlockContext
from flock.core.context.context_manager import initialize_context
from flock.core.execution.local_executor import run_local_workflow
from flock.core.execution.temporal_executor import run_temporal_workflow
from flock.core.logging.logging import get_logger

if TYPE_CHECKING:
    from flock.core.flock import Flock
    from flock.core.flock_agent import FlockAgent

logger = get_logger("flock.execution")
tracer = trace.get_tracer(__name__)
_R = TypeVar("_R")


class FlockExecution:
    """Handles execution management for Flock including run, run_async, and execution coordination."""

    def __init__(self, flock: "Flock"):
        self.flock = flock

    def _run_sync(self, coro) -> _R:
        """Execute *coro* synchronously.

        * If no loop is running → ``asyncio.run``.
        * Otherwise run ``asyncio.run`` inside a fresh thread **with**
          context-vars propagation.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:  # no loop → simple
            return asyncio.run(coro)

        # A loop is already running – Jupyter / ASGI / etc.
        ctx = contextvars.copy_context()  # propagate baggage
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(ctx.run, asyncio.run, coro)
            try:
                return future.result()
            finally:
                if not future.done():
                    future.cancel()

    def run(
        self,
        agent: "FlockAgent | str | None" = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list["FlockAgent"] | None = None,
        servers: list[Any] | None = None,
        memo: dict[str, Any] | None = None,
    ) -> Box | dict:
        """Synchronous execution wrapper."""
        return self._run_sync(
            self.run_async(
                agent=agent,
                input=input,
                context=context,
                run_id=run_id,
                box_result=box_result,
                agents=agents,
                servers=servers,
                memo=memo,
            )
        )

    async def run_async(
        self,
        agent: "FlockAgent | str | None" = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list["FlockAgent"] | None = None,
        servers: list[Any] | None = None,
        memo: dict[str, Any] | None = None,
    ) -> Box | dict:
        """Entry point for running an agent system asynchronously."""
        # Import here to allow forward reference resolution
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent
        from flock.core.mcp.flock_mcp_server import (
            FlockMCPServer as ConcreteFlockServer,
        )

        with tracer.start_as_current_span("flock.run_async") as span:
            # Add passed servers so that agents have access to them.
            if servers:
                for server_obj in servers:
                    if isinstance(server_obj, ConcreteFlockServer):
                        self.flock.add_server(server=server_obj)
                    else:
                        logger.warning(
                            f"Item in 'servers' list is not a FlockMCPServer: {type(server_obj)}"
                        )

            # Add passed agents
            if agents:
                for agent_obj in agents:
                    if isinstance(agent_obj, ConcreteFlockAgent):
                        self.flock.add_agent(agent_obj)
                    else:
                        logger.warning(
                            f"Item in 'agents' list is not a FlockAgent: {type(agent_obj)}"
                        )

            # Determine starting agent name
            start_agent_name = self._resolve_start_agent(agent)

            # Setup execution context and input
            run_input = input if input is not None else self.flock._start_input
            effective_run_id = run_id or f"flockrun_{uuid.uuid4().hex[:8]}"

            # Set span attributes
            span.set_attribute("start_agent", start_agent_name)
            span.set_attribute("input", str(run_input))
            span.set_attribute("run_id", effective_run_id)
            span.set_attribute("enable_temporal", self.flock.enable_temporal)

            logger.info(
                f"Initiating Flock run '{self.flock.name}'. Start Agent: '{start_agent_name}'. Temporal: {self.flock.enable_temporal}."
            )

            try:
                # Setup execution context
                run_context = self._setup_execution_context(
                    context, start_agent_name, run_input, effective_run_id
                )

                # Execute workflow with server management
                async with self.flock._mgr:
                    logger.info("Entering managed server context. Servers starting up.")
                    logger.info(
                        "Starting agent execution",
                        agent=start_agent_name,
                        enable_temporal=self.flock.enable_temporal,
                    )

                    # Execute workflow using appropriate engine
                    result = await self._execute_workflow(run_context, memo)

                    # Set result attributes on span
                    span.set_attribute("result.type", str(type(result)))
                    result_str = str(result)
                    span.set_attribute(
                        "result.preview",
                        result_str[:1000] + ("..." if len(result_str) > 1000 else ""),
                    )

                    # Format and return result
                    return self._format_result(result, box_result)

            except Exception as e:
                logger.error(f"Flock run '{self.flock.name}' failed: {e}", exc_info=True)
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                # Return a consistent error structure
                error_output = {
                    "error": str(e),
                    "details": f"Flock run '{self.flock.name}' failed.",
                    "run_id": effective_run_id,
                    "start_agent": start_agent_name,
                }
                return Box(error_output) if box_result else error_output

    def _resolve_start_agent(self, agent: "FlockAgent | str | None") -> str:
        """Resolve the start agent name from various input types."""
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent
        from flock.core.registry import get_registry

        registry = get_registry()

        # Determine starting agent name
        start_agent_name: str | None = None
        if isinstance(agent, ConcreteFlockAgent):
            start_agent_name = agent.name
            if start_agent_name not in self.flock._agents:  # Add if not already present
                self.flock.add_agent(agent)
        elif isinstance(agent, str):
            start_agent_name = agent
        else:  # start_agent is None
            start_agent_name = self.flock._start_agent_name

        # Default to first agent if only one exists and none specified
        if not start_agent_name and len(self.flock._agents) == 1:
            start_agent_name = next(iter(self.flock._agents.keys()))
        elif not start_agent_name:
            raise ValueError(
                "No start_agent specified and multiple/no agents exist in the Flock instance."
            )

        # Check if start_agent is in agents
        if start_agent_name not in self.flock._agents:
            # Try loading from registry if not found locally yet
            reg_agent = registry.get_agent(start_agent_name)
            if reg_agent:
                self.flock.add_agent(reg_agent)
                logger.info(f"Loaded start agent '{start_agent_name}' from registry.")
            else:
                raise ValueError(
                    f"Start agent '{start_agent_name}' not found locally or in registry."
                )

        return start_agent_name

    def _setup_execution_context(
        self,
        context: FlockContext | None,
        start_agent_name: str,
        run_input: dict,
        run_id: str,
    ) -> FlockContext:
        """Setup the execution context for the workflow."""
        resolved_start_agent = self.flock._agents.get(start_agent_name)
        if not resolved_start_agent:  # Should have been handled by now
            raise ValueError(f"Start agent '{start_agent_name}' not found after checks.")

        run_context = context if context else FlockContext()
        set_baggage("run_id", run_id)  # Set for OpenTelemetry

        initialize_context(
            run_context,
            start_agent_name,
            run_input,
            run_id,
            not self.flock.enable_temporal,  # local_debug is inverse of enable_temporal
            self.flock.model or resolved_start_agent.model or DEFAULT_MODEL,
        )

        # Add agent definitions to context for routing/serialization within workflow
        for agent_name_iter, agent_instance_iter in self.flock.agents.items():
            agent_dict_repr = agent_instance_iter.to_dict()  # Agents handle their own serialization
            run_context.add_agent_definition(
                agent_type=type(agent_instance_iter),
                agent_name=agent_name_iter,
                agent_data=agent_dict_repr,
            )

        # Add temporal config to context if enabled
        if self.flock.enable_temporal and self.flock.temporal_config:
            run_context.set_variable(
                "flock.temporal_workflow_config",
                self.flock.temporal_config.model_dump(mode="json"),
            )

        return run_context

    async def _execute_workflow(
        self, run_context: FlockContext, memo: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute the workflow using the appropriate execution engine."""
        if not self.flock.enable_temporal:
            return await run_local_workflow(run_context, box_result=False)
        else:
            return await run_temporal_workflow(
                self.flock,  # Pass the Flock instance
                run_context,
                box_result=False,
                memo=memo,
            )

    def _format_result(self, result: dict[str, Any], box_result: bool) -> Box | dict:
        """Format the execution result."""
        if box_result:
            try:
                logger.debug("Boxing final result.")
                return Box(result)
            except ImportError:
                logger.warning("Box library not installed, returning raw dict.")
                return result
        else:
            return result
