# src/flock/core/flock.py
"""High-level orchestrator for managing and executing agents within the Flock framework."""

from __future__ import annotations  # Ensure forward references work

import asyncio
import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypeVar,
)

# Third-party imports
from box import Box
from datasets import Dataset
from opentelemetry import trace
from opentelemetry.baggage import get_baggage, set_baggage
from pandas import DataFrame
from pydantic import BaseModel, Field

# Flock core components & utilities
from flock.config import DEFAULT_MODEL, TELEMETRY
from flock.core.context.context import FlockContext
from flock.core.context.context_manager import initialize_context
from flock.core.execution.local_executor import run_local_workflow
from flock.core.execution.temporal_executor import run_temporal_workflow
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.logging.logging import LOGGERS, get_logger, get_module_loggers
from flock.core.serialization.serializable import Serializable
from flock.core.util.cli_helper import init_console

# Import FlockAgent using TYPE_CHECKING to avoid circular import at runtime
if TYPE_CHECKING:
    # These imports are only for type hints
    from flock.core.flock_agent import FlockAgent


# Registry
from flock.core.flock_registry import get_registry

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

logger = get_logger("flock")
TELEMETRY.setup_tracing()  # Setup OpenTelemetry
tracer = trace.get_tracer(__name__)
FlockRegistry = get_registry()  # Get the registry instance

