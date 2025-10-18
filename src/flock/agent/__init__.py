"""Agent implementation modules.

This package contains internal implementation details for the Agent class.

Phase 5B Additions:
- BuilderHelpers: PublishBuilder, RunHandle, Pipeline helper classes
- BuilderValidator: Validation and normalization logic for AgentBuilder
"""

from flock.agent.builder_helpers import Pipeline, PublishBuilder, RunHandle
from flock.agent.builder_validator import BuilderValidator
from flock.agent.component_lifecycle import ComponentLifecycle
from flock.agent.context_resolver import ContextResolver
from flock.agent.mcp_integration import MCPIntegration
from flock.agent.output_processor import OutputProcessor
from flock.core.visibility import AgentIdentity


__all__ = [
    "AgentIdentity",
    "BuilderHelpers",
    "BuilderValidator",
    "ComponentLifecycle",
    "ContextResolver",
    "MCPIntegration",
    "OutputProcessor",
    "Pipeline",
    "PublishBuilder",
    "RunHandle",
]
