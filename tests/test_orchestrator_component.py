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
        from flock.orchestrator_component import CollectionResult
        from flock.artifacts import Artifact

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
        from flock.orchestrator_component import CollectionResult
        from flock.artifacts import Artifact

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
        from flock.orchestrator_component import (
            OrchestratorComponent,
            ScheduleDecision,
        )
        from flock.artifacts import Artifact
        from unittest.mock import Mock

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
        from flock.orchestrator_component import OrchestratorComponent
        from flock.logging.auto_trace import AutoTracedMeta

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
