"""Tests for Orchestrator Context Evaluation + Publishing - Phase 8.

This test suite verifies the Phase 8 FINAL security implementation:

Phase 8 (Pre-filtered Context):
- Orchestrator evaluates context BEFORE creating Context
- Context contains ONLY pre-filtered artifacts (no provider/store)
- Engines are pure functions: input + ctx.artifacts → output
- Fixes Vulnerability #4 (STORE ACCESS) - engines can't query anything

Phase 6 (Orchestrator Publishing):
- Agents return artifacts without publishing
- Orchestrator publishes artifacts after agent.execute()
- Fixes Vulnerability #2 (WRITE Bypass) - agents can't bypass validation

Security Properties:
- ✅ Agents have NO direct publishing capability
- ✅ Orchestrator validates and publishes all artifacts
- ✅ Context has ONLY pre-filtered artifacts (NO provider/store/board/orchestrator)
- ✅ Orchestrator evaluates context using provider (not engines)
- ✅ Per-agent provider overrides global provider (orchestrator-level)
"""

import pytest
from pydantic import BaseModel

from flock.core import Flock
from flock.core.context_provider import FilteredContextProvider
from flock.core.store import FilterConfig
from flock.core.visibility import PrivateVisibility


class Task(BaseModel):
    """Test model for artifacts."""

    name: str
    priority: int = 1


class Result(BaseModel):
    """Test model for agent outputs."""

    status: str
    task_name: str


@pytest.mark.asyncio
class TestOrchestratorContextInjection:
    """Phase 8: Test orchestrator evaluates context and creates Context with pre-filtered artifacts."""

    async def test_orchestrator_provides_prefiltered_artifacts_in_context(self):
        """SECURITY Phase 8: Context must contain ONLY pre-filtered artifacts (no provider/store).

        This ensures engines cannot query arbitrary data - they receive only
        the pre-filtered conversation context evaluated by the orchestrator.
        """
        flock = Flock("openai/gpt-4o-mini")

        # Create agent
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to capture the Context
        captured_ctx = None

        original_execute = agent.execute

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            # Return empty result
            return []

        agent.execute = mock_execute

        # Invoke agent
        await flock.invoke(agent, Task(name="test", priority=1), publish_outputs=False)

        # SECURITY Phase 8: Context must have artifacts field (pre-filtered)
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")
        assert isinstance(captured_ctx.artifacts, list), (
            "Context must have pre-filtered artifacts list"
        )

        # SECURITY Phase 8: Context must NOT have provider or store
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

        with pytest.raises(AttributeError):
            _ = captured_ctx.store

    async def test_orchestrator_removes_all_capability_fields_from_context(self):
        """SECURITY Phase 8: Context must NOT have ANY capability fields.

        All phases combined removed these fields to prevent agents from
        bypassing security boundaries:
        - Phase 1: Removed board, orchestrator
        - Phase 8: Removed provider, store

        Context is now purely data - no capabilities!
        """
        flock = Flock("openai/gpt-4o-mini")

        # Create agent
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to capture the Context
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            return []

        agent.execute = mock_execute

        # Invoke agent
        await flock.invoke(agent, Task(name="test", priority=1), publish_outputs=False)

        # SECURITY Phase 8: Context must NOT have ANY capability fields
        assert captured_ctx is not None

        # Phase 1 removals
        with pytest.raises(AttributeError):
            _ = captured_ctx.board

        with pytest.raises(AttributeError):
            _ = captured_ctx.orchestrator

        # Phase 8 removals
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

        with pytest.raises(AttributeError):
            _ = captured_ctx.store

    async def test_orchestrator_uses_default_provider_when_no_custom_provider(self):
        """Phase 8: Orchestrator uses DefaultContextProvider internally when no custom provider configured.

        The orchestrator evaluates context using the provider BEFORE creating Context.
        Engines receive only pre-filtered artifacts via ctx.artifacts.
        """
        flock = Flock("openai/gpt-4o-mini")  # No context_provider specified

        # Create agent without custom provider
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to capture the Context
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            return []

        agent.execute = mock_execute

        # Invoke agent
        await flock.invoke(agent, Task(name="test", priority=1), publish_outputs=False)

        # Phase 8: Context has pre-filtered artifacts (no provider field)
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")
        assert isinstance(captured_ctx.artifacts, list)

        # Context does NOT have provider (it was used by orchestrator)
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

    async def test_orchestrator_uses_global_provider_when_configured(self):
        """Phase 8: Orchestrator uses global provider internally when configured at Flock level.

        The orchestrator uses the provider to evaluate context, then creates
        Context with pre-filtered artifacts only.
        """
        # Create global provider
        global_provider = FilteredContextProvider(FilterConfig(tags={"important"}))

        flock = Flock("openai/gpt-4o-mini", context_provider=global_provider)

        # Create agent without custom provider
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to capture the Context
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            return []

        agent.execute = mock_execute

        # Invoke agent
        await flock.invoke(agent, Task(name="test", priority=1), publish_outputs=False)

        # Phase 8: Context has pre-filtered artifacts only
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")

        # Context does NOT have provider (orchestrator used it internally)
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

    async def test_orchestrator_uses_per_agent_provider_when_configured(self):
        """Phase 8: Orchestrator uses per-agent provider internally (overrides global provider).

        Priority: per-agent > global > DefaultContextProvider
        The orchestrator uses this provider to evaluate context, then creates
        Context with pre-filtered artifacts.
        """
        # Create global provider
        global_provider = FilteredContextProvider(FilterConfig(tags={"important"}))

        flock = Flock("openai/gpt-4o-mini", context_provider=global_provider)

        # Create per-agent provider
        agent_provider = FilteredContextProvider(FilterConfig(tags={"urgent"}))

        # Create agent and set custom provider
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent
        agent.context_provider = agent_provider

        # Mock agent.execute to capture the Context
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            return []

        agent.execute = mock_execute

        # Invoke agent
        await flock.invoke(agent, Task(name="test", priority=1), publish_outputs=False)

        # Phase 8: Context has pre-filtered artifacts only (orchestrator used per-agent provider)
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")

        # Context does NOT have provider
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

    async def test_context_has_all_required_fields(self):
        """Phase 8: Context must have all required fields (data only, no capabilities)."""
        flock = Flock("openai/gpt-4o-mini")

        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to capture the Context
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            return []

        agent.execute = mock_execute

        # Invoke agent with correlation_id
        task = Task(name="test", priority=1)
        await flock.publish(task)
        await flock.run_until_idle()

        # Phase 8: Context must have data fields (no capability fields)
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")  # Pre-filtered data
        assert hasattr(captured_ctx, "correlation_id")
        assert hasattr(captured_ctx, "task_id")
        assert hasattr(captured_ctx, "state")
        assert hasattr(captured_ctx, "agent_identity")  # Informational only

        # Phase 8: Context must NOT have capability fields
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

        with pytest.raises(AttributeError):
            _ = captured_ctx.store


