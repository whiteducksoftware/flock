# src/flock/core/flock.py
"""High-level orchestrator for managing and executing agents within the Flock framework."""

from __future__ import annotations  # Ensure forward references work

import asyncio
import contextvars
import os
import uuid
from collections.abc import Awaitable, Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypeVar,
)

# Third-party imports
from box import Box
from temporalio import workflow

from flock.core.flock_server_manager import FlockServerManager
from flock.core.mcp.flock_mcp_server import FlockMCPServerBase

with workflow.unsafe.imports_passed_through():
    from datasets import Dataset  # type: ignore

    # Assuming run_local_workflow is correctly placed and importable
    from flock.core.execution.local_executor import (
        run_local_workflow,
    )

import opik
from opentelemetry import trace
from opentelemetry.baggage import get_baggage, set_baggage
from opik.integrations.dspy.callback import OpikCallback
from pandas import DataFrame  # type: ignore
from pydantic import BaseModel, Field

# Flock core components & utilities
from flock.config import DEFAULT_MODEL, TELEMETRY
from flock.core.api.custom_endpoint import (
    FlockEndpoint,  # Keep for type hinting custom_endpoints
)
from flock.core.context.context import FlockContext
from flock.core.context.context_manager import initialize_context

# Assuming run_temporal_workflow is correctly placed and importable
from flock.core.execution.temporal_executor import run_temporal_workflow
from flock.core.flock_evaluator import FlockEvaluator  # For type hint
from flock.core.logging.logging import get_logger
from flock.core.serialization.serializable import Serializable
from flock.core.util.cli_helper import init_console
from flock.workflow.temporal_config import TemporalWorkflowConfig

# Import FlockAgent using TYPE_CHECKING to avoid circular import at runtime
if TYPE_CHECKING:
    # These imports are only for type hints
    from flock.core.flock_agent import FlockAgent


# Registry
from flock.core.flock_registry import get_registry

try:
    import pandas as pd  # type: ignore

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    PANDAS_AVAILABLE = False

logger = get_logger("flock.api")
TELEMETRY.setup_tracing()  # Setup OpenTelemetry
tracer = trace.get_tracer(__name__)
FlockRegistry = get_registry()  # Get the registry instance

# Define TypeVar for generic class methods like from_dict
T = TypeVar("T", bound="Flock")
_R = TypeVar("_R")


