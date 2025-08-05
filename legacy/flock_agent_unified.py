# src/flock/core/flock_agent_unified.py
"""FlockAgent with unified component architecture - NEXT GENERATION VERSION."""

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
from flock.core.component.routing_component import RoutingModuleBase
from flock.core.config.flock_agent_config import FlockAgentConfig
from flock.core.context.context import FlockContext
from flock.core.flock_router import HandOffRequest
from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_server import FlockMCPServer

# Mixins and Serialization components
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.serialization.serializable import Serializable
from flock.workflow.temporal_config import TemporalActivityConfig

logger = get_logger("agent.unified")

T = TypeVar("T", bound="FlockAgentUnified")

SignatureType = (
    str
    | Callable[..., str]
    | type[BaseModel]
    | Callable[..., type[BaseModel]]
    | None
)


class FlockAgentUnified(BaseModel, Serializable, DSPyIntegrationMixin, ABC):
    """Unified FlockAgent using the new component architecture.
    
    This is the next-generation FlockAgent that uses a single components list
    instead of separate evaluator, router, and modules. All agent functionality
    is now provided through AgentComponent instances.
    
    Key changes:
    - components: list[AgentComponent] - unified component list
    - next_handoff: HandOffRequest | None - explicit workflow state
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
    description: str | Callable[..., str] | None = Field(
        "",
        description="A human-readable description or a callable returning one.",
    )
    input: SignatureType = Field(
        None,
        description="Signature for input keys. Supports type hints (:) and descriptions (|).",
    )
    output: SignatureType = Field(
        None,
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

    write_to_file: bool = Field(
        default=False,
        description="Write the agent's output to a file.",
    )
    wait_for_input: bool = Field(
        default=False,
        description="Wait for user input after the agent's output is displayed.",
    )

    # --- UNIFIED COMPONENT SYSTEM ---
    components: list[AgentComponent] = Field(
        default_factory=list,
        description="List of all agent components (evaluators, routers, modules).",
    )

    # --- EXPLICIT WORKFLOW STATE ---
    next_handoff: HandOffRequest | None = Field(
        default=None,
        exclude=True,  # Runtime state, don't serialize
        description="Next step in workflow, set by routing components.",
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
        description: str | Callable[..., str] | None = "",
        input: SignatureType = None,
        output: SignatureType = None,
        tools: list[Callable[..., Any]] | None = None,
        servers: list[str | FlockMCPServer] | None = None,
        components: list[AgentComponent] | None = None,
        write_to_file: bool = False,
        wait_for_input: bool = False,
        temporal_activity_config: TemporalActivityConfig | None = None,
        **kwargs,
    ):
        super().__init__(
            name=name,
            model=model,
            description=description,
            input=input,
            output=output,
            tools=tools,
            servers=servers,
            components=components if components is not None else [],
            write_to_file=write_to_file,
            wait_for_input=wait_for_input,
            temporal_activity_config=temporal_activity_config,
            **kwargs,
        )

        # Initialize helper systems (reuse existing logic)
        self._execution = FlockAgentExecution(self)
        self._integration = FlockAgentIntegration(self)
        self._serialization = FlockAgentSerialization(self)

    # --- CONVENIENCE PROPERTIES ---
    # These provide familiar access patterns while using the unified model

    @property
    def evaluator(self) -> EvaluationComponent | None:
        """Get the primary evaluation component for this agent."""
        return next(
            (c for c in self.components if isinstance(c, EvaluationComponent)),
            None
        )

    @property
    def router(self) -> RoutingModuleBase | None:
        """Get the primary routing component for this agent."""
        return next(
            (c for c in self.components if isinstance(c, RoutingModuleBase)),
            None
        )

    @property
    def modules(self) -> list[AgentComponent]:
        """Get all components (for backward compatibility with module-style access)."""
        return self.components.copy()

    # --- COMPONENT MANAGEMENT ---

    def add_component(self, component: AgentComponent) -> None:
        """Add a component to this agent."""
        if not component.name:
            logger.error("Component must have a name to be added.")
            return

        # Check for existing component with same name
        existing = next((c for c in self.components if c.name == component.name), None)
        if existing:
            logger.warning(f"Replacing existing component: {component.name}")
            self.components.remove(existing)

        self.components.append(component)
        logger.debug(f"Added component '{component.name}' to agent '{self.name}'")

    def remove_component(self, component_name: str) -> None:
        """Remove a component from this agent."""
        component = next((c for c in self.components if c.name == component_name), None)
        if component:
            self.components.remove(component)
            logger.debug(f"Removed component '{component_name}' from agent '{self.name}'")
        else:
            logger.warning(f"Component '{component_name}' not found on agent '{self.name}'.")

    def get_component(self, component_name: str) -> AgentComponent | None:
        """Get a component by name."""
        return next((c for c in self.components if c.name == component_name), None)

    def get_enabled_components(self) -> list[AgentComponent]:
        """Get a list of currently enabled components."""
        return [c for c in self.components if c.config.enabled]

    # --- BACKWARD COMPATIBILITY METHODS ---
    # These maintain the old API while using the new architecture

    def add_module(self, module: AgentComponent) -> None:
        """Add a module (backward compatibility)."""
        self.add_component(module)

    def remove_module(self, module_name: str) -> None:
        """Remove a module (backward compatibility)."""
        self.remove_component(module_name)

    def get_module(self, module_name: str) -> AgentComponent | None:
        """Get a module (backward compatibility)."""
        return self.get_component(module_name)

    def get_enabled_components(self) -> list[AgentComponent]:
        """Get enabled modules (backward compatibility)."""
        return self.get_enabled_components()

    # --- UNIFIED LIFECYCLE EXECUTION ---

    async def initialize(self, inputs: dict[str, Any]) -> None:
        """Initialize agent and run component initializers."""
        logger.debug(f"Initializing unified agent '{self.name}'")

        for component in self.get_enabled_components():
            try:
                await component.on_initialize(self, inputs, self.context)
            except Exception as e:
                logger.error(f"Error initializing component '{component.name}': {e}")

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Core evaluation logic using unified component system."""
        logger.debug(f"Evaluating unified agent '{self.name}'")

        current_inputs = inputs

        # 1. Pre-evaluate hooks (all components)
        for component in self.get_enabled_components():
            try:
                current_inputs = await component.on_pre_evaluate(self, current_inputs, self.context)
            except Exception as e:
                logger.error(f"Error in pre-evaluate for component '{component.name}': {e}")

        # 2. Core evaluation (primary evaluator component)
        result = current_inputs  # Default if no evaluator

        evaluator = self.evaluator
        if evaluator:
            try:
                # Get tools through integration system
                registered_tools = self.tools or []
                mcp_tools = await self._integration.get_mcp_tools() if self.servers else []

                result = await evaluator.evaluate_core(
                    self, current_inputs, self.context, registered_tools, mcp_tools
                )
            except Exception as e:
                logger.error(f"Error in core evaluation: {e}")
                raise
        else:
            logger.warning(f"Agent '{self.name}' has no evaluation component")

        # 3. Post-evaluate hooks (all components)
        current_result = result
        for component in self.get_enabled_components():
            try:
                tmp_result = await component.on_post_evaluate(
                    self, current_inputs, self.context, current_result
                )
                if tmp_result is not None:
                    current_result = tmp_result
            except Exception as e:
                logger.error(f"Error in post-evaluate for component '{component.name}': {e}")

        # 4. Determine next step (routing components)
        self.next_handoff = None  # Reset

        router = self.router
        if router:
            try:
                self.next_handoff = await router.determine_next_step(
                    self, current_result, self.context
                )
            except Exception as e:
                logger.error(f"Error in routing: {e}")

        return current_result

    async def terminate(self, inputs: dict[str, Any], result: dict[str, Any]) -> None:
        """Terminate agent and run component terminators."""
        logger.debug(f"Terminating unified agent '{self.name}'")

        current_result = result

        for component in self.get_enabled_components():
            try:
                tmp_result = await component.on_terminate(self, inputs, self.context, current_result)
                if tmp_result is not None:
                    current_result = tmp_result
            except Exception as e:
                logger.error(f"Error in terminate for component '{component.name}': {e}")

        # Handle output file writing
        if self.write_to_file:
            self._serialization._save_output(self.name, current_result)

        if self.wait_for_input:
            input("Press Enter to continue...")

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        """Handle errors and run component error handlers."""
        logger.error(f"Error occurred in unified agent '{self.name}': {error}")

        for component in self.get_enabled_components():
            try:
                await component.on_error(self, inputs, self.context, error)
            except Exception as e:
                logger.error(f"Error in error handler for component '{component.name}': {e}")

    # --- EXECUTION METHODS ---
    # Delegate to the execution system

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper for run_async."""
        return self._execution.run(inputs)

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Asynchronous execution logic with unified lifecycle."""
        try:
            await self.initialize(inputs)
            result = await self.evaluate(inputs)
            await self.terminate(inputs, result)
            logger.info("Unified agent run completed", agent=self.name)
            return result
        except Exception as run_error:
            logger.error(f"Error running unified agent: {run_error}")
            await self.on_error(run_error, inputs)
            raise

    # --- SERIALIZATION ---
    # Delegate to the serialization system

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary - will need updates for unified components."""
        # TODO: Update serialization for unified component model
        return self._serialization.to_dict()

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize from dictionary - will need updates for unified components."""
        # TODO: Update deserialization for unified component model
        return FlockAgentSerialization.from_dict(cls, data)

    # --- Pydantic v2 Configuration ---
    class Config:
        arbitrary_types_allowed = True
