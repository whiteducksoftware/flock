"""High-level orchestrator for creating and executing agents."""

import os
import uuid
from typing import TypeVar

from rich.prompt import Prompt

from flock.core.context.context import FlockContext
from flock.core.context.context_manager import initialize_context
from flock.core.execution.local_executor import run_local_workflow
from flock.core.execution.temporal_executor import run_temporal_workflow
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.pprint_formatter import PrettyPrintFormatter
from flock.core.logging.logging import get_logger
from flock.core.registry.agent_registry import Registry
from flock.core.util.cli_helper import display_banner
from flock.core.util.input_resolver import top_level_to_keys

T = TypeVar("T", bound=FlockAgent)
logger = get_logger("flock")


class Flock:
    """High-level orchestrator for creating and executing agents.

    Flock manages the registration of agents and tools, sets up the global context, and runs the agent workflows.
    It provides an easy-to-use API for both local (debug) and production (Temporal) execution.
    """

    def __init__(
        self,
        model: str = "openai/gpt-4o",
        local_debug: bool = False,
        enable_logging: bool = False,
        output_formatter: FormatterOptions = FormatterOptions(
            PrettyPrintFormatter
        ),
    ):
        """Initialize the Flock orchestrator.

        Args:
            model (str): The default model identifier to be used for agents. Defaults to "openai/gpt-4o".
            local_debug (bool): If True, run the agent workflow locally for debugging purposes. Defaults to False.
            enable_logging (bool): If True, enable verbose logging. Defaults to False.
            output_formatter (FormatterOptions): Options for formatting output results.
        """
        logger.info(
            "Initializing Flock",
            model=model,
            local_debug=local_debug,
            enable_logging=enable_logging,
        )
        logger.enable_logging = enable_logging

        display_banner()

        self.agents: dict[str, FlockAgent] = {}
        self.registry = Registry()
        self.context = FlockContext()
        self.model = model
        self.local_debug = local_debug
        self.output_formatter = output_formatter

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
        if not agent.model:
            agent.model = self.model
            logger.debug(
                f"Using default model for agent {agent.name}", model=self.model
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
        logger.info("Registering tool", tool_name=tool_name)
        self.registry.register_tool(tool_name, tool)
        logger.debug("Tool registered successfully")

    async def run_async(
        self,
        start_agent: FlockAgent | str,
        input: dict = {},
        context: FlockContext = None,
        run_id: str = "",
        box_result: bool = True,
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

        Returns:
            dict: A dictionary containing the result of the agent workflow execution.

        Raises:
            ValueError: If the specified agent is not found in the registry.
            Exception: For any other errors encountered during execution.
        """
        try:
            if isinstance(start_agent, str):
                logger.debug("Looking up agent by name", agent_name=start_agent)
                start_agent = self.registry.get_agent(start_agent)
                if not start_agent:
                    logger.error("Agent not found", agent_name=start_agent)
                    raise ValueError(
                        f"Agent '{start_agent}' not found in registry"
                    )
            if context:
                logger.debug("Using provided context")
                self.context = context
            if not run_id:
                run_id = f"{start_agent.name}_{uuid.uuid4().hex[:4]}"
                logger.debug("Generated run ID", run_id=run_id)

            # TODO - Add a check for required input keys
            input_keys = top_level_to_keys(start_agent.input)
            for key in input_keys:
                if key.startswith("flock."):
                    key = key[6:]  # Remove the "flock." prefix
                if key not in input:
                    input[key] = Prompt.ask(
                        f"Please enter {key} for {start_agent.name}"
                    )

            # Initialize the context with standardized variables
            initialize_context(
                self.context, start_agent.name, input, run_id, self.local_debug
            )

            logger.info(
                "Starting agent execution",
                agent=start_agent.name,
                local_debug=self.local_debug,
            )

            if self.local_debug:
                return await run_local_workflow(
                    self.context, self.output_formatter, box_result
                )
            else:
                return await run_temporal_workflow(self.context, box_result)
        except Exception as e:
            logger.exception("Execution failed", error=str(e))
            raise
