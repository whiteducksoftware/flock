"""Tests for OrchestratorComponent base class and supporting types."""

import pytest


class TestScheduleDecision:
    """Tests for ScheduleDecision enum."""

    def test_schedule_decision_enum_values(self):
        """Test ScheduleDecision has CONTINUE, SKIP, DEFER values."""
        from flock.components.orchestrator import ScheduleDecision

        assert ScheduleDecision.CONTINUE == "CONTINUE"
        assert ScheduleDecision.SKIP == "SKIP"
        assert ScheduleDecision.DEFER == "DEFER"

    def test_schedule_decision_is_string_enum(self):
        """Test ScheduleDecision is a string enum."""
        from flock.components.orchestrator import ScheduleDecision

        # Should be comparable with strings
        decision = ScheduleDecision.CONTINUE
        assert decision == "CONTINUE"
        assert isinstance(decision.value, str)


class TestCollectionResult:
    """Tests for CollectionResult dataclass."""

    def test_collection_result_has_required_fields(self):
        """Test CollectionResult has artifacts and complete fields."""
        from flock.components.orchestrator import CollectionResult
        from flock.core.artifacts import Artifact

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
        from flock.components.orchestrator import CollectionResult
        from flock.core.artifacts import Artifact

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
        from flock.components.orchestrator import CollectionResult

        result = CollectionResult.waiting()

        assert result.complete is False
        assert result.artifacts == []


