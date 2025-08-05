# src/flock/core/flock.py
"""High-level orchestrator for managing and executing agents within the Flock framework."""

from __future__ import annotations  # Ensure forward references work

import uuid
from collections.abc import Callable, Sequence
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

from flock.core.mcp.flock_mcp_server import FlockMCPServer

with workflow.unsafe.imports_passed_through():
    from datasets import Dataset  # type: ignore

from opentelemetry import trace
from pandas import DataFrame  # type: ignore
from pydantic import BaseModel, Field

# Flock core components & utilities
from flock.config import DEFAULT_MODEL, TELEMETRY
from flock.core.api.custom_endpoint import (
    FlockEndpoint,  # Keep for type hinting custom_endpoints
)
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.serialization.serializable import Serializable
from flock.workflow.temporal_config import TemporalWorkflowConfig

# Import FlockAgent using TYPE_CHECKING to avoid circular import at runtime
if TYPE_CHECKING:
    # These imports are only for type hints
    from flock.core.flock_agent import FlockAgent


# Registry
from flock.core.registry import get_registry

try:
    import pandas as pd  # type: ignore

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None  # type: ignore
    PANDAS_AVAILABLE = False

logger = get_logger("flock.api")
TELEMETRY.setup_tracing()  # Setup OpenTelemetry
tracer = trace.get_tracer(__name__)
registry = get_registry()  # Get the registry instance

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
    _servers: dict[str, FlockMCPServer]

    # Note: _mgr is now handled by the server manager helper

    # Pydantic v2 model config
    model_config = {
        "arbitrary_types_allowed": True,
        # Assuming registry type might not be serializable by default
        "ignored_types": (type(registry),),
    }

    # --- COMPOSITION HELPERS (Lazy-Loaded) ---
    # Following the successful FlockAgent pattern

    @property
    def _execution(self):
        """Get the execution management helper (lazy-loaded)."""
        if not hasattr(self, '_execution_helper'):
            from flock.core.orchestration.flock_execution import FlockExecution
            self._execution_helper = FlockExecution(self)
        return self._execution_helper

    @property
    def _server_manager(self):
        """Get the server management helper (lazy-loaded)."""
        if not hasattr(self, '_server_manager_helper'):
            from flock.core.orchestration.flock_server_manager import (
                FlockServerManager,
            )
            self._server_manager_helper = FlockServerManager(self)
        return self._server_manager_helper

    @property
    def _batch_processor(self):
        """Get the batch processing helper (lazy-loaded)."""
        if not hasattr(self, '_batch_processor_helper'):
            from flock.core.orchestration.flock_batch_processor import (
                FlockBatchProcessor,
            )
            self._batch_processor_helper = FlockBatchProcessor(self)
        return self._batch_processor_helper

    @property
    def _evaluator(self):
        """Get the evaluation helper (lazy-loaded)."""
        if not hasattr(self, '_evaluator_helper'):
            from flock.core.orchestration.flock_evaluator import FlockEvaluator
            self._evaluator_helper = FlockEvaluator(self)
        return self._evaluator_helper

    @property
    def _web_server(self):
        """Get the web server helper (lazy-loaded)."""
        if not hasattr(self, '_web_server_helper'):
            from flock.core.orchestration.flock_web_server import FlockWebServer
            self._web_server_helper = FlockWebServer(self)
        return self._web_server_helper

    @property
    def _initialization(self):
        """Get the initialization helper (lazy-loaded)."""
        if not hasattr(self, '_initialization_helper'):
            from flock.core.orchestration.flock_initialization import (
                FlockInitialization,
            )
            self._initialization_helper = FlockInitialization(self)
        return self._initialization_helper

    @property
    def _mgr(self):
        """Get the internal server manager for compatibility."""
        return self._server_manager._internal_mgr

    def __init__(
        self,
        name: str | None = None,
        model: str | None = DEFAULT_MODEL,
        description: str | None = None,
        show_flock_banner: bool = True,
        enable_temporal: bool = False,
        enable_opik: bool = False,
        agents: list[FlockAgent] | None = None,
        servers: list[FlockMCPServer] | None = None,
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
        # Note: _mgr will be handled by the server manager helper

        # Delegate complex initialization to the initialization helper
        self._initialization.setup(agents=agents, servers=servers)

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
                agent=self.benchmark_agent_name,
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



    def add_server(self, server: FlockMCPServer) -> FlockMCPServer:
        """Adds a server instance to this Flock configuration and registry."""
        return self._server_manager.add_server(server)

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
        registry.register_agent(agent)  # Register globally

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
    def servers(self) -> dict[str, FlockMCPServer]:
        """Returns the dictionary of servers managed by this Flock instance."""
        return self._server_manager.servers

    def run(
        self,
        agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] | None = None,
        servers: list[FlockMCPServer] | None = None,
        memo: dict[str, Any] | None = None,
    ) -> Box | dict:
        """Synchronous execution wrapper."""
        return self._execution.run(
            agent=agent,
            input=input,
            context=context,
            run_id=run_id,
            box_result=box_result,
            agents=agents,
            servers=servers,
            memo=memo,
        )

    async def run_async(
        self,
        agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] | None = None,
        servers: list[FlockMCPServer] | None = None,
        memo: dict[str, Any] | None = None,
    ) -> Box | dict:
        """Entry point for running an agent system asynchronously."""
        return await self._execution.run_async(
            agent=agent,
            input=input,
            context=context,
            run_id=run_id,
            box_result=box_result,
            agents=agents,
            servers=servers,
            memo=memo,
        )

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
        return await self._batch_processor.run_batch_async(
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
        """Synchronous wrapper for batch processing."""
        return self._batch_processor.run_batch(
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
        return await self._evaluator.evaluate_async(
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
        """Synchronous wrapper for evaluation."""
        return self._evaluator.evaluate(
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

    # --- Server & CLI Starters (Delegation) ---

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
        """Launch an HTTP server that exposes the core REST API and, optionally, the browser-based UI."""
        return self._web_server.serve(
            host=host,
            port=port,
            server_name=server_name,
            ui=ui,
            chat=chat,
            chat_agent=chat_agent,
            chat_message_key=chat_message_key,
            chat_history_key=chat_history_key,
            chat_response_key=chat_response_key,
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
        return self._web_server.start_cli(
            start_agent=start_agent,
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
