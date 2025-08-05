"""This module contains the core classes of the flock package."""

from flock.core.component import (
    AgentComponent,
    AgentComponentConfig,
    EvaluationComponent,
    RoutingComponent,
    UtilityComponent,
)
from flock.core.context.context import FlockContext
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.flock_factory import FlockFactory
from flock.core.mcp.flock_mcp_server import (
    FlockMCPServer,
)
from flock.core.mcp.flock_mcp_tool import FlockMCPTool
from flock.core.mcp.mcp_client import FlockMCPClient
from flock.core.mcp.mcp_client_manager import FlockMCPClientManager
from flock.core.registry import (
    RegistryHub as FlockRegistry,  # Keep FlockRegistry name for API compatibility
    flock_callable,
    flock_component,
    flock_tool,
    flock_type,
    get_registry,
)

__all__ = [
    "Flock",
    "FlockAgent",
    "FlockContext",
    "FlockFactory",
        # Components
    "AgentComponent",
    "AgentComponentConfig",
    "EvaluationComponent",
    "RoutingComponent",
    "UtilityComponent",

    "FlockMCPClient",
    "FlockMCPClientManager",
    "FlockMCPServer",
    "FlockMCPServerConfig",
    "FlockMCPTool",
    "FlockRegistry",
    "flock_callable",
    "flock_component",
    "flock_tool",
    "flock_type",
    "get_registry",
]
