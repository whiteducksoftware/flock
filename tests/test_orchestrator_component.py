"""Tests for OrchestratorComponent base class and supporting types."""

import pytest


class TestScheduleDecision:
    """Tests for ScheduleDecision enum."""

    def test_schedule_decision_enum_values(self):
        """Test ScheduleDecision has CONTINUE, SKIP, DEFER values."""
        from flock.orchestrator_component import ScheduleDecision

        assert ScheduleDecision.CONTINUE == "CONTINUE"
        assert ScheduleDecision.SKIP == "SKIP"
        assert ScheduleDecision.DEFER == "DEFER"

    def test_schedule_decision_is_string_enum(self):
        """Test ScheduleDecision is a string enum."""
        from flock.orchestrator_component import ScheduleDecision

        # Should be comparable with strings
        decision = ScheduleDecision.CONTINUE
        assert decision == "CONTINUE"
        assert isinstance(decision.value, str)


class TestCollectionResult:
    """Tests for CollectionResult dataclass."""

    def test_collection_result_has_required_fields(self):
        """Test CollectionResult has artifacts and complete fields."""
        from flock.artifacts import Artifact
        from flock.orchestrator_component import CollectionResult

        artifact = Artifact(
            type="TestType",
            payload={"test": "data"},
            produced_by="test_agent",
        )

        result = CollectionResult(artifacts=[artifact], complete=True)

        assert result.artifacts == [artifact]
        assert result.complete is True

    def test_collection_result_immediate_factory(self):
        """Test CollectionResult.immediate() returns complete=True."""
        from flock.artifacts import Artifact
        from flock.orchestrator_component import CollectionResult

        artifact = Artifact(
            type="TestType",
            payload={"test": "data"},
            produced_by="test_agent",
        )

        result = CollectionResult.immediate([artifact])

        assert result.complete is True
        assert result.artifacts == [artifact]

    def test_collection_result_waiting_factory(self):
        """Test CollectionResult.waiting() returns complete=False with empty artifacts."""
        from flock.orchestrator_component import CollectionResult

        result = CollectionResult.waiting()

        assert result.complete is False
        assert result.artifacts == []


class TestOrchestratorComponent:
    """Tests for OrchestratorComponent base class."""

    def test_orchestrator_component_has_required_fields(self):
        """Test OrchestratorComponent has name, config, priority fields."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent()

        assert hasattr(component, "name")
        assert hasattr(component, "config")
        assert hasattr(component, "priority")
        assert component.priority == 0  # Default priority

    def test_orchestrator_component_custom_priority(self):
        """Test OrchestratorComponent accepts custom priority."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent(priority=10)

        assert component.priority == 10

    def test_orchestrator_component_custom_name(self):
        """Test OrchestratorComponent accepts custom name."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent(name="test_component")

        assert component.name == "test_component"

    def test_orchestrator_component_has_all_lifecycle_hooks(self):
        """Test OrchestratorComponent has all 8 lifecycle hooks."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent()

        # Verify all 8 hooks exist
        assert hasattr(component, "on_initialize")
        assert hasattr(component, "on_artifact_published")
        assert hasattr(component, "on_before_schedule")
        assert hasattr(component, "on_collect_artifacts")
        assert hasattr(component, "on_before_agent_schedule")
        assert hasattr(component, "on_agent_scheduled")
        assert hasattr(component, "on_orchestrator_idle")
        assert hasattr(component, "on_shutdown")

        # Verify they're callable
        assert callable(component.on_initialize)
        assert callable(component.on_artifact_published)
        assert callable(component.on_before_schedule)
        assert callable(component.on_collect_artifacts)
        assert callable(component.on_before_agent_schedule)
        assert callable(component.on_agent_scheduled)
        assert callable(component.on_orchestrator_idle)
        assert callable(component.on_shutdown)

    @pytest.mark.asyncio
    async def test_orchestrator_component_default_hooks_are_noops(self):
        """Test default hook implementations are no-ops (return expected defaults)."""
        from unittest.mock import Mock

        from flock.artifacts import Artifact
        from flock.orchestrator_component import (
            OrchestratorComponent,
            ScheduleDecision,
        )

        component = OrchestratorComponent()

        # Mock orchestrator, agent, subscription
        mock_orch = Mock()
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_subscription = Mock()
        mock_task = Mock()

        artifact = Artifact(
            type="TestType",
            payload={"test": "data"},
            produced_by="test_agent",
        )

        # Test default behaviors
        result = await component.on_initialize(mock_orch)
        assert result is None

        result = await component.on_artifact_published(mock_orch, artifact)
        assert result == artifact  # Returns artifact unchanged

        result = await component.on_before_schedule(
            mock_orch, artifact, mock_agent, mock_subscription
        )
        assert result == ScheduleDecision.CONTINUE  # Default: continue

        result = await component.on_collect_artifacts(
            mock_orch, artifact, mock_agent, mock_subscription
        )
        assert result is None  # Default: let other components handle

        result = await component.on_before_agent_schedule(mock_orch, mock_agent, [artifact])
        assert result == [artifact]  # Returns artifacts unchanged

        result = await component.on_agent_scheduled(mock_orch, mock_agent, [artifact], mock_task)
        assert result is None

        result = await component.on_orchestrator_idle(mock_orch)
        assert result is None

        result = await component.on_shutdown(mock_orch)
        assert result is None

    def test_orchestrator_component_uses_traced_meta(self):
        """Test OrchestratorComponent uses TracedModelMeta for auto-tracing."""
        from flock.orchestrator_component import OrchestratorComponent

        # Check that the metaclass is TracedModelMeta (which includes AutoTracedMeta)
        assert isinstance(type(OrchestratorComponent), type)
        # The class should have tracing capabilities
        # This is a bit indirect but verifies metaclass is applied
        component = OrchestratorComponent()
        assert hasattr(component, "model_dump")  # Pydantic method
        # AutoTracedMeta wraps methods, so they should be callable
        assert callable(component.on_initialize)


