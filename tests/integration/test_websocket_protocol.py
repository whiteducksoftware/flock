"""End-to-end integration tests for WebSocket protocol.

Tests verify full event flow from DashboardEventCollector → WebSocketManager → WebSocket client.
Tests all 5 event types, JSON serialization, correlation_id propagation, and event ordering.
"""

import asyncio
import json
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from flock.core.artifacts import Artifact
from flock.core.store import InMemoryBlackboardStore
from flock.core.visibility import PublicVisibility
from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.events import (
    AgentActivatedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
)
from flock.utils.runtime import Context


@pytest.fixture
def collector():
    """Create DashboardEventCollector instance."""
    return DashboardEventCollector(store=InMemoryBlackboardStore())


@pytest.fixture
def websocket_manager():
    """Create WebSocketManager instance."""
    try:
        from flock.dashboard.websocket_manager import WebSocketManager

        return WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet (TDD approach)")


@pytest.fixture
def mock_websocket_client():
    """Create mock WebSocket client that captures received messages."""

    class MockWebSocketClient:
        def __init__(self):
            self.received_messages: list[str] = []
            self.is_connected = True

        async def send(self, message: str):
            if not self.is_connected:
                raise ConnectionError("WebSocket disconnected")
            self.received_messages.append(message)

        async def receive(self):
            # Mock receive for testing
            await asyncio.sleep(0.01)
            if self.received_messages:
                return self.received_messages[-1]
            return None

        def get_events(self) -> list[dict[str, Any]]:
            """Parse received messages as JSON events."""
            return [json.loads(msg) for msg in self.received_messages]

    return MockWebSocketClient()


