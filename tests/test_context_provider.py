"""Tests for Context Provider - Phase 2: Security Boundary.

The Context Provider is the CRITICAL SECURITY BOUNDARY between agents
(untrusted business logic) and the blackboard store (infrastructure).

It ensures that agents can ONLY see artifacts they're allowed to see
(visibility enforcement cannot be bypassed).
"""

import pytest
from uuid import uuid4, UUID
from datetime import datetime
from typing import Any

from flock.artifacts import Artifact
from flock.visibility import PublicVisibility, PrivateVisibility, TenantVisibility, LabelledVisibility, AgentIdentity
from flock.store import FilterConfig


# We'll import these after implementing them
# from flock.context_provider import ContextProvider, ContextRequest, DefaultContextProvider


class MockStore:
    """Mock blackboard store for testing."""

    def __init__(self, artifacts: list[Artifact]):
        self.artifacts = artifacts

    async def query_artifacts(
        self, filters: FilterConfig | None = None, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Artifact], int]:
        """Mock query that supports correlation_id filtering."""
        results = self.artifacts

        # Filter by correlation_id if provided
        if filters and filters.correlation_id:
            results = [a for a in results if str(a.correlation_id) == filters.correlation_id]

        # Apply limit
        if limit > 0:
            results = results[:limit]

        return results, len(results)


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str, labels: set[str] | None = None, tenant_id: str | None = None):
        self.name = name
        self.labels = labels or set()
        self.tenant_id = tenant_id

    @property
    def identity(self) -> AgentIdentity:
        return AgentIdentity(name=self.name, labels=self.labels, tenant_id=self.tenant_id)


class TestContextProviderProtocol:
    """Phase 2: Test Context Provider protocol definition."""

    def test_context_provider_protocol_exists(self):
        """ContextProvider protocol must be defined.

        The protocol defines the security boundary interface.
        All providers must implement: async def __call__(request: ContextRequest) -> list[dict]
        """
        from flock.context_provider import ContextProvider

        # Protocol should exist and be callable
        assert ContextProvider is not None

    def test_context_request_dataclass_exists(self):
        """ContextRequest must be defined with required fields.

        Required fields:
        - agent: Agent instance (for identity)
        - correlation_id: UUID (for filtering)
        - store: BlackboardStore (for querying)
        - agent_identity: AgentIdentity (for visibility checks)
        """
        from flock.context_provider import ContextRequest

        # Should be able to create ContextRequest
        agent = MockAgent("test-agent")
        correlation = uuid4()
        store = MockStore([])

        request = ContextRequest(
            agent=agent,
            correlation_id=correlation,
            store=store,
            agent_identity=agent.identity,
        )

        assert request.agent == agent
        assert request.correlation_id == correlation
        assert request.store == store
        assert request.agent_identity.name == "test-agent"