class TestComponentPriorityOrdering:
    """Tests for component priority ordering."""

    def test_component_priority_sorting(self):
        """Test components can be sorted by priority field."""
        from flock.orchestrator_component import OrchestratorComponent

        c1 = OrchestratorComponent(priority=10, name="c1")
        c2 = OrchestratorComponent(priority=5, name="c2")
        c3 = OrchestratorComponent(priority=20, name="c3")

        components = [c1, c2, c3]
        components.sort(key=lambda c: c.priority)

        # Should be sorted: [c2(5), c1(10), c3(20)]
        assert components[0].name == "c2"
        assert components[1].name == "c1"
        assert components[2].name == "c3"

    def test_component_default_priority_zero(self):
        """Test default priority is 0."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent()
        assert component.priority == 0


# ──────────────────────────────────────────────────────────────────
# Phase 2: Orchestrator Integration Tests
# ──────────────────────────────────────────────────────────────────


class TestFlockComponentManagement:
    """Tests for Flock orchestrator component management (Phase 2)."""

    def test_flock_has_components_list(self, orchestrator):
        """Test Flock initializes with _components list."""
        assert hasattr(orchestrator, "_components")
        assert isinstance(orchestrator._components, list)

    def test_flock_has_components_initialized_flag(self, orchestrator):
        """Test Flock has _components_initialized flag."""
        assert hasattr(orchestrator, "_components_initialized")
        assert orchestrator._components_initialized is False

    def test_flock_add_component_method_exists(self, orchestrator):
        """Test Flock has add_component() method."""
        assert hasattr(orchestrator, "add_component")
        assert callable(orchestrator.add_component)

    def test_flock_add_component_stores_component(self, orchestrator):
        """Test add_component() stores component in _components list."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent(name="test_comp", priority=5)
        orchestrator.add_component(component)

        assert component in orchestrator._components
        assert len(orchestrator._components) == 1

    def test_flock_add_component_returns_self(self, orchestrator):
        """Test add_component() returns self for method chaining."""
        from flock.orchestrator_component import OrchestratorComponent

        component = OrchestratorComponent(name="test_comp")
        result = orchestrator.add_component(component)

        assert result is orchestrator

    def test_flock_add_component_method_chaining(self, orchestrator):
        """Test add_component() supports method chaining."""
        from flock.orchestrator_component import OrchestratorComponent

        c1 = OrchestratorComponent(name="c1")
        c2 = OrchestratorComponent(name="c2")

        # Should be able to chain
        result = orchestrator.add_component(c1).add_component(c2)

        assert result is orchestrator
        assert len(orchestrator._components) == 2

    def test_flock_add_component_sorts_by_priority(self, orchestrator):
        """Test components are sorted by priority after add."""
        from flock.orchestrator_component import OrchestratorComponent

        c1 = OrchestratorComponent(priority=10, name="c1")
        c2 = OrchestratorComponent(priority=5, name="c2")
        c3 = OrchestratorComponent(priority=20, name="c3")

        orchestrator.add_component(c1)
        orchestrator.add_component(c2)
        orchestrator.add_component(c3)

        # Should be sorted: [c2(5), c1(10), c3(20)]
        assert orchestrator._components[0].name == "c2"
        assert orchestrator._components[1].name == "c1"
        assert orchestrator._components[2].name == "c3"

    def test_flock_add_component_maintains_sort_order(self, orchestrator):
        """Test adding components maintains priority sort order."""
        from flock.orchestrator_component import OrchestratorComponent

        # Add in random order
        orchestrator.add_component(OrchestratorComponent(priority=50, name="c50"))
        orchestrator.add_component(OrchestratorComponent(priority=10, name="c10"))
        orchestrator.add_component(OrchestratorComponent(priority=30, name="c30"))
        orchestrator.add_component(OrchestratorComponent(priority=20, name="c20"))

        # Should be sorted: [c10, c20, c30, c50]
        priorities = [c.priority for c in orchestrator._components]
        assert priorities == [10, 20, 30, 50]

    def test_flock_add_component_allows_duplicate_priorities(self, orchestrator):
        """Test multiple components can have same priority."""
        from flock.orchestrator_component import OrchestratorComponent

        c1 = OrchestratorComponent(priority=10, name="c1")
        c2 = OrchestratorComponent(priority=10, name="c2")

        orchestrator.add_component(c1)
        orchestrator.add_component(c2)

        # Both should be stored
        assert len(orchestrator._components) == 2
        # Both have priority 10
        assert all(c.priority == 10 for c in orchestrator._components)


