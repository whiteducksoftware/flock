"""Additional tests for graph_builder.py to improve coverage."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from flock.api.graph_builder import GraphAssembler
from flock.core.subscription import ScheduleSpec
from datetime import timedelta


class TestGraphBuilderCoverage:
    """Tests to improve code coverage for graph_builder.py."""

    @pytest.mark.asyncio
    async def test_build_snapshot_with_statistics(self, orchestrator):
        """Test build_snapshot with include_statistics option (lines 88-96)."""
        from flock.api.collector import DashboardEventCollector
        from flock.components.server.models.graph import GraphRequest, GraphRequestOptions
        
        orchestrator.store.summarize_artifacts = AsyncMock(return_value={})
        
        collector = DashboardEventCollector(store=orchestrator.store)
        await collector.load_persistent_snapshots()
        assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
        
        # Create request with statistics enabled
        request = GraphRequest(
            view_mode="agent",
            options=GraphRequestOptions(include_statistics=True)
        )
        
        result = await assembler.build_snapshot(request)
        
        # Verify statistics were included
        assert result.statistics is not None
        orchestrator.store.summarize_artifacts.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_snapshot_without_statistics(self, orchestrator):
        """Test build_snapshot without statistics (lines 88-96)."""
        from flock.api.collector import DashboardEventCollector
        from flock.components.server.models.graph import GraphRequest, GraphRequestOptions
        
        collector = DashboardEventCollector(store=orchestrator.store)
        await collector.load_persistent_snapshots()
        assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
        
        request = GraphRequest(
            view_mode="agent",
            options=GraphRequestOptions(include_statistics=False)
        )
        
        result = await assembler.build_snapshot(request)
        
        # Verify statistics were not included
        assert result.statistics is None

    @pytest.mark.asyncio
    async def test_build_snapshot_with_scheduled_agent_no_timer_component(self, orchestrator):
        """Test build_snapshot with scheduled agent but no TimerComponent (lines 214-237)."""
        from flock.api.collector import DashboardEventCollector
        from flock.components.server.models.graph import GraphRequest
        from pydantic import BaseModel
        
        class TestOutput(BaseModel):
            value: str
        
        # Create agent with schedule_spec
        scheduled_agent = (
            orchestrator.agent("scheduled_agent")
            .publishes(TestOutput)
            .schedule(every=timedelta(seconds=30))
        )
        
        # Remove TimerComponent to test the no-timer-component path
        orchestrator._components = [c for c in orchestrator._components if c.name != "timer"]
        
        collector = DashboardEventCollector(store=orchestrator.store)
        await collector.load_persistent_snapshots()
        assembler = GraphAssembler(orchestrator.store, collector, orchestrator)
        
        request = GraphRequest(view_mode="agent")
        result = await assembler.build_snapshot(request)
        
        # Should still build graph successfully
        assert result is not None
        scheduled_node = next((n for n in result.nodes if n.id == "scheduled_agent"), None)
        assert scheduled_node is not None
        # Should have scheduleSpec but no timerState
        assert "scheduleSpec" in scheduled_node.data
        assert "timerState" not in scheduled_node.data