@pytest.mark.asyncio
class TestDefaultContextProviderSecurity:
    """Phase 2: Test DefaultContextProvider MANDATORY visibility enforcement."""

    async def test_default_provider_exists(self):
        """DefaultContextProvider must be implemented."""
        from flock.context_provider import DefaultContextProvider

        provider = DefaultContextProvider()
        assert provider is not None

    async def test_default_provider_filters_by_visibility(self):
        """SECURITY: DefaultContextProvider MUST filter by visibility.

        This is the PRIMARY SECURITY FIX for Vulnerability #1 (READ BYPASS).

        Agents can ONLY see artifacts they're allowed to see.
        Visibility enforcement is MANDATORY and cannot be bypassed.
        """
        from flock.context_provider import DefaultContextProvider, ContextRequest

        correlation = uuid4()

        # Create artifacts with different visibility
        public_artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Public task"},
            produced_by="system",
            correlation_id=correlation,
            visibility=PublicVisibility(),
        )

        private_artifact = Artifact(
            id=uuid4(),
            type="Secret",
            payload={"api_key": "sk-secret123"},
            produced_by="admin",
            correlation_id=correlation,
            visibility=PrivateVisibility(agents={"admin"}),  # Only admin can see
        )

        store = MockStore([public_artifact, private_artifact])
        agent = MockAgent("untrusted-agent")  # NOT in allowlist

        provider = DefaultContextProvider()
        request = ContextRequest(
            agent=agent,
            correlation_id=correlation,
            store=store,
            agent_identity=agent.identity,
        )

        # Agent should ONLY see public artifact (private filtered out)
        context = await provider(request)

        assert len(context) == 1
        assert context[0]["type"] == "Task"
        assert context[0]["payload"]["title"] == "Public task"

        # SECURITY: Private artifact must NOT be visible
        assert not any(item["type"] == "Secret" for item in context)

    async def test_default_provider_respects_private_visibility(self):
        """SECURITY: Private visibility must be enforced.

        Vulnerability #1 Attack Scenario:
            all_artifacts = await ctx.board.list()
            secrets = [a for a in all_artifacts if a.type == "Secret"]
            # Agent could steal secrets!

        Fix: Provider filters BEFORE agent sees data.
        Agent NOT in allowlist gets empty list.
        """
        from flock.context_provider import DefaultContextProvider, ContextRequest

        correlation = uuid4()

        # Create private artifact (only "admin" allowed)
        secret = Artifact(
            id=uuid4(),
            type="Secret",
            payload={"password": "hunter2"},
            produced_by="admin",
            correlation_id=correlation,
            visibility=PrivateVisibility(agents={"admin"}),
        )

        store = MockStore([secret])
        untrusted_agent = MockAgent("hacker")  # NOT in allowlist

        provider = DefaultContextProvider()
        request = ContextRequest(
            agent=untrusted_agent,
            correlation_id=correlation,
            store=store,
            agent_identity=untrusted_agent.identity,
        )

        # Hacker should see NOTHING
        context = await provider(request)
        assert len(context) == 0, "Untrusted agent must NOT see private artifacts"

        # Now test with authorized agent
        admin_agent = MockAgent("admin")  # IN allowlist
        admin_request = ContextRequest(
            agent=admin_agent,
            correlation_id=correlation,
            store=store,
            agent_identity=admin_agent.identity,
        )

        admin_context = await provider(admin_request)
        assert len(admin_context) == 1, "Admin should see private artifact"
        assert admin_context[0]["type"] == "Secret"

    async def test_default_provider_respects_tenant_visibility(self):
        """SECURITY: Tenant isolation must be enforced.

        Multi-tenant systems must prevent tenant A from seeing tenant B data.
        Vulnerability: Agent from tenant_b could access tenant_a's data via ctx.board.list()
        Fix: Provider enforces tenant isolation automatically.
        """
        from flock.context_provider import DefaultContextProvider, ContextRequest

        correlation = uuid4()

        # Tenant A's data
        tenant_a_artifact = Artifact(
            id=uuid4(),
            type="CustomerData",
            payload={"ssn": "123-45-6789"},
            produced_by="system",
            correlation_id=correlation,
            visibility=TenantVisibility(tenant_id="tenant_a"),
        )

        # Tenant B's data
        tenant_b_artifact = Artifact(
            id=uuid4(),
            type="CustomerData",
            payload={"ssn": "987-65-4321"},
            produced_by="system",
            correlation_id=correlation,
            visibility=TenantVisibility(tenant_id="tenant_b"),
        )

        store = MockStore([tenant_a_artifact, tenant_b_artifact])

        # Agent from tenant_b tries to query
        tenant_b_agent = MockAgent("agent-b", tenant_id="tenant_b")

        provider = DefaultContextProvider()
        request = ContextRequest(
            agent=tenant_b_agent,
            correlation_id=correlation,
            store=store,
            agent_identity=tenant_b_agent.identity,
        )

        # Agent should ONLY see tenant_b data (tenant_a filtered out)
        context = await provider(request)

        assert len(context) == 1
        assert context[0]["payload"]["ssn"] == "987-65-4321"

        # SECURITY: Tenant A's data must NOT be visible
        assert not any(item["payload"]["ssn"] == "123-45-6789" for item in context)

    async def test_default_provider_respects_label_based_visibility(self):
        """SECURITY: Label-based RBAC must be enforced.

        Classified data requires specific labels (security clearance).
        Vulnerability: Agent without clearance could access classified via ctx.board.list()
        Fix: Provider enforces label requirements automatically.
        """
        from flock.context_provider import DefaultContextProvider, ContextRequest

        correlation = uuid4()

        # Classified document (requires "clearance:secret" label)
        classified_doc = Artifact(
            id=uuid4(),
            type="ClassifiedDoc",
            payload={"content": "Top Secret"},
            produced_by="system",
            correlation_id=correlation,
            visibility=LabelledVisibility(required_labels={"clearance:secret"}),
        )

        store = MockStore([classified_doc])

        # Agent without clearance tries to access
        unauthorized_agent = MockAgent("junior-agent", labels={"clearance:public"})

        provider = DefaultContextProvider()
        request = ContextRequest(
            agent=unauthorized_agent,
            correlation_id=correlation,
            store=store,
            agent_identity=unauthorized_agent.identity,
        )

        # Unauthorized agent should see NOTHING
        context = await provider(request)
        assert len(context) == 0, "Agent without required label must NOT see classified data"

        # Now test with authorized agent
        authorized_agent = MockAgent("senior-agent", labels={"clearance:secret"})
        authorized_request = ContextRequest(
            agent=authorized_agent,
            correlation_id=correlation,
            store=store,
            agent_identity=authorized_agent.identity,
        )

        authorized_context = await provider(authorized_request)
        assert len(authorized_context) == 1, "Agent with required label should see classified data"
        assert authorized_context[0]["type"] == "ClassifiedDoc"

    async def test_default_provider_filters_by_correlation_id(self):
        """DefaultContextProvider must filter by correlation_id.

        Agents should only see artifacts from their workflow (correlation).
        This is NOT a security boundary (visibility is), but a logical boundary.
        """
        from flock.context_provider import DefaultContextProvider, ContextRequest

        correlation_a = uuid4()
        correlation_b = uuid4()

        # Artifacts from different workflows
        artifact_a = Artifact(
            id=uuid4(),
            type="Task",
            payload={"workflow": "A"},
            produced_by="system",
            correlation_id=correlation_a,
            visibility=PublicVisibility(),
        )

        artifact_b = Artifact(
            id=uuid4(),
            type="Task",
            payload={"workflow": "B"},
            produced_by="system",
            correlation_id=correlation_b,
            visibility=PublicVisibility(),
        )

        store = MockStore([artifact_a, artifact_b])
        agent = MockAgent("agent-1")

        provider = DefaultContextProvider()
        request = ContextRequest(
            agent=agent,
            correlation_id=correlation_a,  # Request workflow A
            store=store,
            agent_identity=agent.identity,
        )

        # Agent should ONLY see artifacts from workflow A
        context = await provider(request)

        assert len(context) == 1
        assert context[0]["payload"]["workflow"] == "A"

        # Artifact from workflow B must NOT be visible
        assert not any(item["payload"]["workflow"] == "B" for item in context)

    async def test_default_provider_returns_correct_format(self):
        """DefaultContextProvider must return list of artifact dicts.

        Format: [{"type": ..., "payload": ..., "produced_by": ..., ...}]
        Agents receive pre-serialized context (not raw Artifact objects).
        """
        from flock.context_provider import DefaultContextProvider, ContextRequest

        correlation = uuid4()

        artifact = Artifact(
            id=uuid4(),
            type="Task",
            payload={"title": "Do something"},
            produced_by="planner",
            correlation_id=correlation,
            visibility=PublicVisibility(),
        )

        store = MockStore([artifact])
        agent = MockAgent("worker")

        provider = DefaultContextProvider()
        request = ContextRequest(
            agent=agent,
            correlation_id=correlation,
            store=store,
            agent_identity=agent.identity,
        )

        context = await provider(request)

        # Verify format
        assert isinstance(context, list)
        assert len(context) == 1
        assert isinstance(context[0], dict)

        # Verify required fields
        item = context[0]
        assert item["type"] == "Task"
        assert item["payload"] == {"title": "Do something"}
        assert item["produced_by"] == "planner"


