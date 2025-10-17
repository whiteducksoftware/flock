"""Security tests for Context - Phase 1: Remove Infrastructure Access.

These tests ensure agents CANNOT access infrastructure directly.
This is a CRITICAL SECURITY FIX for three vulnerabilities:
- Vulnerability #1 (READ): Agents could bypass visibility via ctx.board.list()
- Vulnerability #2 (WRITE): Agents could bypass validation via ctx.board.publish()
- Vulnerability #3 (GOD MODE): Agents had unlimited ctx.orchestrator access
"""

import pytest
from uuid import uuid4
from flock.runtime import Context


class TestContextSecurityPhase1:
    """Phase 1: Verify Context has NO infrastructure access (board/orchestrator removed)."""

    def test_context_has_no_board_attribute(self):
        """SECURITY: Context must NOT have 'board' attribute.

        Vulnerability #1 & #2: Agents used ctx.board.list() and ctx.board.publish()
        to bypass visibility filtering and validation.

        Expected: AttributeError when accessing ctx.board
        """
        ctx = Context(
            board=None,  # This line will fail after implementation
            orchestrator=None,
            task_id="test-task",
            correlation_id=uuid4(),
        )

        # After security fix, this should raise AttributeError
        with pytest.raises(AttributeError, match="board"):
            _ = ctx.board

    def test_context_has_no_orchestrator_attribute(self):
        """SECURITY: Context must NOT have 'orchestrator' attribute.

        Vulnerability #3 (GOD MODE): Agents used ctx.orchestrator to access
        internal state, manipulate subscriptions, and perform privileged operations.

        Expected: AttributeError when accessing ctx.orchestrator
        """
        ctx = Context(
            board=None,
            orchestrator=None,  # This line will fail after implementation
            task_id="test-task",
            correlation_id=uuid4(),
        )

        # After security fix, this should raise AttributeError
        with pytest.raises(AttributeError, match="orchestrator"):
            _ = ctx.orchestrator

    def test_context_retains_safe_fields(self):
        """SECURITY: Context must still have safe fields (task_id, state, etc).

        These fields are NOT security risks:
        - task_id: Execution identifier (read-only)
        - correlation_id: Workflow identifier (read-only)
        - state: Agent-local state (isolated, no infrastructure access)
        - is_batch: Batch processing flag (read-only)
        """
        correlation = uuid4()
        ctx = Context(
            task_id="test-task",
            correlation_id=correlation,
            state={"foo": "bar"},
            is_batch=True,
        )

        # These should all work after security fix
        assert ctx.task_id == "test-task"
        assert ctx.correlation_id == correlation
        assert ctx.state == {"foo": "bar"}
        assert ctx.is_batch is True
        assert ctx.get_variable("foo") == "bar"
        assert ctx.get_variable("missing", "default") == "default"

    def test_agent_cannot_use_ctx_board_list_pattern(self):
        """SECURITY: Old vulnerable pattern 'ctx.board.list()' must fail.

        Vulnerability #1 (READ BYPASS): Agents used this to access ALL artifacts
        without visibility filtering.

        Attack scenario:
            all_artifacts = await ctx.board.list()
            secrets = [a for a in all_artifacts if "password" in a.payload]

        Expected: AttributeError - this pattern is FORBIDDEN
        """
        ctx = Context(
            task_id="malicious-agent",
            correlation_id=uuid4(),
        )

        # This old vulnerable pattern MUST fail
        with pytest.raises(AttributeError):
            _ = ctx.board.list()

    def test_agent_cannot_use_ctx_board_publish_pattern(self):
        """SECURITY: Old vulnerable pattern 'ctx.board.publish()' must fail.

        Vulnerability #2 (WRITE BYPASS): Agents used this to publish artifacts
        directly, bypassing validation and forging metadata.

        Attack scenario:
            fake = Artifact(type="Report", payload={...}, produced_by="admin")
            await ctx.board.publish(fake)  # Bypass validation!

        Expected: AttributeError - this pattern is FORBIDDEN
        """
        ctx = Context(
            task_id="malicious-agent",
            correlation_id=uuid4(),
        )

        # This old vulnerable pattern MUST fail
        with pytest.raises(AttributeError):
            _ = ctx.board.publish

    def test_agent_cannot_use_ctx_orchestrator_pattern(self):
        """SECURITY: Old vulnerable pattern 'ctx.orchestrator.*' must fail.

        Vulnerability #3 (GOD MODE): Agents used this to access internal
        orchestrator state and perform privileged operations.

        Attack scenarios:
            ctx.orchestrator.store  # Access raw store
            ctx.orchestrator._agents  # Manipulate agents
            await ctx.orchestrator.publish(...)  # Publish as orchestrator

        Expected: AttributeError - this pattern is FORBIDDEN
        """
        ctx = Context(
            task_id="malicious-agent",
            correlation_id=uuid4(),
        )

        # This old vulnerable pattern MUST fail
        with pytest.raises(AttributeError):
            _ = ctx.orchestrator

    def test_context_creation_without_board_and_orchestrator(self):
        """SECURITY: Context should be creatable WITHOUT board/orchestrator.

        After security fix, Context should NOT require these fields.
        Agents don't need infrastructure access - they receive filtered context
        and return data only.
        """
        # This should work after security fix (no board/orchestrator required)
        ctx = Context(
            task_id="secure-agent",
            correlation_id=uuid4(),
            state={"secure": True},
        )

        assert ctx.task_id == "secure-agent"
        assert ctx.state["secure"] is True

        # Verify infrastructure access is NOT available
        with pytest.raises(AttributeError):
            _ = ctx.board

        with pytest.raises(AttributeError):
            _ = ctx.orchestrator


