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
from datetime import datetime, timedelta
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
    """Default context provider - shows ALL artifacts on blackboard with MANDATORY visibility enforcement.

    **EXPLICIT IS BETTER THAN IMPLICIT**: This provider shows agents everything on the
    blackboard they're allowed to see (visibility-filtered). No magic correlation filtering!

    If you want correlation-based filtering, use CorrelatedContextProvider explicitly.

    This provider implements the secure replacement for the old vulnerable pattern:
        Old (INSECURE): all_artifacts = await ctx.board.list()
        New (SECURE): context = await provider(request)

    Security Properties:
    - ✅ Shows ALL artifacts on blackboard (no hidden filtering)
    - ✅ Enforces visibility (security boundary) - CANNOT BE BYPASSED
    - ✅ Returns only artifacts agent is allowed to see
    - ✅ No direct store access exposed to agents

    This fixes Vulnerability #1 (READ BYPASS) where agents could access
    any artifact regardless of visibility by calling ctx.board.list().

    Example:
        >>> # Global: All agents see everything they're allowed to
        >>> flock = Flock(context_provider=DefaultContextProvider())
        >>>
        >>> # Per-agent: This agent sees full blackboard
        >>> agent.context_provider = DefaultContextProvider()
    """

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch ALL artifacts with mandatory visibility enforcement.

        SECURITY IMPLEMENTATION:
        1. Query ALL artifacts from blackboard (no filtering)
        2. Filter by visibility (security filtering) - THIS IS THE CRITICAL FIX
        3. Return only artifacts agent is allowed to see

        Args:
            request: Context request with agent identity

        Returns:
            List of artifact dicts agent can see (visibility-filtered)
        """
        # Step 1: Query ALL artifacts (no filtering - explicit!)
        artifacts, _ = await request.store.query_artifacts(
            FilterConfig(),  # Empty filter = get everything
            limit=-1,  # Get all artifacts (will filter by visibility)
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


class CorrelatedContextProvider:
    """Context provider that filters by correlation_id + visibility.

    **EXPLICIT WORKFLOW ISOLATION**: Use this when you want agents to see only
    artifacts from their specific workflow (correlation_id).

    This is the explicit version of what DefaultContextProvider used to do implicitly.
    Now you choose: full blackboard (DefaultContextProvider) or workflow-scoped
    (CorrelatedContextProvider).

    Security Properties:
    - ✅ Filters by correlation_id (workflow boundary)
    - ✅ Enforces visibility (security boundary) - CANNOT BE BYPASSED
    - ✅ Returns only workflow artifacts agent is allowed to see

    Example:
        >>> # Global: All agents only see their workflow
        >>> flock = Flock(context_provider=CorrelatedContextProvider())
        >>>
        >>> # Per-agent: This agent only sees workflow artifacts
        >>> agent.context_provider = CorrelatedContextProvider()
        >>>
        >>> # Use case: Multi-tenant SaaS with workflow isolation
        >>> # Each workflow (correlation_id) is isolated from others
    """

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch workflow artifacts with mandatory visibility enforcement.

        SECURITY IMPLEMENTATION:
        1. Query artifacts by correlation_id (workflow filtering)
        2. Filter by visibility (security filtering)
        3. Return only workflow artifacts agent is allowed to see

        Args:
            request: Context request with correlation_id and agent identity

        Returns:
            List of artifact dicts from workflow that agent can see
        """
        # Step 1: Query by correlation_id (workflow boundary)
        artifacts, _ = await request.store.query_artifacts(
            FilterConfig(correlation_id=str(request.correlation_id)),
            limit=-1,  # Get all workflow artifacts (will filter by visibility)
        )

        # Step 2: CRITICAL SECURITY STEP - Filter by visibility
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


