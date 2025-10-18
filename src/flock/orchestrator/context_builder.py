"""Execution context building with security boundary enforcement.

Phase 5A: Extracted from orchestrator.py to eliminate code duplication.

This module implements the security boundary pattern for context creation,
consolidating duplicated code from direct_invoke(), invoke(), and _run_agent_task().

SECURITY CRITICAL: This module enforces the Phase 8 context provider pattern
that prevents identity spoofing and READ capability bypass.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4


if TYPE_CHECKING:
    from flock.core import Agent
    from flock.core.artifacts import Artifact
    from flock.core.store import BlackboardStore
    from flock.utils.runtime import Context


class ContextBuilder:
    """Builds execution contexts with security boundary enforcement.

    This module implements the security boundary pattern:
    1. Resolve provider (agent > global > default)
    2. Wrap with BoundContextProvider (prevent identity spoofing)
    3. Evaluate context artifacts (orchestrator controls READ)
    4. Create Context with data-only (no capabilities)

    Phase 5A: Extracted to eliminate duplication across 3 methods and
    reduce _run_agent_task complexity from C(11) to B or A.

    SECURITY NOTICE: Changes to this module affect the security boundary
    between agents and the blackboard. Review carefully.
    """

    def __init__(
        self,
        *,
        store: BlackboardStore,
        default_context_provider: Any | None = None,
    ):
        """Initialize ContextBuilder with blackboard store and default provider.

        Args:
            store: BlackboardStore instance for context provider queries
            default_context_provider: Global context provider (Phase 3 security fix).
                If None, agents use DefaultContextProvider. Can be overridden per-agent.
        """
        self._store = store
        self._default_context_provider = default_context_provider
        self._logger = logging.getLogger(__name__)

    async def build_execution_context(
        self,
        *,
        agent: Agent,
        artifacts: list[Artifact],
        correlation_id: UUID | None = None,
        is_batch: bool = False,
    ) -> Context:
        """Build Context with pre-filtered artifacts (Phase 8 security fix).

        Implements the security boundary pattern:
        1. Resolve provider (agent > global > default)
        2. Wrap with BoundContextProvider (prevent identity spoofing)
        3. Evaluate context artifacts (orchestrator controls READ)
        4. Create Context with data-only (no capabilities)

        SECURITY NOTICE: This method enforces the security boundary between
        agents and the blackboard. Agents receive pre-filtered context data
        and cannot bypass visibility controls.

        Args:
            agent: Agent instance being executed
            artifacts: Input artifacts that triggered execution
            correlation_id: Optional correlation ID for grouping related work
            is_batch: Whether this is a batch execution (affects context metadata)

        Returns:
            Context with pre-filtered artifacts and agent identity

        Examples:
            >>> # Direct invocation
            >>> context = await builder.build_execution_context(
            ...     agent=pizza_agent,
            ...     artifacts=[input_artifact],
            ...     correlation_id=uuid4(),
            ...     is_batch=False,
            ... )
            >>> outputs = await agent.execute(context, artifacts)

            >>> # Batch execution
            >>> context = await builder.build_execution_context(
            ...     agent=batch_agent,
            ...     artifacts=batch_artifacts,
            ...     correlation_id=batch_correlation,
            ...     is_batch=True,
            ... )
        """
        # Phase 8: Evaluate context BEFORE creating Context (security fix)
        # Provider resolution: per-agent > global > DefaultContextProvider
        from flock.core.context_provider import (
            BoundContextProvider,
            ContextRequest,
            DefaultContextProvider,
        )

        # Resolve correlation ID
        resolved_correlation_id = correlation_id or (
            artifacts[0].correlation_id
            if artifacts and artifacts[0].correlation_id
            else uuid4()
        )

        # Step 1: Resolve provider (agent > global > default)
        inner_provider = (
            getattr(agent, "context_provider", None)
            or self._default_context_provider
            or DefaultContextProvider()
        )

        # Step 2: SECURITY FIX - Wrap provider with BoundContextProvider
        # This prevents identity spoofing by binding the provider to the agent's identity
        provider = BoundContextProvider(inner_provider, agent.identity)

        # Step 3: Evaluate context using provider (orchestrator controls READ capability)
        # Engines will receive pre-filtered artifacts via ctx.artifacts
        request = ContextRequest(
            agent=agent,
            correlation_id=resolved_correlation_id,
            store=self._store,
            agent_identity=agent.identity,
            exclude_ids={a.id for a in artifacts},  # Exclude input artifacts
        )
        context_artifacts = await provider(request)

        # Step 4: Create Context with pre-filtered data (no capabilities!)
        # SECURITY: Context is now just data - engines can't query anything
        from flock.utils.runtime import Context

        ctx = Context(
            artifacts=context_artifacts,  # Pre-filtered conversation context
            agent_identity=agent.identity,
            task_id=str(uuid4()),
            correlation_id=resolved_correlation_id,
            is_batch=is_batch,
        )

        # Log context creation for debugging
        self._logger.debug(
            f"Context built: agent={agent.name}, "
            f"correlation_id={resolved_correlation_id}, "
            f"is_batch={is_batch}, "
            f"context_artifacts={len(context_artifacts)}, "
            f"input_artifacts={len(artifacts)}"
        )

        return ctx


__all__ = ["ContextBuilder"]
