# src/flock/core/flock_agent.py
"""FlockAgent is the core, declarative base class for all agents in the Flock framework."""

import asyncio
import json
import os
import uuid
from abc import ABC
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from flock.core.config.flock_agent_config import FlockAgentConfig
from flock.core.mcp.flock_mcp_server import FlockMCPServer
from flock.core.serialization.json_encoder import FlockJSONEncoder
from flock.workflow.temporal_config import TemporalActivityConfig

if TYPE_CHECKING:
    from flock.core.context.context import FlockContext
    from flock.core.flock_evaluator import FlockEvaluator
    from flock.core.flock_module import FlockModule
    from flock.core.flock_router import FlockRouter

from opentelemetry import trace
from pydantic import BaseModel, Field

# Core Flock components (ensure these are importable)
from flock.core.context.context import FlockContext
from flock.core.flock_evaluator import FlockEvaluator, FlockEvaluatorConfig
from flock.core.flock_module import FlockModule, FlockModuleConfig
from flock.core.flock_router import FlockRouter, FlockRouterConfig
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
        evaluator: "FlockEvaluator | None" = None,
        handoff_router: "FlockRouter | None" = None,
        # Use dict for modules
        modules: dict[str, "FlockModule"] | None = None,
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

    def get_enabled_components(self) -> list[FlockModule]:
        """Get a list of currently enabled modules attached to this agent."""
        return [m for m in self.modules.values() if m.config.enabled]

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
                logger.warning(
                    f"Callable description for agent '{self.name}' could not be resolved "
                    f"without context via the simple 'resolved_description' property. "
                    f"Consider calling 'agent.resolve_callables(context)' beforehand if context is required."
                )
                return None # Or a placeholder like "[Callable Description]"
            except Exception as e:
                logger.error(
                    f"Error resolving callable description for agent '{self.name}': {e}"
                )
                return None
        elif isinstance(self.description, str):
            return self.description
        return None

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
                for module in self.get_enabled_components():
                    await module.on_initialize(self, inputs, self.context)
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
                current_result = result
                for module in self.get_enabled_components():
                    tmp_result = await module.on_terminate(
                        self, inputs, self.context, current_result
                    )
                    # If the module returns a result, use it
                    if tmp_result:
                        current_result = tmp_result

                if self.write_to_file:
                    self._save_output(self.name, current_result)

                if self.wait_for_input:
                    # simple input prompt
                    input("Press Enter to continue...")

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
                for module in self.get_enabled_components():
                    await module.on_error(self, inputs, self.context, error)
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
            for module in self.get_enabled_components():
                current_inputs = await module.on_pre_evaluate(
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

                # Retrieve available mcp_tools if the evaluator needs them
                mcp_tools = []
                if self.servers:
                    from flock.core.flock_registry import get_registry

                    FlockRegistry = get_registry()  # Get the registry
                    for server in self.servers:
                        registered_server: FlockMCPServer | None = None
                        server_tools = []
                        if isinstance(server, FlockMCPServer):
                            # check if registered
                            server_name = server.config.name
                            registered_server = FlockRegistry.get_server(
                                server_name
                            )
                        else:
                            # servers must be registered.
                            registered_server = FlockRegistry.get_server(
                                name=server
                            )
                        if registered_server:
                            server_tools = await registered_server.get_tools(
                                agent_id=self.agent_id,
                                run_id=self.context.run_id,
                            )
                        else:
                            logger.warning(
                                f"No Server with name '{server.config.name}' registered! Skipping."
                            )
                        mcp_tools = mcp_tools + server_tools

                # --------------------------------------------------
                # Optional DI middleware pipeline
                # --------------------------------------------------
                container = None
                if self.context is not None:
                    container = self.context.get_variable("di.container")

                # If a MiddlewarePipeline is registered in DI, wrap the evaluator
                result: dict[str, Any] | None = None

                if container is not None:
                    try:
                        from wd.di.middleware import (
                            MiddlewarePipeline,
                        )

                        pipeline: MiddlewarePipeline | None = None
                        try:
                            pipeline = container.get_service(MiddlewarePipeline)
                        except Exception:
                            pipeline = None

                        if pipeline is not None:
                            # Build execution chain where the evaluator is the terminal handler

                            async def _final_handler():
                                return await self.evaluator.evaluate(
                                    self, current_inputs, registered_tools
                                )

                            idx = 0

                            async def _invoke_next():
                                nonlocal idx

                                if idx < len(pipeline._middleware):
                                    mw = pipeline._middleware[idx]
                                    idx += 1
                                    return await mw(self.context, _invoke_next)  # type: ignore[arg-type]
                                return await _final_handler()

                            # Execute pipeline
                            result = await _invoke_next()
                        else:
                            # No pipeline registered, direct evaluation
                            result = await self.evaluator.evaluate(
                                self, current_inputs, registered_tools
                            )
                    except ImportError:
                        # wd.di not installed – fall back
                        result = await self.evaluator.evaluate(
                            self, current_inputs, registered_tools
                        )
                else:
                    # No DI container – standard execution
                    result = await self.evaluator.evaluate(
                        self,
                    current_inputs,
                    registered_tools,
                    mcp_tools=mcp_tools,
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
            for module in self.get_enabled_components():
                tmp_result = await module.on_post_evaluate(
                    self,
                    current_inputs,
                    self.context,
                    current_result,
                )
                # If the module returns a result, use it
                if tmp_result:
                    current_result = tmp_result

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

    def add_component(
        self,
        config_instance: FlockModuleConfig
        | FlockRouterConfig
        | FlockEvaluatorConfig,
        component_name: str | None = None,
    ) -> "FlockAgent":
        """Adds or replaces a component (Evaluator, Router, Module) based on its configuration object.

        Args:
            config_instance: An instance of a config class inheriting from
                             FlockModuleConfig, FlockRouterConfig, or FlockEvaluatorConfig.
            component_name: Explicit name for the component (required for Modules if not in config).

        Returns:
            self for potential chaining.
        """
        from flock.core.flock_registry import get_registry

        config_type = type(config_instance)
        registry = get_registry()  # Get registry instance
        logger.debug(
            f"Attempting to add component via config: {config_type.__name__}"
        )

        # --- 1. Find Component Class using Registry Map ---
        ComponentClass = registry.get_component_class_for_config(config_type)

        if not ComponentClass:
            logger.error(
                f"No component class registered for config type {config_type.__name__}. Use @flock_component(config_class=...) on the component."
            )
            raise TypeError(
                f"Cannot find component class for config {config_type.__name__}"
            )

        component_class_name = ComponentClass.__name__
        logger.debug(
            f"Found component class '{component_class_name}' mapped to config '{config_type.__name__}'"
        )

        # --- 2. Determine Assignment Target and Name (Same as before) ---
        instance_name = component_name
        attribute_name: str = ""

        if issubclass(ComponentClass, FlockEvaluator):
            attribute_name = "evaluator"
            if not instance_name:
                instance_name = getattr(
                    config_instance, "name", component_class_name.lower()
                )

        elif issubclass(ComponentClass, FlockRouter):
            attribute_name = "handoff_router"
            if not instance_name:
                instance_name = getattr(
                    config_instance, "name", component_class_name.lower()
                )

        elif issubclass(ComponentClass, FlockModule):
            attribute_name = "modules"
            if not instance_name:
                instance_name = getattr(
                    config_instance, "name", component_class_name.lower()
                )
            if not instance_name:
                raise ValueError(
                    "Module name must be provided either in config or as component_name argument."
                )
            # Ensure config has name if module expects it
            if hasattr(config_instance, "name") and not getattr(
                config_instance, "name", None
            ):
                setattr(config_instance, "name", instance_name)

        else:  # Should be caught by registry map logic ideally
            raise TypeError(
                f"Class '{component_class_name}' mapped from config is not a valid Flock component."
            )

        # --- 3. Instantiate the Component (Same as before) ---
        try:
            init_args = {"config": config_instance, "name": instance_name}

            component_instance = ComponentClass(**init_args)
        except Exception as e:
            logger.error(
                f"Failed to instantiate {ComponentClass.__name__} with config {config_type.__name__}: {e}",
                exc_info=True,
            )
            raise RuntimeError(f"Component instantiation failed: {e}") from e

        # --- 4. Assign to the Agent (Same as before) ---
        if attribute_name == "modules":
            if not isinstance(self.modules, dict):
                self.modules = {}
            self.modules[instance_name] = component_instance
            logger.info(
                f"Added/Updated module '{instance_name}' (type: {ComponentClass.__name__}) to agent '{self.name}'"
            )
        else:
            setattr(self, attribute_name, component_instance)
            logger.info(
                f"Set {attribute_name} to {ComponentClass.__name__} (instance name: '{instance_name}') for agent '{self.name}'"
            )

        return self

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

    def _save_output(self, agent_name: str, result: dict[str, Any]) -> None:
        """Save output to file if configured."""
        if not self.write_to_file:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{agent_name}_output_{timestamp}.json"
        filepath = os.path.join(".flock/output/", filename)
        os.makedirs(".flock/output/", exist_ok=True)

        output_data = {
            "agent": agent_name,
            "timestamp": timestamp,
            "output": result,
        }

        try:
            with open(filepath, "w") as f:
                json.dump(output_data, f, indent=2, cls=FlockJSONEncoder)
        except Exception as e:
            logger.warning(f"Failed to save output to file: {e}")

    def to_dict(self) -> dict[str, Any]:
        """Convert instance to dictionary representation suitable for serialization."""
        from flock.core.flock_registry import get_registry

        FlockRegistry = get_registry()

        exclude = [
            "context",
            "evaluator",
            "modules",
            "handoff_router",
            "tools",
            "servers",
        ]

        is_descrition_callable = False
        is_input_callable = False
        is_output_callable = False

        # if self.description is a callable, exclude it
        if callable(self.description):
            is_descrition_callable = True
            exclude.append("description")
        # if self.input is a callable, exclude it
        if callable(self.input):
            is_input_callable = True
            exclude.append("input")
        # if self.output is a callable, exclude it
        if callable(self.output):
            is_output_callable = True
            exclude.append("output")

        logger.debug(f"Serializing agent '{self.name}' to dict.")
        # Use Pydantic's dump, exclude manually handled fields and runtime context
        data = self.model_dump(
            exclude=exclude,
            mode="json",  # Use json mode for better handling of standard types by Pydantic
            exclude_none=True,  # Exclude None values for cleaner output
        )
        logger.debug(f"Base agent data for '{self.name}': {list(data.keys())}")
        serialized_modules = {}

        def add_serialized_component(component: Any, field_name: str):
            if component:
                comp_type = type(component)
                type_name = FlockRegistry.get_component_type_name(
                    comp_type
                )  # Get registered name
                if type_name:
                    try:
                        serialized_component_data = serialize_item(component)

                        if not isinstance(serialized_component_data, dict):
                            logger.error(
                                f"Serialization of component {type_name} for field '{field_name}' did not result in a dictionary. Got: {type(serialized_component_data)}"
                            )
                            serialized_modules[field_name] = {
                                "type": type_name,
                                "name": getattr(component, "name", "unknown"),
                                "error": "serialization_failed_non_dict",
                            }
                        else:
                            serialized_component_data["type"] = type_name
                            serialized_modules[field_name] = (
                                serialized_component_data
                            )
                            logger.debug(
                                f"Successfully serialized component for field '{field_name}' (type: {type_name})"
                            )

                    except Exception as e:
                        logger.error(
                            f"Failed to serialize component {type_name} for field '{field_name}': {e}",
                            exc_info=True,
                        )
                        serialized_modules[field_name] = {
                            "type": type_name,
                            "name": getattr(component, "name", "unknown"),
                            "error": "serialization_failed",
                        }
                else:
                    logger.warning(
                        f"Cannot serialize unregistered component {comp_type.__name__} for field '{field_name}'"
                    )

        add_serialized_component(self.evaluator, "evaluator")
        if serialized_modules:
            data["evaluator"] = serialized_modules["evaluator"]
            logger.debug(f"Added evaluator to agent '{self.name}'")

        serialized_modules = {}
        add_serialized_component(self.handoff_router, "handoff_router")
        if serialized_modules:
            data["handoff_router"] = serialized_modules["handoff_router"]
            logger.debug(f"Added handoff_router to agent '{self.name}'")

        serialized_modules = {}
        for module in self.modules.values():
            add_serialized_component(module, module.name)

        if serialized_modules:
            data["modules"] = serialized_modules
            logger.debug(
                f"Added {len(serialized_modules)} modules to agent '{self.name}'"
            )

        # --- Serialize Servers ---
        if self.servers:
            logger.debug(
                f"Serializing {len(self.servers)} servers for agent '{self.name}'"
            )
            serialized_servers = []
            for server in self.servers:
                if isinstance(server, FlockMCPServer):
                    serialized_servers.append(server.config.name)
                else:
                    # Write it down as a list of server names.
                    serialized_servers.append(server)

            if serialized_servers:
                data["mcp_servers"] = serialized_servers
                logger.debug(
                    f"Added {len(serialized_servers)} servers to agent '{self.name}'"
                )

        # --- Serialize Tools (Callables) ---
        if self.tools:
            logger.debug(
                f"Serializing {len(self.tools)} tools for agent '{self.name}'"
            )
            serialized_tools = []
            for tool in self.tools:
                if callable(tool) and not isinstance(tool, type):
                    path_str = FlockRegistry.get_callable_path_string(tool)
                    if path_str:
                        # Get just the function name from the path string
                        # If it's a namespaced path like module.submodule.function_name
                        # Just use the function_name part
                        func_name = path_str.split(".")[-1]
                        serialized_tools.append(func_name)
                        logger.debug(
                            f"Added tool '{func_name}' (from path '{path_str}') to agent '{self.name}'"
                        )
                    else:
                        logger.warning(
                            f"Could not get path string for tool {tool} in agent '{self.name}'. Skipping."
                        )
                else:
                    logger.warning(
                        f"Non-callable item found in tools list for agent '{self.name}': {tool}. Skipping."
                    )
            if serialized_tools:
                data["tools"] = serialized_tools
                logger.debug(
                    f"Added {len(serialized_tools)} tools to agent '{self.name}'"
                )

        if is_descrition_callable:
            path_str = FlockRegistry.get_callable_path_string(self.description)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["description_callable"] = func_name
                logger.debug(
                    f"Added description '{func_name}' (from path '{path_str}') to agent '{self.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for description {self.description} in agent '{self.name}'. Skipping."
                )

        if is_input_callable:
            path_str = FlockRegistry.get_callable_path_string(self.input)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["input_callable"] = func_name
                logger.debug(
                    f"Added input '{func_name}' (from path '{path_str}') to agent '{self.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for input {self.input} in agent '{self.name}'. Skipping."
                )

        if is_output_callable:
            path_str = FlockRegistry.get_callable_path_string(self.output)
            if path_str:
                func_name = path_str.split(".")[-1]
                data["output_callable"] = func_name
                logger.debug(
                    f"Added output '{func_name}' (from path '{path_str}') to agent '{self.name}'"
                )
            else:
                logger.warning(
                    f"Could not get path string for output {self.output} in agent '{self.name}'. Skipping."
                )

        # No need to call _filter_none_values here as model_dump(exclude_none=True) handles it
        logger.info(
            f"Serialization of agent '{self.name}' complete with {len(data)} fields"
        )
        return data

    @classmethod
    def from_dict(cls: type[T], data: dict[str, Any]) -> T:
        """Deserialize the agent from a dictionary, including components, tools, and callables."""
        from flock.core.flock_registry import (
            get_registry,  # Import registry locally
        )

        registry = get_registry()
        logger.debug(
            f"Deserializing agent from dict. Keys: {list(data.keys())}"
        )

        # --- Separate Data ---
        component_configs = {}
        callable_configs = {}
        tool_config = []
        servers_config = []
        agent_data = {}

        component_keys = [
            "evaluator",
            "handoff_router",
            "modules",
            "temporal_activity_config",
        ]
        callable_keys = [
            "description_callable",
            "input_callable",
            "output_callable",
        ]
        tool_key = "tools"

        servers_key = "mcp_servers"

        for key, value in data.items():
            if key in component_keys and value is not None:
                component_configs[key] = value
            elif key in callable_keys and value is not None:
                callable_configs[key] = value
            elif key == tool_key and value is not None:
                tool_config = value  # Expecting a list of names
            elif key == servers_key and value is not None:
                servers_config = value  # Expecting a list of names
            elif key not in component_keys + callable_keys + [
                tool_key,
                servers_key,
            ]:  # Avoid double adding
                agent_data[key] = value
            # else: ignore keys that are None or already handled

        # --- Deserialize Base Agent ---
        # Ensure required fields like 'name' are present if needed by __init__
        if "name" not in agent_data:
            raise ValueError(
                "Agent data must include a 'name' field for deserialization."
            )
        agent_name_log = agent_data["name"]  # For logging
        logger.info(f"Deserializing base agent data for '{agent_name_log}'")

        # Pydantic should handle base fields based on type hints in __init__
        agent = cls(**agent_data)
        logger.debug(f"Base agent '{agent.name}' instantiated.")

        # --- Deserialize Components ---
        logger.debug(f"Deserializing components for '{agent.name}'")
        # Evaluator
        if "evaluator" in component_configs:
            try:
                agent.evaluator = deserialize_component(
                    component_configs["evaluator"], FlockEvaluator
                )
                logger.debug(f"Deserialized evaluator for '{agent.name}'")
            except Exception as e:
                logger.error(
                    f"Failed to deserialize evaluator for '{agent.name}': {e}",
                    exc_info=True,
                )

        # Handoff Router
        if "handoff_router" in component_configs:
            try:
                agent.handoff_router = deserialize_component(
                    component_configs["handoff_router"], FlockRouter
                )
                logger.debug(f"Deserialized handoff_router for '{agent.name}'")
            except Exception as e:
                logger.error(
                    f"Failed to deserialize handoff_router for '{agent.name}': {e}",
                    exc_info=True,
                )

        # Modules
        if "modules" in component_configs:
            agent.modules = {}  # Initialize
            for module_name, module_data in component_configs[
                "modules"
            ].items():
                try:
                    module_instance = deserialize_component(
                        module_data, FlockModule
                    )
                    if module_instance:
                        # Use add_module for potential logic within it
                        agent.add_module(module_instance)
                        logger.debug(
                            f"Deserialized and added module '{module_name}' for '{agent.name}'"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to deserialize module '{module_name}' for '{agent.name}': {e}",
                        exc_info=True,
                    )

        # Temporal Activity Config
        if "temporal_activity_config" in component_configs:
            try:
                agent.temporal_activity_config = TemporalActivityConfig(
                    **component_configs["temporal_activity_config"]
                )
                logger.debug(
                    f"Deserialized temporal_activity_config for '{agent.name}'"
                )
            except Exception as e:
                logger.error(
                    f"Failed to deserialize temporal_activity_config for '{agent.name}': {e}",
                    exc_info=True,
                )
                agent.temporal_activity_config = None

        # --- Deserialize Tools ---
        agent.tools = []  # Initialize tools list
        if tool_config:
            logger.debug(
                f"Deserializing {len(tool_config)} tools for '{agent.name}'"
            )
            # Use get_callable to find each tool
            for tool_name_or_path in tool_config:
                try:
                    found_tool = registry.get_callable(tool_name_or_path)
                    if found_tool and callable(found_tool):
                        agent.tools.append(found_tool)
                        logger.debug(
                            f"Resolved and added tool '{tool_name_or_path}' for agent '{agent.name}'"
                        )
                    else:
                        # Should not happen if get_callable returns successfully but just in case
                        logger.warning(
                            f"Registry returned non-callable for tool '{tool_name_or_path}' for agent '{agent.name}'. Skipping."
                        )
                except (
                    ValueError
                ) as e:  # get_callable raises ValueError if not found/ambiguous
                    logger.warning(
                        f"Could not resolve tool '{tool_name_or_path}' for agent '{agent.name}': {e}. Skipping."
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error resolving tool '{tool_name_or_path}' for agent '{agent.name}': {e}. Skipping.",
                        exc_info=True,
                    )

        # --- Deserialize Servers ---
        agent.servers = []  # Initialize Servers list.
        if servers_config:
            logger.debug(
                f"Deserializing {len(servers_config)} servers for '{agent.name}'"
            )
            # Agents keep track of server by getting a list of server names.
            # The server instances will be retrieved during runtime from the registry. (default behavior)

            for server_name in servers_config:
                if isinstance(server_name, str):
                    # Case 1 (default behavior): A server name is passe.
                    agent.servers.append(server_name)
                elif isinstance(server_name, FlockMCPServer):
                    # Case 2 (highly unlikely): If someone somehow manages to pass
                    # an instance of a server during the deserialization step (however that might be achieved)
                    # check the registry, if the server is already registered, if not, register it
                    # and store the name in the servers list
                    FlockRegistry = get_registry()
                    server_exists = (
                        FlockRegistry.get_server(server_name.config.name)
                        is not None
                    )
                    if server_exists:
                        agent.servers.append(server_name.config.name)
                    else:
                        FlockRegistry.register_server(
                            server=server_name
                        )  # register it.
                        agent.servers.append(server_name.config.name)

        # --- Deserialize Callables ---
        logger.debug(f"Deserializing callable fields for '{agent.name}'")
        # available_callables = registry.get_all_callables() # Incorrect

        def resolve_and_assign(field_name: str, callable_key: str):
            if callable_key in callable_configs:
                callable_name = callable_configs[callable_key]
                try:
                    # Use get_callable to find the signature function
                    found_callable = registry.get_callable(callable_name)
                    if found_callable and callable(found_callable):
                        setattr(agent, field_name, found_callable)
                        logger.debug(
                            f"Resolved callable '{callable_name}' for field '{field_name}' on agent '{agent.name}'"
                        )
                    else:
                        logger.warning(
                            f"Registry returned non-callable for name '{callable_name}' for field '{field_name}' on agent '{agent.name}'. Field remains default."
                        )
                except (
                    ValueError
                ) as e:  # get_callable raises ValueError if not found/ambiguous
                    logger.warning(
                        f"Could not resolve callable '{callable_name}' in registry for field '{field_name}' on agent '{agent.name}': {e}. Field remains default."
                    )
                except Exception as e:
                    logger.error(
                        f"Unexpected error resolving callable '{callable_name}' for field '{field_name}' on agent '{agent.name}': {e}. Field remains default.",
                        exc_info=True,
                    )
            # Else: key not present, field retains its default value from __init__

        resolve_and_assign("description", "description_callable")
        resolve_and_assign("input", "input_callable")
        resolve_and_assign("output", "output_callable")

        logger.info(f"Successfully deserialized agent '{agent.name}'.")
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
