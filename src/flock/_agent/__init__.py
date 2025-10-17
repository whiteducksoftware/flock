"""Agent internal modules.

Phase 4: Extracted modules from agent.py for improved maintainability.

This package contains internal implementation details for the Agent class.
These modules are not part of the public API.
"""

from flock._agent.component_lifecycle import ComponentLifecycle
from flock._agent.context_resolver import ContextResolver
from flock._agent.mcp_integration import MCPIntegration
from flock._agent.output_processor import OutputProcessor


__all__ = [
    "ComponentLifecycle",
    "ContextResolver",
    "MCPIntegration",
    "OutputProcessor",
]