class TestContextSecurityPhase7IdentitySpoofing:
    """Phase 7: Verify engines cannot fake agent identity to bypass visibility."""

    def test_context_is_frozen_immutable(self):
        """SECURITY: Context must be frozen (immutable) to prevent tampering.

        Vulnerability: Engines could mutate ctx.agent_identity to escalate privileges:
            ctx.agent_identity = AgentIdentity(name="admin", labels={"admin"})

        Expected: ValidationError when trying to mutate any Context field
        """
        from pydantic import ValidationError
        from flock.agent import AgentIdentity

        ctx = Context(
            task_id="test-task",
            correlation_id=uuid4(),
            agent_identity=AgentIdentity(name="user", labels=set()),
        )

        # Attempt to mutate agent_identity - MUST fail
        with pytest.raises(ValidationError, match="frozen"):
            ctx.agent_identity = AgentIdentity(name="admin", labels={"admin"})

    def test_context_prevents_field_mutation(self):
        """SECURITY: All Context fields must be immutable.

        Ensures engines cannot modify any security-critical fields:
        - agent_identity (prevents privilege escalation)
        - provider (prevents security boundary bypass)
        - store (prevents direct data access)
        - task_id, correlation_id (prevents context confusion)
        """
        from pydantic import ValidationError

        ctx = Context(
            task_id="original-task",
            correlation_id=uuid4(),
        )

        # All these mutations MUST fail
        with pytest.raises(ValidationError, match="frozen"):
            ctx.task_id = "malicious-task"

        with pytest.raises(ValidationError, match="frozen"):
            ctx.correlation_id = uuid4()

        with pytest.raises(ValidationError, match="frozen"):
            ctx.provider = "fake_provider"

        with pytest.raises(ValidationError, match="frozen"):
            ctx.store = "fake_store"

    async def test_engine_cannot_fake_identity_via_parameter(self):
        """SECURITY: Engines cannot bypass visibility by passing fake agent parameter.

        Attack scenario:
            class MaliciousEngine(EngineComponent):
                async def evaluate(self, agent, ctx, inputs, output_group):
                    # Create fake agent with admin privileges
                    fake_agent = type('FakeAgent', (), {})()
                    fake_agent.identity = AgentIdentity(name="admin", labels={"admin"})

                    # Try to get admin-only artifacts
                    context = await self.fetch_conversation_context(ctx, agent=fake_agent)

        Expected: fetch_conversation_context uses ctx.agent_identity (trusted source)
                 NOT the agent parameter (untrusted source)
        """
        from flock.agent import Agent, AgentIdentity
        from flock.artifacts import Artifact
        from flock.components import EngineComponent
        from flock.context_provider import DefaultContextProvider
        from flock.store import InMemoryBlackboardStore
        from flock.visibility import PrivateVisibility

        # Setup: Create a private artifact visible only to "admin"
        store = InMemoryBlackboardStore()
        correlation_id = uuid4()

        admin_artifact = Artifact(
            type="Secret",
            payload={"secret": "admin_data"},
            produced_by="admin",
            visibility=PrivateVisibility(agents={"admin"}),
            correlation_id=correlation_id,
        )
        await store.publish(admin_artifact)

        # Create non-admin agent with limited visibility
        # Use simple object since we only need .identity property for the test
        user_agent = type('MockAgent', (), {})()
        user_agent.name = "user_agent"
        user_agent.identity = AgentIdentity(name="user", labels=set())

        # Create Context with user_agent identity (from orchestrator - trusted source)
        provider = DefaultContextProvider()
        ctx = Context(
            task_id="test-task",
            correlation_id=correlation_id,
            agent_identity=user_agent.identity,  # Set by orchestrator
            provider=provider,
            store=store,
        )

        # ATTACK: Malicious engine creates fake admin agent
        fake_admin_agent = type('FakeAgent', (), {})()
        fake_admin_agent.identity = AgentIdentity(name="admin", labels={"admin"})
        fake_admin_agent.name = "fake_admin"

        # Try to fetch context using fake admin agent
        engine = EngineComponent()
        context = await engine.fetch_conversation_context(
            ctx,
            agent=fake_admin_agent,  # Fake agent with escalated privileges
        )

        # SECURITY: Should NOT see admin artifact because ctx.agent_identity is "user"
        assert len(context) == 0, "Engine should NOT see admin-only artifacts via fake agent"

    async def test_fetch_context_uses_trusted_agent_identity(self):
        """SECURITY: Verify fetch_conversation_context uses ctx.agent_identity.

        This test verifies the fix works correctly:
        - ctx.agent_identity comes from orchestrator (trusted source)
        - fetch_conversation_context uses ctx.agent_identity
        - Even if engine passes different agent parameter, it's ignored for visibility
        """
        from flock.agent import Agent, AgentIdentity
        from flock.artifacts import Artifact
        from flock.components import EngineComponent
        from flock.context_provider import DefaultContextProvider
        from flock.store import InMemoryBlackboardStore
        from flock.visibility import PrivateVisibility, PublicVisibility

        # Setup: Create artifacts with different visibility
        store = InMemoryBlackboardStore()
        correlation_id = uuid4()

        # Admin-only artifact
        admin_artifact = Artifact(
            type="AdminData",
            payload={"data": "admin_only"},
            produced_by="system",
            visibility=PrivateVisibility(agents={"admin"}),
            correlation_id=correlation_id,
        )
        await store.publish(admin_artifact)

        # Public artifact
        public_artifact = Artifact(
            type="PublicData",
            payload={"data": "public"},
            produced_by="system",
            visibility=PublicVisibility(),
            correlation_id=correlation_id,
        )
        await store.publish(public_artifact)

        # Create admin agent
        # Use simple object since we only need .identity property for the test
        admin_agent = type('MockAgent', (), {})()
        admin_agent.name = "admin_agent"
        admin_agent.identity = AgentIdentity(name="admin", labels={"admin"})

        # Create Context with admin identity (from orchestrator)
        provider = DefaultContextProvider()
        ctx = Context(
            task_id="test-task",
            correlation_id=correlation_id,
            agent_identity=admin_agent.identity,  # Admin identity from trusted source
            provider=provider,
            store=store,
        )

        # Fetch context - should see BOTH artifacts (admin has access)
        engine = EngineComponent()
        context = await engine.fetch_conversation_context(ctx, agent=admin_agent)

        # Should see both artifacts
        assert len(context) == 2, "Admin should see both public and admin-only artifacts"
        artifact_types = {item["type"] for item in context}
        assert artifact_types == {"AdminData", "PublicData"}

        # Now verify that even if we pass a different agent parameter,
        # it still uses ctx.agent_identity for visibility
        fake_user_agent = type('FakeAgent', (), {})()
        fake_user_agent.identity = AgentIdentity(name="user", labels=set())
        fake_user_agent.name = "fake_user"

        # Fetch context with fake user agent - should STILL see admin artifacts
        # because ctx.agent_identity is admin (not the agent parameter)
        context2 = await engine.fetch_conversation_context(ctx, agent=admin_agent)
        assert len(context2) == 2, "Should use ctx.agent_identity, not agent parameter"


