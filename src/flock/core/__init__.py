"""Core package public API with lazy imports.

This module exposes key symbols while avoiding heavy imports at package import time.
Symbols are imported lazily on first access via ``__getattr__``.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "Flock",
    "FlockAgent",
    "DefaultAgent",
    "FlockContext",
    "FlockFactory",
    # Components
    "AgentComponent",
    "AgentComponentConfig",
    "EvaluationComponent",
    "RoutingComponent",
    "UtilityComponent",
    # MCP
    "FlockMCPClient",
    "FlockMCPClientManager",
    "FlockMCPServer",
    "FlockMCPTool",
    # Registry
    "FlockRegistry",
    "flock_callable",
    "flock_component",
    "flock_tool",
    "flock_type",
    "get_registry",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - thin loader
    if name == "Flock":
        from .flock import Flock

        return Flock
    if name == "FlockAgent":
        from .flock_agent import FlockAgent

        return FlockAgent
    if name == "DefaultAgent":
        from .agent.default_agent import DefaultAgent

        return DefaultAgent
    if name == "FlockContext":
        from .context.context import FlockContext

        return FlockContext
    if name == "FlockFactory":
        from .flock_factory import FlockFactory

        return FlockFactory
    if name in {"AgentComponent", "AgentComponentConfig", "EvaluationComponent", "RoutingComponent", "UtilityComponent"}:
        from .component import (
            AgentComponent,
            AgentComponentConfig,
            EvaluationComponent,
            RoutingComponent,
            UtilityComponent,
        )

        return {
            "AgentComponent": AgentComponent,
            "AgentComponentConfig": AgentComponentConfig,
            "EvaluationComponent": EvaluationComponent,
            "RoutingComponent": RoutingComponent,
            "UtilityComponent": UtilityComponent,
        }[name]
    if name in {"FlockMCPClient", "FlockMCPClientManager", "FlockMCPServer", "FlockMCPTool"}:
        if name == "FlockMCPClient":
            from .mcp.mcp_client import FlockMCPClient

            return FlockMCPClient
        if name == "FlockMCPClientManager":
            from .mcp.mcp_client_manager import FlockMCPClientManager

            return FlockMCPClientManager
        if name == "FlockMCPServer":
            from .mcp.flock_mcp_server import FlockMCPServer

            return FlockMCPServer
        if name == "FlockMCPTool":
            from .mcp.flock_mcp_tool import FlockMCPTool

            return FlockMCPTool
    if name in {"FlockRegistry", "flock_callable", "flock_component", "flock_tool", "flock_type", "get_registry"}:
        from .registry import (
            RegistryHub as FlockRegistry,
            flock_callable,
            flock_component,
            flock_tool,
            flock_type,
            get_registry,
        )

        return {
            "FlockRegistry": FlockRegistry,
            "flock_callable": flock_callable,
            "flock_component": flock_component,
            "flock_tool": flock_tool,
            "flock_type": flock_type,
            "get_registry": get_registry,
        }[name]
    raise AttributeError(name)
