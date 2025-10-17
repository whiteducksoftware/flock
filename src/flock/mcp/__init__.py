"""MCP (Model Context Protocol) Integration for Flock-Flow.

This package provides integration with MCP servers, enabling agents to
dynamically discover and use external tools following the Model Context Protocol.

Architecture Decisions:
- AD001: Two-Level Architecture (orchestrator + agent)
- AD003: Tool Namespacing ({server}__{tool})
- AD004: Per-(agent_id, run_id) Connection Isolation
- AD005: Lazy Connection Establishment
- AD007: Graceful Degradation on MCP Failures

Key Components:
- FlockMCPConfiguration: Server configuration
- FlockMCPClient: Individual server connection
- FlockMCPClientManager: Connection pooling and lifecycle
- FlockMCPTool: MCP tool wrapper compatible with DSPy

Example Usage:
    ```python
    from flock import Flock
    from flock.mcp import StdioServerParameters

    # Create orchestrator
    orchestrator = Flock()

    # Register MCP server
    orchestrator.add_mcp(
        name="filesystem",
        connection_params=StdioServerParameters(
            command="uvx", args=["mcp-server-filesystem", "/tmp"]
        ),
    )

    # Build agent with MCP access
    agent = (
        orchestrator.agent("file_agent").with_mcps(["filesystem"]).build()
    )
    ```
"""

from flock.mcp.client import FlockMCPClient
from flock.mcp.config import (
    FlockMCPCachingConfiguration,
    FlockMCPCallbackConfiguration,
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
    FlockMCPFeatureConfiguration,
)
from flock.mcp.manager import FlockMCPClientManager
from flock.mcp.tool import FlockMCPTool
from flock.mcp.types import (
    FlockListRootsMCPCallback,
    FlockLoggingMCPCallback,
    FlockMessageHandlerMCPCallback,
    FlockSamplingMCPCallback,
    MCPRoot,
    ServerParameters,
    SseServerParameters,
    StdioServerParameters,
    StreamableHttpServerParameters,
    WebsocketServerParameters,
)


__all__ = [
    "FlockListRootsMCPCallback",
    "FlockLoggingMCPCallback",
    "FlockMCPCachingConfiguration",
    "FlockMCPCallbackConfiguration",
    # Client and Manager
    "FlockMCPClient",
    "FlockMCPClientManager",
    # Configuration
    "FlockMCPConfiguration",
    "FlockMCPConnectionConfiguration",
    "FlockMCPFeatureConfiguration",
    "FlockMCPTool",
    "FlockMessageHandlerMCPCallback",
    "FlockSamplingMCPCallback",
    "MCPRoot",
    # Types
    "ServerParameters",
    "SseServerParameters",
    "StdioServerParameters",
    "StreamableHttpServerParameters",
    "WebsocketServerParameters",
]