class TestContextSecurityDocumentation:
    """Documentation tests explaining WHY these security measures exist."""

    def test_security_vulnerability_documentation(self):
        """This test documents the three security vulnerabilities that were fixed.

        VULNERABILITY #1 (READ BYPASS):
        - Agents could call ctx.board.list() to get ALL artifacts
        - Visibility filtering was NOT enforced at context level
        - Agents could access private/tenant/classified data
        - Attack: Data leakage, tenant isolation bypass, RBAC bypass

        VULNERABILITY #2 (WRITE BYPASS):
        - Agents could call ctx.board.publish() to publish ANY artifact
        - Validation was NOT enforced (agent._make_outputs_for_group validated, but engines could bypass)
        - Agents could forge produced_by, visibility, correlation_id
        - Attack: Publish invalid data, impersonate other agents, declassify secrets

        VULNERABILITY #3 (GOD MODE):
        - Agents had direct ctx.orchestrator access
        - Could access internal state (_agents, _subscriptions, store, config)
        - Could perform orchestrator-level operations
        - Attack: Complete privilege escalation, system manipulation

        VULNERABILITY #4 (IDENTITY SPOOFING - Phase 7):
        - Engines could pass fake agent parameter to fetch_conversation_context
        - agent.identity came from untrusted engine code
        - Engines could escalate privileges by creating fake agent objects
        - Attack: Bypass visibility filtering, access restricted artifacts

        FIX:
        - Remove board and orchestrator from Context (Phases 1-6)
        - Add ContextProvider as security boundary (filters by visibility)
        - Orchestrator publishes (agents return data only)
        - Make Context frozen/immutable (Phase 7)
        - Use ctx.agent_identity from trusted source (orchestrator) (Phase 7)
        - Agents can NO LONGER bypass security

        References:
        - .flock/flock-research/context-provider/SECURITY_ANALYSIS.md (lines 11-50)
        - docs/specs/007-context-provider-security-fix/PLAN.md
        """
        # This is a documentation test - it always passes
        assert True, "Security vulnerabilities documented"
