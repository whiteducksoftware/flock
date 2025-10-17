"""Orchestrator module - extracted components for better organization.

This package contains the modularized orchestrator functionality:
- component_runner: Component lifecycle hook execution
- mcp_manager: MCP server configuration and management
"""

from flock._orchestrator.component_runner import ComponentRunner
from flock._orchestrator.mcp_manager import MCPManager


__all__ = [
    "ComponentRunner",
    "MCPManager",
]
