# src/flock/core/flock.py
"""High-level orchestrator for creating and executing agents."""

from __future__ import annotations  # Ensure forward references work

import asyncio
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from box import Box
from opentelemetry import trace
from opentelemetry.baggage import get_baggage, set_baggage

# Pydantic and OpenTelemetry
from pydantic import BaseModel, Field  # Using Pydantic directly now

# Flock core components & utilities
from flock.config import TELEMETRY
from flock.core.context.context import FlockContext
from flock.core.context.context_manager import initialize_context
from flock.core.execution.local_executor import run_local_workflow
from flock.core.execution.temporal_executor import run_temporal_workflow
from flock.core.logging.logging import LOGGERS, get_logger, get_module_loggers

# Import FlockAgent using TYPE_CHECKING to avoid circular import at runtime
if TYPE_CHECKING:
    from flock.core.flock_agent import FlockAgent
else:
    # Provide a forward reference string or Any for runtime if FlockAgent is used in hints here
    FlockAgent = "FlockAgent"  # Forward reference string for Pydantic/runtime

# Registry and Serialization
from flock.core.flock_registry import (
    get_registry,  # Use the unified registry
)
from flock.core.serialization.serializable import (
    Serializable,  # Import Serializable base
)

# NOTE: Flock.to_dict/from_dict primarily orchestrates agent serialization.
# It doesn't usually need serialize_item/deserialize_item directly,
# relying on FlockAgent's implementation instead.
# from flock.core.serialization.serialization_utils import serialize_item, deserialize_item
# CLI Helper (if still used directly, otherwise can be removed)
from flock.core.util.cli_helper import init_console

# Cloudpickle for fallback/direct serialization if needed
try:
    import cloudpickle

    PICKLE_AVAILABLE = True
except ImportError:
    PICKLE_AVAILABLE = False


logger = get_logger("flock")
TELEMETRY.setup_tracing()  # Setup OpenTelemetry
tracer = trace.get_tracer(__name__)
FlockRegistry = get_registry()  # Get the registry instance

# Define TypeVar for generic methods like from_dict
T = TypeVar("T", bound="Flock")


