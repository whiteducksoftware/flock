"""Orchestrator initialization helper.

Handles component setup and state initialization.
Extracted from orchestrator.py to reduce __init__ complexity.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any

from flock.core.store import InMemoryBlackboardStore
from flock.orchestrator.artifact_collector import ArtifactCollector
from flock.orchestrator.batch_accumulator import BatchEngine
from flock.orchestrator.component_runner import ComponentRunner
from flock.orchestrator.context_builder import ContextBuilder
from flock.orchestrator.correlation_engine import CorrelationEngine
from flock.orchestrator.event_emitter import EventEmitter
from flock.orchestrator.lifecycle_manager import LifecycleManager
from flock.orchestrator.mcp_manager import MCPManager
from flock.orchestrator.tracing import TracingManager
from flock.utils.cli_helper import init_console


if TYPE_CHECKING:
    from flock.components.orchestrator import OrchestratorComponent
    from flock.core.store import BlackboardStore


class OrchestratorInitializer:
    """Handles orchestrator component initialization.

    Centralizes the complex setup logic from Flock.__init__ into
    a focused helper class.
    """

    @staticmethod
    def initialize_components(
        store: BlackboardStore | None,
        context_provider: Any,
        max_agent_iterations: int,
        logger: logging.Logger,
        model: str | None,
    ) -> dict[str, Any]:
        """Initialize all orchestrator components and state.

        Args:
            store: Blackboard storage backend (or None for default)
            context_provider: Global context provider for agents
            max_agent_iterations: Circuit breaker limit
            logger: Logger instance
            model: Default LLM model

        Returns:
            Dictionary of initialized components and state

        Examples:
            >>> logger = logging.getLogger(__name__)
            >>> components = OrchestratorInitializer.initialize_components(
            ...     store=None,
            ...     context_provider=None,
            ...     max_agent_iterations=1000,
            ...     logger=logger,
            ...     model="openai/gpt-4.1",
            ... )
            >>> orchestrator.store = components["store"]
            >>> orchestrator._scheduler = components["scheduler"]
        """
        # Initialize console (with error handling for encoding issues)
        try:
            init_console(clear_screen=True, show_banner=True, model=model)
        except (UnicodeEncodeError, UnicodeDecodeError):
            # Skip banner on Windows consoles with encoding issues (e.g., tests, CI)
            pass

        # Basic state
        resolved_store = store or InMemoryBlackboardStore()
        agents: dict[str, Any] = {}
        lock = asyncio.Lock()
        metrics: dict[str, float] = {"artifacts_published": 0, "agent_runs": 0}
        agent_iteration_count: dict[str, int] = {}

        # Engines
        artifact_collector = ArtifactCollector()
        correlation_engine = CorrelationEngine()
        batch_engine = BatchEngine()

        # Phase 5A modules
        context_builder = ContextBuilder(
            store=resolved_store,
            default_context_provider=context_provider,
        )
        event_emitter = EventEmitter(websocket_manager=None)
        lifecycle_manager = LifecycleManager(
            correlation_engine=correlation_engine,
            batch_engine=batch_engine,
            cleanup_interval=0.1,
        )

        # Phase 3 modules
        mcp_manager_instance = MCPManager()
        tracing_manager = TracingManager()

        # Auto-workflow tracing feature flag
        auto_workflow_enabled = os.getenv(
            "FLOCK_AUTO_WORKFLOW_TRACE", "false"
        ).lower() in {
            "true",
            "1",
            "yes",
            "on",
        }

        return {
            # Basic state
            "store": resolved_store,
            "agents": agents,
            "lock": lock,
            "metrics": metrics,
            "agent_iteration_count": agent_iteration_count,
            # Engines
            "artifact_collector": artifact_collector,
            "correlation_engine": correlation_engine,
            "batch_engine": batch_engine,
            # Phase 5A modules
            "context_builder": context_builder,
            "event_emitter": event_emitter,
            "lifecycle_manager": lifecycle_manager,
            # Phase 3 modules
            "mcp_manager_instance": mcp_manager_instance,
            "tracing_manager": tracing_manager,
            # Feature flags
            "auto_workflow_enabled": auto_workflow_enabled,
            # Placeholders
            "websocket_manager": None,
        }

    @staticmethod
    def initialize_components_and_runner(
        components_list: list[OrchestratorComponent],
        max_agent_iterations: int,
        logger: logging.Logger,
    ) -> dict[str, Any]:
        """Initialize built-in components and create ComponentRunner.

        Args:
            components_list: List to populate with components
            max_agent_iterations: Circuit breaker limit
            logger: Logger instance

        Returns:
            Dictionary with component_runner and updated components list

        Examples:
            >>> components = []
            >>> result = OrchestratorInitializer.initialize_components_and_runner(
            ...     components, max_agent_iterations=1000, logger=logger
            ... )
            >>> component_runner = result["component_runner"]
        """
        from flock.components.orchestrator import (
            BuiltinCollectionComponent,
            CircuitBreakerComponent,
            DeduplicationComponent,
        )

        # Add built-in components
        components_list.append(
            CircuitBreakerComponent(max_iterations=max_agent_iterations)
        )
        components_list.append(DeduplicationComponent())
        components_list.append(BuiltinCollectionComponent())

        # Sort by priority
        components_list.sort(key=lambda c: c.priority)

        # Create ComponentRunner
        component_runner = ComponentRunner(components_list, logger)

        return {
            "component_runner": component_runner,
        }
