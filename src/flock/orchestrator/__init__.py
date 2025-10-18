"""Orchestrator implementation modules.

This package contains internal implementation details for the Flock orchestrator.

Phase 5A Additions:
- ContextBuilder: Security-critical context building with provider resolution
- EventEmitter: Dashboard WebSocket event emission
- LifecycleManager: Background task coordination for batches and correlations
"""

from flock.orchestrator.artifact_manager import ArtifactManager
from flock.orchestrator.component_runner import ComponentRunner
from flock.orchestrator.context_builder import ContextBuilder
from flock.orchestrator.event_emitter import EventEmitter
from flock.orchestrator.lifecycle_manager import LifecycleManager
from flock.orchestrator.mcp_manager import MCPManager
from flock.orchestrator.scheduler import AgentScheduler


__all__ = [
    "AgentScheduler",
    "ArtifactManager",
    "ComponentRunner",
    "ContextBuilder",
    "EventEmitter",
    "LifecycleManager",
    "MCPManager",
]
