# src/flock/core/component/agent_component_base.py
"""Base classes for the unified Flock component system."""

from abc import ABC
from typing import Any, TypeVar

from pydantic import BaseModel, Field, create_model

from flock.core.context.context import FlockContext

# HandOffRequest removed - using agent.next_agent directly

T = TypeVar("T", bound="AgentComponentConfig")


class AgentComponentConfig(BaseModel):
    """Base configuration class for all Flock agent components.
    
    This unified config class replaces FlockModuleConfig, FlockEvaluatorConfig, 
    and FlockRouterConfig, providing common functionality for all component types.
    """

    enabled: bool = Field(
        default=True,
        description="Whether this component is currently enabled"
    )

    model: str | None = Field(
        default=None,
        description="Model to use for this component (if applicable)"
    )

    @classmethod
    def with_fields(cls: type[T], **field_definitions) -> type[T]:
        """Create a new config class with additional fields.
        
        This allows dynamic config creation for components with custom configuration needs.
        
        Example:
            CustomConfig = AgentComponentConfig.with_fields(
                temperature=Field(default=0.7, description="LLM temperature"),
                max_tokens=Field(default=1000, description="Max tokens to generate")
            )
        """
        return create_model(
            f"Dynamic{cls.__name__}",
            __base__=cls,
            **field_definitions
        )