class RecentContextProvider:
    """Context provider that shows only the N most recent artifacts.

    **TOKEN COST CONTROL**: Perfect for keeping context small and relevant by
    showing only the most recent artifacts (sorted by creation time).

    Security Properties:
    - ✅ Limits context to N most recent artifacts
    - ✅ Enforces visibility (security boundary) - CANNOT BE BYPASSED
    - ✅ Reduces token costs by limiting context size

    Example:
        >>> # Global: All agents see only last 10 artifacts
        >>> flock = Flock(context_provider=RecentContextProvider(limit=10))
        >>>
        >>> # Per-agent: This agent sees only last 50 artifacts
        >>> agent.context_provider = RecentContextProvider(limit=50)
        >>>
        >>> # Use case: High-volume systems where full history is too expensive
        >>> # Agent only needs recent context to make decisions
    """

    def __init__(self, limit: int = 50):
        """Initialize RecentContextProvider with artifact limit.

        Args:
            limit: Maximum number of recent artifacts to return (default: 50)
        """
        self.limit = limit

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch most recent artifacts with mandatory visibility enforcement.

        SECURITY IMPLEMENTATION:
        1. Query ALL artifacts from blackboard
        2. Filter by visibility (security filtering)
        3. Sort by creation time (most recent first)
        4. Return only N most recent artifacts

        Args:
            request: Context request with agent identity

        Returns:
            List of N most recent artifact dicts agent can see
        """
        # Step 1: Query ALL artifacts (we'll filter by recency after visibility)
        artifacts, _ = await request.store.query_artifacts(
            FilterConfig(),
            limit=-1,  # Get all artifacts (will filter by visibility and recency)
        )

        # Step 2: CRITICAL SECURITY STEP - Filter by visibility
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

        # Step 3: Sort by creation time (most recent first) and limit
        visible_artifacts.sort(key=lambda a: a.created_at, reverse=True)
        recent_artifacts = visible_artifacts[: self.limit]

        # Step 4: Return serialized context
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
            for artifact in recent_artifacts
        ]


class TimeWindowContextProvider:
    """Context provider that shows only artifacts from the last X hours.

    **TIME-BASED FILTERING**: Perfect for real-time monitoring or event-driven
    systems where only recent data is relevant.

    Security Properties:
    - ✅ Filters artifacts by time window (last X hours)
    - ✅ Enforces visibility (security boundary) - CANNOT BE BYPASSED
    - ✅ Automatic cleanup of old context (no manual pruning needed)

    Example:
        >>> # Global: All agents see only last hour
        >>> flock = Flock(context_provider=TimeWindowContextProvider(hours=1))
        >>>
        >>> # Per-agent: This agent sees last 24 hours
        >>> agent.context_provider = TimeWindowContextProvider(hours=24)
        >>>
        >>> # Use case: Real-time monitoring dashboard
        >>> # Only show events from last hour, ignore old data
    """

    def __init__(self, hours: int = 1):
        """Initialize TimeWindowContextProvider with time window.

        Args:
            hours: Number of hours to look back (default: 1)
        """
        self.hours = hours

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Fetch time-windowed artifacts with mandatory visibility enforcement.

        SECURITY IMPLEMENTATION:
        1. Query ALL artifacts from blackboard
        2. Filter by visibility (security filtering)
        3. Filter by time window (last X hours)
        4. Return only recent artifacts within window

        Args:
            request: Context request with agent identity

        Returns:
            List of artifact dicts within time window that agent can see
        """
        # Calculate cutoff time
        cutoff = datetime.now() - timedelta(hours=self.hours)

        # Step 1: Query ALL artifacts (we'll filter by time after visibility)
        artifacts, _ = await request.store.query_artifacts(
            FilterConfig(),
            limit=-1,  # Get all artifacts (will filter by visibility and time)
        )

        # Step 2: CRITICAL SECURITY STEP - Filter by visibility
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

        # Step 3: Filter by time window
        recent_artifacts = [artifact for artifact in visible_artifacts if artifact.created_at >= cutoff]

        # Step 4: Return serialized context
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
            for artifact in recent_artifacts
        ]


class EmptyContextProvider:
    """Context provider that returns NO historical context.

    **STATELESS AGENTS**: Use this for purely functional agents that only
    transform input → output without needing any historical context.

    This is the ultimate token saver - zero context overhead!

    Security Properties:
    - ✅ Returns empty context (no artifacts)
    - ✅ Enforces visibility (N/A - no artifacts to filter)
    - ✅ Maximum token savings (zero context tokens)

    Example:
        >>> # Global: All agents are stateless (no context)
        >>> flock = Flock(context_provider=EmptyContextProvider())
        >>>
        >>> # Per-agent: This agent is purely functional
        >>> translator.context_provider = EmptyContextProvider()
        >>>
        >>> # Use case: Simple transformation agents
        >>> # Agent: English → Spanish (no history needed)
        >>> # Agent: Markdown → HTML (no history needed)
        >>> # Agent: Image → Thumbnail (no history needed)
    """

    async def __call__(self, request: ContextRequest) -> list[dict[str, Any]]:
        """Return empty context (no artifacts).

        SECURITY IMPLEMENTATION:
        No artifacts = no security concerns!

        Args:
            request: Context request (ignored)

        Returns:
            Empty list (no context)
        """
        return []


__all__ = [
    "ContextProvider",
    "ContextRequest",
    "DefaultContextProvider",
    "CorrelatedContextProvider",
    "RecentContextProvider",
    "TimeWindowContextProvider",
    "EmptyContextProvider",
    "FilteredContextProvider",
    "BoundContextProvider",
]
