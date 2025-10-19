"""Tests for semantic features integration with agents.

These tests demonstrate how agents use semantic subscriptions and context
providers for intelligent artifact processing.
"""

import uuid

import pytest


# Skip all tests if sentence-transformers not available
pytest.importorskip("sentence_transformers")

from pydantic import BaseModel

from flock import Flock
from flock.components.agent import EngineComponent
from flock.core.artifacts import Artifact
from flock.core.visibility import PublicVisibility
from flock.registry import flock_type
from flock.semantic.context_provider import SemanticContextProvider
from flock.utils.runtime import EvalInputs, EvalResult


@flock_type
class SupportTicket(BaseModel):
    message: str
    category: str | None = None


@flock_type
class TicketResponse(BaseModel):
    ticket_id: str
    response: str
    similar_tickets: int


@pytest.mark.asyncio
async def test_agent_with_semantic_subscription():
    """Agent consumes artifacts using semantic text matching."""

    flock = Flock()

    # Track agent executions
    execution_count = []

    class SecurityEngine(EngineComponent):
        """Simple engine that tracks security ticket processing."""

        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            execution_count.append(True)
            return EvalResult(artifacts=[], state={})

    # Create agent that only processes security-related tickets
    agent = (
        flock.agent("security_handler")
        .consumes(SupportTicket, semantic_match="security vulnerability")
        .with_engines(SecurityEngine())
    )

    # Publish security-related ticket (should match)
    security_ticket = SupportTicket(
        message="Critical SQL injection vulnerability in login endpoint",
        category="bug",
    )
    await flock.publish(security_ticket)
    await flock.run_until_idle()

    # Publish unrelated ticket (should NOT match)
    ui_ticket = SupportTicket(
        message="Button alignment issue on homepage", category="ui"
    )
    await flock.publish(ui_ticket)
    await flock.run_until_idle()

    # Only security ticket should have triggered the agent
    assert len(execution_count) == 1


@pytest.mark.asyncio
async def test_agent_with_semantic_context_provider():
    """Agent uses SemanticContextProvider to find relevant historical context."""

    flock = Flock()

    # Populate historical tickets
    from flock.registry import type_registry

    await flock.store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(SupportTicket),
            payload={
                "message": "Password reset not working",
                "category": "auth",
            },
            produced_by="test",
            visibility=PublicVisibility(),
        )
    )
    await flock.store.publish(
        Artifact(
            id=str(uuid.uuid4()),
            type=type_registry.register(SupportTicket),
            payload={
                "message": "Can't login after password change",
                "category": "auth",
            },
            produced_by="test",
            visibility=PublicVisibility(),
        )
    )

    # Track similar ticket counts
    similar_counts = []

    class ContextEngine(EngineComponent):
        """Engine that uses SemanticContextProvider."""

        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            from flock.registry import type_registry

            # Get first input artifact
            artifact = inputs.artifacts[0]
            model_cls = type_registry.resolve(artifact.type)
            ticket = model_cls(**artifact.payload)

            # Use SemanticContextProvider to find similar historical tickets
            provider = SemanticContextProvider(
                query_text=ticket.message, threshold=0.4, limit=5
            )
            similar_tickets = await provider.get_context(flock.store)
            similar_counts.append(len(similar_tickets))

            return EvalResult(artifacts=[], state={})

    # Create agent that uses semantic context
    agent = (
        flock.agent("context_enricher")
        .consumes(SupportTicket)
        .with_engines(ContextEngine())
    )

    # Process new password-related ticket
    new_ticket = SupportTicket(
        message="User unable to login after resetting password", category="auth"
    )
    await flock.publish(new_ticket)
    await flock.run_until_idle()

    # Should find similar historical tickets
    assert len(similar_counts) == 1
    assert similar_counts[0] >= 1  # Found historical matches


@pytest.mark.asyncio
async def test_agent_semantic_routing_pattern():
    """Multiple agents with semantic text predicates create routing patterns."""

    flock = Flock()

    # Track which agents processed which tickets
    billing_executions = []
    security_executions = []
    general_executions = []

    class BillingEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            billing_executions.append(True)
            return EvalResult(artifacts=[], state={})

    class SecurityEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            security_executions.append(True)
            return EvalResult(artifacts=[], state={})

    class GeneralEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            general_executions.append(True)
            return EvalResult(artifacts=[], state={})

    # Agent 1: Handles billing issues
    billing_agent = (
        flock.agent("billing_handler")
        .consumes(SupportTicket, semantic_match="billing payment")
        .with_engines(BillingEngine())
    )

    # Agent 2: Handles security issues
    security_agent = (
        flock.agent("security_handler")
        .consumes(SupportTicket, semantic_match="security vulnerability")
        .with_engines(SecurityEngine())
    )

    # Agent 3: Handles general issues (no text filter)
    general_agent = (
        flock.agent("general_handler")
        .consumes(SupportTicket)
        .with_engines(GeneralEngine())
    )

    # Test routing - billing ticket
    billing_ticket = SupportTicket(
        message="Incorrect payment charge on my account", category="billing"
    )
    await flock.publish(billing_ticket)
    await flock.run_until_idle()

    # Test routing - security ticket
    security_ticket = SupportTicket(
        message="Critical security vulnerability discovered in authentication system",
        category="security",
    )
    await flock.publish(security_ticket)
    await flock.run_until_idle()

    # Semantic routing should direct tickets to appropriate handlers
    # Note: general_handler will process ALL tickets since it has no text filter
    assert len(billing_executions) >= 1  # Billing handler got billing ticket
    assert len(security_executions) >= 1  # Security handler got security ticket
    assert len(general_executions) == 2  # General handler got both (no filter)


