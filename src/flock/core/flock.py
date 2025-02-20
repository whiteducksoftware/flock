"""High-level orchestrator for creating and executing agents."""

import asyncio
import json
import os
import uuid
from typing import Any, TypeVar

import cloudpickle
from opentelemetry import trace
from opentelemetry.baggage import get_baggage, set_baggage

from flock.config import TELEMETRY
from flock.core.context.context import FlockContext
from flock.core.context.context_manager import initialize_context
from flock.core.execution.local_executor import run_local_workflow
from flock.core.execution.temporal_executor import run_temporal_workflow
from flock.core.flock_agent import FlockAgent
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry
from flock.core.util.cli_helper import display_banner
from flock.core.util.input_resolver import top_level_to_keys

T = TypeVar("T", bound=FlockAgent)
logger = get_logger("flock")
TELEMETRY.setup_tracing()
tracer = trace.get_tracer(__name__)


def init_loggers(enable_logging: bool | list[str] = False):
    """Initialize the loggers for the Flock system.

    Args:
        enable_logging (bool): If True, enable verbose logging. Defaults to False.
    """
    if isinstance(enable_logging, list):
        for log_name in enable_logging:
            other_loggers = get_logger(log_name)
            other_loggers.enable_logging = True
    else:
        logger.enable_logging = enable_logging
        other_loggers = get_logger("interpreter")
        other_loggers.enable_logging = enable_logging
        other_loggers = get_logger("memory")
        other_loggers.enable_logging = enable_logging
        other_loggers = get_logger("activities")
        other_loggers.enable_logging = enable_logging
        other_loggers = get_logger("context")
        other_loggers.enable_logging = enable_logging
        other_loggers = get_logger("registry")
        other_loggers.enable_logging = enable_logging
        other_loggers = get_logger("tools")
        other_loggers.enable_logging = enable_logging
        other_loggers = get_logger("agent")
        other_loggers.enable_logging = enable_logging