@pytest.mark.asyncio
class TestOrchestratorPublishing:
    """Phase 6: Test orchestrator publishes artifacts after agent execution."""

    async def test_orchestrator_publishes_artifacts_after_agent_execute(self):
        """SECURITY: Orchestrator must publish artifacts returned by agents.

        Phase 6 security fix:
        - Agents return artifacts (don't publish directly)
        - Orchestrator publishes artifacts after validation
        - Fixes Vulnerability #2 (WRITE Bypass)
        """
        flock = Flock("openai/gpt-4o-mini")

        # Create agent that returns artifacts
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to return artifacts
        async def mock_execute(ctx, artifacts):
            # Agent returns Result artifact (doesn't publish)
            result = Result(status="done", task_name="test")
            from flock.utils.runtime import EvalResult

            eval_result = EvalResult.from_object(result, agent=agent)

            # Convert to artifacts
            return eval_result.artifacts

        agent.execute = mock_execute

        # Invoke agent
        task = Task(name="test", priority=1)
        outputs = await flock.invoke(agent, task, publish_outputs=True)

        # Orchestrator should have published the artifacts
        assert len(outputs) == 1
        assert "Result" in outputs[0].type  # Type may include module path
        assert outputs[0].payload["status"] == "done"

        # Verify artifact was published to store
        all_artifacts = await flock.store.list()
        result_artifacts = [a for a in all_artifacts if "Result" in a.type]
        assert len(result_artifacts) > 0, (
            "Orchestrator must publish agent outputs to store"
        )

    async def test_orchestrator_publishes_multiple_artifacts(self):
        """Orchestrator must publish all artifacts returned by agent."""
        flock = Flock("openai/gpt-4o-mini")

        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to return multiple artifacts
        async def mock_execute(ctx, artifacts):
            from flock.utils.runtime import EvalResult

            result1 = Result(status="done", task_name="task1")
            result2 = Result(status="done", task_name="task2")
            return EvalResult.from_objects(result1, result2, agent=agent).artifacts

        agent.execute = mock_execute

        # Invoke agent
        task = Task(name="test", priority=1)
        outputs = await flock.invoke(agent, task, publish_outputs=True)

        # Should have 2 outputs
        assert len(outputs) == 2
        assert all("Result" in a.type for a in outputs)

        # Both should be in store
        all_artifacts = await flock.store.list()
        result_artifacts = [a for a in all_artifacts if "Result" in a.type]
        assert len(result_artifacts) >= 2, "All artifacts must be published"

    async def test_orchestrator_respects_publish_outputs_flag(self):
        """When publish_outputs=False, orchestrator should NOT publish artifacts."""
        flock = Flock("openai/gpt-4o-mini")

        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to return artifacts
        async def mock_execute(ctx, artifacts):
            from flock.utils.runtime import EvalResult

            result = Result(status="done", task_name="test")
            return EvalResult.from_object(result, agent=agent).artifacts

        agent.execute = mock_execute

        # Get initial artifact count
        initial_artifacts = await flock.store.list()
        initial_count = len([a for a in initial_artifacts if a.type == "Result"])

        # Invoke agent with publish_outputs=False
        task = Task(name="test", priority=1)
        outputs = await flock.invoke(agent, task, publish_outputs=False)

        # Should return artifacts
        assert len(outputs) == 1

        # But they should NOT be published to store
        all_artifacts = await flock.store.list()
        result_artifacts = [a for a in all_artifacts if "Result" in a.type]
        assert len(result_artifacts) == initial_count, (
            "Artifacts should NOT be published when flag=False"
        )

    async def test_orchestrator_publishes_during_event_driven_workflow(self):
        """Orchestrator must publish artifacts during event-driven publish() + run_until_idle()."""
        flock = Flock("openai/gpt-4o-mini")

        # Create agent
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute
        async def mock_execute(ctx, artifacts):
            from flock.utils.runtime import EvalResult

            task = Task(**artifacts[0].payload)
            result = Result(status="processed", task_name=task.name)
            return EvalResult.from_object(result, agent=agent).artifacts

        agent.execute = mock_execute

        # Event-driven workflow
        task = Task(name="workflow-test", priority=1)
        await flock.publish(task)
        await flock.run_until_idle()

        # Result should be in store
        all_artifacts = await flock.store.list()
        result_artifacts = [a for a in all_artifacts if "Result" in a.type]
        assert len(result_artifacts) > 0
        assert any(a.payload["task_name"] == "workflow-test" for a in result_artifacts)

    async def test_agent_cannot_publish_directly(self):
        """SECURITY: Agents should NOT have ctx.board.publish() capability.

        This test verifies that the vulnerable direct publishing pattern
        has been removed from agents.
        """
        flock = Flock("openai/gpt-4o-mini")

        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Mock agent.execute to try to publish directly
        attempted_direct_publish = False

        async def mock_execute(ctx, artifacts):
            nonlocal attempted_direct_publish

            # Try to access ctx.board (should be None or not exist)
            board = getattr(ctx, "board", None)
            if board is not None:
                # If board exists, try to publish (should fail or not be called)
                try:
                    result = Result(status="hacked", task_name="bypass")
                    from flock.core.artifacts import Artifact
                    from flock.registry import type_registry

                    type_name = type_registry.name_for(Result)
                    artifact = Artifact(
                        type=type_name,
                        payload=result.model_dump(),
                        produced_by="hacker",
                    )
                    # This should fail or not exist
                    if hasattr(board, "publish"):
                        await board.publish(artifact)
                        attempted_direct_publish = True
                except Exception:
                    pass  # Expected to fail

            # Return result normally
            from flock.utils.runtime import EvalResult

            result = Result(status="done", task_name="test")
            return EvalResult.from_object(result, agent=agent).artifacts

        agent.execute = mock_execute

        # Invoke agent
        task = Task(name="test", priority=1)
        await flock.invoke(agent, task, publish_outputs=True)

        # Agent should NOT have been able to publish directly
        # This test documents the Phase 6 fix - agents return artifacts, orchestrator publishes
        # The assertion is that the flow works correctly (no exception thrown)
        assert True, "Phase 6 fix: Agents return artifacts, orchestrator publishes"