# Inherit from Serializable for YAML/JSON/etc. methods
# Use BaseModel directly for Pydantic features
class Flock(BaseModel, Serializable):
    """High-level orchestrator for creating and executing agent systems.

    Flock manages agent definitions, context, and execution flow, supporting
    both local debugging and robust distributed execution via Temporal.
    It is serializable to various formats like YAML and JSON.
    """

    name: str | None = Field(
        default_factory=lambda: f"flock_{uuid.uuid4().hex[:8]}",
        description="A unique identifier for this Flock instance.",
    )
    model: str | None = Field(
        default="openai/gpt-4o",
        description="Default model identifier to be used for agents if not specified otherwise.",
    )
    description: str | None = Field(
        default=None,
        description="A brief description of the purpose of this Flock configuration.",
    )
    enable_temporal: bool = Field(
        default=False,
        description="If True, execute workflows via Temporal; otherwise, run locally.",
    )
    # --- Runtime Attributes (Excluded from Serialization) ---
    # Store agents internally but don't make it part of the Pydantic model definition
    # Use a regular attribute, initialized in __init__
    # Pydantic V2 handles __init__ and attributes not in Field correctly
    _agents: dict[str, FlockAgent]
    _start_agent_name: str | None
    _start_input: dict

    # Pydantic v2 model config
    model_config = {
        "arbitrary_types_allowed": True,
        "ignored_types": (
            type(FlockRegistry),
        ),  # Prevent validation issues with registry
        # No need to exclude fields here, handled in to_dict
    }

    def __init__(
        self,
        name: str | None = None,
        model: str | None = "openai/gpt-4o",
        description: str | None = None,
        show_flock_banner: bool = True,
        enable_temporal: bool = False,
        enable_logging: bool
        | list[str] = False,  # Keep logging control at init
        agents: list[FlockAgent] | None = None,  # Allow passing agents at init
        **kwargs,  # Allow extra fields during init if needed, Pydantic handles it
    ):
        """Initialize the Flock orchestrator."""
        # Initialize Pydantic fields
        super().__init__(
            name=name,
            model=model,
            description=description,
            enable_temporal=enable_temporal,
            **kwargs,  # Pass extra kwargs to Pydantic BaseModel
        )

        # Initialize runtime attributes AFTER super().__init__()
        self._agents = {}
        self._start_agent_name = None
        self._start_input = {}

        # Set up logging
        self._configure_logging(enable_logging)

        # Register passed agents
        if agents:
            # Ensure FlockAgent type is available for isinstance check
            # This import might need to be deferred or handled carefully if it causes issues
            from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

            for agent in agents:
                if isinstance(agent, ConcreteFlockAgent):
                    self.add_agent(agent)
                else:
                    logger.warning(
                        f"Item provided in 'agents' list is not a FlockAgent: {type(agent)}"
                    )

        # Initialize console if needed
        if show_flock_banner:
            init_console()

        # Set Temporal debug environment variable
        self._set_temporal_debug_flag()

        # Ensure session ID exists in baggage
        self._ensure_session_id()

        logger.info(
            "Flock instance initialized",
            model=self.model,
            enable_temporal=self.enable_temporal,
        )

    # --- Keep _configure_logging, _set_temporal_debug_flag, _ensure_session_id ---
    # ... (implementation as before) ...
    def _configure_logging(self, enable_logging: bool | list[str]):
        """Configure logging levels based on the enable_logging flag."""
        # logger.debug(f"Configuring logging, enable_logging={enable_logging}")
        is_enabled_globally = False
        enabled_loggers = []

        if isinstance(enable_logging, bool):
            is_enabled_globally = enable_logging
        elif isinstance(enable_logging, list):
            is_enabled_globally = bool(
                enable_logging
            )  # Enable if list is not empty
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

    # --- Keep add_agent, agents property, run, run_async ---
    # ... (implementation as before, ensuring FlockAgent type hint is handled) ...
    def add_agent(self, agent: FlockAgent) -> FlockAgent:
        """Adds an agent instance to this Flock configuration."""
        # Ensure FlockAgent type is available for isinstance check
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        if not isinstance(agent, ConcreteFlockAgent):
            raise TypeError("Provided object is not a FlockAgent instance.")
        if not agent.name:
            raise ValueError("Agent must have a name.")

        if agent.name in self._agents:
            logger.warning(
                f"Agent '{agent.name}' already exists in this Flock instance. Overwriting."
            )
        self._agents[agent.name] = agent
        FlockRegistry.register_agent(agent)  # Also register globally

        # Set default model if agent doesn't have one
        if agent.model is None:
            # agent.set_model(self.model) # Use Flock's default model
            if self.model:  # Ensure Flock has a model defined
                agent.set_model(self.model)
                logger.debug(
                    f"Agent '{agent.name}' using Flock default model: {self.model}"
                )
            else:
                logger.warning(
                    f"Agent '{agent.name}' has no model and Flock default model is not set."
                )

        logger.info(f"Agent '{agent.name}' added to Flock.")
        return agent

    @property
    def agents(self) -> dict[str, FlockAgent]:
        """Returns the dictionary of agents managed by this Flock instance."""
        return self._agents

    def run(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict = {},
        context: FlockContext
        | None = None,  # Allow passing initial context state
        run_id: str = "",
        box_result: bool = True,  # Changed default to False for raw dict
        agents: list[FlockAgent] | None = None,  # Allow adding agents via run
    ) -> Box:
        """Entry point for running an agent system synchronously."""
        # Check if an event loop is already running
        try:
            loop = asyncio.get_running_loop()
            # If we get here, an event loop is already running
            # Run directly in this loop using run_until_complete
            return loop.run_until_complete(
                self.run_async(
                    start_agent=start_agent,
                    input=input,
                    context=context,
                    run_id=run_id,
                    box_result=box_result,
                    agents=agents,
                )
            )
        except RuntimeError:
            # No running event loop, create a new one with asyncio.run
            return asyncio.run(
                self.run_async(
                    start_agent=start_agent,
                    input=input,
                    context=context,
                    run_id=run_id,
                    box_result=box_result,
                    agents=agents,
                )
            )

    async def run_async(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict | None = None,
        context: FlockContext | None = None,
        run_id: str = "",
        box_result: bool = True,  # Changed default
        agents: list[FlockAgent] | None = None,  # Allow adding agents via run
    ) -> Box:
        """Entry point for running an agent system asynchronously."""
        # This import needs to be here or handled carefully due to potential cycles
        from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent

        with tracer.start_as_current_span("flock.run_async") as span:
            # Add passed agents first
            if agents:
                for agent_obj in agents:
                    if isinstance(agent_obj, ConcreteFlockAgent):
                        self.add_agent(
                            agent_obj
                        )  # Adds to self._agents and registry
                    else:
                        logger.warning(
                            f"Item in 'agents' list is not a FlockAgent: {type(agent_obj)}"
                        )

            # Determine starting agent name
            start_agent_name: str | None = None
            if isinstance(start_agent, ConcreteFlockAgent):
                start_agent_name = start_agent.name
                if start_agent_name not in self._agents:
                    self.add_agent(
                        start_agent
                    )  # Add if instance was passed but not added
            elif isinstance(start_agent, str):
                start_agent_name = start_agent
            else:
                start_agent_name = (
                    self._start_agent_name
                )  # Use pre-configured if any

            # Default to first agent if only one exists and none specified
            if not start_agent_name and len(self._agents) == 1:
                start_agent_name = list(self._agents.keys())[0]
            elif not start_agent_name:
                raise ValueError(
                    "No start_agent specified and multiple agents exist or none are added."
                )

            # Get starting input
            run_input = input if input is not None else self._start_input

            # Log and trace start info
            span.set_attribute("start_agent", start_agent_name)
            span.set_attribute("input", str(run_input))
            span.set_attribute("run_id", run_id)
            span.set_attribute("enable_temporal", self.enable_temporal)
            logger.info(
                f"Initiating Flock run. Start Agent: '{start_agent_name}'. Temporal: {self.enable_temporal}."
            )

            try:
                # Resolve start agent instance from internal dict
                resolved_start_agent = self._agents.get(start_agent_name)
                if not resolved_start_agent:
                    # Maybe it's only in the global registry? (Less common)
                    resolved_start_agent = FlockRegistry.get_agent(
                        start_agent_name
                    )
                    if not resolved_start_agent:
                        raise ValueError(
                            f"Start agent '{start_agent_name}' not found in Flock instance or registry."
                        )
                    else:
                        # If found globally, add it to this instance for consistency during run
                        self.add_agent(resolved_start_agent)

                # Create or use provided context
                run_context = context if context else FlockContext()
                if not run_id:
                    run_id = f"flockrun_{uuid.uuid4().hex[:8]}"
                set_baggage("run_id", run_id)  # Ensure run_id is in baggage

                # Initialize context
                initialize_context(
                    run_context,
                    start_agent_name,
                    run_input,
                    run_id,
                    not self.enable_temporal,
                    self.model
                    or resolved_start_agent.model
                    or "default-model-missing",  # Pass effective model
                )

                # Execute workflow
                logger.info(
                    "Starting agent execution",
                    agent=start_agent_name,
                    enable_temporal=self.enable_temporal,
                )

                if not self.enable_temporal:
                    result = await run_local_workflow(
                        run_context, box_result=False
                    )  # Get raw dict
                else:
                    result = await run_temporal_workflow(
                        run_context, box_result=False
                    )  # Get raw dict

                span.set_attribute("result.type", str(type(result)))
                # Avoid overly large results in trace attributes
                result_str = str(result)
                if len(result_str) > 1000:
                    result_str = result_str[:1000] + "... (truncated)"
                span.set_attribute("result.preview", result_str)

                # Optionally box result before returning
                if box_result:
                    try:
                        from box import Box

                        logger.debug("Boxing final result.")
                        return Box(result)
                    except ImportError:
                        logger.warning(
                            "Box library not installed, returning raw dict. Install with 'pip install python-box'"
                        )
                        return result
                else:
                    return result

            except Exception as e:
                logger.error(f"Flock run failed: {e}", exc_info=True)
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                # Depending on desired behavior, either raise or return an error dict
                # raise # Option 1: Let the exception propagate
                return {
                    "error": str(e),
                    "details": "Flock run failed.",
                }  # Option 2: Return error dict

    # --- ADDED Serialization Methods ---

    def to_dict(self) -> dict[str, Any]:
        """Convert Flock instance to dictionary representation."""
        logger.debug("Serializing Flock instance to dict.")
        # Use Pydantic's dump for base fields
        data = self.model_dump(mode="json", exclude_none=True)

        # Manually add serialized agents
        data["agents"] = {}
        for name, agent_instance in self._agents.items():
            try:
                # Agents handle their own serialization via their to_dict
                data["agents"][name] = agent_instance.to_dict()
            except Exception as e:
                logger.error(
                    f"Failed to serialize agent '{name}' within Flock: {e}"
                )
                # Optionally skip problematic agents or raise error
                # data["agents"][name] = {"error": f"Serialization failed: {e}"}

        # Exclude runtime fields that shouldn't be serialized
        # These are not Pydantic fields, so they aren't dumped by model_dump
        # No need to explicitly remove _start_agent_name, _start_input unless added manually

        # Filter final dict (optional, Pydantic's exclude_none helps)
        # return self._filter_none_values(data)
        return data

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create Flock instance from dictionary representation."""
        logger.debug(
            f"Deserializing Flock from dict. Provided keys: {list(data.keys())}"
        )

        # Ensure FlockAgent is importable for type checking later
        try:
            from flock.core.flock_agent import FlockAgent as ConcreteFlockAgent
        except ImportError:
            logger.error(
                "Cannot import FlockAgent, deserialization may fail for agents."
            )
            ConcreteFlockAgent = Any  # Fallback

        # Extract agent data before initializing Flock base model
        agents_data = data.pop("agents", {})

        # Create Flock instance using Pydantic constructor for basic fields
        try:
            # Pass only fields defined in Flock's Pydantic model
            init_data = {k: v for k, v in data.items() if k in cls.model_fields}
            flock_instance = cls(**init_data)
        except Exception as e:
            logger.error(
                f"Pydantic validation/init failed for Flock: {e}", exc_info=True
            )
            raise ValueError(
                f"Failed to initialize Flock from dict: {e}"
            ) from e

        # Deserialize and add agents AFTER Flock instance exists
        for name, agent_data in agents_data.items():
            try:
                # Ensure agent_data has the name, or add it from the key
                agent_data.setdefault("name", name)
                # Use FlockAgent's from_dict method
                agent_instance = ConcreteFlockAgent.from_dict(agent_data)
                flock_instance.add_agent(
                    agent_instance
                )  # Adds to _agents and registers
            except Exception as e:
                logger.error(
                    f"Failed to deserialize or add agent '{name}' during Flock deserialization: {e}",
                    exc_info=True,
                )
                # Decide: skip agent or raise error?

        logger.info("Successfully deserialized Flock instance.")
        return flock_instance

    # --- API Start Method ---
    def start_api(
        self,
        host: str = "127.0.0.1",
        port: int = 8344,
        server_name: str = "Flock API",
        create_ui: bool = False,
    ) -> None:
        """Start a REST API server for this Flock instance."""
        # Import locally to avoid making API components a hard dependency
        try:
            from flock.core.api import FlockAPI
        except ImportError:
            logger.error(
                "API components not found. Cannot start API. "
                "Ensure 'fastapi' and 'uvicorn' are installed."
            )
            return

        logger.info(
            f"Preparing to start API server on {host}:{port} {'with UI' if create_ui else 'without UI'}"
        )
        api_instance = FlockAPI(self)  # Pass the current Flock instance
        # Use the start method of FlockAPI
        api_instance.start(
            host=host, port=port, server_name=server_name, create_ui=create_ui
        )

    # --- CLI Start Method ---
    def start_cli(
        self,
        server_name: str = "Flock CLI",
        show_results: bool = False,
        edit_mode: bool = False,
    ) -> None:
        """Start a CLI interface for this Flock instance.

        This method loads the CLI with the current Flock instance already available,
        allowing users to execute, edit, or manage agents from the existing configuration.

        Args:
            server_name: Optional name for the CLI interface
            show_results: Whether to initially show results of previous runs
            edit_mode: Whether to open directly in edit mode
        """
        # Import locally to avoid circular imports
        try:
            from flock.cli.loaded_flock_cli import start_loaded_flock_cli
        except ImportError:
            logger.error(
                "CLI components not found. Cannot start CLI. "
                "Ensure the CLI modules are properly installed."
            )
            return

        logger.info(
            f"Starting CLI interface with loaded Flock instance ({len(self._agents)} agents)"
        )

        # Pass the current Flock instance to the CLI
        start_loaded_flock_cli(
            flock=self,
            server_name=server_name,
            show_results=show_results,
            edit_mode=edit_mode,
        )

    # --- Static Method Loaders (Keep for convenience) ---
    @staticmethod
    def load_from_file(file_path: str) -> Flock:
        """Load a Flock instance from various file formats (detects type)."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Flock file not found: {file_path}")

        if p.suffix in [".yaml", ".yml"]:
            return Flock.from_yaml_file(p)
        elif p.suffix == ".json":
            return Flock.from_json(p.read_text())
        elif p.suffix == ".msgpack":
            return Flock.from_msgpack_file(p)
        elif p.suffix == ".pkl":
            if PICKLE_AVAILABLE:
                return Flock.from_pickle_file(p)
            else:
                raise RuntimeError(
                    "Cannot load Pickle file: cloudpickle not installed."
                )
        else:
            raise ValueError(
                f"Unsupported file extension: {p.suffix}. Use .yaml, .json, .msgpack, or .pkl."
            )