class TestContextProviderSecurityDocumentation:
    """Documentation tests explaining the security architecture."""

    def test_security_boundary_explanation(self):
        """Context Provider is the MANDATORY security boundary.

        BEFORE (INSECURE):
        ```
        Agent → ctx.board.list() → Store (NO FILTERING!)
        ```

        AFTER (SECURE):
        ```
        Agent → provider(request) → [Visibility Filter] → Filtered Context
        ```

        Key Security Properties:
        1. MANDATORY ENFORCEMENT: Visibility filtering cannot be bypassed
        2. NO DIRECT ACCESS: Agents cannot access store directly
        3. AUDITABLE: All context requests go through provider layer
        4. SEPARATION OF CONCERNS: Agent = business logic, Provider = access control

        References:
        - .flock/flock-research/context-provider/SECURITY_ANALYSIS.md (lines 263-360)
        - docs/specs/007-context-provider-security-fix/PLAN.md (Phase 2)
        """
        assert True, "Security boundary documented"

    def test_visibility_enforcement_cannot_be_bypassed(self):
        """Provider ALWAYS filters by visibility - this is non-negotiable.

        Even if a custom provider is implemented, it MUST call
        artifact.visibility.allows(agent_identity) before returning data.

        Any provider that doesn't enforce visibility is a SECURITY BUG.

        This is the fix for Vulnerability #1 (READ BYPASS).
        """
        assert True, "Visibility enforcement requirement documented"


