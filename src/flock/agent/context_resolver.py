"""Agent context resolution - future context provider integration.

Phase 4: Extracted from agent.py to organize context provider logic.

NOTE: This module provides the foundation for context provider resolution.
Currently minimal as context resolution happens at the orchestrator level.
This extraction prepares for future refactoring where agents will have
more control over their execution context.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from flock.core import Agent
    from flock.core.artifacts import Artifact
    from flock.core.subscription import Subscription
    from flock.utils.runtime import Context

logger = get_logger(__name__)


class ContextResolver:
    """Manages context provider resolution for agent execution.

    This module handles determining which context provider to use
    and potentially fetching context artifacts in future phases.

    Currently minimal as context resolution is orchestrator-level.
    This extraction prepares for Phase 6 refactoring where context
    providers will be more agent-centric.
    """

    def __init__(self, agent_name: str):
        """Initialize ContextResolver for a specific agent.

        Args:
            agent_name: Name of the agent (for logging)
        """
        self._agent_name = agent_name
        self._logger = logging.getLogger(__name__)

    def get_provider(
        self, agent: Agent, default_provider: Any | None = None
    ) -> Any | None:
        """Determine which context provider to use for this agent.

        Resolution order:
        1. Agent-specific provider (agent.context_provider)
        2. Orchestrator default provider (default_provider)
        3. None (no provider configured)

        Args:
            agent: Agent instance
            default_provider: Default provider from orchestrator

        Returns:
            Context provider to use, or None if not configured
        """
        # Check agent-specific provider first (Phase 3 security fix)
        if agent.context_provider is not None:
            logger.debug(
                f"Agent context resolution: agent={self._agent_name}, "
                f"using_agent_provider=True"
            )
            return agent.context_provider

        # Fall back to orchestrator default
        if default_provider is not None:
            logger.debug(
                f"Agent context resolution: agent={self._agent_name}, "
                f"using_default_provider=True"
            )
            return default_provider

        # No provider configured
        logger.debug(
            f"Agent context resolution: agent={self._agent_name}, "
            f"no_provider_configured=True"
        )
        return None

    async def resolve_context(
        self,
        agent: Agent,
        subscription: Subscription,
        trigger_artifacts: list[Artifact],
        default_provider: Any | None = None,
    ) -> Context:
        """Resolve execution context for agent (future implementation).

        NOTE: Currently returns a basic Context. Future phases will:
        - Use provider to fetch additional context artifacts
        - Build AgentContext with trigger + context artifacts
        - Apply visibility filtering at security boundary

        Args:
            agent: Agent being executed
            subscription: Subscription that triggered execution
            trigger_artifacts: Artifacts that triggered agent
            default_provider: Default context provider from orchestrator

        Returns:
            Resolved execution context (currently basic)
        """
        # Determine which provider to use
        provider = self.get_provider(agent, default_provider)

        # Future: Use provider to fetch context artifacts
        # For now, we just log the resolution
        if provider is None:
            self._logger.debug(
                f"Agent context: agent={self._agent_name}, "
                f"no_context_provider, using_trigger_artifacts_only=True"
            )

        # Future implementation will:
        # 1. Build context request from subscription
        # 2. Call provider.get_artifacts(request)
        # 3. Return AgentContext with both trigger + context artifacts

        # For now, return a minimal context structure
        # (actual Context building is orchestrator-level in current architecture)
        from flock.utils.runtime import Context

        return Context(
            correlation_id=None,  # Will be filled by orchestrator
            task_id="",  # Will be filled by orchestrator
            state={},
            is_batch=False,
            artifacts=[],
            agent_identity=None,
        )


__all__ = ["ContextResolver"]