class TestOrchestratorComponent:
    """Tests for OrchestratorComponent base class."""

    def test_orchestrator_component_has_required_fields(self):
        """Test OrchestratorComponent has name, config, priority fields."""
        from flock.components.orchestrator import OrchestratorComponent

        component = OrchestratorComponent()

        assert hasattr(component, "name")
        assert hasattr(component, "config")
        assert hasattr(component, "priority")
        assert component.priority == 0  # Default priority

    def test_orchestrator_component_custom_priority(self):
        """Test OrchestratorComponent accepts custom priority."""
        from flock.components.orchestrator import OrchestratorComponent

        component = OrchestratorComponent(priority=10)

        assert component.priority == 10

    def test_orchestrator_component_custom_name(self):
        """Test OrchestratorComponent accepts custom name."""
        from flock.components.orchestrator import OrchestratorComponent

        component = OrchestratorComponent(name="test_component")

        assert component.name == "test_component"

    def test_orchestrator_component_has_all_lifecycle_hooks(self):
        """Test OrchestratorComponent has all 8 lifecycle hooks."""
        from flock.components.orchestrator import OrchestratorComponent

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

        from flock.components.orchestrator import (
            OrchestratorComponent,
            ScheduleDecision,
        )
        from flock.core.artifacts import Artifact

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

        result = await component.on_before_agent_schedule(
            mock_orch, mock_agent, [artifact]
        )
        assert result == [artifact]  # Returns artifacts unchanged

        result = await component.on_agent_scheduled(
            mock_orch, mock_agent, [artifact], mock_task
        )
        assert result is None

        result = await component.on_orchestrator_idle(mock_orch)
        assert result is None

        result = await component.on_shutdown(mock_orch)
        assert result is None

    def test_orchestrator_component_uses_traced_meta(self):
        """Test OrchestratorComponent uses TracedModelMeta for auto-tracing."""
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

        component = OrchestratorComponent(name="test_comp", priority=5)
        orchestrator.add_component(component)

        assert component in orchestrator._components
        # orchestrator has 3 built-ins + 1 added = 4 total
        assert len(orchestrator._components) == 4

    def test_flock_add_component_returns_self(self, orchestrator):
        """Test add_component() returns self for method chaining."""
        from flock.components.orchestrator import OrchestratorComponent

        component = OrchestratorComponent(name="test_comp")
        result = orchestrator.add_component(component)

        assert result is orchestrator

    def test_flock_add_component_method_chaining(self, orchestrator):
        """Test add_component() supports method chaining."""
        from flock.components.orchestrator import OrchestratorComponent

        c1 = OrchestratorComponent(name="c1")
        c2 = OrchestratorComponent(name="c2")

        # Should be able to chain
        result = orchestrator.add_component(c1).add_component(c2)

        assert result is orchestrator
        # Note: orchestrator has 3 built-ins + 2 added = 5 total
        assert len(orchestrator._components) == 5

    def test_flock_add_component_sorts_by_priority(self, orchestrator):
        """Test components are sorted by priority after add."""
        from flock.components.orchestrator import OrchestratorComponent

        c1 = OrchestratorComponent(
            priority=10, name="c1_user"
        )  # Same as circuit_breaker
        c2 = OrchestratorComponent(priority=5, name="c2")
        c3 = OrchestratorComponent(priority=20, name="c3")  # Same as dedup

        orchestrator.add_component(c1)
        orchestrator.add_component(c2)
        orchestrator.add_component(c3)

        # Should be sorted: [c2(5), circuit_breaker(10), c1_user(10), dedup(20), c3(20), builtin(100)]
        assert orchestrator._components[0].name == "c2"
        assert orchestrator._components[1].name == "circuit_breaker"
        assert orchestrator._components[2].name == "c1_user"
        assert orchestrator._components[3].name == "deduplication"
        assert orchestrator._components[4].name == "c3"
        assert orchestrator._components[5].name == "builtin_collection"

    def test_flock_add_component_maintains_sort_order(self, orchestrator):
        """Test adding components maintains priority sort order."""
        from flock.components.orchestrator import OrchestratorComponent

        # Add in random order
        orchestrator.add_component(OrchestratorComponent(priority=50, name="c50"))
        orchestrator.add_component(
            OrchestratorComponent(priority=10, name="c10_user")
        )  # Will conflict with circuit_breaker at 10
        orchestrator.add_component(OrchestratorComponent(priority=30, name="c30"))
        orchestrator.add_component(
            OrchestratorComponent(priority=20, name="c20")
        )  # Same as dedup

        # Should be sorted: [circuit_breaker(10), c10_user(10), dedup(20), c20(20), c30, c50, builtin(100)]
        priorities = [c.priority for c in orchestrator._components]
        assert priorities == [10, 10, 20, 20, 30, 50, 100]

    def test_flock_add_component_allows_duplicate_priorities(self, orchestrator):
        """Test multiple components can have same priority."""
        from flock.components.orchestrator import OrchestratorComponent

        c1 = OrchestratorComponent(priority=15, name="c1")
        c2 = OrchestratorComponent(priority=15, name="c2")

        orchestrator.add_component(c1)
        orchestrator.add_component(c2)

        # Should have: circuit(10) + dedup(20) + builtin(100) + c1(15) + c2(15) = 5 total
        assert len(orchestrator._components) == 5
        # Two components with priority 15
        priority_15_count = sum(1 for c in orchestrator._components if c.priority == 15)
        assert priority_15_count == 2


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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

        class FailingComponent(OrchestratorComponent):
            async def on_initialize(self, orch):
                raise ValueError("Initialization failed")

        orchestrator.add_component(FailingComponent())

        with pytest.raises(ValueError, match="Initialization failed"):
            await orchestrator._run_initialize()


class TestHookRunnerArtifactPublished:
    """Tests for _run_artifact_published() hook runner."""

    @pytest.mark.asyncio
    async def test_run_artifact_published_chains_components(
        self, orchestrator, sample_artifact
    ):
        """Test _run_artifact_published() chains components in priority order."""
        from flock.components.orchestrator import OrchestratorComponent

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
    async def test_run_artifact_published_stops_on_none(
        self, orchestrator, sample_artifact
    ):
        """Test _run_artifact_published() stops if component returns None."""
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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

        from flock.components.orchestrator import ScheduleDecision

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )

        assert result == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_run_before_schedule_stops_on_skip(
        self, orchestrator, sample_artifact
    ):
        """Test _run_before_schedule() stops on SKIP decision."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            OrchestratorComponent,
            ScheduleDecision,
        )

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

        result = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )

        assert result == ScheduleDecision.SKIP
        assert call_order == ["skip"]  # After component not called

    @pytest.mark.asyncio
    async def test_run_before_schedule_stops_on_defer(
        self, orchestrator, sample_artifact
    ):
        """Test _run_before_schedule() stops on DEFER decision."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            OrchestratorComponent,
            ScheduleDecision,
        )

        class DeferComponent(OrchestratorComponent):
            async def on_before_schedule(self, orch, artifact, agent, sub):
                return ScheduleDecision.DEFER

        orchestrator.add_component(DeferComponent())

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        result = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )

        assert result == ScheduleDecision.DEFER