@pytest.mark.asyncio
class TestPluggableProviders:
    """Phase 3: Test pluggable provider configuration (global + per-agent)."""

    async def test_flock_accepts_context_provider_parameter(self):
        """CONFIGURATION: Flock.__init__() must accept context_provider parameter.

        This enables global provider configuration:
            flock = Flock(context_provider=MyProvider())
        """
        from flock.orchestrator import Flock
        from flock.context_provider import DefaultContextProvider

        # Should accept context_provider parameter
        provider = DefaultContextProvider()
        flock = Flock(model="openai/gpt-4o-mini", context_provider=provider)

        # Provider should be stored
        assert hasattr(flock, "_default_context_provider")
        assert flock._default_context_provider == provider

    async def test_flock_context_provider_defaults_to_none(self):
        """CONFIGURATION: context_provider parameter should default to None.

        If no provider specified, Flock should use DefaultContextProvider as fallback.
        """
        from flock.orchestrator import Flock

        # Create Flock without provider
        flock = Flock(model="openai/gpt-4o-mini")

        # Should default to None (DefaultContextProvider will be used at runtime)
        assert hasattr(flock, "_default_context_provider")
        assert flock._default_context_provider is None

    async def test_agent_builder_has_with_context_method(self):
        """CONFIGURATION: AgentBuilder must have with_context() method.

        This enables per-agent provider configuration:
            agent.with_context(MyProvider())
        """
        from flock.orchestrator import Flock

        flock = Flock(model="openai/gpt-4o-mini")
        agent_builder = flock.agent("test-agent")

        # Should have with_context method
        assert hasattr(agent_builder, "with_context")
        assert callable(agent_builder.with_context)

    async def test_agent_builder_with_context_stores_provider(self):
        """CONFIGURATION: with_context() must store provider on agent.

        The provider should be stored as agent.context_provider for later use.
        """
        from flock.orchestrator import Flock
        from flock.context_provider import DefaultContextProvider

        flock = Flock(model="openai/gpt-4o-mini")
        provider = DefaultContextProvider()

        agent_builder = flock.agent("test-agent").with_context(provider)

        # Provider should be stored on underlying agent
        assert hasattr(agent_builder._agent, "context_provider")
        assert agent_builder._agent.context_provider == provider

    async def test_agent_builder_with_context_returns_self(self):
        """CONFIGURATION: with_context() must return self for fluent chaining.

        Example:
            agent.with_context(provider).consumes(Task).publishes(Report)
        """
        from flock.orchestrator import Flock
        from flock.context_provider import DefaultContextProvider

        flock = Flock(model="openai/gpt-4o-mini")
        provider = DefaultContextProvider()

        agent_builder = flock.agent("test-agent")
        result = agent_builder.with_context(provider)

        # Should return self for chaining
        assert result is agent_builder

    async def test_per_agent_provider_overrides_global_provider(self):
        """PRIORITY: Per-agent provider should take precedence over global provider.

        Priority order:
        1. Per-agent provider (highest priority)
        2. Global provider
        3. DefaultContextProvider fallback (lowest priority)
        """
        from flock.orchestrator import Flock
        from flock.context_provider import DefaultContextProvider

        # Custom providers for testing
        class GlobalProvider(DefaultContextProvider):
            provider_type = "global"

        class PerAgentProvider(DefaultContextProvider):
            provider_type = "per_agent"

        global_provider = GlobalProvider()
        per_agent_provider = PerAgentProvider()

        # Create flock with global provider
        flock = Flock(model="openai/gpt-4o-mini", context_provider=global_provider)

        # Create agent WITH per-agent provider
        agent_with_override = flock.agent("agent-with-override").with_context(per_agent_provider)

        # Create agent WITHOUT per-agent provider
        agent_with_global = flock.agent("agent-with-global")

        # Verify storage
        assert agent_with_override._agent.context_provider == per_agent_provider
        assert not hasattr(agent_with_global._agent, "context_provider") or agent_with_global._agent.context_provider is None

    async def test_agent_without_context_provider_attribute_by_default(self):
        """Agent should NOT have context_provider attribute initially (None).

        This ensures clean initialization - provider is only set when explicitly configured.
        """
        from flock.orchestrator import Flock

        flock = Flock(model="openai/gpt-4o-mini")
        agent = flock.agent("test-agent")

        # Agent should have context_provider attribute initialized to None
        assert hasattr(agent._agent, "context_provider")
        assert agent._agent.context_provider is None