class AgentComponent(BaseModel, ABC):
    """Base class for all Flock agent components.
    
    This unified base class replaces the separate FlockModule, FlockEvaluator, 
    and FlockRouter base classes. All agent extensions now inherit from this 
    single base class and use the unified lifecycle hooks.
    
    Components can specialize by:
    - EvaluationComponentBase: Implements evaluate_core() for agent intelligence
    - RoutingComponentBase: Implements determine_next_step() for workflow routing  
    - UtilityComponentBase: Uses standard lifecycle hooks for cross-cutting concerns
    """

    name: str = Field(
        ...,
        description="Unique identifier for this component"
    )

    config: AgentComponentConfig = Field(
        default_factory=AgentComponentConfig,
        description="Component configuration"
    )

    def __init__(self, **data):
        super().__init__(**data)

    # --- Standard Lifecycle Hooks ---
    # These are called for ALL components during agent execution

    async def on_initialize(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Called when the agent starts running.
        
        Use this for component initialization, resource setup, etc.
        """
        pass

    async def on_pre_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
    ) -> dict[str, Any]:
        """Called before agent evaluation, can modify inputs.
        
        Args:
            agent: The agent being executed
            inputs: Current input data
            context: Execution context
            
        Returns:
            Modified input data (or original if no changes)
        """
        return inputs

    async def on_post_evaluate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Called after agent evaluation, can modify results.
        
        Args:
            agent: The agent that was executed  
            inputs: Original input data
            context: Execution context
            result: Evaluation result
            
        Returns:
            Modified result data (or original if no changes)
        """
        return result

    async def on_terminate(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Called when the agent finishes running.
        
        Use this for cleanup, final result processing, etc.
        """
        return result

    async def on_error(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        error: Exception | None = None,
    ) -> None:
        """Called when an error occurs during agent execution.
        
        Use this for error handling, logging, recovery, etc.
        """
        pass

    # --- Specialized Hooks ---
    # These are overridden by specialized component types

    async def evaluate_core(
        self,
        agent: Any,
        inputs: dict[str, Any],
        context: FlockContext | None = None,
        tools: list[Any] | None = None,
        mcp_tools: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Core evaluation logic - override in EvaluationComponentBase.
        
        This is where the main "intelligence" of the agent happens.
        Only one component per agent should implement this meaningfully.
        
        Args:
            agent: The agent being executed
            inputs: Input data for evaluation
            context: Execution context  
            tools: Available tools for the agent
            mcp_tools: Available MCP tools
            
        Returns:
            Evaluation result
        """
        # Default implementation is pass-through
        return inputs

    async def determine_next_step(
        self,
        agent: Any,
        result: dict[str, Any],
        context: FlockContext | None = None,
    ) -> None:
        """Determine the next step in the workflow - override in RoutingComponentBase.
        
        This is where routing decisions are made. Sets agent.next_agent directly.
        
        Args:
            agent: The agent that just completed
            result: Result from the agent's evaluation
            context: Execution context
            
        Returns:
            None - routing components set agent.next_agent directly
        """
        # Default implementation provides no routing
        pass

    # --- MCP Server Lifecycle Hooks ---
    # For components that interact directly with MCP servers

    async def on_pre_server_init(self, server: Any) -> None:
        """Called before a server initializes."""
        pass

    async def on_post_server_init(self, server: Any) -> None:
        """Called after a server initializes."""
        pass

    async def on_pre_server_terminate(self, server: Any) -> None:
        """Called before a server terminates."""
        pass

    async def on_post_server_terminate(self, server: Any) -> None:
        """Called after a server terminates."""
        pass

    async def on_server_error(self, server: Any, error: Exception) -> None:
        """Called when a server errors."""
        pass

    async def on_connect(
        self,
        server: Any,
        additional_params: dict[str, Any],
    ) -> dict[str, Any]:
        """Called before a connection is being established to a mcp server.

        use `server` (type FlockMCPServer) to modify the core behavior of the server.
        use `additional_params` to 'tack_on' additional configurations (for example additional headers for sse-clients.)

        (For example: modify the server's config)
        new_config = NewConfigObject(...)
        server.config = new_config

        Warning:
            Be very careful when modifying a server's internal state.
            If you just need to 'tack on' additional information (such as headers)
            or want to temporarily override certain configurations (such as timeouts)
            use `additional_params` instead if you can.

        (Or pass additional values downstream:)
        additional_params["headers"] = { "Authorization": "Bearer 123" }
        additional_params["read_timeout_seconds"] = 100


        Note:
            `additional_params` resets between mcp_calls.
            so there is not persistence between individual calls.
            This choice has been made to allow developers to
            dynamically switch configurations.
            (This can be used, for example, to use a module to inject oauth headers for
            individual users on a call-to-call basis. this also gives you direct control over
            managing the headers yourself. For example, checking for lifetimes on JWT-Tokens.)

        Note:
            you can access `additional_params` when you are implementing your own subclasses of
            FlockMCPClientManager and FlockMCPClient. (with self.additional_params.)

        keys which are processed for `additional_params` in the flock core code are:
        --- General ---

        "refresh_client": bool -> defaults to False. Indicates whether or not to restart a connection on a call. (can be used when headers oder api-keys change to automatically switch to a new client.)
        "read_timeout_seconds": float -> How long to wait for a connection to happen.

        --- SSE ---

        "override_headers": bool -> default False. If set to false, additional headers will be appended, if set to True, additional headers will override existing ones.
        "headers": dict[str, Any] -> Additional Headers injected in sse-clients and ws-clients
        "sse_read_timeout_seconds": float -> how long until a connection is being terminated for sse-clients.
        "url": str -> which url the server listens on (allows switching between mcp-servers with modules.)

        --- Stdio ---

        "command": str -> Command to run for stdio-servers.
        "args": list[str] -> additional paramters for stdio-servers.
        "env": dict[str, Any] -> Environment-Variables for stdio-servers.
        "encoding": str -> Encoding to use when talking to stdio-servers.
        "encoding-error-handler": str -> Encoding error handler to use when talking to stdio-servers.

        --- Websockets ---

        "url": str -> Which url the server listens on (allows switching between mcp-servers with modules.)
        """
        pass

    async def on_pre_mcp_call(
        self,
        server: Any,
        arguments: Any | None = None,
    ) -> None:
        """Called before any MCP Calls."""
        pass

    async def on_post_mcp_call(
        self,
        server: Any,
        result: Any | None = None,
    ) -> None:
        """Called after any MCP Calls."""
        pass