# Define TypeVar for generic class methods like from_dict
T = TypeVar("T", bound="Flock")


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
    enable_logging: bool = Field(
        default=False,
        description="If True, enable logging for the Flock instance.",
    )
    show_flock_banner: bool = Field(
        default=True,
        description="If True, show the Flock banner on console interactions.",
    )
    # Internal agent storage - not part of the Pydantic model for direct serialization
    _agents: dict[str, FlockAgent]
    _start_agent_name: str | None = None  # For potential pre-configuration
    _start_input: dict = {}  # For potential pre-configuration

    # Pydantic v2 model config
    model_config = {
        "arbitrary_types_allowed": True,
        "ignored_types": (type(FlockRegistry),),
    }

    def __init__(
        self,
        name: str | None = None,
        model: str | None = DEFAULT_MODEL,
        description: str | None = None,
        show_flock_banner: bool = True,
        enable_temporal: bool = False,
        enable_logging: bool | list[str] = False,
        agents: list[FlockAgent] | None = None,
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
            enable_logging=enable_logging,
            show_flock_banner=show_flock_banner,
            **kwargs,
        )

        # Initialize runtime attributes AFTER super().__init__()
        self._agents = {}
        self._start_agent_name = None
        self._start_input = {}

        # Set up logging based on the enable_logging flag
        self._configure_logging(enable_logging)  # Use instance attribute

        # Register passed agents
        if agents:
            from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

            for agent in agents:
                if isinstance(agent, ConcreteFlockAgent):
                    self.add_agent(agent)
                else:
                    logger.warning(
                        f"Item provided in 'agents' list is not a FlockAgent: {type(agent)}"
                    )

        # Initialize console if needed for banner
        if self.show_flock_banner:  # Use instance attribute
            init_console()

        # Set Temporal debug environment variable
        self._set_temporal_debug_flag()

        # Ensure session ID exists in baggage
        self._ensure_session_id()

        logger.info(
            "Flock instance initialized",
            name=self.name,
            model=self.model,
            enable_temporal=self.enable_temporal,
        )

    def _configure_logging(self, enable_logging: bool | list[str]):
        """Configure logging levels based on the enable_logging flag."""
        is_enabled_globally = False
        enabled_loggers = []

        if isinstance(enable_logging, bool):
            is_enabled_globally = enable_logging
        elif isinstance(enable_logging, list):
            is_enabled_globally = bool(enable_logging)
            enabled_loggers = enable_logging

        # Configure core loggers
        for log_name in LOGGERS:
            log_instance = get_logger(log_name)
            if is_enabled_globally or log_name in enabled_loggers:
                log_instance.enable_logging = True
            else:
                log_instance.enable_logging = False

        # Configure module loggers (existing ones)
        module_loggers = get_module_loggers()
        for mod_log in module_loggers:
            if is_enabled_globally or mod_log.name in enabled_loggers:
                mod_log.enable_logging = True
            else:
                mod_log.enable_logging = False

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

    def add_agent(self, agent: FlockAgent) -> FlockAgent:
        """Adds an agent instance to this Flock configuration and registry."""
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        if not isinstance(agent, ConcreteFlockAgent):
            raise TypeError("Provided object is not a FlockAgent instance.")
        if not agent.name:
            raise ValueError("Agent must have a name.")

        if agent.name in self._agents:
            logger.warning(f"Agent '{agent.name}' already exists. Overwriting.")
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

    def run(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict = {},
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] | None = None,
    ) -> Box | dict:
        """Entry point for running an agent system synchronously."""
        try:
            loop = asyncio.get_running_loop()
            # If loop exists, check if it's closed
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:  # No running loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Ensure the loop runs the task and handles closure if we created it
        if asyncio.get_event_loop() is loop and not loop.is_running():
            result = loop.run_until_complete(
                self.run_async(
                    start_agent=start_agent,
                    input=input,
                    context=context,
                    run_id=run_id,
                    box_result=box_result,
                    agents=agents,
                )
            )
            return result
        else:
            future = asyncio.ensure_future(
                self.run_async(
                    start_agent=start_agent,
                    input=input,
                    context=context,
                    run_id=run_id,
                    box_result=box_result,
                    agents=agents,
                )
            )
            return loop.run_until_complete(future)

    async def run_async(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] | None = None,
    ) -> Box | dict:
        """Entry point for running an agent system asynchronously."""
        # Import here to allow forward reference resolution
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        with tracer.start_as_current_span("flock.run_async") as span:
            # Add passed agents first
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
                if start_agent_name not in self._agents:
                    self.add_agent(start_agent)
            elif isinstance(start_agent, str):
                start_agent_name = start_agent
            else:
                start_agent_name = self._start_agent_name

            # Default to first agent if only one exists and none specified
            if not start_agent_name and len(self._agents) == 1:
                start_agent_name = list(self._agents.keys())[0]
            elif not start_agent_name:
                raise ValueError(
                    "No start_agent specified and multiple/no agents exist."
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
                if not resolved_start_agent:
                    resolved_start_agent = FlockRegistry.get_agent(
                        start_agent_name
                    )
                    if not resolved_start_agent:
                        raise ValueError(
                            f"Start agent '{start_agent_name}' not found."
                        )
                    self.add_agent(resolved_start_agent)

                run_context = context if context else FlockContext()
                set_baggage("run_id", effective_run_id)

                initialize_context(
                    run_context,
                    start_agent_name,
                    run_input,
                    effective_run_id,
                    not self.enable_temporal,
                    self.model or resolved_start_agent.model or DEFAULT_MODEL,
                )
                # Add agent definitions to context for routing/serialization within workflow
                for agent_name, agent_instance in self.agents.items():
                    # Agents already handle their serialization
                    agent_dict_repr = agent_instance.to_dict()
                    run_context.add_agent_definition(
                        agent_type=type(agent_instance),
                        agent_name=agent_name,
                        agent_data=agent_dict_repr,  # Pass the serialized dict
                    )

                logger.info(
                    "Starting agent execution",
                    agent=start_agent_name,
                    enable_temporal=self.enable_temporal,
                )

                # Execute workflow
                if not self.enable_temporal:
                    result = await run_local_workflow(
                        run_context, box_result=False
                    )
                else:
                    result = await run_temporal_workflow(
                        run_context, box_result=False
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

            except Exception as e:
                logger.error(
                    f"Flock run '{self.name}' failed: {e}", exc_info=True
                )
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                return {
                    "error": str(e),
                    "details": f"Flock run '{self.name}' failed.",
                }

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
        """Synchronous wrapper for run_batch_async."""
        # (Standard asyncio run wrapper logic)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:  # No running loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        coro = self.run_batch_async(
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

        if asyncio.get_event_loop() is loop and not loop.is_running():
            results = loop.run_until_complete(coro)
            return results
        else:
            future = asyncio.ensure_future(coro)
            return loop.run_until_complete(future)

    # --- Evaluation (Delegation) ---
    async def evaluate_async(
        self,
        dataset: str | Path | list[dict[str, Any]] | DataFrame | Dataset,
        start_agent: FlockAgent | str,
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            str
            | Callable[[Any, Any], bool | float | dict[str, Any]]
            | FlockAgent
            | FlockEvaluator
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
    ) -> DataFrame | list[dict[str, Any]]:
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
        dataset: str | Path | list[dict[str, Any]] | DataFrame | Dataset,
        start_agent: FlockAgent | str,
        input_mapping: dict[str, str],
        answer_mapping: dict[str, str],
        metrics: list[
            str
            | Callable[[Any, Any], bool | float | dict[str, Any]]
            | FlockAgent
            | FlockEvaluator
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
    ) -> DataFrame | list[dict[str, Any]]:
        """Synchronous wrapper for evaluate_async."""
        # (Standard asyncio run wrapper logic)
        try:
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                raise RuntimeError("Event loop is closed")
        except RuntimeError:  # No running loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        coro = self.evaluate_async(
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

        if asyncio.get_event_loop() is loop and not loop.is_running():
            results = loop.run_until_complete(coro)
            return results
        else:
            future = asyncio.ensure_future(coro)
            return loop.run_until_complete(future)

    # --- API Server Starter ---
    def start_api(
        self,
        host: str = "127.0.0.1",
        port: int = 8344,
        server_name: str = "Flock API",
        create_ui: bool = False,
    ) -> None:
        """Starts a REST API server for this Flock instance."""
        # Import runner locally
        from flock.core.api.runner import start_flock_api

        start_flock_api(self, host, port, server_name, create_ui)

    # --- CLI Starter ---
    def start_cli(
        self,
        server_name: str = "Flock CLI",
        show_results: bool = False,
        edit_mode: bool = False,
    ) -> None:
        """Starts an interactive CLI for this Flock instance."""
        # Import runner locally
        from flock.cli.runner import start_flock_cli

        start_flock_cli(self, server_name, show_results, edit_mode)

    # --- Serialization Delegation Methods ---
    def to_dict(self, path_type: str = "relative") -> dict[str, Any]:
        """Serialize Flock instance to dictionary using FlockSerializer."""
        # Import locally to prevent circular imports at module level if structure is complex
        from flock.core.serialization.flock_serializer import FlockSerializer

        return FlockSerializer.serialize(self, path_type=path_type)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize Flock instance from dictionary using FlockSerializer."""
        # Import locally
        from flock.core.serialization.flock_serializer import FlockSerializer

        return FlockSerializer.deserialize(cls, data)

    # --- Static Method Loader (Delegates to loader module) ---
    @staticmethod
    def load_from_file(file_path: str) -> Flock:
        """Load a Flock instance from various file formats (delegates to loader)."""
        # Import locally
        from flock.core.util.loader import load_flock_from_file

        return load_flock_from_file(file_path)
