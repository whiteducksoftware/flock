# src/flock/core/flock_agent.py
"""FlockAgent is the core, declarative base class for all agents in the Flock framework."""

import asyncio
from abc import ABC
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from flock.core.context.context import FlockContext
    from flock.core.flock_evaluator import FlockEvaluator
    from flock.core.flock_module import FlockModule
    from flock.core.flock_router import FlockRouter

from opentelemetry import trace
from pydantic import BaseModel, Field

# Core Flock components (ensure these are importable)
from flock.core.context.context import FlockContext
from flock.core.flock_evaluator import FlockEvaluator
from flock.core.flock_module import FlockModule
from flock.core.flock_router import FlockRouter
from flock.core.logging.logging import get_logger

# Mixins and Serialization components
from flock.core.mixin.dspy_integration import DSPyIntegrationMixin
from flock.core.serialization.serializable import (
    Serializable,  # Import Serializable base
)
from flock.core.serialization.serialization_utils import (
    deserialize_component,
    serialize_item,
)

logger = get_logger("agent")
tracer = trace.get_tracer(__name__)
T = TypeVar("T", bound="FlockAgent")


# Make FlockAgent inherit from Serializable
class FlockAgent(BaseModel, Serializable, DSPyIntegrationMixin, ABC):
    """Core, declarative base class for Flock agents, enabling serialization,
    modularity, and integration with evaluation and routing components.
    Inherits from Pydantic BaseModel, ABC, DSPyIntegrationMixin, and Serializable.
    """

    name: str = Field(..., description="Unique identifier for the agent.")
    model: str | None = Field(
        None,
        description="The model identifier to use (e.g., 'openai/gpt-4o'). If None, uses Flock's default.",
    )
    description: str | Callable[..., str] | None = Field(
        "",
        description="A human-readable description or a callable returning one.",
    )
    input: str | Callable[..., str] | None = Field(
        None,
        description=(
            "Signature for input keys. Supports type hints (:) and descriptions (|). "
            "E.g., 'query: str | Search query, context: dict | Conversation context'. Can be a callable."
        ),
    )
    output: str | Callable[..., str] | None = Field(
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
    use_cache: bool = Field(
        default=True,
        description="Enable caching for the agent's evaluator (if supported).",
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

    # --- Runtime State (Excluded from Serialization) ---
    context: FlockContext | None = Field(
        default=None,
        exclude=True,  # Exclude context from model_dump and serialization
        description="Runtime context associated with the flock execution.",
    )

    # --- Existing Methods (add_module, remove_module, etc.) ---
    # (Keep these methods as they were, adding type hints where useful)
    def add_module(self, module: FlockModule) -> None:
        """Add a module to this agent."""
        if not module.name:
            logger.error("Module must have a name to be added.")
            return
        if module.name in self.modules:
            logger.warning(f"Overwriting existing module: {module.name}")
        self.modules[module.name] = module
        logger.debug(f"Added module '{module.name}' to agent '{self.name}'")

    def remove_module(self, module_name: str) -> None:
        """Remove a module from this agent."""
        if module_name in self.modules:
            del self.modules[module_name]
            logger.debug(
                f"Removed module '{module_name}' from agent '{self.name}'"
            )
        else:
            logger.warning(
                f"Module '{module_name}' not found on agent '{self.name}'."
            )

    def get_module(self, module_name: str) -> FlockModule | None:
        """Get a module by name."""
        return self.modules.get(module_name)

    def get_enabled_modules(self) -> list[FlockModule]:
        """Get a list of currently enabled modules attached to this agent."""
        return [m for m in self.modules.values() if m.config.enabled]

    # --- Lifecycle Hooks (Keep as they were) ---
    async def initialize(self, inputs: dict[str, Any]) -> None:
        """Initialize agent and run module initializers."""
        logger.debug(f"Initializing agent '{self.name}'")
        with tracer.start_as_current_span("agent.initialize") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            logger.info(
                f"agent.initialize",
                agent=self.name,
            )
            try:
                for module in self.get_enabled_modules():
                    await module.initialize(self, inputs, self.context)
            except Exception as module_error:
                logger.error(
                    "Error during initialize",
                    agent=self.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def terminate(
        self, inputs: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """Terminate agent and run module terminators."""
        logger.debug(f"Terminating agent '{self.name}'")
        with tracer.start_as_current_span("agent.terminate") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            span.set_attribute("result", str(result))
            logger.info(
                f"agent.terminate",
                agent=self.name,
            )
            try:
                for module in self.get_enabled_modules():
                    await module.terminate(self, inputs, result, self.context)
            except Exception as module_error:
                logger.error(
                    "Error during terminate",
                    agent=self.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def on_error(self, error: Exception, inputs: dict[str, Any]) -> None:
        """Handle errors and run module error handlers."""
        logger.error(f"Error occurred in agent '{self.name}': {error}")
        with tracer.start_as_current_span("agent.on_error") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                for module in self.get_enabled_modules():
                    await module.on_error(self, error, inputs, self.context)
            except Exception as module_error:
                logger.error(
                    "Error during on_error",
                    agent=self.name,
                    error=str(module_error),
                )
                span.record_exception(module_error)

    async def evaluate(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Core evaluation logic, calling the assigned evaluator and modules."""
        if not self.evaluator:
            raise RuntimeError(
                f"Agent '{self.name}' has no evaluator assigned."
            )
        with tracer.start_as_current_span("agent.evaluate") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            logger.info(
                f"agent.evaluate",
                agent=self.name,
            )

            logger.debug(f"Evaluating agent '{self.name}'")
            current_inputs = inputs

            # Pre-evaluate hooks
            for module in self.get_enabled_modules():
                current_inputs = await module.pre_evaluate(
                    self, current_inputs, self.context
                )

            # Actual evaluation
            try:
                # Pass registered tools if the evaluator needs them
                registered_tools = []
                if self.tools:
                    # Ensure tools are actually retrieved/validated if needed by evaluator type
                    # For now, assume evaluator handles tool resolution if necessary
                    registered_tools = self.tools

                result = await self.evaluator.evaluate(
                    self, current_inputs, registered_tools
                )
            except Exception as eval_error:
                logger.error(
                    "Error during evaluate",
                    agent=self.name,
                    error=str(eval_error),
                )
                span.record_exception(eval_error)
                await self.on_error(
                    eval_error, current_inputs
                )  # Call error hook
                raise  # Re-raise the exception

            # Post-evaluate hooks
            current_result = result
            for module in self.get_enabled_modules():
                current_result = await module.post_evaluate(
                    self, current_inputs, current_result, self.context
                )

            logger.debug(f"Evaluation completed for agent '{self.name}'")
            return current_result

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper for run_async."""
        try:
            loop = asyncio.get_running_loop()
        except (
            RuntimeError
        ):  # 'RuntimeError: There is no current event loop...'
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.run_async(inputs))

    def set_model(self, model: str):
        """Set the model for the agent and its evaluator."""
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

    async def run_async(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Asynchronous execution logic with lifecycle hooks."""
        with tracer.start_as_current_span("agent.run") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                await self.initialize(inputs)
                result = await self.evaluate(inputs)
                await self.terminate(inputs, result)
                span.set_attribute("result", str(result))
                logger.info("Agent run completed", agent=self.name)
                return result
            except Exception as run_error:
                logger.error(
                    "Error running agent", agent=self.name, error=str(run_error)
                )
                if "evaluate" not in str(
                    run_error
                ):  # Simple check, might need refinement
                    await self.on_error(run_error, inputs)
                logger.error(
                    f"Agent '{self.name}' run failed: {run_error}",
                    exc_info=True,
                )
                span.record_exception(run_error)
                raise  # Re-raise after handling

    async def run_temporal(self, inputs: dict[str, Any]) -> dict[str, Any]:
        with tracer.start_as_current_span("agent.run_temporal") as span:
            span.set_attribute("agent.name", self.name)
            span.set_attribute("inputs", str(inputs))
            try:
                from temporalio.client import Client

                from flock.workflow.agent_activities import (
                    run_flock_agent_activity,
                )
                from flock.workflow.temporal_setup import run_activity

                client = await Client.connect(
                    "localhost:7233", namespace="default"
                )
                agent_data = self.to_dict()
                inputs_data = inputs

                result = await run_activity(
                    client,
                    self.name,
                    run_flock_agent_activity,
                    {"agent_data": agent_data, "inputs": inputs_data},
                )
                span.set_attribute("result", str(result))
                logger.info("Temporal run successful", agent=self.name)
                return result
            except Exception as temporal_error:
                logger.error(
                    "Error in Temporal workflow",
                    agent=self.name,
                    error=str(temporal_error),
                )
                span.record_exception(temporal_error)
                raise

    # resolve_callables remains useful for dynamic definitions
    def resolve_callables(self, context: FlockContext | None = None) -> None:
        """Resolves callable fields (description, input, output) using context."""
        if callable(self.description):
            self.description = self.description(
                context
            )  # Pass context if needed by callable
        if callable(self.input):
            self.input = self.input(context)
        if callable(self.output):
            self.output = self.output(context)

    # --- Serialization Implementation ---

    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary representation suitable for serialization."""
        from flock.core.flock_registry import get_registry

        FlockRegistry = get_registry()
        logger.debug(f"Serializing agent '{self.name}' to dict.")
        # Use Pydantic's dump, exclude manually handled fields and runtime context
        data = self.model_dump(
            exclude={
                "context",
                "evaluator",
                "modules",
                "handoff_router",
                "tools",
            },
            mode="json",  # Use json mode for better handling of standard types by Pydantic
            exclude_none=True,  # Exclude None values for cleaner output
        )

        # --- Serialize Components using Registry Type Names ---
        # Evaluator
        if self.evaluator:
            evaluator_type_name = FlockRegistry.get_component_type_name(
                type(self.evaluator)
            )
            if evaluator_type_name:
                # Recursively serialize the evaluator's dict representation
                evaluator_dict = serialize_item(
                    self.evaluator.model_dump(mode="json", exclude_none=True)
                )
                evaluator_dict["type"] = evaluator_type_name  # Add type marker
                data["evaluator"] = evaluator_dict
            else:
                logger.warning(
                    f"Could not get registered type name for evaluator {type(self.evaluator).__name__} in agent '{self.name}'. Skipping serialization."
                )

        # Router
        if self.handoff_router:
            router_type_name = FlockRegistry.get_component_type_name(
                type(self.handoff_router)
            )
            if router_type_name:
                router_dict = serialize_item(
                    self.handoff_router.model_dump(
                        mode="json", exclude_none=True
                    )
                )
                router_dict["type"] = router_type_name
                data["handoff_router"] = router_dict
            else:
                logger.warning(
                    f"Could not get registered type name for router {type(self.handoff_router).__name__} in agent '{self.name}'. Skipping serialization."
                )

        # Modules
        if self.modules:
            serialized_modules = {}
            for name, module_instance in self.modules.items():
                module_type_name = FlockRegistry.get_component_type_name(
                    type(module_instance)
                )
                if module_type_name:
                    module_dict = serialize_item(
                        module_instance.model_dump(
                            mode="json", exclude_none=True
                        )
                    )
                    module_dict["type"] = module_type_name
                    serialized_modules[name] = module_dict
                else:
                    logger.warning(
                        f"Could not get registered type name for module {type(module_instance).__name__} ('{name}') in agent '{self.name}'. Skipping."
                    )
            if serialized_modules:
                data["modules"] = serialized_modules

        # --- Serialize Tools (Callables) ---
        if self.tools:
            serialized_tools = []
            for tool in self.tools:
                if callable(tool) and not isinstance(tool, type):
                    path_str = FlockRegistry.get_callable_path_string(tool)
                    if path_str:
                        serialized_tools.append({"__callable_ref__": path_str})
                    else:
                        logger.warning(
                            f"Could not get path string for tool {tool} in agent '{self.name}'. Skipping."
                        )
                # Silently skip non-callable items or log warning
                # else:
                #      logger.warning(f"Non-callable item found in tools list for agent '{self.name}': {tool}. Skipping.")
            if serialized_tools:
                data["tools"] = serialized_tools

        # No need to call _filter_none_values here as model_dump(exclude_none=True) handles it
        return data

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Create instance from dictionary representation."""
        from flock.core.flock_registry import get_registry

        logger.debug(
            f"Deserializing agent from dict. Provided keys: {list(data.keys())}"
        )
        if "name" not in data:
            raise ValueError("Agent data must include a 'name' field.")
        FlockRegistry = get_registry()
        agent_name = data["name"]  # For logging context

        # Pop complex components to handle them after basic agent instantiation
        evaluator_data = data.pop("evaluator", None)
        router_data = data.pop("handoff_router", None)
        modules_data = data.pop("modules", {})
        tools_data = data.pop("tools", [])

        # Deserialize remaining data recursively (handles nested basic types/callables)
        # Note: Pydantic v2 handles most basic deserialization well if types match.
        # Explicit deserialize_item might be needed if complex non-pydantic structures exist.
        # For now, assume Pydantic handles basic fields based on type hints.
        deserialized_basic_data = data  # Assume Pydantic handles basic fields

        try:
            # Create the agent instance using Pydantic's constructor
            agent = cls(**deserialized_basic_data)
        except Exception as e:
            logger.error(
                f"Pydantic validation/init failed for agent '{agent_name}': {e}",
                exc_info=True,
            )
            raise ValueError(
                f"Failed to initialize agent '{agent_name}' from dict: {e}"
            ) from e

        # --- Deserialize and Attach Components ---
        # Evaluator
        if evaluator_data:
            try:
                agent.evaluator = deserialize_component(
                    evaluator_data, FlockEvaluator
                )
                if agent.evaluator is None:
                    raise ValueError("deserialize_component returned None")
                logger.debug(
                    f"Deserialized evaluator '{agent.evaluator.name}' for agent '{agent_name}'"
                )
            except Exception as e:
                logger.error(
                    f"Failed to deserialize evaluator for agent '{agent_name}': {e}",
                    exc_info=True,
                )
                # Decide: raise error or continue without evaluator?
                # raise ValueError(f"Failed to deserialize evaluator for agent '{agent_name}': {e}") from e

        # Router
        if router_data:
            try:
                agent.handoff_router = deserialize_component(
                    router_data, FlockRouter
                )
                if agent.handoff_router is None:
                    raise ValueError("deserialize_component returned None")
                logger.debug(
                    f"Deserialized router '{agent.handoff_router.name}' for agent '{agent_name}'"
                )
            except Exception as e:
                logger.error(
                    f"Failed to deserialize router for agent '{agent_name}': {e}",
                    exc_info=True,
                )
                # Decide: raise error or continue without router?

        # Modules
        if modules_data:
            agent.modules = {}  # Ensure it's initialized
            for name, module_data in modules_data.items():
                try:
                    module_instance = deserialize_component(
                        module_data, FlockModule
                    )
                    if module_instance:
                        # Ensure instance name matches key if possible
                        module_instance.name = module_data.get("name", name)
                        agent.add_module(
                            module_instance
                        )  # Use add_module for consistency
                    else:
                        raise ValueError("deserialize_component returned None")
                except Exception as e:
                    logger.error(
                        f"Failed to deserialize module '{name}' for agent '{agent_name}': {e}",
                        exc_info=True,
                    )
                    # Decide: skip module or raise error?

        # --- Deserialize Tools ---
        agent.tools = []  # Initialize tools list
        if tools_data:
            for tool_ref in tools_data:
                if (
                    isinstance(tool_ref, dict)
                    and "__callable_ref__" in tool_ref
                ):
                    path_str = tool_ref["__callable_ref__"]
                    try:
                        tool_func = FlockRegistry.get_callable(path_str)
                        agent.tools.append(tool_func)
                    except KeyError:
                        logger.error(
                            f"Tool callable '{path_str}' not found in registry for agent '{agent_name}'. Skipping."
                        )
                else:
                    logger.warning(
                        f"Invalid tool format found during deserialization for agent '{agent_name}': {tool_ref}. Skipping."
                    )

        logger.info(f"Successfully deserialized agent: {agent.name}")
        return agent

    # --- Pydantic v2 Configuration ---
    class Config:
        arbitrary_types_allowed = (
            True  # Important for components like evaluator, router etc.
        )
        # Might need custom json_encoders if not using model_dump(mode='json') everywhere
        # json_encoders = {
        #      FlockEvaluator: lambda v: v.to_dict() if v else None,
        #      FlockRouter: lambda v: v.to_dict() if v else None,
        #      FlockModule: lambda v: v.to_dict() if v else None,
        # }
