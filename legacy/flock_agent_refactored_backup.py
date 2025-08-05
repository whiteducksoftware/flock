# src/flock/core/flock_agent_refactored.py
"""FlockAgent is the core, declarative base class for all agents in the Flock framework - REFACTORED VERSION."""

import uuid
from abc import ABC
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from flock.core.agent.flock_agent_components import FlockAgentComponents
from flock.core.agent.flock_agent_execution import FlockAgentExecution
from flock.core.agent.flock_agent_integration import FlockAgentIntegration
from flock.core.agent.flock_agent_lifecycle import FlockAgentLifecycle
from flock.core.agent.flock_agent_serialization import FlockAgentSerialization
from flock.core.config.flock_agent_config import FlockAgentConfig

# Core Flock components (ensure these are importable)
from flock.core.context.context import FlockContext
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.flock_router import FlockRouter, FlockRouterConfig
from flock.core.mcp.flock_mcp_server import FlockMCPServer

# Mixins and Serialization components
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.serialization.serializable import (
    Serializable,  # Import Serializable base
)
from flock.workflow.temporal_config import TemporalActivityConfig

T = TypeVar("T", bound="FlockAgent")

SignatureType = (
    str
    | Callable[..., str]
    | type[BaseModel]
    | Callable[..., type[BaseModel]]
    | None
)