class Flock:
    """High-level orchestrator for creating and executing agents.

    Flock manages the registration of agents and tools, sets up the global context, and runs the agent workflows.
    It provides an easy-to-use API for both local (debug) and production (Temporal) execution.
    """

    def __init__(
        self,
        model: str = "openai/gpt-4o",
        local_debug: bool = False,
        enable_logging: bool | list[str] = False,
        show_cli_banner: bool = True,
    ):
        """Initialize the Flock orchestrator.

        Args:
            model (str): The default model identifier to be used for agents. Defaults to "openai/gpt-4o".
            local_debug (bool): If True, run the agent workflow locally for debugging purposes. Defaults to False.
            enable_logging (bool): If True, enable verbose logging. Defaults to False.
            output_formatter (FormatterOptions): Options for formatting output results.
        """
        with tracer.start_as_current_span("flock_init") as span:
            span.set_attribute("model", model)
            span.set_attribute("local_debug", local_debug)
            span.set_attribute("enable_logging", enable_logging)
            logger.info(
                "Initializing Flock",
                model=model,
                local_debug=local_debug,
                enable_logging=enable_logging,
            )
            init_loggers(enable_logging)

            session_id = get_baggage("session_id")
            if not session_id:
                session_id = str(uuid.uuid4())
                set_baggage("session_id", session_id)

            if show_cli_banner:
                display_banner()

            self.agents: dict[str, FlockAgent] = {}
            self.registry = Registry()
            self.context = FlockContext()
            self.model = model
            self.local_debug = local_debug
            self.start_agent: FlockAgent | str | None = None
            self.input: dict = {}

            if local_debug:
                os.environ["LOCAL_DEBUG"] = "1"
                logger.debug("Set LOCAL_DEBUG environment variable")
            elif "LOCAL_DEBUG" in os.environ:
                del os.environ["LOCAL_DEBUG"]
                logger.debug("Removed LOCAL_DEBUG environment variable")

    def add_agent(self, agent: T) -> T:
        """Add a new agent to the Flock system.

        This method registers the agent, updates the internal registry and global context, and
        sets default values if needed. If an agent with the same name already exists, the existing
        agent is returned.

        Args:
            agent (FlockAgent): The agent instance to add.

        Returns:
            FlockAgent: The registered agent instance.
        """
        with tracer.start_as_current_span("add_agent") as span:
            span.set_attribute("agent_name", agent.name)
            if not agent.model:
                agent.model = self.model
                logger.debug(
                    f"Using default model for agent {agent.name}",
                    model=self.model,
                )

            if agent.name in self.agents:
                logger.warning(
                    f"Agent {agent.name} already exists, returning existing instance"
                )
                return self.agents[agent.name]
            logger.info("Adding new agent")

            self.agents[agent.name] = agent
            self.registry.register_agent(agent)
            self.context.add_agent_definition(
                type(agent), agent.name, agent.to_dict()
            )

            if hasattr(agent, "tools") and agent.tools:
                for tool in agent.tools:
                    self.registry.register_tool(tool.__name__, tool)
                    logger.debug("Registered tool", tool_name=tool.__name__)
            logger.success("Agent added successfully")
            return agent

    def add_tool(self, tool_name: str, tool: callable):
        """Register a tool with the Flock system.

        Args:
            tool_name (str): The name under which the tool will be registered.
            tool (callable): The tool function to register.
        """
        with tracer.start_as_current_span("add_tool") as span:
            span.set_attribute("tool_name", tool_name)
            span.set_attribute("tool", tool.__name__)
            logger.info("Registering tool", tool_name=tool_name)
            self.registry.register_tool(tool_name, tool)
            logger.debug("Tool registered successfully")

    def run(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict = {},
        context: FlockContext = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] = [],
    ) -> dict:
        """Entry point for running an agent system synchronously."""
        return asyncio.run(
            self.run_async(
                start_agent, input, context, run_id, box_result, agents
            )
        )

    def save_to_file(
        self,
        file_path: str,
        start_agent: str | None = None,
        input: dict | None = None,
    ) -> None:
        """Save the Flock instance to a file.

        This method serializes the Flock instance to a dictionary using the `to_dict()` method and saves it to a file.
        The saved file can be reloaded later using the `from_file()` method.

        Args:
            file_path (str): The path to the file where the Flock instance should be saved.
        """
        hex_str = cloudpickle.dumps(self).hex()

        result = {
            "start_agent": start_agent,
            "input": input,
            "flock": hex_str,
        }

        path = os.path.dirname(file_path)
        if path:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w") as file:
            file.write(json.dumps(result))

    @staticmethod
    def load_from_file(file_path: str) -> "Flock":
        """Load a Flock instance from a file.

        This class method deserializes a Flock instance from a file that was previously saved using the `save_to_file()`
        method. It reads the file, converts the hexadecimal string back into a Flock instance, and returns it.

        Args:
            file_path (str): The path to the file containing the serialized Flock instance.

        Returns:
            Flock: A new Flock instance reconstructed from the saved file.
        """
        with open(file_path) as file:
            json_flock = json.load(file)
            hex_str = json_flock["flock"]
            flock = cloudpickle.loads(bytes.fromhex(hex_str))
            if json_flock["start_agent"]:
                agent = flock.registry.get_agent(json_flock["start_agent"])
                flock.start_agent = agent
            if json_flock["input"]:
                flock.input = json_flock["input"]
            return flock

    def to_dict(self) -> dict[str, Any]:
        """Serialize the FlockAgent instance to a dictionary.

        This method converts the entire agent instance—including its configuration, state, and lifecycle hooks—
        into a dictionary format. It uses cloudpickle to serialize any callable objects (such as functions or
        methods), converting them into hexadecimal string representations. This ensures that the agent can be
        easily persisted, transmitted, or logged as JSON.

        The serialization process is recursive:
        - If a field is a callable (and not a class), it is serialized using cloudpickle.
        - Lists and dictionaries are processed recursively to ensure that all nested callables are properly handled.

        **Returns:**
            dict[str, Any]: A dictionary representing the FlockAgent, which includes all of its configuration data.
            This dictionary is suitable for storage, debugging, or transmission over the network.

        **Example:**
            For an agent defined as:
                name = "idea_agent",
                model = "openai/gpt-4o",
                input = "query: str | The search query, context: dict | The full conversation context",
                output = "idea: str | The generated idea"
            Calling `agent.to_dict()` might produce:
                {
                    "name": "idea_agent",
                    "model": "openai/gpt-4o",
                    "input": "query: str | The search query, context: dict | The full conversation context",
                    "output": "idea: str | The generated idea",
                    "tools": ["<serialized tool representation>"],
                    "use_cache": False,
                    "hand_off": None,
                    "termination": None,
                    ...
                }
        """

        def convert_callable(obj: Any) -> Any:
            if callable(obj) and not isinstance(obj, type):
                return cloudpickle.dumps(obj).hex()
            if isinstance(obj, list):
                return [convert_callable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert_callable(v) for k, v in obj.items()}
            return obj

        data = self.model_dump()
        return convert_callable(data)

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize a FlockAgent instance from a dictionary.

        This class method reconstructs a FlockAgent from its serialized dictionary representation, as produced
        by the `to_dict()` method. It recursively processes the dictionary to convert any serialized callables
        (stored as hexadecimal strings via cloudpickle) back into executable callable objects.

        **Arguments:**
            data (dict[str, Any]): A dictionary representation of a FlockAgent, typically produced by `to_dict()`.
                The dictionary should contain all configuration fields and state information necessary to fully
                reconstruct the agent.

        **Returns:**
            FlockAgent: An instance of FlockAgent reconstructed from the provided dictionary. The deserialized agent
            will have the same configuration, state, and behavior as the original instance.

        **Example:**
            Suppose you have the following dictionary:
                {
                    "name": "idea_agent",
                    "model": "openai/gpt-4o",
                    "input": "query: str | The search query, context: dict | The full conversation context",
                    "output": "idea: str | The generated idea",
                    "tools": ["<serialized tool representation>"],
                    "use_cache": False,
                    "hand_off": None,
                    "termination": None,
                    ...
                }
            Then, calling:
                agent = FlockAgent.from_dict(data)
            will return a FlockAgent instance with the same properties and behavior as when it was originally serialized.
        """

        def convert_callable(obj: Any) -> Any:
            if isinstance(obj, str) and len(obj) > 2:
                try:
                    return cloudpickle.loads(bytes.fromhex(obj))
                except Exception:
                    return obj
            if isinstance(obj, list):
                return [convert_callable(item) for item in obj]
            if isinstance(obj, dict):
                return {k: convert_callable(v) for k, v in obj.items()}
            return obj

        converted = convert_callable(data)
        return cls(**converted)

    async def run_async(
        self,
        start_agent: FlockAgent | str | None = None,
        input: dict = {},
        context: FlockContext = None,
        run_id: str = "",
        box_result: bool = True,
        agents: list[FlockAgent] = [],
    ) -> dict:
        """Entry point for running an agent system asynchronously.

        This method performs the following steps:
          1. If a string is provided for start_agent, it looks up the agent in the registry.
          2. Optionally uses a provided global context.
          3. Generates a unique run ID if one is not provided.
          4. Initializes the context with standard variables (like agent name, input data, run ID, and debug flag).
          5. Executes the agent workflow either locally (for debugging) or via Temporal (for production).

        Args:
            start_agent (FlockAgent | str): The agent instance or the name of the agent to start the workflow.
            input (dict): A dictionary of input values required by the agent.
            context (FlockContext, optional): A FlockContext instance to use. If not provided, a default context is used.
            run_id (str, optional): A unique identifier for this run. If empty, one is generated automatically.
            box_result (bool, optional): If True, wraps the output in a Box for nicer formatting. Defaults to True.
            agents (list, optional): additional way to add agents to flock instead of add_agent

        Returns:
            dict: A dictionary containing the result of the agent workflow execution.

        Raises:
            ValueError: If the specified agent is not found in the registry.
            Exception: For any other errors encountered during execution.
        """
        with tracer.start_as_current_span("run_async") as span:
            span.set_attribute(
                "start_agent",
                start_agent.name
                if hasattr(start_agent, "name")
                else start_agent,
            )
            for agent in agents:
                self.add_agent(agent)

            if start_agent:
                self.start_agent = start_agent
            if input:
                self.input = input

            span.set_attribute("input", str(self.input))
            span.set_attribute("context", str(context))
            span.set_attribute("run_id", run_id)
            span.set_attribute("box_result", box_result)

            try:
                if isinstance(self.start_agent, str):
                    logger.debug(
                        "Looking up agent by name", agent_name=self.start_agent
                    )
                    self.start_agent = self.registry.get_agent(self.start_agent)
                    if not self.start_agent:
                        logger.error(
                            "Agent not found", agent_name=self.start_agent
                        )
                        raise ValueError(
                            f"Agent '{self.start_agent}' not found in registry"
                        )
                    self.start_agent.resolve_callables(context=self.context)
                if context:
                    logger.debug("Using provided context")
                    self.context = context
                if not run_id:
                    run_id = f"{self.start_agent.name}_{uuid.uuid4().hex[:4]}"
                    logger.debug("Generated run ID", run_id=run_id)

                set_baggage("run_id", run_id)

                # TODO - Add a check for required input keys
                input_keys = top_level_to_keys(self.start_agent.input)
                for key in input_keys:
                    if key.startswith("flock."):
                        key = key[6:]  # Remove the "flock." prefix
                    if key not in self.input:
                        from rich.prompt import Prompt

                        self.input[key] = Prompt.ask(
                            f"Please enter {key} for {self.start_agent.name}"
                        )

                # Initialize the context with standardized variables
                initialize_context(
                    self.context,
                    self.start_agent.name,
                    self.input,
                    run_id,
                    self.local_debug,
                )

                logger.info(
                    "Starting agent execution",
                    agent=self.start_agent.name,
                    local_debug=self.local_debug,
                )

                if self.local_debug:
                    return await run_local_workflow(self.context, box_result)
                else:
                    return await run_temporal_workflow(self.context, box_result)
            except Exception as e:
                logger.exception("Execution failed", error=str(e))
                raise
