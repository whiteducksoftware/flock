"""Context Provider - Security Boundary Layer.

The Context Provider is the CRITICAL SECURITY BOUNDARY between agents
(untrusted business logic) and the blackboard store (infrastructure).

SECURITY FIX (2025-10-16): This module implements the fix for three
critical security vulnerabilities:

- Vulnerability #1 (READ BYPASS): Agents could bypass visibility via ctx.board.list()
- Vulnerability #2 (WRITE BYPASS): Agents could bypass validation via ctx.board.publish()
- Vulnerability #3 (GOD MODE): Agents had unlimited ctx.orchestrator access

Solution: Context Provider enforces visibility filtering BEFORE agents see data.
Agents can NO LONGER bypass security because they don't have direct store access.

References:
- .flock/flock-research/context-provider/SECURITY_ANALYSIS.md
- docs/specs/007-context-provider-security-fix/PLAN.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from flock.artifacts import Artifact
from flock.store import FilterConfig, BlackboardStore
from flock.visibility import AgentIdentity


@dataclass
class ContextRequest:
    """Request for agent context.

    This carries all information needed for providers to filter context
    with mandatory visibility enforcement.

    Attributes:
        agent: Agent instance requesting context
        correlation_id: Workflow identifier for filtering
        store: Blackboard store for querying artifacts
        agent_identity: Agent identity for visibility checks (includes labels, tenant_id)
        exclude_ids: Set of artifact IDs to exclude from context (e.g., input artifacts)
    """

    agent: Any  # Agent type to avoid circular import
    correlation_id: UUID
    store: BlackboardStore
    agent_identity: AgentIdentity
    exclude_ids: set[UUID] | None = None


class ContextProvider(Protocol):
    """Protocol for context providers.

    Context Providers are the MANDATORY security boundary between agents
    and the blackboard store. All providers MUST enforce visibility filtering.

    SECURITY REQUIREMENT: Every provider implementation MUST call
    artifact.visibility.allows(agent_identity) before returning artifacts.
    Any provider that doesn't enforce visibility is a SECURITY BUG.

    Implementations:
    - DefaultContextProvider: Filters by correlation_id + visibility (default behavior)
    - FilteredContextProvider: Wraps FilterConfig for declarative filtering + visibility

    Usage:
        # Global provider
        flock = Flock(context_provider=MyProvider())

        # Per-agent provider
        agent.with_context(MyProvider())
    """

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch context with MANDATORY visibility enforcement.

        Args:
            request: Context request with agent identity and correlation

        Returns:
            List of artifact dicts that agent is allowed to see.
            Format: [{"type": ..., "payload": ..., "produced_by": ..., ...}]

        SECURITY: Implementation MUST filter by visibility using:
            artifact.visibility.allows(request.agent_identity)
        """
        ...