@pytest.mark.asyncio
async def test_full_event_flow_agent_activated(
    orchestrator, collector, websocket_manager, mock_websocket_client
):
    """Test full event flow: DashboardEventCollector → WebSocketManager → WebSocket client."""
    # Connect WebSocket client to manager
    await websocket_manager.add_client(mock_websocket_client)

    # Create test agent and context
    agent = orchestrator.agent("test_agent")._agent
    correlation_id = uuid4()
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=correlation_id,
    )

    # Create input artifact
    artifact = Artifact(
        id=uuid4(),
        type="TestInput",
        payload={"content": "test"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )

    # Trigger event emission via collector
    await collector.on_pre_consume(agent, ctx, [artifact])

    # Get emitted event
    assert len(collector.events) == 1
    event = collector.events[0]

    # Broadcast event through WebSocket manager
    await websocket_manager.broadcast(event)

    # Verify client received the event
    assert len(mock_websocket_client.received_messages) == 1

    # Parse and verify event structure
    received_events = mock_websocket_client.get_events()
    assert len(received_events) == 1

    received_event = received_events[0]
    assert received_event["agent_name"] == "test_agent"
    assert received_event["consumed_types"] == ["TestInput"]
    assert received_event["correlation_id"] == str(correlation_id)
    assert "timestamp" in received_event


@pytest.mark.asyncio
async def test_all_five_event_types_serialization(
    orchestrator, collector, websocket_manager, mock_websocket_client
):
    """Test all 5 event types are properly serialized and transmitted."""
    # Connect client
    await websocket_manager.add_client(mock_websocket_client)

    # Create test context
    correlation_id = uuid4()
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={"metrics": {"tokens": 100}},
        correlation_id=correlation_id,
    )

    agent = orchestrator.agent("test_agent")._agent

    # 1. AgentActivatedEvent
    artifact = Artifact(
        id=uuid4(),
        type="Input",
        payload={"data": "test"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await collector.on_pre_consume(agent, ctx, [artifact])

    # 2. MessagePublishedEvent
    output_artifact = Artifact(
        id=uuid4(),
        type="Output",
        payload={"result": "success"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await collector.on_post_publish(agent, ctx, output_artifact)

    # 3. StreamingOutputEvent (manually create as it's optional in Phase 1)
    streaming_event = StreamingOutputEvent(
        agent_name="test_agent",
        run_id=ctx.task_id,
        output_type="llm_token",
        content="Generated text...",
        sequence=1,
        correlation_id=str(correlation_id),
    )
    collector.events.append(streaming_event)

    # 4. AgentCompletedEvent
    await collector.on_terminate(agent, ctx)

    # 5. AgentErrorEvent (create manually to avoid actual error)
    error_event = AgentErrorEvent(
        agent_name="test_agent",
        run_id=ctx.task_id,
        error_type="ValueError",
        error_message="Test error",
        traceback="Traceback...",
        failed_at=datetime.utcnow().isoformat() + "Z",
        correlation_id=str(correlation_id),
    )
    collector.events.append(error_event)

    # Broadcast all events
    for event in collector.events:
        await websocket_manager.broadcast(event)

    # Verify all 5 event types were received
    received_events = mock_websocket_client.get_events()
    assert len(received_events) == 5

    # Verify event types

    # Check each event has expected structure
    # Note: Actual event type field depends on serialization implementation
    # May need to check specific fields instead of type field

    # AgentActivatedEvent
    assert "agent_name" in received_events[0]
    assert "consumed_types" in received_events[0]

    # MessagePublishedEvent
    assert "artifact_id" in received_events[1]
    assert "artifact_type" in received_events[1]

    # StreamingOutputEvent
    assert "output_type" in received_events[2]
    assert "content" in received_events[2]

    # AgentCompletedEvent
    assert "duration_ms" in received_events[3]
    assert received_events[3]["agent_name"] == "test_agent"

    # AgentErrorEvent
    assert "error_type" in received_events[4]
    assert received_events[4]["error_message"] == "Test error"


@pytest.mark.asyncio
async def test_correlation_id_propagation_through_websocket(
    orchestrator, collector, websocket_manager, mock_websocket_client
):
    """Test that correlation_id is propagated through entire WebSocket flow."""
    # Connect client
    await websocket_manager.add_client(mock_websocket_client)

    # Create context with specific correlation_id
    correlation_id = uuid4()
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=correlation_id,
    )

    agent = orchestrator.agent("test_agent")._agent

    # Emit multiple events with same correlation_id
    artifact = Artifact(
        id=uuid4(),
        type="Input",
        payload={"data": "test"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await collector.on_pre_consume(agent, ctx, [artifact])

    output = Artifact(
        id=uuid4(),
        type="Output",
        payload={"result": "test"},
        produced_by="test_agent",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await collector.on_post_publish(agent, ctx, output)

    await collector.on_terminate(agent, ctx)

    # Broadcast all events
    for event in collector.events:
        await websocket_manager.broadcast(event)

    # Verify all received events have the same correlation_id
    received_events = mock_websocket_client.get_events()
    assert len(received_events) == 3

    for event in received_events:
        assert event["correlation_id"] == str(correlation_id)


@pytest.mark.asyncio
async def test_multiple_clients_receive_same_events(
    websocket_manager, collector, orchestrator
):
    """Test that multiple clients receive the same events."""
    # Create multiple mock clients
    client1 = Mock()
    client1.send = AsyncMock()
    client2 = Mock()
    client2.send = AsyncMock()
    client3 = Mock()
    client3.send = AsyncMock()

    # Connect all clients
    await websocket_manager.add_client(client1)
    await websocket_manager.add_client(client2)
    await websocket_manager.add_client(client3)

    # Create and emit event
    correlation_id = uuid4()
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=correlation_id,
    )

    agent = orchestrator.agent("test_agent")._agent
    artifact = Artifact(
        id=uuid4(),
        type="Input",
        payload={"data": "test"},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )

    await collector.on_pre_consume(agent, ctx, [artifact])

    # Broadcast event
    event = collector.events[0]
    await websocket_manager.broadcast(event)

    # Verify all clients received the same event
    client1.send.assert_called_once()
    client2.send.assert_called_once()
    client3.send.assert_called_once()

    # Verify message content is identical
    msg1 = client1.send.call_args[0][0]
    msg2 = client2.send.call_args[0][0]
    msg3 = client3.send.call_args[0][0]

    assert msg1 == msg2 == msg3

    # Parse and verify content
    event_data = json.loads(msg1)
    assert event_data["agent_name"] == "test_agent"
    assert event_data["correlation_id"] == str(correlation_id)


@pytest.mark.asyncio
async def test_event_ordering_preservation(
    orchestrator, collector, websocket_manager, mock_websocket_client
):
    """Test that event ordering is preserved through WebSocket transmission."""
    # Connect client
    await websocket_manager.add_client(mock_websocket_client)

    # Create context
    correlation_id = uuid4()
    ctx = Context(
        board=orchestrator.store,
        orchestrator=orchestrator,
        task_id=f"task-{uuid4()}",
        state={},
        correlation_id=correlation_id,
    )

    # Emit events in specific order
    events_order = []

    # 1. Agent activated
    agent = orchestrator.agent("test_agent")._agent
    artifact = Artifact(
        id=uuid4(),
        type="Input",
        payload={"sequence": 1},
        produced_by="external",
        visibility=PublicVisibility(),
        correlation_id=correlation_id,
    )
    await collector.on_pre_consume(agent, ctx, [artifact])
    events_order.append("activated")

    # 2. Multiple messages published
    for i in range(3):
        output = Artifact(
            id=uuid4(),
            type="Output",
            payload={"sequence": 2 + i, "index": i},
            produced_by="test_agent",
            visibility=PublicVisibility(),
            correlation_id=correlation_id,
        )
        await collector.on_post_publish(agent, ctx, output)
        events_order.append(f"message_{i}")

    # 3. Agent completed
    await collector.on_terminate(agent, ctx)
    events_order.append("completed")

    # Broadcast all events in order
    for event in collector.events:
        await websocket_manager.broadcast(event)

    # Verify order is preserved
    received_events = mock_websocket_client.get_events()
    assert len(received_events) == 5

    # Verify event order
    assert "consumed_types" in received_events[0]  # AgentActivatedEvent
    assert received_events[1]["payload"]["index"] == 0  # First message
    assert received_events[2]["payload"]["index"] == 1  # Second message
    assert received_events[3]["payload"]["index"] == 2  # Third message
    assert "duration_ms" in received_events[4]  # AgentCompletedEvent


@pytest.mark.asyncio
async def test_json_serialization_deserialization_roundtrip(
    collector, websocket_manager, mock_websocket_client
):
    """Test that events can be serialized to JSON and deserialized correctly."""
    # Connect client
    await websocket_manager.add_client(mock_websocket_client)

    # Create event with various data types
    from flock.dashboard.events import VisibilitySpec

    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="TestOutput",
        produced_by="test_agent",
        payload={
            "string": "test",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3],
            "nested": {"key": "value"},
        },
        visibility=VisibilitySpec(kind="Public"),
        tags=["test", "integration"],
        version=1,
        correlation_id=str(uuid4()),
    )

    # Broadcast event
    await websocket_manager.broadcast(event)

    # Verify serialization/deserialization
    received_events = mock_websocket_client.get_events()
    assert len(received_events) == 1

    received = received_events[0]

    # Verify all data types are preserved
    assert received["payload"]["string"] == "test"
    assert received["payload"]["number"] == 42
    assert received["payload"]["float"] == 3.14
    assert received["payload"]["boolean"] is True
    assert received["payload"]["null"] is None
    assert received["payload"]["array"] == [1, 2, 3]
    assert received["payload"]["nested"]["key"] == "value"
    assert "test" in received["tags"]
    assert received["version"] == 1


@pytest.mark.asyncio
async def test_websocket_latency_target(
    websocket_manager, mock_websocket_client, collector
):
    """Test that WebSocket latency is under 50ms target (performance baseline)."""
    import time

    # Connect client
    await websocket_manager.add_client(mock_websocket_client)

    # Create simple event
    from flock.dashboard.events import SubscriptionInfo

    event = AgentActivatedEvent(
        agent_name="test",
        agent_id="test",
        consumed_types=["Input"],
        consumed_artifacts=[str(uuid4())],
        subscription_info=SubscriptionInfo(),
        labels=[],
        correlation_id=str(uuid4()),
    )

    # Measure broadcast time
    start_time = time.perf_counter()
    await websocket_manager.broadcast(event)
    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    # Verify latency is under 50ms (generous threshold for unit test)
    # In real deployment with network I/O, this will be validated differently
    assert latency_ms < 50, (
        f"WebSocket broadcast took {latency_ms:.2f}ms (target: <50ms)"
    )

    # Note: This test measures in-memory broadcast only
    # Actual network latency will be tested in integration/E2E tests