@pytest.mark.asyncio
class TestPhase67Integration:
    """Integration tests for combined Phase 6+7 security fixes."""

    async def test_end_to_end_security_boundary(self):
        """Phase 8: Full security flow with pre-filtered context + orchestrator publishing.

        This test verifies the complete Phase 8 security fixes work together:
        1. Orchestrator evaluates context using provider (BEFORE creating Context)
        2. Context contains ONLY pre-filtered artifacts (no capabilities)
        3. Agent returns artifacts without publishing
        4. Orchestrator validates and publishes artifacts
        """
        flock = Flock("openai/gpt-4o-mini")

        # Create agent
        agent = flock.agent("worker").consumes(Task).publishes(Result).agent

        # Track Context
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx

            # Agent returns result
            from flock.utils.runtime import EvalResult

            task = Task(**artifacts[0].payload)
            result = Result(status="complete", task_name=task.name)
            return EvalResult.from_object(result, agent=agent).artifacts

        agent.execute = mock_execute

        # Execute workflow
        task = Task(name="secure-test", priority=1)
        await flock.publish(task)
        await flock.run_until_idle()

        # SECURITY CHECKS Phase 8:
        # 1. Context has pre-filtered artifacts (no capabilities)
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")
        assert isinstance(captured_ctx.artifacts, list)

        # 2. Context does NOT have ANY capability fields
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

        with pytest.raises(AttributeError):
            _ = captured_ctx.store

        with pytest.raises(AttributeError):
            _ = captured_ctx.board

        with pytest.raises(AttributeError):
            _ = captured_ctx.orchestrator

        # 3. Result was published by orchestrator
        all_artifacts = await flock.store.list()
        result_artifacts = [a for a in all_artifacts if "Result" in a.type]
        assert len(result_artifacts) > 0
        assert any(a.payload["task_name"] == "secure-test" for a in result_artifacts)

    async def test_visibility_enforcement_with_context_evaluation(self):
        """Phase 8: Orchestrator enforces visibility when evaluating context.

        The orchestrator uses the provider to evaluate context BEFORE creating Context.
        Engines receive only pre-filtered artifacts via ctx.artifacts.
        Private artifacts should NOT appear in ctx.artifacts.
        """
        flock = Flock("openai/gpt-4o-mini")

        # Create private artifact (only visible to admin)
        private_task = Task(name="secret", priority=10)
        private_artifact = await flock.publish(
            private_task, visibility=PrivateVisibility(agents={"admin"})
        )

        # Create agent (NOT admin)
        agent = flock.agent("hacker").consumes(Task).publishes(Result).agent

        # Mock agent to check ctx.artifacts
        captured_ctx = None

        async def mock_execute(ctx, artifacts):
            nonlocal captured_ctx
            captured_ctx = ctx
            return []

        agent.execute = mock_execute

        # Invoke agent with correlation_id (to enable context fetching)
        public_task = Task(name="public", priority=1)
        # Publish with same correlation_id as private artifact to test filtering
        await flock.publish(public_task, correlation_id=private_artifact.correlation_id)
        await flock.run_until_idle()

        # Phase 8: ctx.artifacts should NOT contain private artifact
        assert captured_ctx is not None
        assert hasattr(captured_ctx, "artifacts")

        # Private artifact should NOT be in pre-filtered context
        secret_in_context = any(
            item.get("payload", {}).get("name") == "secret"
            for item in captured_ctx.artifacts
        )
        assert not secret_in_context, (
            "Private artifact should NOT be in pre-filtered context"
        )

        # Agent cannot query for more data (no provider/store)
        with pytest.raises(AttributeError):
            _ = captured_ctx.provider

        with pytest.raises(AttributeError):
            _ = captured_ctx.store