class Flock(BaseModel, Serializable):
    """Orchestrator for managing and executing agent systems.

    Manages agent definitions, context, and execution flow (local or Temporal).
    Relies on FlockSerializer for serialization/deserialization logic.
    Inherits from Pydantic BaseModel and Serializable.
    """

    name: str | None = Field(
        default_factory=lambda: f"flock_{uuid.uuid4().hex[:8]}",
        description="A unique identifier for this Flock instance.",
    )
    model: str | None = Field(
        default=DEFAULT_MODEL,
        description="Default model identifier for agents if not specified otherwise.",
    )
    description: str | None = Field(
        default=None,
        description="A brief description of the purpose of this Flock configuration.",
    )
    enable_temporal: bool = Field(
        default=False,
        description="If True, execute workflows via Temporal; otherwise, run locally.",
    )
    enable_opik: bool = Field(
        default=False,
        description="If True, enable Opik for cost tracking and model management.",
    )
    show_flock_banner: bool = Field(
        default=True,
        description="If True, show the Flock banner on console interactions.",
    )
    # --- Temporal Configuration (Optional) ---
    temporal_config: TemporalWorkflowConfig | None = Field(
        default=None,
        description="Optional Temporal settings specific to the workflow execution for this Flock.",
    )
    # --- Temporal Dev/Test Setting ---
    temporal_start_in_process_worker: bool = Field(
        default=True,
        description="If True (default) and enable_temporal=True, start a temporary in-process worker for development/testing convenience. Set to False when using dedicated workers.",
    )

    benchmark_agent_name: str | None = Field(
        default=None,
        description="The name of the agent to use for the benchmark.",
    )
    benchmark_eval_field: str | None = Field(
        default=None,
        description="The output field to use for the benchmark.",
    )
    benchmark_input_field: str | None = Field(
        default=None,
        description="The input field to use for the benchmark.",
    )
    # Internal agent storage - not part of the Pydantic model for direct serialization
    # Marked with underscore to indicate it's managed internally and accessed via property
    _agents: dict[str, FlockAgent]
    _start_agent_name: str | None = None  # For potential pre-configuration
    _start_input: dict = {}  # For potential pre-configuration

    # Internal server storage - not part of the Pydantic model for direct serialization
    _servers: dict[str, FlockMCPServerBase]

    # Async context-manager for startup and teardown of servers
    # Not part of the pydantic model
    _mgr: FlockServerManager

    # Pydantic v2 model config
    model_config = {
        "arbitrary_types_allowed": True,
        # Assuming FlockRegistry type might not be serializable by default
        "ignored_types": (type(FlockRegistry),),
    }

    def _run_sync(self, coro: Awaitable[_R]) -> _R:
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
                setattr(stub, "general_settings", {})
                sys.modules["litellm.proxy.proxy_server"] = stub
        except Exception as e:
            # Safe to ignore; worst case litellm will log a warning
            logger.debug(f"Failed to stub litellm proxy_server: {e}")

    def __init__(
        self,
        name: str | None = None,
        model: str | None = DEFAULT_MODEL,
        description: str | None = None,
        show_flock_banner: bool = True,
        enable_temporal: bool = False,
        enable_opik: bool = False,
        agents: list[FlockAgent] | None = None,
        servers: list[FlockMCPServerBase] | None = None,
        temporal_config: TemporalWorkflowConfig | None = None,
        temporal_start_in_process_worker: bool = True,
        **kwargs,
    ):
        """Initialize the Flock orchestrator."""
        # Use provided name or generate default BEFORE super init if needed elsewhere
        effective_name = name or f"flock_{uuid.uuid4().hex[:8]}"

        # Initialize Pydantic fields
        super().__init__(
            name=effective_name,
            model=model,
            description=description,
            enable_temporal=enable_temporal,
            enable_opik=enable_opik,
            show_flock_banner=show_flock_banner,
            temporal_config=temporal_config,
            temporal_start_in_process_worker=temporal_start_in_process_worker,
            **kwargs,
        )

        # Initialize runtime attributes AFTER super().__init__()
        self._agents = {}
        self._servers = {}
        self._start_agent_name = None
        self._start_input = {}
        self._mgr = FlockServerManager()

        self._patch_litellm_proxy_imports()

        # Register passed servers
        # (need to be registered first so that agents can retrieve them from the registry)
        # This will also add them to the managed list of self._mgr
        if servers:
            from flock.core.mcp.flock_mcp_server import (
                FlockMCPServerBase as ConcreteFlockMCPServer,
            )

            for server in servers:
                if isinstance(server, ConcreteFlockMCPServer):
                    self.add_server(server)
                else:
                    logger.warning(
                        f"Item provided in 'servers' list is not a FlockMCPServer: {type(server)}"
                    )

        # Register passed agents
        if agents:
            from flock.core.flock_agent import (
                FlockAgent as ConcreteFlockAgent,  # Local import
            )

            for agent in agents:
                if isinstance(agent, ConcreteFlockAgent):
                    self.add_agent(agent)
                else:
                    logger.warning(
                        f"Item provided in 'agents' list is not a FlockAgent: {type(agent)}"
                    )

        # Initialize console if needed for banner
        if self.show_flock_banner:  # Check instance attribute
            init_console(clear_screen=True, show_banner=self.show_flock_banner)

        # Set Temporal debug environment variable
        self._set_temporal_debug_flag()

        # Ensure session ID exists in baggage
        self._ensure_session_id()

        FlockRegistry.discover_and_register_components()

        if self.enable_opik:
            import dspy

            opik.configure(use_local=True, automatic_approvals=True)
            opik_callback = OpikCallback(project_name=self.name, log_graph=True)
            dspy.settings.configure(
                callbacks=[opik_callback],
            )

        logger.info(
            "Flock instance initialized",
            name=self.name,
            model=self.model,
            enable_temporal=self.enable_temporal,
        )

    def prepare_benchmark(
        self,
        agent: FlockAgent | str | None = None,
        input_field: str | None = None,
        eval_field: str | None = None,
    ):
        """Prepare a benchmark for the Flock instance."""
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        logger.info(
            f"Preparing benchmark for Flock instance '{self.name}' with agent '{agent}'."
        )

        name = agent.name if isinstance(agent, ConcreteFlockAgent) else agent

        if self._agents.get(name) is None:
            raise ValueError(
                f"Agent '{name}' not found in Flock instance '{self.name}'."
            )

        self.benchmark_agent_name = name
        self.benchmark_eval_field = eval_field
        self.benchmark_input_field = input_field

    def inspect(self):
        """Inspect the Flock instance."""
        logger.info(
            f"Inspecting Flock instance '{self.name}' with start agent '{self.benchmark_agent_name}' and input '{input}'."
        )

        async def run(input: dict[str, Any]) -> dict[str, Any]:
            """Inspect the Flock instance."""
            logger.info(
                f"Inspecting Flock instance '{self.name}' with start agent '{self.benchmark_agent_name}' and input '{input}'."
            )
            msg_content = input.get("messages")[0].get("content")

            agent_input = {self.benchmark_input_field: msg_content}

            result = await self.run_async(
                start_agent=self.benchmark_agent_name,
                input=agent_input,
                box_result=False,
            )

            agent_output = result.get(
                self.benchmark_eval_field, "No answer found"
            )

            return {
                "output": agent_output,
            }

        return run

    def _set_temporal_debug_flag(self):
        """Set or remove LOCAL_DEBUG env var based on enable_temporal."""
        if not self.enable_temporal:
            if "LOCAL_DEBUG" not in os.environ:
                os.environ["LOCAL_DEBUG"] = "1"
                logger.debug(
                    "Set LOCAL_DEBUG environment variable for local execution."
                )
        elif "LOCAL_DEBUG" in os.environ:
            del os.environ["LOCAL_DEBUG"]
            logger.debug(
                "Removed LOCAL_DEBUG environment variable for Temporal execution."
            )

    def _ensure_session_id(self):
        """Ensure a session_id exists in the OpenTelemetry baggage."""
        session_id = get_baggage("session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            set_baggage("session_id", session_id)
            logger.debug(f"Generated new session_id: {session_id}")

    def add_server(self, server: FlockMCPServerBase) -> FlockMCPServerBase:
        """Adds a server instance to this Flock configuration and registry as well as set it up to be managed by self._mgr."""
        from flock.core.mcp.flock_mcp_server import (
            FlockMCPServerBase as ConcreteFlockMCPServer,
        )

        if not isinstance(server, ConcreteFlockMCPServer):
            raise TypeError("Provided object is not a FlockMCPServer instance.")
        if not server.config.name:
            raise ValueError("Server must have a name.")

        if server.config.name in self.servers:
            raise ValueError(
                f"Server with this name already exists. Name: '{server.config.name}'"
            )

        self._servers[server.config.name] = server
        FlockRegistry.register_server(server)  # Register globally.

        # Make sure that the server is also added to
        # the server_list managed by FlockServerManager
        if not self._mgr:
            self._mgr = FlockServerManager()

        # Prepare server to be managed by the FlockServerManager
        logger.info(f"Adding server '{server.config.name}' to managed list.")
        self._mgr.add_server_sync(server=server)
        logger.info(f"Server '{server.config.name}' is now on managed list.")

        logger.info(
            f"Server '{server.config.name}' added to Flock '{self.name}'"
        )
        return server

    def add_agent(self, agent: FlockAgent) -> FlockAgent:
        """Adds an agent instance to this Flock configuration and registry.

        This also registers all servers attached to the agent, if they have not been registered
        beforehand.
        """
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        if not isinstance(agent, ConcreteFlockAgent):
            raise TypeError("Provided object is not a FlockAgent instance.")
        if not agent.name:
            raise ValueError("Agent must have a name.")

        if agent.name in self._agents:
            # Allow re-adding the same instance, but raise error for different instance with same name
            if self._agents[agent.name] is not agent:
                raise ValueError(
                    f"Agent with name '{agent.name}' already exists with a different instance."
                )
            else:
                logger.debug(
                    f"Agent '{agent.name}' is already added. Skipping."
                )
                return agent  # Return existing agent

        self._agents[agent.name] = agent
        FlockRegistry.register_agent(agent)  # Register globally

        # Set default model if agent doesn't have one
        if agent.model is None:
            if self.model:
                agent.set_model(self.model)
                logger.debug(
                    f"Agent '{agent.name}' using Flock default model: {self.model}"
                )
            else:
                logger.warning(
                    f"Agent '{agent.name}' has no model and Flock default model is not set."
                )

        logger.info(f"Agent '{agent.name}' added to Flock '{self.name}'.")
        return agent

    @property
    def agents(self) -> dict[str, FlockAgent]:
        """Returns the dictionary of agents managed by this Flock instance."""
        return self._agents

    @property
    def servers(self) -> dict[str, FlockMCPServerBase]:
        """Returns the dictionary of servers managed by this Flock instance."""
        return self._servers

    def run(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] | None = None,
        servers: list[FlockMCPServerBase] | None = None,
        memo: dict[str, Any] | None = None,
        *,
        use_production_tools: bool = False,
    ) -> Box | dict:
        return self._run_sync(
            self.run_async(
                start_agent=start_agent,
                input=input,
                context=context,
                run_id=run_id,
                box_result=box_result,
                agents=agents,
                servers=servers,
                memo=memo,
                use_production_tools=use_production_tools,
            )
        )

    async def run_async(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] | None = None,
        servers: list[FlockMCPServerBase] | None = None,
        memo: dict[str, Any] | None = None,
        *,
        use_production_tools: bool = False,
    ) -> Box | dict:
        """Entry point for running an agent system asynchronously."""
        # Import here to allow forward reference resolution
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent
        from flock.core.mcp.flock_mcp_server import (
            FlockMCPServerBase as ConcreteFlockServer,
        )

        with tracer.start_as_current_span("flock.run_async") as span:
            # Add passed servers so that agents have access to them.
            if servers:
                for server_obj in servers:
                    if isinstance(server_obj, ConcreteFlockServer):
                        self.add_server(server=server_obj)
                    else:
                        logger.warning(
                            f"Item in 'servers' list is not a FlockMCPServer: {type(server_obj)}"
                        )

            # Add passed agents
            if agents:
                for agent_obj in agents:
                    if isinstance(agent_obj, ConcreteFlockAgent):
                        self.add_agent(agent_obj)
                    else:
                        logger.warning(
                            f"Item in 'agents' list is not a FlockAgent: {type(agent_obj)}"
                        )

            # Determine starting agent name
            start_agent_name: str | None = None
            if isinstance(start_agent, ConcreteFlockAgent):
                start_agent_name = start_agent.name
                if (
                    start_agent_name not in self._agents
                ):  # Add if not already present
                    self.add_agent(start_agent)
            elif isinstance(start_agent, str):
                start_agent_name = start_agent
            else:  # start_agent is None
                start_agent_name = self._start_agent_name

            # Default to first agent if only one exists and none specified
            if not start_agent_name and len(self._agents) == 1:
                start_agent_name = next(iter(self._agents.keys()))
            elif not start_agent_name:
                raise ValueError(
                    "No start_agent specified and multiple/no agents exist in the Flock instance."
                )

            # Check if start_agent is in agents
            if start_agent_name not in self._agents:
                # Try loading from registry if not found locally yet
                reg_agent = FlockRegistry.get_agent(start_agent_name)
                if reg_agent:
                    self.add_agent(reg_agent)
                    logger.info(
                        f"Loaded start agent '{start_agent_name}' from registry."
                    )
                else:
                    raise ValueError(
                        f"Start agent '{start_agent_name}' not found locally or in registry."
                    )

            run_input = input if input is not None else self._start_input
            effective_run_id = run_id or f"flockrun_{uuid.uuid4().hex[:8]}"

            span.set_attribute("start_agent", start_agent_name)
            span.set_attribute("input", str(run_input))
            span.set_attribute("run_id", effective_run_id)
            span.set_attribute("enable_temporal", self.enable_temporal)
            logger.info(
                f"Initiating Flock run '{self.name}'. Start Agent: '{start_agent_name}'. Temporal: {self.enable_temporal}."
            )

            try:
                resolved_start_agent = self._agents.get(start_agent_name)
                if not resolved_start_agent:  # Should have been handled by now
                    raise ValueError(
                        f"Start agent '{start_agent_name}' not found after checks."
                    )

                run_context = context if context else FlockContext()
                set_baggage("run_id", effective_run_id)  # Set for OpenTelemetry

                initialize_context(
                    run_context,
                    start_agent_name,
                    run_input,
                    effective_run_id,
                    not self.enable_temporal,  # local_debug is inverse of enable_temporal
                    self.model or resolved_start_agent.model or DEFAULT_MODEL,
                    use_production_tools,
                )
                # Add agent definitions to context for routing/serialization within workflow
                for agent_name_iter, agent_instance_iter in self.agents.items():
                    agent_dict_repr = (
                        agent_instance_iter.to_dict()
                    )  # Agents handle their own serialization
                    run_context.add_agent_definition(
                        agent_type=type(agent_instance_iter),
                        agent_name=agent_name_iter,
                        agent_data=agent_dict_repr,
                    )

                # Add temporal config to context if enabled
                if self.enable_temporal and self.temporal_config:
                    run_context.set_variable(
                        "flock.temporal_workflow_config",
                        self.temporal_config.model_dump(mode="json"),
                    )

                # At this point, initial setup is done
                # and flock is ready to execute it's agent_workflow.
                # Befor that happens, the ServerManager needs to
                # get the Servers up and running (Populate pools, build connections, start scripts, etc.)
                async with self._mgr:
                    # Enter the manager's async context,
                    # running it's __aenter__ method and starting all registered servers
                    # after this block ends, self._mgr's __aexit__ will be called
                    # all servers will be torn down.
                    logger.info(
                        f"Entering managed server context. Servers starting up."
                    )

                    logger.info(
                        "Starting agent execution",
                        agent=start_agent_name,
                        enable_temporal=self.enable_temporal,
                    )

                    # Execute workflow
                    if not self.enable_temporal:
                        result = await run_local_workflow(
                            run_context,
                            box_result=False,  # Boxing handled below
                        )
                    else:
                        result = await run_temporal_workflow(
                            self,  # Pass the Flock instance
                            run_context,
                            box_result=False,  # Boxing handled below
                            memo=memo,
                        )

                    span.set_attribute("result.type", str(type(result)))
                    result_str = str(result)
                    span.set_attribute(
                        "result.preview",
                        result_str[:1000]
                        + ("..." if len(result_str) > 1000 else ""),
                    )

                    if box_result:
                        try:
                            logger.debug("Boxing final result.")
                            return Box(result)
                        except ImportError:
                            logger.warning(
                                "Box library not installed, returning raw dict."
                            )
                            return result
                    else:
                        return result

                        # The context of self._mgr ends here, meaning, that servers will
                        # be cleaned up and shut down.

            except Exception as e:
                logger.error(
                    f"Flock run '{self.name}' failed: {e}", exc_info=True
                )
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                # Return a consistent error structure
                error_output = {
                    "error": str(e),
                    "details": f"Flock run '{self.name}' failed.",
                    "run_id": effective_run_id,
                    "start_agent": start_agent_name,
                }
                return Box(error_output) if box_result else error_output

    # --- Batch Processing (Delegation) ---
    async def run_batch_async(
        self,
        start_agent: FlockAgent | str,
        batch_inputs: list[dict[str, Any]] | DataFrame | str,
        input_mapping: dict[str, str] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        box_results: bool = True,
        return_errors: bool = False,
        silent_mode: bool = False,
        write_to_csv: str | None = None,
        hide_columns: list[str] | None = None,
        delimiter: str = ",",
    ) -> list[Box | dict | None | Exception]:
        """Runs the specified agent/workflow for each item in a batch asynchronously (delegated)."""
        # Import processor locally
        from flock.core.execution.batch_executor import BatchProcessor

        processor = BatchProcessor(self)  # Pass self
        return await processor.run_batch_async(
            start_agent=start_agent,
            batch_inputs=batch_inputs,
            input_mapping=input_mapping,
            static_inputs=static_inputs,
            parallel=parallel,
            max_workers=max_workers,
            use_temporal=use_temporal,
            box_results=box_results,
            return_errors=return_errors,
            silent_mode=silent_mode,
            write_to_csv=write_to_csv,
            hide_columns=hide_columns,
            delimiter=delimiter,
        )

    def run_batch(
        self,
        start_agent: FlockAgent | str,
        batch_inputs: list[dict[str, Any]] | DataFrame | str,
        input_mapping: dict[str, str] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        box_results: bool = True,
        return_errors: bool = False,
        silent_mode: bool = False,
        write_to_csv: str | None = None,
        hide_columns: list[str] | None = None,
        delimiter: str = ",",
    ) -> list[Box | dict | None | Exception]:
        return self._run_sync(
            self.run_batch_async(
                start_agent=start_agent,
                batch_inputs=batch_inputs,
                input_mapping=input_mapping,
                static_inputs=static_inputs,
                parallel=parallel,
                max_workers=max_workers,
                use_temporal=use_temporal,
                box_results=box_results,
                return_errors=return_errors,
                silent_mode=silent_mode,
                write_to_csv=write_to_csv,
                hide_columns=hide_columns,
                delimiter=delimiter,
            )
        )

    # --- Evaluation (Delegation) ---
    async def evaluate_async(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | Dataset,  # type: ignore
        start_agent: FlockAgent | str,
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            str
            | Callable[[Any, Any], bool | float | dict[str, Any]]
            | FlockAgent  # Type hint only
            | FlockEvaluator  # Type hint only
        ],
        metric_configs: dict[str, dict[str, Any]] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        error_handling: Literal["raise", "skip", "log"] = "log",
        output_file: str | Path | None = None,
        return_dataframe: bool = True,
        silent_mode: bool = False,
        metadata_columns: list[str] | None = None,
    ) -> DataFrame | list[dict[str, Any]]:  # type: ignore
        """Evaluates the Flock's performance against a dataset (delegated)."""
        # Import processor locally
        from flock.core.execution.evaluation_executor import (
            EvaluationExecutor,
        )

        processor = EvaluationExecutor(self)  # Pass self
        return await processor.evaluate_async(
            dataset=dataset,
            start_agent=start_agent,
            input_mapping=input_mapping,
            answer_mapping=answer_mapping,
            metrics=metrics,
            metric_configs=metric_configs,
            static_inputs=static_inputs,
            parallel=parallel,
            max_workers=max_workers,
            use_temporal=use_temporal,
            error_handling=error_handling,
            output_file=output_file,
            return_dataframe=return_dataframe,
            silent_mode=silent_mode,
            metadata_columns=metadata_columns,
        )

    def evaluate(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | Dataset,  # type: ignore
        start_agent: FlockAgent | str,
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            str
            | Callable[[Any, Any], bool | float | dict[str, Any]]
            | FlockAgent  # Type hint only
            | FlockEvaluator  # Type hint only
        ],
        metric_configs: dict[str, dict[str, Any]] | None = None,
        static_inputs: dict[str, Any] | None = None,
        parallel: bool = True,
        max_workers: int = 5,
        use_temporal: bool | None = None,
        error_handling: Literal["raise", "skip", "log"] = "log",
        output_file: str | Path | None = None,
        return_dataframe: bool = True,
        silent_mode: bool = False,
        metadata_columns: list[str] | None = None,
    ) -> DataFrame | list[dict[str, Any]]:  # type: ignore
        return self._run_sync(
            self.evaluate_async(
                dataset=dataset,
                start_agent=start_agent,
                input_mapping=input_mapping,
                answer_mapping=answer_mapping,
                metrics=metrics,
                metric_configs=metric_configs,
                static_inputs=static_inputs,
                parallel=parallel,
                max_workers=max_workers,
                use_temporal=use_temporal,
                error_handling=error_handling,
                output_file=output_file,
                return_dataframe=return_dataframe,
                silent_mode=silent_mode,
                metadata_columns=metadata_columns,
            )
        )

    # --- Server & CLI Starters (Delegation) ---
    def start_api(
        self,
        host: str = "127.0.0.1",
        port: int = 8344,
        server_name: str = "Flock Server",
        create_ui: bool = True,  # Default to True for the integrated experience
        ui_theme: str | None = None,
        custom_endpoints: Sequence[FlockEndpoint]
        | dict[tuple[str, list[str] | None], Callable[..., Any]]
        | None = None,
    ) -> None:
        """Starts a unified REST API server and/or Web UI for this Flock instance."""
        import warnings

        warnings.warn(
            "start_api() is deprecated and will be removed in a future release. "
            "Use serve() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Delegate to the new serve() method (create_ui maps to ui)
        return self.serve(
            host=host,
            port=port,
            server_name=server_name,
            ui=create_ui,
            ui_theme=ui_theme,
            custom_endpoints=custom_endpoints,
        )

    # ------------------------------------------------------------------
    # New preferred method name
    # ------------------------------------------------------------------

    def serve(
        self,
        host: str = "127.0.0.1",
        port: int = 8344,
        server_name: str = "Flock Server",
        ui: bool = True,
        chat: bool = False,
        chat_agent: str | None = None,  # Reserved for future real agent chat
        chat_message_key: str = "message",
        chat_history_key: str = "history",
        chat_response_key: str = "response",
        ui_theme: str | None = None,
        custom_endpoints: Sequence[FlockEndpoint]
        | dict[tuple[str, list[str] | None], Callable[..., Any]]
        | None = None,
    ) -> None:
        """Launch an HTTP server that exposes the core REST API and, optionally, the
        browser-based UI.

        Args:
            host: Bind address for the server (default "127.0.0.1").
            port: TCP port to listen on (default 8344).
            server_name: Title shown in the OpenAPI docs / logs.
            ui: If True (default) the Pico/HTMX web UI routes are included. If False
                 only the JSON API groups (core & custom) are served.
            chat: If True, enable chat routes.
            chat_agent: Name of the agent to use for chat.
            chat_message_key: Key for chat message in input.
            chat_history_key: Key for chat history in input.
            chat_response_key: Key for chat response in output.
            ui_theme: Optional UI theme name or "random".
            custom_endpoints: Additional API routes to add, either as a list of
                 FlockEndpoint objects or the legacy dict format.
        """
        try:
            from flock.webapp.run import start_unified_server
        except ImportError:
            logger.error(
                "Web application components not found (flock.webapp.run). "
                "Cannot start HTTP server. Ensure webapp dependencies are installed."
            )
            return

        logger.info(
            f"Attempting to start server for Flock '{self.name}' on {host}:{port}. UI enabled: {ui}"
        )

        start_unified_server(
            flock_instance=self,
            host=host,
            port=port,
            server_title=server_name,
            enable_ui_routes=ui,
            enable_chat_routes=chat,
            ui_theme=ui_theme,
            custom_endpoints=custom_endpoints,
        )

    def start_cli(
        self,
        start_agent: FlockAgent
        | str
        | None = None,  # Added start_agent to match method signature in file_26
        server_name: str = "Flock CLI",
        show_results: bool = False,
        edit_mode: bool = False,
    ) -> None:
        """Starts an interactive CLI for this Flock instance."""
        # Import runner locally
        try:
            from flock.cli.runner import start_flock_cli
        except ImportError:
            logger.error(
                "CLI components not found. Cannot start CLI. "
                "Ensure CLI dependencies are installed."
            )
            return

        # The start_flock_cli function in file_50 doesn't take start_agent
        # but the original docs for start_cli did.
        # For now, I'll pass it through, assuming start_flock_cli will be updated or ignore it.
        # If start_agent is crucial here, start_flock_cli needs to handle it.
        logger.info(f"Starting CLI for Flock '{self.name}'...")
        start_flock_cli(
            flock=self,  # Pass the Flock instance
            # start_agent=start_agent, # This argument is not in the definition of start_flock_cli in file_50
            server_name=server_name,
            show_results=show_results,
            edit_mode=edit_mode,
        )

    # --- Serialization Delegation Methods ---
    def to_dict(self, path_type: str = "relative") -> dict[str, Any]:
        """Serialize Flock instance to dictionary using FlockSerializer."""
        from flock.core.serialization.flock_serializer import FlockSerializer

        return FlockSerializer.serialize(self, path_type=path_type)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize Flock instance from dictionary using FlockSerializer."""
        from flock.core.serialization.flock_serializer import FlockSerializer

        return FlockSerializer.deserialize(cls, data)

    # --- Static Method Loader (Delegates to loader module) ---
    @staticmethod
    def load_from_file(file_path: str) -> Flock:  # Ensure return type is Flock
        """Load a Flock instance from various file formats (delegates to loader)."""
        from flock.core.util.loader import load_flock_from_file

        loaded_flock = load_flock_from_file(file_path)
        # Ensure the loaded object is indeed a Flock instance
        if not isinstance(loaded_flock, Flock):
            raise TypeError(
                f"Loaded object from {file_path} is not a Flock instance, but {type(loaded_flock)}"
            )
        return loaded_flock