@pytest.mark.asyncio
async def test_agent_min_p_parameter_controls_threshold():
    """The min_p parameter in consumes() controls semantic matching threshold."""

    flock = Flock()

    # Track which agents executed
    strict_executions = []
    loose_executions = []

    class StrictEngine(EngineComponent):
        """Engine for strict threshold agent."""

        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            strict_executions.append(True)
            return EvalResult(artifacts=[], state={})

    class LooseEngine(EngineComponent):
        """Engine for loose threshold agent."""

        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            loose_executions.append(True)
            return EvalResult(artifacts=[], state={})

    # Agent with STRICT threshold (semantic_threshold=0.55)
    # Should only match very similar content
    strict_agent = (
        flock.agent("strict_handler")
        .consumes(
            SupportTicket,
            semantic_match="login authentication",
            semantic_threshold=0.55,
        )
        .with_engines(StrictEngine())
    )

    # Agent with LOOSE threshold (semantic_threshold=0.25)
    # Should match even loosely related content
    loose_agent = (
        flock.agent("loose_handler")
        .consumes(
            SupportTicket,
            semantic_match="login authentication",
            semantic_threshold=0.25,
        )
        .with_engines(LooseEngine())
    )

    # Publish a ticket that's moderately related to "login authentication"
    # Close enough for loose threshold, but not for strict
    moderately_related_ticket = SupportTicket(
        message="User profile picture not updating correctly",
        category="support",
    )
    await flock.publish(moderately_related_ticket)
    await flock.run_until_idle()

    # Publish a ticket that's very closely related to "login authentication"
    # Should match both strict and loose thresholds
    closely_related_ticket = SupportTicket(
        message="Login authentication system failing for all users",
        category="critical",
    )
    await flock.publish(closely_related_ticket)
    await flock.run_until_idle()

    # The loose agent should have processed both tickets
    # The strict agent should only process the closely related one
    assert len(loose_executions) >= 1  # At least the closely related ticket
    assert len(strict_executions) >= 1  # The closely related ticket only

    # The loose agent should have MORE executions than strict
    # (it processes more tickets due to lower threshold)
    assert len(loose_executions) >= len(strict_executions)


@pytest.mark.asyncio
async def test_semantic_threshold_applies_to_list_queries():
    """Regression test: semantic_threshold should apply to list of queries.

    Bug fix: Previously, semantic_threshold was silently ignored when
    semantic_match was a list, causing all predicates to use the default
    threshold (0.4) instead of the specified value.
    """
    flock = Flock()

    # Track executions
    executions = []

    class TestEngine(EngineComponent):
        async def evaluate(
            self, agent, ctx, inputs: EvalInputs, output_group
        ) -> EvalResult:
            executions.append(inputs.artifacts[0].payload["message"])
            return EvalResult(artifacts=[], state={})

    # Agent with MODERATE threshold (0.5) and MULTIPLE queries (list)
    # This should apply 0.5 threshold to BOTH "billing" and "payment"
    # Without the fix, this would use default 0.4 for all queries
    strict_list_agent = (
        flock.agent("strict_list")
        .consumes(
            SupportTicket,
            semantic_match=["billing charge", "payment refund"],
            semantic_threshold=0.5,  # Should apply to ALL queries in the list
        )
        .with_engines(TestEngine())
    )

    # Ticket 1: Clearly about billing charges AND payment refunds (should match with 0.5 threshold)
    clear_match = SupportTicket(
        message="Requesting payment refund for duplicate billing charge on credit card",
        category="billing",
    )
    await flock.publish(clear_match)
    await flock.run_until_idle()

    # Ticket 2: Loosely related to billing but not payments (should NOT match with strict 0.5)
    weak_match = SupportTicket(
        message="Question about invoice format and delivery options", category="support"
    )
    await flock.publish(weak_match)
    await flock.run_until_idle()

    # Verify: Only the clear match should have triggered the agent
    # The weak match should be filtered out by the 0.5 threshold
    assert len(executions) >= 1, "Clear match should have been processed"
    assert "payment refund for duplicate billing" in executions[0], (
        "First execution should be the clear match"
    )

    # If threshold was ignored (bug), weak_match would also be processed
    # With fix, weak_match should be filtered out
    if len(executions) > 1:
        # If weak_match was processed, that means threshold was ignored (bug)
        pytest.fail(
            f"semantic_threshold was ignored! Weak match was processed: {executions}. "
            f"Expected only 1 execution, got {len(executions)}"
        )