class DefaultContextProvider:
    """Default context provider with correlation-based filtering and MANDATORY visibility enforcement.

    This provider implements the secure replacement for the old vulnerable pattern:
        Old (INSECURE): all_artifacts = await ctx.board.list()
        New (SECURE): context = await provider(request)

    Security Properties:
    - ✅ Filters by correlation_id (logical workflow boundary)
    - ✅ Enforces visibility (security boundary) - CANNOT BE BYPASSED
    - ✅ Returns only artifacts agent is allowed to see
    - ✅ No direct store access exposed to agents

    This fixes Vulnerability #1 (READ BYPASS) where agents could access
    any artifact regardless of visibility by calling ctx.board.list().
    """

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch context with mandatory visibility enforcement.

        SECURITY IMPLEMENTATION:
        1. Query artifacts by correlation_id (workflow filtering)
        2. Filter by visibility (security filtering) - THIS IS THE CRITICAL FIX
        3. Return only artifacts agent is allowed to see

        Args:
            request: Context request with agent identity and correlation

        Returns:
            List of artifact dicts agent can see (visibility-filtered)
        """
        # Step 1: Query by correlation_id (logical boundary)
        artifacts, _ = await request.store.query_artifacts(
            FilterConfig(correlation_id=str(request.correlation_id)),
            limit=-1,  # Get all artifacts in this correlation (will filter by visibility)
        )

        # Step 2: CRITICAL SECURITY STEP - Filter by visibility
        # This is the FIX for Vulnerability #1 (READ BYPASS)
        # Agents can ONLY see artifacts they're allowed to see
        visible_artifacts = [
            artifact
            for artifact in artifacts
            if artifact.visibility.allows(request.agent_identity)
        ]

        # Step 2.5: Exclude specific artifacts (e.g., input artifacts to avoid duplication)
        if request.exclude_ids:
            visible_artifacts = [
                artifact
                for artifact in visible_artifacts
                if artifact.id not in request.exclude_ids
            ]

        # Step 3: Return serialized context
        return [
            {
                "type": artifact.type,
                "payload": artifact.payload,
                "produced_by": artifact.produced_by,
                "created_at": artifact.created_at,
                "id": str(artifact.id),
                "correlation_id": str(artifact.correlation_id) if artifact.correlation_id else None,
                "tags": list(artifact.tags) if artifact.tags else [],
            }
            for artifact in visible_artifacts
        ]


class FilteredContextProvider:
    """Context provider with declarative filtering + MANDATORY visibility enforcement.

    This provider combines declarative filtering (FilterConfig) with security
    enforcement (visibility). It implements Phase 4 of the security fix.

    Security Properties:
    - ✅ Filters by FilterConfig (declarative filtering: tags, types, correlation, etc.)
    - ✅ Enforces visibility (security boundary) - CANNOT BE BYPASSED
    - ✅ Returns only artifacts matching BOTH filters AND visibility
    - ✅ No direct store access exposed to agents

    Example:
        >>> # Filter by tags + enforce visibility
        >>> provider = FilteredContextProvider(
        ...     FilterConfig(tags={"important", "urgent"}),
        ...     limit=10
        ... )
        >>> agent.with_context(provider)

        >>> # Filter by type + enforce visibility
        >>> provider = FilteredContextProvider(
        ...     FilterConfig(type_names={"Task", "Report"}),
        ...     limit=50
        ... )
    """

    def __init__(self, filter_config: FilterConfig, limit: int = 50):
        """Initialize FilteredContextProvider with declarative filters.

        Args:
            filter_config: FilterConfig specifying declarative filters
            limit: Maximum number of artifacts to return (default: 50)
        """
        self.filter_config = filter_config
        self.limit = limit

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch context with declarative filtering + mandatory visibility enforcement.

        SECURITY IMPLEMENTATION:
        1. Query artifacts using FilterConfig (declarative filtering)
        2. Filter by visibility (security filtering) - THIS IS CRITICAL
        3. Return only artifacts matching BOTH filters AND visibility

        Args:
            request: Context request with agent identity and store

        Returns:
            List of artifact dicts matching filters AND visible to agent
        """
        # Step 1: Query by FilterConfig (declarative filtering)
        artifacts, _ = await request.store.query_artifacts(
            self.filter_config,
            limit=self.limit,
        )

        # Step 2: CRITICAL SECURITY STEP - Filter by visibility
        # This ensures visibility is ALWAYS enforced, even with declarative filters
        visible_artifacts = [
            artifact
            for artifact in artifacts
            if artifact.visibility.allows(request.agent_identity)
        ]

        # Step 2.5: Exclude specific artifacts (e.g., input artifacts to avoid duplication)
        if request.exclude_ids:
            visible_artifacts = [
                artifact
                for artifact in visible_artifacts
                if artifact.id not in request.exclude_ids
            ]

        # Step 3: Return serialized context
        return [
            {
                "type": artifact.type,
                "payload": artifact.payload,
                "produced_by": artifact.produced_by,
                "created_at": artifact.created_at,
                "id": str(artifact.id),
                "correlation_id": str(artifact.correlation_id) if artifact.correlation_id else None,
                "tags": list(artifact.tags) if artifact.tags else [],
            }
            for artifact in visible_artifacts
        ]


class BoundContextProvider:
    """Security wrapper that binds a provider to a specific agent identity.

    SECURITY FIX (2025-10-17): This wrapper prevents engines from forging
    Context objects with fake agent_identity values. Even if an engine creates
    a fake Context with a different agent_identity, this wrapper will use the
    trusted identity that was bound at creation time by the orchestrator.

    The orchestrator creates a BoundContextProvider for each agent execution,
    binding it to the agent's true identity. Engines cannot bypass this because
    they would need to create a fake BoundContextProvider, but they don't have
    access to the real bound identity.

    Example Attack (prevented):
        >>> # Malicious engine tries to escalate privileges
        >>> fake_ctx = Context(
        ...     ...
        ...     agent_identity=AgentIdentity(name="admin", labels={"admin"}),  # FAKE
        ... )
        >>> # Provider ignores fake identity, uses bound identity instead
        >>> context = await bound_provider(request)  # Still filters as original agent
    """

    def __init__(self, inner_provider: ContextProvider, bound_agent_identity: AgentIdentity):
        """Create provider bound to specific agent identity.

        Args:
            inner_provider: Wrapped provider (e.g., DefaultContextProvider)
            bound_agent_identity: Trusted agent identity from orchestrator
        """
        self._inner = inner_provider
        self._bound_identity = bound_agent_identity

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch context using BOUND agent identity (ignoring request.agent_identity).

        SECURITY: This method ignores request.agent_identity because it could
        come from untrusted engine code. Instead, it uses the bound identity
        that was set by the orchestrator at Context creation time.

        Args:
            request: Context request (agent_identity field is IGNORED)

        Returns:
            List of artifact dicts filtered by BOUND identity (not request identity)
        """
        # SECURITY: Replace untrusted agent_identity with trusted bound identity
        secure_request = ContextRequest(
            agent=request.agent,
            correlation_id=request.correlation_id,
            store=request.store,
            agent_identity=self._bound_identity,  # Use trusted identity, ignore request
            exclude_ids=request.exclude_ids,
        )
        return await self._inner(secure_request)


__all__ = [
    "ContextProvider",
    "ContextRequest",
    "DefaultContextProvider",
    "FilteredContextProvider",
    "BoundContextProvider",
]