class TestHookRunnerCollectArtifacts:
    """Tests for _run_collect_artifacts() hook runner."""

    @pytest.mark.asyncio
    async def test_run_collect_artifacts_returns_first_non_none(
        self, orchestrator, sample_artifact
    ):
        """Test _run_collect_artifacts() returns first non-None result."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            CollectionResult,
            OrchestratorComponent,
        )

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

        result = await orchestrator._run_collect_artifacts(
            sample_artifact, agent, subscription
        )

        assert result.complete is True
        assert call_order == ["c1", "c2"]  # c3 not called (short-circuit)

    @pytest.mark.asyncio
    async def test_run_collect_artifacts_default_immediate(
        self, orchestrator, sample_artifact
    ):
        """Test _run_collect_artifacts() uses builtin component for default collection."""
        from unittest.mock import Mock

        from flock.components.orchestrator import OrchestratorComponent

        class PassthroughComponent(OrchestratorComponent):
            priority: int = 1  # Run before builtin (100)

            async def on_collect_artifacts(self, orch, artifact, agent, sub):
                return None  # Let builtin handle

        orchestrator.add_component(PassthroughComponent())

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()
        # Mock all attributes that builtin component and artifact collector need
        subscription.join = None
        subscription.type_models = ["TestType"]  # Single type
        subscription.batch = None
        subscription.type_names = ["TestType"]
        subscription.type_counts = {"TestType": 1}

        result = await orchestrator._run_collect_artifacts(
            sample_artifact, agent, subscription
        )

        # Default behavior: builtin component returns immediate with single artifact
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

        from flock.components.orchestrator import OrchestratorComponent

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
    async def test_run_before_agent_schedule_stops_on_none(
        self, orchestrator, sample_artifact
    ):
        """Test _run_before_agent_schedule() stops if component returns None."""
        from unittest.mock import Mock

        from flock.components.orchestrator import OrchestratorComponent

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
    async def test_run_agent_scheduled_calls_all_components(
        self, orchestrator, sample_artifact
    ):
        """Test _run_agent_scheduled() calls all components (notification)."""
        import asyncio
        from unittest.mock import Mock

        from flock.components.orchestrator import OrchestratorComponent

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
    async def test_run_agent_scheduled_continues_on_exception(
        self, orchestrator, sample_artifact
    ):
        """Test _run_agent_scheduled() continues even if component raises."""
        import asyncio
        from unittest.mock import Mock

        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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
        from flock.components.orchestrator import OrchestratorComponent

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


# ──────────────────────────────────────────────────────────────────
# Phase 5: CircuitBreakerComponent Tests
# ──────────────────────────────────────────────────────────────────


class TestCircuitBreakerComponent:
    """Tests for CircuitBreakerComponent (Phase 5)."""

    def test_circuit_breaker_component_exists(self):
        """Test CircuitBreakerComponent can be imported."""
        from flock.components.orchestrator import CircuitBreakerComponent

        component = CircuitBreakerComponent(max_iterations=100)
        assert component.max_iterations == 100
        assert component.priority == 10
        assert component.name == "circuit_breaker"

    def test_circuit_breaker_default_max_iterations(self):
        """Test default max_iterations is 1000."""
        from flock.components.orchestrator import CircuitBreakerComponent

        component = CircuitBreakerComponent()
        assert component.max_iterations == 1000

    @pytest.mark.asyncio
    async def test_circuit_breaker_allows_under_limit(self, sample_artifact):
        """Test circuit breaker allows scheduling under limit."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            CircuitBreakerComponent,
            ScheduleDecision,
        )

        component = CircuitBreakerComponent(max_iterations=3)

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()
        orchestrator = Mock()

        # First 3 calls should be CONTINUE
        result1 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        result2 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result2 == ScheduleDecision.CONTINUE

        result3 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result3 == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_at_limit(self, sample_artifact):
        """Test circuit breaker blocks scheduling at limit."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            CircuitBreakerComponent,
            ScheduleDecision,
        )

        component = CircuitBreakerComponent(max_iterations=2)

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()
        orchestrator = Mock()

        # First 2 calls should be CONTINUE
        await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )

        # Third call should be SKIP (limit reached)
        result = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result == ScheduleDecision.SKIP

    @pytest.mark.asyncio
    async def test_circuit_breaker_per_agent_tracking(self, sample_artifact):
        """Test circuit breaker tracks iterations per agent."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            CircuitBreakerComponent,
            ScheduleDecision,
        )

        component = CircuitBreakerComponent(max_iterations=2)

        agent1 = Mock()
        agent1.name = "agent1"
        agent2 = Mock()
        agent2.name = "agent2"
        subscription = Mock()
        orchestrator = Mock()

        # Agent1: 2 iterations
        await component.on_before_schedule(
            orchestrator, sample_artifact, agent1, subscription
        )
        await component.on_before_schedule(
            orchestrator, sample_artifact, agent1, subscription
        )

        # Agent1: 3rd iteration should be blocked
        result = await component.on_before_schedule(
            orchestrator, sample_artifact, agent1, subscription
        )
        assert result == ScheduleDecision.SKIP

        # Agent2: should still be allowed (separate counter)
        result = await component.on_before_schedule(
            orchestrator, sample_artifact, agent2, subscription
        )
        assert result == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_idle(self, sample_artifact):
        """Test circuit breaker resets counters on idle."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            CircuitBreakerComponent,
            ScheduleDecision,
        )

        component = CircuitBreakerComponent(max_iterations=1)

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()
        orchestrator = Mock()

        # First call: CONTINUE
        result1 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        # Second call: SKIP (limit reached)
        result2 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result2 == ScheduleDecision.SKIP

        # Call on_orchestrator_idle (reset)
        await component.on_orchestrator_idle(orchestrator)

        # Third call: should be CONTINUE again (counter reset)
        result3 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result3 == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_circuit_breaker_auto_added_to_orchestrator(self, orchestrator):
        """Test CircuitBreakerComponent is auto-added to orchestrator."""
        from flock.components.orchestrator import CircuitBreakerComponent

        # Check if circuit breaker component is in components list
        circuit_breaker = next(
            (
                c
                for c in orchestrator._components
                if isinstance(c, CircuitBreakerComponent)
            ),
            None,
        )

        assert circuit_breaker is not None
        assert circuit_breaker.max_iterations == 1000  # Default
        assert circuit_breaker.priority == 10

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, orchestrator, sample_artifact):
        """Test circuit breaker integration with orchestrator."""
        from unittest.mock import Mock

        from flock.components.orchestrator import ScheduleDecision

        # Set max_iterations to 2 for testing (on both component AND orchestrator)
        orchestrator.max_agent_iterations = (
            2  # Component checks orchestrator property first
        )
        for component in orchestrator._components:
            if component.name == "circuit_breaker":
                component.max_iterations = 2

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        # First 2 calls should return CONTINUE
        result1 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        result2 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result2 == ScheduleDecision.CONTINUE

        # Third call should return SKIP (circuit breaker engaged)
        result3 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result3 == ScheduleDecision.SKIP


# ──────────────────────────────────────────────────────────────────
# Phase 6: DeduplicationComponent Tests
# ──────────────────────────────────────────────────────────────────


class TestDeduplicationComponent:
    """Tests for DeduplicationComponent (Phase 6)."""

    def test_deduplication_component_exists(self):
        """Test DeduplicationComponent can be imported."""
        from flock.components.orchestrator import DeduplicationComponent

        component = DeduplicationComponent()
        assert component.priority == 20
        assert component.name == "deduplication"

    @pytest.mark.asyncio
    async def test_deduplication_allows_first_occurrence(self, sample_artifact):
        """Test deduplication allows first occurrence of artifact for agent."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            DeduplicationComponent,
            ScheduleDecision,
        )

        component = DeduplicationComponent()

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()
        orchestrator = Mock()

        # First occurrence should be CONTINUE
        result = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_deduplication_blocks_duplicate(self, sample_artifact):
        """Test deduplication blocks duplicate artifact for same agent."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            DeduplicationComponent,
            ScheduleDecision,
        )

        component = DeduplicationComponent()

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()
        orchestrator = Mock()

        # First occurrence: CONTINUE
        result1 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        # Mark as processed (simulating on_before_agent_schedule)
        await component.on_before_agent_schedule(orchestrator, agent, [sample_artifact])

        # Second occurrence: SKIP (duplicate)
        result2 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent, subscription
        )
        assert result2 == ScheduleDecision.SKIP

    @pytest.mark.asyncio
    async def test_deduplication_per_agent(self, sample_artifact):
        """Test deduplication is per-agent (different agents can process same artifact)."""
        from unittest.mock import Mock

        from flock.components.orchestrator import (
            DeduplicationComponent,
            ScheduleDecision,
        )

        component = DeduplicationComponent()

        agent1 = Mock()
        agent1.name = "agent1"
        agent2 = Mock()
        agent2.name = "agent2"
        subscription = Mock()
        orchestrator = Mock()

        # Agent1 processes artifact
        result1 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent1, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        await component.on_before_agent_schedule(
            orchestrator, agent1, [sample_artifact]
        )

        # Agent1 tries again: SKIP (duplicate)
        result2 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent1, subscription
        )
        assert result2 == ScheduleDecision.SKIP

        # Agent2 should still be allowed (different agent)
        result3 = await component.on_before_schedule(
            orchestrator, sample_artifact, agent2, subscription
        )
        assert result3 == ScheduleDecision.CONTINUE

    @pytest.mark.asyncio
    async def test_deduplication_handles_multiple_artifacts(self, sample_artifact):
        """Test deduplication handles multiple artifacts in before_agent_schedule."""
        from unittest.mock import Mock

        from flock.components.orchestrator import DeduplicationComponent
        from flock.core.artifacts import Artifact

        component = DeduplicationComponent()

        agent = Mock()
        agent.name = "test_agent"
        orchestrator = Mock()

        # Create multiple artifacts
        artifact2 = Artifact(
            type="TestType", payload={"data": "test2"}, produced_by="test"
        )
        artifact3 = Artifact(
            type="TestType", payload={"data": "test3"}, produced_by="test"
        )

        # Mark all as processed
        result = await component.on_before_agent_schedule(
            orchestrator, agent, [sample_artifact, artifact2, artifact3]
        )

        # Should return the same list
        assert result == [sample_artifact, artifact2, artifact3]

        # All should be marked as processed
        assert (str(sample_artifact.id), agent.name) in component._processed
        assert (str(artifact2.id), agent.name) in component._processed
        assert (str(artifact3.id), agent.name) in component._processed

    @pytest.mark.asyncio
    async def test_deduplication_auto_added_to_orchestrator(self, orchestrator):
        """Test DeduplicationComponent is auto-added to orchestrator."""
        from flock.components.orchestrator import DeduplicationComponent

        # Check if deduplication component is in components list
        dedup = next(
            (
                c
                for c in orchestrator._components
                if isinstance(c, DeduplicationComponent)
            ),
            None,
        )

        assert dedup is not None
        assert dedup.priority == 20

    @pytest.mark.asyncio
    async def test_deduplication_integration(self, orchestrator, sample_artifact):
        """Test deduplication integration with orchestrator."""
        from unittest.mock import Mock

        from flock.components.orchestrator import ScheduleDecision

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        # First call should return CONTINUE
        result1 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        # Simulate marking as processed
        await orchestrator._run_before_agent_schedule(agent, [sample_artifact])

        # Second call should return SKIP (deduplication engaged)
        result2 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result2 == ScheduleDecision.SKIP

    @pytest.mark.asyncio
    async def test_deduplication_and_circuit_breaker_order(
        self, orchestrator, sample_artifact
    ):
        """Test circuit breaker runs before deduplication (priority order)."""
        from unittest.mock import Mock

        from flock.components.orchestrator import ScheduleDecision

        # Set circuit breaker to 1 iteration
        for component in orchestrator._components:
            if component.name == "circuit_breaker":
                component.max_iterations = 1

        agent = Mock()
        agent.name = "test_agent"
        subscription = Mock()

        # First call: circuit breaker allows, deduplication allows
        result1 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result1 == ScheduleDecision.CONTINUE

        # Mark as processed
        await orchestrator._run_before_agent_schedule(agent, [sample_artifact])

        # Second call: circuit breaker should block (runs at priority 10, before dedup at 20)
        result2 = await orchestrator._run_before_schedule(
            sample_artifact, agent, subscription
        )
        assert result2 == ScheduleDecision.SKIP
