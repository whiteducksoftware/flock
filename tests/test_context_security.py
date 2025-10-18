"""Security tests for Context - Phase 1: Remove Infrastructure Access.

These tests ensure agents CANNOT access infrastructure directly.
This is a CRITICAL SECURITY FIX for three vulnerabilities:
- Vulnerability #1 (READ): Agents could bypass visibility via ctx.board.list()
- Vulnerability #2 (WRITE): Agents could bypass validation via ctx.board.publish()
- Vulnerability #3 (GOD MODE): Agents had unlimited ctx.orchestrator access
"""

from uuid import uuid4

import pytest

from flock.utils.runtime import Context


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
        - artifacts (prevents tampering with pre-filtered context)
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
            ctx.artifacts = [{"type": "Fake", "payload": {}}]

    def test_engine_cannot_query_store_directly(self):
        """SECURITY: Phase 8 fix - engines cannot query store at all.

        Old attack (Phase 1-7): Engines could call ctx.store.list() or ctx.provider(request)
        to query arbitrary data and bypass security.

        Phase 8 fix: Context has NO provider or store fields. Engines receive only
        pre-filtered artifacts via ctx.artifacts (evaluated by orchestrator).

        Expected: AttributeError when accessing ctx.store or ctx.provider
        """
        ctx = Context(
            task_id="test-task",
            correlation_id=uuid4(),
            artifacts=[],  # Pre-filtered by orchestrator
        )

        # Engines cannot access store or provider anymore
        with pytest.raises(AttributeError):
            _ = ctx.store

        with pytest.raises(AttributeError):
            _ = ctx.provider

    def test_context_has_only_pre_filtered_artifacts(self):
        """SECURITY: Phase 8 - Context contains ONLY pre-filtered artifacts.

        The orchestrator evaluates context using the context provider BEFORE creating
        Context. Engines receive only the result via ctx.artifacts.

        This is the FINAL security fix:
        - No provider (can't query)
        - No store (can't query)
        - Only artifacts (pre-filtered data)

        Engines are now PURE FUNCTIONS: input + context → output
        """
        # Orchestrator pre-filters context before creating Context
        pre_filtered_artifacts = [
            {"type": "Message", "payload": {"text": "hello"}, "produced_by": "user"},
            {"type": "Response", "payload": {"text": "hi"}, "produced_by": "bot"},
        ]

        ctx = Context(
            task_id="test-task",
            correlation_id=uuid4(),
            artifacts=pre_filtered_artifacts,  # Pre-filtered by orchestrator!
        )

        # Engines can ONLY read pre-filtered artifacts
        assert len(ctx.artifacts) == 2
        assert ctx.artifacts[0].type == "Message"
        assert ctx.artifacts[1].type == "Response"

        # Engines CANNOT query for more data
        with pytest.raises(AttributeError):
            _ = ctx.store.list()  # No store access

        with pytest.raises(AttributeError):
            _ = ctx.provider  # No provider access


class TestContextSecurityDocumentation:
    """Documentation tests explaining WHY these security measures exist."""

    def test_security_vulnerability_documentation(self):
        """This test documents the FOUR security vulnerabilities that were fixed.

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

        VULNERABILITY #4 (STORE ACCESS - Phase 8):
        - Engines could access ctx.store or ctx.provider to query arbitrary data
        - Even with provider security boundary, engines could bypass by calling methods
        - Engines could query cross-workflow data, bypass filters
        - Attack: Access control bypass, data exfiltration

        FIX (Phase 8 - FINAL SOLUTION):
        - Remove board and orchestrator from Context (Phases 1-6)
        - Add ContextProvider as security boundary (Phases 1-7)
        - Orchestrator evaluates context BEFORE creating Context (Phase 8)
        - Context contains ONLY pre-filtered artifacts (Phase 8)
        - Engines are pure functions: input + ctx.artifacts → output
        - NO provider, NO store, NO querying capabilities (Phase 8)
        - Agents can NO LONGER bypass security

        References:
        - .flock/flock-research/context-provider/SECURITY_ANALYSIS.md (lines 11-50)
        - docs/specs/007-context-provider-security-fix/PLAN.md
        """
        # This is a documentation test - it always passes
        assert True, "Security vulnerabilities documented"