# Make FlockAgent inherit from Serializable
class FlockAgent(BaseModel, Serializable, DSPyIntegrationMixin, ABC):
    """Core, declarative base class for Flock agents, enabling serialization,
    modularity, and integration with evaluation and routing components.
    Inherits from Pydantic BaseModel, ABC, DSPyIntegrationMixin, and Serializable.
    """

    agent_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Internal, Unique UUID4 for this agent instance. No need to set it manually. Used for MCP features.",
    )

    name: str = Field(..., description="Unique identifier for the agent.")

    model: str | None = Field(
        None,
        description="The model identifier to use (e.g., 'openai/gpt-4o'). If None, uses Flock's default.",
    )
    description: str | Callable[..., str] | None = Field(
        "",
        description="A human-readable description or a callable returning one.",
    )
    input: SignatureType = Field(
        None,
        description=(
            "Signature for input keys. Supports type hints (:) and descriptions (|). "
            "E.g., 'query: str | Search query, context: dict | Conversation context'. Can be a callable."
        ),
    )
    output: SignatureType = Field(
        None,
        description=(
            "Signature for output keys. Supports type hints (:) and descriptions (|). "
            "E.g., 'result: str | Generated result, summary: str | Brief summary'. Can be a callable."
        ),
    )
    tools: list[Callable[..., Any]] | None = (
        Field(  # Assume tools are always callable for serialization simplicity
            default=None,
            description="List of callable tools the agent can use. These must be registered.",
        )
    )
    servers: list[str | FlockMCPServer] | None = Field(
        default=None,
        description="List of MCP Servers the agent can use to enhance its capabilities. These must be registered.",
    )

    write_to_file: bool = Field(
        default=False,
        description="Write the agent's output to a file.",
    )
    wait_for_input: bool = Field(
        default=False,
        description="Wait for user input after the agent's output is displayed.",
    )

    # --- Components ---
    evaluator: FlockEvaluator | None = Field(  # Make optional, allow None
        default=None,
        description="The evaluator instance defining the agent's core logic.",
    )
    handoff_router: FlockRouter | None = Field(  # Make optional, allow None
        default=None,
        description="Router determining the next agent in the workflow.",
    )
    modules: dict[str, FlockModule] = Field(  # Keep as dict
        default_factory=dict,
        description="Dictionary of FlockModules attached to this agent.",
    )

    config: FlockAgentConfig = Field(
        default_factory=lambda: FlockAgentConfig(),
        description="Configuration for this agent, holding various settings and parameters.",
    )

    # --- Temporal Configuration (Optional) ---
    temporal_activity_config: TemporalActivityConfig | None = Field(
        default=None,
        description="Optional Temporal settings specific to this agent's activity execution.",
    )

    # --- Runtime State (Excluded from Serialization) ---
    context: FlockContext | None = Field(
        default=None,
        exclude=True,  # Exclude context from model_dump and serialization
        description="Runtime context associated with the flock execution.",
    )

    def __init__(
        self,
        name: str,
        model: str | None = None,
        description: str | Callable[..., str] | None = "",
        input: SignatureType = None,
        output: SignatureType = None,
        tools: list[Callable[..., Any]] | None = None,
        servers: list[str | FlockMCPServer] | None = None,
        evaluator: FlockEvaluator | None = None,
        handoff_router: FlockRouter | None = None,
        # Use dict for modules
        modules: dict[str, FlockModule] | None = None,
        write_to_file: bool = False,
        wait_for_input: bool = False,
        temporal_activity_config: TemporalActivityConfig | None = None,
        **kwargs,
    ):
        super().__init__(
            name=name,
            model=model,
            description=description,
            input=input,  # Store the raw input spec
            output=output,  # Store the raw output spec
            tools=tools,
            servers=servers,
            write_to_file=write_to_file,
            wait_for_input=wait_for_input,
            evaluator=evaluator,
            handoff_router=handoff_router,
            modules=modules
            if modules is not None
            else {},  # Ensure modules is a dict
            temporal_activity_config=temporal_activity_config,
            **kwargs,
        )

        if isinstance(self.input, type) and issubclass(self.input, BaseModel):
            self._input_model = self.input
        if isinstance(self.output, type) and issubclass(self.output, BaseModel):
            self._output_model = self.output

        # Initialize composed components
        self._components = FlockAgentComponents(self)
        self._lifecycle = FlockAgentLifecycle(self)
        self._execution = FlockAgentExecution(self)
        self._integration = FlockAgentIntegration(self)
        self._serialization = FlockAgentSerialization(self)

    # --- Properties and simple methods ---
    @property
    def resolved_description(self) -> str | None:
        """Returns the resolved agent description.
        If the description is a callable, it attempts to call it.
        Returns None if the description is None or a callable that fails.
        """
        if callable(self.description):
            try:
                # Attempt to call without context first.
                # If callables consistently need context, this might need adjustment
                # or the template-facing property might need to be simpler,
                # relying on prior resolution via resolve_callables.
                return self.description()
            except TypeError:
                # Log a warning that context might be needed?
                # For now, treat as unresolvable in this simple property.
                from flock.core.logging.logging import get_logger
                logger = get_logger("agent")
                logger.warning(
                    f"Callable description for agent '{self.name}' could not be resolved "
                    f"without context via the simple 'resolved_description' property. "
                    f"Consider calling 'agent.resolve_callables(context)' beforehand if context is required."
                )
                return None # Or a placeholder like "[Callable Description]"
            except Exception as e:
                from flock.core.logging.logging import get_logger
                logger = get_logger("agent")
                logger.error(
                    f"Error resolving callable description for agent '{self.name}': {e}"
                )
                return None
        elif isinstance(self.description, str):
            return self.description
        return None

    # --- Delegated Methods (Component Management) ---
    def add_module(self, module: FlockModule) -> None:
        """Add a module to this agent."""
        return self._components.add_module(module)

    def remove_module(self, module_name: str) -> None:
        """Remove a module from this agent."""
        return self._components.remove_module(module_name)

    def get_module(self, module_name: str) -> FlockModule | None:
        """Get a module by name."""
        return self._components.get_module(module_name)

    def get_enabled_components(self) -> list[FlockModule]:
        """Get a list of currently enabled modules attached to this agent."""
        return self._components.get_enabled_components()

    def add_component(
        self,
        config_instance: FlockModuleConfig
        | FlockRouterConfig
        | FlockEvaluatorConfig,
        component_name: str | None = None,
    ) -> "FlockAgent":
        """Adds or replaces a component (Evaluator, Router, Module) based on its configuration object."""
        return self._components.add_component(config_instance, component_name)

    def set_model(self, model: str):
        """Set the model for the agent and its evaluator."""
        return self._components.set_model(model)

    # --- Delegated Methods (Lifecycle) ---
    async def initialize(self, inputs: dict[str, Any]) -> None:
        """Initialize agent and run module initializers."""
        return await self._lifecycle.initialize(inputs)

    async def terminate(
        self, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Terminate agent and run module terminators."""
        return await self._lifecycle.terminate(inputs, result)

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        """Handle errors and run module error handlers."""
        return await self._lifecycle.on_error(error, inputs)

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Core evaluation logic, calling the assigned evaluator and modules."""
        return await self._lifecycle.evaluate(inputs)

    # --- Delegated Methods (Execution) ---
    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper for run_async."""
        return self._execution.run(inputs)

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Asynchronous execution logic with lifecycle hooks."""
        return await self._execution.run_async(inputs)

    async def run_temporal(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute agent using Temporal workflow orchestration."""
        return await self._execution.run_temporal(inputs)

    # --- Delegated Methods (Integration) ---
    def resolve_callables(self, context: FlockContext | None = None) -> None:
        """Resolves callable fields (description, input, output) using context."""
        return self._integration.resolve_callables(context)

    # --- Delegated Methods (Serialization) ---
    def _save_output(self, agent_name: str, result: dict[str, Any]) -> None:
        """Save output to file if configured."""
        return self._serialization._save_output(agent_name, result)

    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary representation suitable for serialization."""
        return self._serialization.to_dict()

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize the agent from a dictionary, including components, tools, and callables."""
        return FlockAgentSerialization.from_dict(cls, data)

    # --- Pydantic v2 Configuration ---
    class Config:
        arbitrary_types_allowed = (
            True  # Important for components like evaluator, router etc.
        )
