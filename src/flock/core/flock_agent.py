# src/flock/core/flock_agent.py
"""FlockAgent with unified component architecture."""

import uuid
from abc import ABC
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from flock.core.agent.flock_agent_execution import FlockAgentExecution
from flock.core.agent.flock_agent_integration import FlockAgentIntegration
from flock.core.agent.flock_agent_serialization import FlockAgentSerialization
from flock.core.component.agent_component_base import AgentComponent
from flock.core.component.evaluation_component import (
    EvaluationComponent,
)
from flock.core.component.routing_component import RoutingComponent
from flock.core.config.flock_agent_config import FlockAgentConfig
from flock.core.context.context import FlockContext
from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_server import FlockMCPServer

# Mixins and Serialization components
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.serialization.serializable import Serializable
from flock.workflow.temporal_config import TemporalActivityConfig

logger = get_logger("agent.unified")

T = TypeVar("T", bound="FlockAgent")


DynamicStr = str | Callable[[FlockContext], str]

class FlockAgent(BaseModel, Serializable, DSPyIntegrationMixin, ABC):
    """Unified FlockAgent using the new component architecture.
    
    This is the next-generation FlockAgent that uses a single components list
    instead of separate evaluator, router, and modules. All agent functionality
    is now provided through AgentComponent instances.
    
    Key changes:
    - components: list[AgentComponent] - unified component list
    - next_agent: str | None - explicit workflow state
    - evaluator/router properties - convenience access to primary components
    """

    agent_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Internal, Unique UUID4 for this agent instance.",
    )

    name: str = Field(..., description="Unique identifier for the agent.")

    model: str | None = Field(
        None,
        description="The model identifier to use (e.g., 'openai/gpt-4o'). If None, uses Flock's default.",
    )
    description_spec: DynamicStr | None = Field(
        default="",
        alias="description",
        validation_alias="description",
        description="A human-readable description or a callable returning one.",
    )
    input_spec: DynamicStr | None = Field(
        default="",
        alias="input",
        validation_alias="input",
        description="Signature for input keys. Supports type hints (:) and descriptions (|).",
    )
    output_spec: DynamicStr | None = Field(
        default="",
        alias="output",
        validation_alias="output",
        description="Signature for output keys. Supports type hints (:) and descriptions (|).",
    )
    tools: list[Callable[..., Any]] | None = Field(
        default=None,
        description="List of callable tools the agent can use. These must be registered.",
    )
    servers: list[str | FlockMCPServer] | None = Field(
        default=None,
        description="List of MCP Servers the agent can use to enhance its capabilities.",
    )

    # --- UNIFIED COMPONENT SYSTEM ---
    components: list[AgentComponent] = Field(
        default_factory=list,
        description="List of all agent components (evaluators, routers, modules).",
    )

    # --- EXPLICIT WORKFLOW STATE ---
    next_agent_spec: DynamicStr | None = Field(
        default=None,
        alias="next_agent",
        validation_alias="next_agent",
        description="Next agent in workflow - set by user or routing components.",
    )

    config: FlockAgentConfig = Field(
        default_factory=lambda: FlockAgentConfig(),
        description="Configuration for this agent.",
    )

    temporal_activity_config: TemporalActivityConfig | None = Field(
        default=None,
        description="Optional Temporal settings specific to this agent.",
    )

    # --- Runtime State (Excluded from Serialization) ---
    context: FlockContext | None = Field(
        default=None,
        exclude=True,
        description="Runtime context associated with the flock execution.",
    )

    def __init__(
        self,
        name: str,
        model: str | None = None,
        description: DynamicStr | None = None,
        input: DynamicStr | None = None,
        output: DynamicStr | None = None,
        tools: list[Callable[..., Any]] | None = None,
        servers: list[str | FlockMCPServer] | None = None,
        components: list[AgentComponent] | None = None,
        config: FlockAgentConfig | None = None,
        next_agent: DynamicStr | None = None,
        temporal_activity_config: TemporalActivityConfig | None = None,
    ):
        """Initialize the unified FlockAgent with components and configuration."""
        if config is None:
            config = FlockAgentConfig()
        super().__init__(
            name=name,
            model=model,
            description=description,
            input=input,
            output=output,
            tools=tools,
            servers=servers,
            components=components if components is not None else [],
            config=config,
            temporal_activity_config=temporal_activity_config,
            next_agent=next_agent,
        )

        # Initialize helper systems (reuse existing logic)
        self._execution = FlockAgentExecution(self)
        self._integration = FlockAgentIntegration(self)
        self._serialization = FlockAgentSerialization(self)
        # Lifecycle will be lazy-loaded when needed

    # --- CONVENIENCE PROPERTIES ---
    # These provide familiar access patterns while using the unified model

    @property
    def evaluator(self) -> EvaluationComponent | None:
        """Get the primary evaluation component for this agent."""
        return self._components.get_primary_evaluator()

    @property
    def router(self) -> RoutingComponent | None:
        """Get the primary routing component for this agent."""
        return self._components.get_primary_router()

    @property
    def modules(self) -> list[AgentComponent]:
        """Get all components (for backward compatibility with module-style access)."""
        return self.components.copy()

    @property
    def _components(self):
        """Get the component management helper."""
        if not hasattr(self, '_components_helper'):
            from flock.core.agent.flock_agent_components import (
                FlockAgentComponents,
            )
            self._components_helper = FlockAgentComponents(self)
        return self._components_helper

    # Component management delegated to _components
    def add_component(self, component: AgentComponent) -> None:
        """Add a component to this agent."""
        self._components.add_component(component)

    def remove_component(self, component_name: str) -> None:
        """Remove a component from this agent."""
        self._components.remove_component(component_name)

    def get_component(self, component_name: str) -> AgentComponent | None:
        """Get a component by name."""
        return self._components.get_component(component_name)


    def get_enabled_components(self) -> list[AgentComponent]:
        """Get enabled components (backward compatibility)."""
        return self._components.get_enabled_components()

    # --- LIFECYCLE DELEGATION ---
    # Delegate lifecycle methods to the composition objects

    @property
    def _lifecycle(self):
        """Get the lifecycle management helper (lazy-loaded)."""
        if not hasattr(self, '_lifecycle_helper'):
            from flock.core.agent.flock_agent_lifecycle import (
                FlockAgentLifecycle,
            )
            self._lifecycle_helper = FlockAgentLifecycle(self)
        return self._lifecycle_helper

    async def initialize(self, inputs: dict[str, Any]) -> None:
        """Initialize agent and run component initializers."""
        return await self._lifecycle.initialize(inputs)

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Core evaluation logic using unified component system."""
        return await self._lifecycle.evaluate(inputs)

    async def terminate(self, inputs: dict[str, Any], result: dict[str, Any]) -> None:
        """Terminate agent and run component terminators."""
        return await self._lifecycle.terminate(inputs, result)

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        """Handle errors and run component error handlers."""
        return await self._lifecycle.on_error(error, inputs)

    # --- EXECUTION METHODS ---
    # Delegate to the execution system

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper for run_async."""
        return self._execution.run(inputs)

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Asynchronous execution logic with unified lifecycle."""
        return await self._execution.run_async(inputs)

    # --- SERIALIZATION ---
    # Delegate to the serialization system

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary using unified component serialization."""
        return self._serialization.to_dict()

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize from dictionary using unified component deserialization."""
        return FlockAgentSerialization.from_dict(cls, data)

    def set_model(self, model: str):
        """Set the model for the agent and its evaluator.
        
        This method updates both the agent's model property and propagates
        the model to the evaluator component if it has a config with a model field.
        """
        self.model = model
        if self.evaluator and hasattr(self.evaluator, "config"):
            self.evaluator.config.model = model
            logger.info(
                f"Set model to '{model}' for agent '{self.name}' and its evaluator."
            )
        elif self.evaluator:
            logger.warning(
                f"Evaluator for agent '{self.name}' does not have a standard config to set model."
            )
        else:
            logger.warning(
                f"Agent '{self.name}' has no evaluator to set model for."
            )

    @property
    def description(self) -> str | None:
        """Returns the resolved agent description."""
        return self._integration.resolve_description(self.context)

    @property
    def input(self) -> str | None:
        """Returns the resolved agent input."""
        return self._integration.resolve_input(self.context)

    @property
    def output(self) -> str | None:
        """Returns the resolved agent output."""
        return self._integration.resolve_output(self.context)

    @property
    def next_agent(self) -> str | None:
        """Returns the resolved agent next agent."""
        return self._integration.resolve_next_agent(self.context)

    @description.setter
    def description(self, value: DynamicStr) -> None:
        self.description_spec = value

    @input.setter
    def input(self, value: DynamicStr) -> None:
        self.input_spec = value

    @output.setter
    def output(self, value: DynamicStr) -> None:
        self.output_spec = value

    @next_agent.setter
    def next_agent(self, value: DynamicStr) -> None:
        self.next_agent_spec = value

    def _save_output(self, agent_name: str, result: dict[str, Any]) -> None:
        """Save output to file if configured (delegated to serialization)."""
        return self._serialization._save_output(agent_name, result)

    # --- Pydantic v2 Configuration ---
    model_config = {
        "arbitrary_types_allowed": True,
        "populate_by_name": True,
        # "json_encoders": {
        #     Callable: lambda f: f"{f.__module__}.{f.__qualname__}",
        # },
    }