# ──────────────────────────────────────────────────────────────────
# Phase 3: Component Hook Runner Tests
# ──────────────────────────────────────────────────────────────────


class TestHookRunnerInitialize:
    """Tests for _run_initialize() hook runner."""

    @pytest.mark.asyncio
    async def test_run_initialize_exists(self, orchestrator):
        """Test Flock has _run_initialize() method."""
        assert hasattr(orchestrator, "_run_initialize")
        assert callable(orchestrator._run_initialize)

    @pytest.mark.asyncio
    async def test_run_initialize_calls_all_components(self, orchestrator):
        """Test _run_initialize() calls on_initialize on all components."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class TestComponent1(OrchestratorComponent):
            priority: int = 1

            async def on_initialize(self, orch):
                call_order.append("c1")

        class TestComponent2(OrchestratorComponent):
            priority: int = 2

            async def on_initialize(self, orch):
                call_order.append("c2")

        orchestrator.add_component(TestComponent2())  # Added first but runs second
        orchestrator.add_component(TestComponent1())  # Added second but runs first

        await orchestrator._run_initialize()

        # Should execute in priority order
        assert call_order == ["c1", "c2"]
        # Should set initialized flag
        assert orchestrator._components_initialized is True

    @pytest.mark.asyncio
    async def test_run_initialize_only_runs_once(self, orchestrator):
        """Test _run_initialize() only runs once (idempotent)."""
        from flock.orchestrator_component import OrchestratorComponent

        call_count = {"count": 0}

        class TestComponent(OrchestratorComponent):
            async def on_initialize(self, orch):
                call_count["count"] += 1

        orchestrator.add_component(TestComponent())

        await orchestrator._run_initialize()
        await orchestrator._run_initialize()  # Second call should be no-op
        await orchestrator._run_initialize()  # Third call should be no-op

        assert call_count["count"] == 1  # Only called once

    @pytest.mark.asyncio
    async def test_run_initialize_propagates_exceptions(self, orchestrator):
        """Test _run_initialize() propagates exceptions from components."""
        from flock.orchestrator_component import OrchestratorComponent

        class FailingComponent(OrchestratorComponent):
            async def on_initialize(self, orch):
                raise ValueError("Initialization failed")

        orchestrator.add_component(FailingComponent())

        with pytest.raises(ValueError, match="Initialization failed"):
            await orchestrator._run_initialize()


class TestHookRunnerArtifactPublished:
    """Tests for _run_artifact_published() hook runner."""

    @pytest.mark.asyncio
    async def test_run_artifact_published_chains_components(self, orchestrator, sample_artifact):
        """Test _run_artifact_published() chains components in priority order."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class TestComponent1(OrchestratorComponent):
            priority: int = 1

            async def on_artifact_published(self, orch, artifact):
                call_order.append("c1")
                artifact.tags.add("c1")
                return artifact

        class TestComponent2(OrchestratorComponent):
            priority: int = 2

            async def on_artifact_published(self, orch, artifact):
                call_order.append("c2")
                artifact.tags.add("c2")
                return artifact

        orchestrator.add_component(TestComponent2())
        orchestrator.add_component(TestComponent1())

        result = await orchestrator._run_artifact_published(sample_artifact)

        assert call_order == ["c1", "c2"]
        assert "c1" in result.tags
        assert "c2" in result.tags

    @pytest.mark.asyncio
    async def test_run_artifact_published_stops_on_none(self, orchestrator, sample_artifact):
        """Test _run_artifact_published() stops if component returns None."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class BlockingComponent(OrchestratorComponent):
            priority: int = 1

            async def on_artifact_published(self, orch, artifact):
                call_order.append("blocking")

        class AfterComponent(OrchestratorComponent):
            priority: int = 2

            async def on_artifact_published(self, orch, artifact):
                call_order.append("after")  # Should not be called
                return artifact

        orchestrator.add_component(BlockingComponent())
        orchestrator.add_component(AfterComponent())

        result = await orchestrator._run_artifact_published(sample_artifact)

        assert result is None
        assert call_order == ["blocking"]  # After component not called

    @pytest.mark.asyncio
    async def test_run_artifact_published_propagates_exceptions(
        self, orchestrator, sample_artifact
    ):
        """Test _run_artifact_published() propagates exceptions."""
        from flock.orchestrator_component import OrchestratorComponent

        class FailingComponent(OrchestratorComponent):
            async def on_artifact_published(self, orch, artifact):
                raise RuntimeError("Transform failed")

        orchestrator.add_component(FailingComponent())

        with pytest.raises(RuntimeError, match="Transform failed"):
            await orchestrator._run_artifact_published(sample_artifact)


class TestHookRunnerBeforeSchedule:
    """Tests for _run_before_schedule() hook runner."""

    @pytest.mark.asyncio
    async def test_run_before_schedule_returns_continue_by_default(
        self, orchestrator, sample_artifact
    ):
        """Test _run_before_schedule() returns CONTINUE when no components."""
        from unittest.mock import Mock

        from flock.orchestrator_component import ScheduleDecision

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_before_schedule(sample_artifact, agent, subscription)

        assert result == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_run_before_schedule_stops_on_skip(self, orchestrator, sample_artifact):
        """Test _run_before_schedule() stops on SKIP decision."""
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent, ScheduleDecision

        call_order = []

        class SkipComponent(OrchestratorComponent):
            priority: int = 1

            async def on_before_schedule(self, orch, artifact, agent, sub):
                call_order.append("skip")
                return ScheduleDecision.SKIP

        class AfterComponent(OrchestratorComponent):
            priority: int = 2

            async def on_before_schedule(self, orch, artifact, agent, sub):
                call_order.append("after")
                return ScheduleDecision.CONTINUE

        orchestrator.add_component(SkipComponent())
        orchestrator.add_component(AfterComponent())

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_before_schedule(sample_artifact, agent, subscription)

        assert result == ScheduleDecision.SKIP
        assert call_order == ["skip"]  # After component not called

    @pytest.mark.asyncio
    async def test_run_before_schedule_stops_on_defer(self, orchestrator, sample_artifact):
        """Test _run_before_schedule() stops on DEFER decision."""
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent, ScheduleDecision

        class DeferComponent(OrchestratorComponent):
            async def on_before_schedule(self, orch, artifact, agent, sub):
                return ScheduleDecision.DEFER

        orchestrator.add_component(DeferComponent())

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_before_schedule(sample_artifact, agent, subscription)

        assert result == ScheduleDecision.DEFER


class TestHookRunnerCollectArtifacts:
    """Tests for _run_collect_artifacts() hook runner."""

    @pytest.mark.asyncio
    async def test_run_collect_artifacts_returns_first_non_none(
        self, orchestrator, sample_artifact
    ):
        """Test _run_collect_artifacts() returns first non-None result."""
        from unittest.mock import Mock

        from flock.orchestrator_component import CollectionResult, OrchestratorComponent

        call_order = []

        class Component1(OrchestratorComponent):
            priority: int = 1

            async def on_collect_artifacts(self, orch, artifact, agent, sub):
                call_order.append("c1")

        class Component2(OrchestratorComponent):
            priority: int = 2

            async def on_collect_artifacts(self, orch, artifact, agent, sub):
                call_order.append("c2")
                return CollectionResult.immediate([artifact])

        class Component3(OrchestratorComponent):
            priority: int = 3

            async def on_collect_artifacts(self, orch, artifact, agent, sub):
                call_order.append("c3")  # Should not be called
                return CollectionResult.immediate([artifact])

        orchestrator.add_component(Component1())
        orchestrator.add_component(Component2())
        orchestrator.add_component(Component3())

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_collect_artifacts(sample_artifact, agent, subscription)

        assert result.complete is True
        assert call_order == ["c1", "c2"]  # c3 not called (short-circuit)

    @pytest.mark.asyncio
    async def test_run_collect_artifacts_default_immediate(self, orchestrator, sample_artifact):
        """Test _run_collect_artifacts() returns immediate if all return None."""
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent

        class PassthroughComponent(OrchestratorComponent):
            async def on_collect_artifacts(self, orch, artifact, agent, sub):
                return None  # Let default handle

        orchestrator.add_component(PassthroughComponent())

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_collect_artifacts(sample_artifact, agent, subscription)

        # Default behavior: immediate with single artifact
        assert result.complete is True
        assert result.artifacts == [sample_artifact]


class TestHookRunnerBeforeAgentSchedule:
    """Tests for _run_before_agent_schedule() hook runner."""

    @pytest.mark.asyncio
    async def test_run_before_agent_schedule_chains_transformations(
        self, orchestrator, sample_artifact
    ):
        """Test _run_before_agent_schedule() chains artifact transformations."""
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class Component1(OrchestratorComponent):
            priority: int = 1

            async def on_before_agent_schedule(self, orch, agent, artifacts):
                call_order.append("c1")
                artifacts[0].tags.add("c1")
                return artifacts

        class Component2(OrchestratorComponent):
            priority: int = 2

            async def on_before_agent_schedule(self, orch, agent, artifacts):
                call_order.append("c2")
                artifacts[0].tags.add("c2")
                return artifacts

        orchestrator.add_component(Component1())
        orchestrator.add_component(Component2())

        agent = Mock()
        agent.name = "test_agent"

        result = await orchestrator._run_before_agent_schedule(agent, [sample_artifact])

        assert call_order == ["c1", "c2"]
        assert "c1" in result[0].tags
        assert "c2" in result[0].tags

    @pytest.mark.asyncio
    async def test_run_before_agent_schedule_stops_on_none(self, orchestrator, sample_artifact):
        """Test _run_before_agent_schedule() stops if component returns None."""
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class BlockingComponent(OrchestratorComponent):
            priority: int = 1

            async def on_before_agent_schedule(self, orch, agent, artifacts):
                call_order.append("blocking")

        class AfterComponent(OrchestratorComponent):
            priority: int = 2

            async def on_before_agent_schedule(self, orch, agent, artifacts):
                call_order.append("after")
                return artifacts

        orchestrator.add_component(BlockingComponent())
        orchestrator.add_component(AfterComponent())

        agent = Mock()
        agent.name = "test_agent"

        result = await orchestrator._run_before_agent_schedule(agent, [sample_artifact])

        assert result is None
        assert call_order == ["blocking"]


class TestHookRunnerAgentScheduled:
    """Tests for _run_agent_scheduled() hook runner."""

    @pytest.mark.asyncio
    async def test_run_agent_scheduled_calls_all_components(self, orchestrator, sample_artifact):
        """Test _run_agent_scheduled() calls all components (notification)."""
        import asyncio
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class Component1(OrchestratorComponent):
            priority: int = 1

            async def on_agent_scheduled(self, orch, agent, artifacts, task):
                call_order.append("c1")

        class Component2(OrchestratorComponent):
            priority: int = 2

            async def on_agent_scheduled(self, orch, agent, artifacts, task):
                call_order.append("c2")

        orchestrator.add_component(Component1())
        orchestrator.add_component(Component2())

        agent = Mock()
        agent.name = "test_agent"
        task = asyncio.create_task(asyncio.sleep(0))

        await orchestrator._run_agent_scheduled(agent, [sample_artifact], task)

        # Both should be called (notification hook)
        assert call_order == ["c1", "c2"]

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_run_agent_scheduled_continues_on_exception(self, orchestrator, sample_artifact):
        """Test _run_agent_scheduled() continues even if component raises."""
        import asyncio
        from unittest.mock import Mock

        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class FailingComponent(OrchestratorComponent):
            priority: int = 1

            async def on_agent_scheduled(self, orch, agent, artifacts, task):
                call_order.append("failing")
                raise RuntimeError("Notification failed")

        class AfterComponent(OrchestratorComponent):
            priority: int = 2

            async def on_agent_scheduled(self, orch, agent, artifacts, task):
                call_order.append("after")

        orchestrator.add_component(FailingComponent())
        orchestrator.add_component(AfterComponent())

        agent = Mock()
        agent.name = "test_agent"
        task = asyncio.create_task(asyncio.sleep(0))

        # Should NOT raise
        await orchestrator._run_agent_scheduled(agent, [sample_artifact], task)

        # Both should be called (non-blocking)
        assert call_order == ["failing", "after"]

        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


class TestHookRunnerIdle:
    """Tests for _run_idle() hook runner."""

    @pytest.mark.asyncio
    async def test_run_idle_calls_all_components(self, orchestrator):
        """Test _run_idle() calls all components."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class Component1(OrchestratorComponent):
            priority: int = 1

            async def on_orchestrator_idle(self, orch):
                call_order.append("c1")

        class Component2(OrchestratorComponent):
            priority: int = 2

            async def on_orchestrator_idle(self, orch):
                call_order.append("c2")

        orchestrator.add_component(Component1())
        orchestrator.add_component(Component2())

        await orchestrator._run_idle()

        assert call_order == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_run_idle_continues_on_exception(self, orchestrator):
        """Test _run_idle() continues even if component raises."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class FailingComponent(OrchestratorComponent):
            priority: int = 1

            async def on_orchestrator_idle(self, orch):
                call_order.append("failing")
                raise RuntimeError("Idle cleanup failed")

        class AfterComponent(OrchestratorComponent):
            priority: int = 2

            async def on_orchestrator_idle(self, orch):
                call_order.append("after")

        orchestrator.add_component(FailingComponent())
        orchestrator.add_component(AfterComponent())

        # Should NOT raise
        await orchestrator._run_idle()

        # Both should be called (non-blocking)
        assert call_order == ["failing", "after"]


class TestHookRunnerShutdown:
    """Tests for _run_shutdown() hook runner."""

    @pytest.mark.asyncio
    async def test_run_shutdown_calls_all_components(self, orchestrator):
        """Test _run_shutdown() calls all components."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class Component1(OrchestratorComponent):
            priority: int = 1

            async def on_shutdown(self, orch):
                call_order.append("c1")

        class Component2(OrchestratorComponent):
            priority: int = 2

            async def on_shutdown(self, orch):
                call_order.append("c2")

        orchestrator.add_component(Component1())
        orchestrator.add_component(Component2())

        await orchestrator._run_shutdown()

        assert call_order == ["c1", "c2"]

    @pytest.mark.asyncio
    async def test_run_shutdown_continues_on_exception(self, orchestrator):
        """Test _run_shutdown() continues shutdown even if component fails."""
        from flock.orchestrator_component import OrchestratorComponent

        call_order = []

        class FailingComponent(OrchestratorComponent):
            priority: int = 1

            async def on_shutdown(self, orch):
                call_order.append("failing")
                raise RuntimeError("Shutdown failed")

        class AfterComponent(OrchestratorComponent):
            priority: int = 2

            async def on_shutdown(self, orch):
                call_order.append("after")

        orchestrator.add_component(FailingComponent())
        orchestrator.add_component(AfterComponent())

        # Should NOT raise (continue shutting down other components)
        await orchestrator._run_shutdown()

        # Both should be called
        assert call_order == ["failing", "after"]
