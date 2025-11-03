"""Enhanced unit tests for WebSocketManager with improved coverage.

This file adds additional tests to increase coverage of WebSocketManager,
focusing on edge cases, error handling, and singleton behavior.
"""

import asyncio
import json
from uuid import uuid4

import pytest

from flock.api.websocket import WebSocketManager
from flock.components.server.models.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
    SubscriptionInfo,
    VisibilitySpec,
)


# Mock WebSocket class for testing
class MockWebSocket:
    """Mock WebSocket connection for testing."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.messages_sent: list[str] = []
        self.is_closed = False
        self._send_exception: Exception | None = None
        self.ping_messages: list[dict] = []

    async def send(self, message: str) -> None:
        """Mock send method."""
        if self.is_closed:
            raise ConnectionError("WebSocket is closed")
        if self._send_exception:
            raise self._send_exception
        self.messages_sent.append(message)

    async def send_text(self, message: str) -> None:
        """Mock send_text method (FastAPI WebSocket uses send_text for JSON)."""
        await self.send(message)

    async def send_json(self, data: dict) -> None:
        """Mock send_json method."""
        self.ping_messages.append(data)

    async def close(self) -> None:
        """Mock close method."""
        self.is_closed = True

    def simulate_disconnect(self) -> None:
        """Simulate a disconnection that causes send to fail."""
        self._send_exception = ConnectionError("Connection lost")


@pytest.fixture
async def websocket_manager():
    """Create isolated WebSocketManager instance for each test."""
    # Reset singleton before test
    await WebSocketManager.reset_singleton()
    manager = WebSocketManager()
    yield manager
    # Cleanup after test
    await manager.shutdown()
    await WebSocketManager.reset_singleton()


# ============================================================
# Singleton Pattern Tests
# ============================================================


@pytest.mark.asyncio
async def test_singleton_pattern_returns_same_instance():
    """Test that WebSocketManager implements singleton pattern correctly."""
    await WebSocketManager.reset_singleton()

    manager1 = WebSocketManager()
    manager2 = WebSocketManager()
    manager3 = WebSocketManager(heartbeat_interval=60)  # Different params ignored

    assert manager1 is manager2
    assert manager2 is manager3
    assert id(manager1) == id(manager2) == id(manager3)

    await manager1.shutdown()
    await WebSocketManager.reset_singleton()


@pytest.mark.asyncio
async def test_singleton_warns_on_different_parameters():
    """Test that singleton warns when instantiated with different parameters."""
    await WebSocketManager.reset_singleton()

    # First instantiation with specific params
    manager1 = WebSocketManager(heartbeat_interval=60, enable_heartbeat=True)
    assert manager1.heartbeat_interval == 60
    assert manager1.enable_heartbeat is True

    # Second instantiation with different params should be ignored and log warning
    manager2 = WebSocketManager(heartbeat_interval=120, enable_heartbeat=False)

    # Should still have original params
    assert manager2.heartbeat_interval == 60
    assert manager2.enable_heartbeat is True
    assert manager1 is manager2

    await manager1.shutdown()
    await WebSocketManager.reset_singleton()


@pytest.mark.asyncio
async def test_reset_singleton():
    """Test reset_singleton method."""
    await WebSocketManager.reset_singleton()

    manager1 = WebSocketManager()
    first_id = id(manager1)

    await WebSocketManager.reset_singleton()

    manager2 = WebSocketManager()
    second_id = id(manager2)

    assert first_id != second_id
    assert manager1 is not manager2

    await manager2.shutdown()
    await WebSocketManager.reset_singleton()


# ============================================================
# Broadcast Edge Cases
# ============================================================


@pytest.mark.asyncio
async def test_broadcast_timeout_handling(websocket_manager):
    """Test that broadcast handles slow clients with timeout."""

    class SlowWebSocket(MockWebSocket):
        """WebSocket that simulates slow send operation."""

        async def send_text(self, message: str):
            # Simulate slow send that exceeds 500ms timeout
            await asyncio.sleep(0.6)
            await super().send_text(message)

    slow_client = SlowWebSocket("slow-client")
    fast_client = MockWebSocket("fast-client")

    await websocket_manager.add_client(slow_client)
    await websocket_manager.add_client(fast_client)

    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="TestOutput",
        produced_by="test_agent",
        payload={"test": "data"},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    await websocket_manager.broadcast(event)

    # Fast client should receive message
    assert len(fast_client.messages_sent) == 1

    # Slow client should be removed due to timeout
    assert slow_client not in websocket_manager.clients
    assert fast_client in websocket_manager.clients


@pytest.mark.asyncio
async def test_broadcast_with_different_event_types(websocket_manager):
    """Test broadcasting different event types to ensure all are handled."""
    client = MockWebSocket("client-1")
    await websocket_manager.add_client(client)

    # Test AgentActivatedEvent
    event1 = AgentActivatedEvent(
        agent_name="test_agent",
        agent_id="test_agent",
        consumed_types=["Input"],
        produced_types=["Output"],
        consumed_artifacts=[str(uuid4())],
        subscription_info=SubscriptionInfo(),
        labels=["test"],
        tenant_id=None,
        max_concurrency=1,
        correlation_id=str(uuid4()),
        run_id=str(uuid4()),
    )
    await websocket_manager.broadcast(event1)

    # Test MessagePublishedEvent
    event2 = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="Output",
        produced_by="test_agent",
        payload={"result": "success"},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )
    await websocket_manager.broadcast(event2)

    # Test AgentCompletedEvent
    event3 = AgentCompletedEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        duration_ms=100.0,
        correlation_id=str(uuid4()),
    )
    await websocket_manager.broadcast(event3)

    # Test AgentErrorEvent
    event4 = AgentErrorEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        error_type="ValueError",
        error_message="Test error",
        traceback="Traceback...",
        failed_at="2025-10-31T00:00:00Z",
        correlation_id=str(uuid4()),
    )
    await websocket_manager.broadcast(event4)

    # Test StreamingOutputEvent
    event5 = StreamingOutputEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        output_type="stdout",
        content="output chunk",
        sequence=1,
        correlation_id=str(uuid4()),
    )
    await websocket_manager.broadcast(event5)

    # Verify all events were sent
    assert len(client.messages_sent) == 5

    # Verify each message is valid JSON
    for msg in client.messages_sent:
        data = json.loads(msg)
        assert "agent_name" in data or "artifact_type" in data


@pytest.mark.asyncio
async def test_streaming_history_thread_safety(websocket_manager):
    """Test that streaming history updates are thread-safe."""

    async def concurrent_broadcast(agent_name: str, count: int):
        for i in range(count):
            event = StreamingOutputEvent(
                agent_name=agent_name,
                run_id=str(uuid4()),
                output_type="stdout",
                content=f"chunk {i}",
                sequence=i,
                correlation_id=str(uuid4()),
            )
            await websocket_manager.broadcast(event)

    # Run concurrent broadcasts for same agent
    tasks = [
        asyncio.create_task(concurrent_broadcast("agent_a", 10)),
        asyncio.create_task(concurrent_broadcast("agent_a", 10)),
        asyncio.create_task(concurrent_broadcast("agent_b", 5)),
    ]

    await asyncio.gather(*tasks)

    # Verify history was maintained correctly
    history_a = await websocket_manager.get_streaming_history("agent_a")
    history_b = await websocket_manager.get_streaming_history("agent_b")

    assert len(history_a) == 20  # Two concurrent tasks * 10
    assert len(history_b) == 5


# ============================================================
# Shutdown and Cleanup Tests
# ============================================================


@pytest.mark.asyncio
async def test_shutdown_sets_shutdown_flag(websocket_manager):
    """Test that shutdown() sets the _shutdown flag."""
    assert websocket_manager._shutdown is False
    await websocket_manager.shutdown()
    assert websocket_manager._shutdown is True


@pytest.mark.asyncio
async def test_shutdown_clears_all_clients(websocket_manager):
    """Test that shutdown removes all clients."""
    # Add multiple clients
    for i in range(5):
        ws = MockWebSocket(f"client-{i}")
        await websocket_manager.add_client(ws)

    assert len(websocket_manager.clients) == 5

    await websocket_manager.shutdown()

    assert len(websocket_manager.clients) == 0


@pytest.mark.asyncio
async def test_shutdown_closes_client_connections(websocket_manager):
    """Test that shutdown closes all client WebSocket connections."""
    clients = []
    for i in range(3):
        ws = MockWebSocket(f"client-{i}")
        clients.append(ws)
        await websocket_manager.add_client(ws)

    await websocket_manager.shutdown()

    # Verify all clients were closed
    for client in clients:
        assert client.is_closed


@pytest.mark.asyncio
async def test_shutdown_idempotent(websocket_manager):
    """Test that calling shutdown multiple times is safe."""
    await websocket_manager.shutdown()
    # Should not raise error
    await websocket_manager.shutdown()
    await websocket_manager.shutdown()


# ============================================================
# Heartbeat Edge Cases
# ============================================================


@pytest.mark.asyncio
async def test_heartbeat_not_started_when_disabled():
    """Test that heartbeat task is not created when enable_heartbeat=False."""
    await WebSocketManager.reset_singleton()
    manager = WebSocketManager(enable_heartbeat=False)

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Verify heartbeat task was not created
    assert manager._heartbeat_task is None

    await manager.shutdown()
    await WebSocketManager.reset_singleton()


@pytest.mark.asyncio
async def test_heartbeat_respects_shutdown_flag():
    """Test that heartbeat loop respects _shutdown flag."""
    await WebSocketManager.reset_singleton()
    manager = WebSocketManager(enable_heartbeat=True, heartbeat_interval=0.1)

    # Add client to start heartbeat
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Verify heartbeat started
    assert manager._heartbeat_task is not None

    # Shutdown should stop heartbeat
    await manager.shutdown()

    # Verify heartbeat task was cancelled
    assert manager._heartbeat_task is None

    await WebSocketManager.reset_singleton()


@pytest.mark.asyncio
async def test_add_client_after_shutdown():
    """Test that add_client after shutdown doesn't start heartbeat."""
    await WebSocketManager.reset_singleton()
    manager = WebSocketManager(enable_heartbeat=True)

    await manager.shutdown()

    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Heartbeat should not start because _shutdown is True
    assert manager._heartbeat_task is None

    await WebSocketManager.reset_singleton()


# ============================================================
# Client Pool Management Edge Cases
# ============================================================


@pytest.mark.asyncio
async def test_remove_same_client_multiple_times(websocket_manager):
    """Test that removing same client multiple times is safe."""
    ws = MockWebSocket("client-1")
    await websocket_manager.add_client(ws)

    assert len(websocket_manager.clients) == 1

    await websocket_manager.remove_client(ws)
    assert len(websocket_manager.clients) == 0

    # Should not raise error
    await websocket_manager.remove_client(ws)
    assert len(websocket_manager.clients) == 0


@pytest.mark.asyncio
async def test_add_same_client_multiple_times(websocket_manager):
    """Test adding same client multiple times (set behavior)."""
    ws = MockWebSocket("client-1")

    await websocket_manager.add_client(ws)
    await websocket_manager.add_client(ws)
    await websocket_manager.add_client(ws)

    # Set should only contain one instance
    assert len(websocket_manager.clients) == 1


# ============================================================
# Error Handling Tests
# ============================================================


@pytest.mark.asyncio
async def test_broadcast_continues_after_client_error(websocket_manager):
    """Test that broadcast continues processing other clients after one fails."""

    class FailingWebSocket(MockWebSocket):
        """WebSocket that fails on first send."""

        def __init__(self, client_id: str):
            super().__init__(client_id)
            self.send_count = 0

        async def send_text(self, message: str):
            self.send_count += 1
            if self.send_count == 1:
                raise ValueError("First send fails")
            await super().send_text(message)

    failing_client = FailingWebSocket("failing")
    good_client = MockWebSocket("good")

    await websocket_manager.add_client(failing_client)
    await websocket_manager.add_client(good_client)

    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="Test",
        produced_by="test",
        payload={},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    # First broadcast should fail for failing_client
    await websocket_manager.broadcast(event)

    # Good client should receive message
    assert len(good_client.messages_sent) == 1

    # Failing client should be removed
    assert failing_client not in websocket_manager.clients


# ============================================================
# Streaming History Tests
# ============================================================


@pytest.mark.asyncio
async def test_streaming_history_maxlen_enforcement(websocket_manager):
    """Test that streaming history enforces maxlen correctly."""
    # The default maxlen is 128344
    agent_name = "test_agent"

    # Add events beyond maxlen to verify deque behavior
    # Use a smaller number for test performance
    num_events = 200

    for i in range(num_events):
        event = StreamingOutputEvent(
            agent_name=agent_name,
            run_id=str(uuid4()),
            output_type="stdout",
            content=f"chunk {i}",
            sequence=i,
            correlation_id=str(uuid4()),
        )
        await websocket_manager.broadcast(event)

    history = await websocket_manager.get_streaming_history(agent_name)

    # Should have all 200 (under maxlen of 128344)
    assert len(history) == num_events


@pytest.mark.asyncio
async def test_streaming_history_separate_per_agent(websocket_manager):
    """Test that streaming history is maintained separately per agent."""
    # Add events for multiple agents
    for agent_num in range(5):
        for event_num in range(3):
            event = StreamingOutputEvent(
                agent_name=f"agent_{agent_num}",
                run_id=str(uuid4()),
                output_type="stdout",
                content=f"chunk {event_num}",
                sequence=event_num,
                correlation_id=str(uuid4()),
            )
            await websocket_manager.broadcast(event)

    # Verify each agent has separate history
    for agent_num in range(5):
        history = await websocket_manager.get_streaming_history(f"agent_{agent_num}")
        assert len(history) == 3
        # Verify events belong to correct agent
        for event in history:
            assert event.agent_name == f"agent_{agent_num}"


@pytest.mark.asyncio
async def test_get_streaming_history_empty_for_new_agent(websocket_manager):
    """Test that get_streaming_history returns empty list for new agent."""
    history = await websocket_manager.get_streaming_history("nonexistent_agent")
    assert history == []
    assert isinstance(history, list)


# ============================================================
# _clear_pool() Internal Method Tests
# ============================================================


@pytest.mark.asyncio
async def test_clear_pool_removes_all_clients(websocket_manager):
    """Test _clear_pool() internal method removes all clients."""
    # Add clients
    for i in range(10):
        ws = MockWebSocket(f"client-{i}")
        await websocket_manager.add_client(ws)

    assert len(websocket_manager.clients) == 10

    # Call internal clear method
    await websocket_manager._clear_pool()

    assert len(websocket_manager.clients) == 0


# ============================================================
# JSON Serialization Tests
# ============================================================


@pytest.mark.asyncio
async def test_broadcast_handles_none_values(websocket_manager):
    """Test that broadcast handles None values in payload correctly."""
    client = MockWebSocket("client-1")
    await websocket_manager.add_client(client)

    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="TestOutput",
        produced_by="test_agent",
        payload={"value": None, "optional": None},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    await websocket_manager.broadcast(event)

    assert len(client.messages_sent) == 1
    data = json.loads(client.messages_sent[0])
    assert data["payload"]["value"] is None


@pytest.mark.asyncio
async def test_broadcast_handles_empty_payload(websocket_manager):
    """Test that broadcast handles empty payload correctly."""
    client = MockWebSocket("client-1")
    await websocket_manager.add_client(client)

    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="TestOutput",
        produced_by="test_agent",
        payload={},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    await websocket_manager.broadcast(event)

    assert len(client.messages_sent) == 1
    data = json.loads(client.messages_sent[0])
    assert data["payload"] == {}


# ============================================================
# Lock and Thread Safety Tests
# ============================================================


@pytest.mark.asyncio
async def test_concurrent_add_remove_clients(websocket_manager):
    """Test concurrent add/remove operations are thread-safe."""

    async def add_clients(count: int, prefix: str):
        for i in range(count):
            ws = MockWebSocket(f"{prefix}-{i}")
            await websocket_manager.add_client(ws)
            await asyncio.sleep(0.001)  # Small delay to increase concurrency

    async def remove_clients(clients: list[MockWebSocket]):
        for client in clients:
            await websocket_manager.remove_client(client)
            await asyncio.sleep(0.001)

    # Create clients for removal
    remove_clients_list = []
    for i in range(5):
        ws = MockWebSocket(f"remove-{i}")
        remove_clients_list.append(ws)
        await websocket_manager.add_client(ws)

    # Run concurrent operations
    tasks = [
        asyncio.create_task(add_clients(10, "add1")),
        asyncio.create_task(add_clients(10, "add2")),
        asyncio.create_task(remove_clients(remove_clients_list)),
    ]

    await asyncio.gather(*tasks)

    # Verify consistent state
    assert len(websocket_manager.clients) == 20  # 10 + 10, 5 removed


@pytest.mark.asyncio
async def test_concurrent_broadcasts_different_events(websocket_manager):
    """Test concurrent broadcasts with different event types."""
    client = MockWebSocket("client-1")
    await websocket_manager.add_client(client)

    async def broadcast_messages(count: int):
        for i in range(count):
            event = MessagePublishedEvent(
                artifact_id=str(uuid4()),
                artifact_type=f"Output{i}",
                produced_by="test_agent",
                payload={"index": i},
                visibility=VisibilitySpec(kind="Public"),
                correlation_id=str(uuid4()),
            )
            await websocket_manager.broadcast(event)

    async def broadcast_streaming(count: int):
        for i in range(count):
            event = StreamingOutputEvent(
                agent_name="test_agent",
                run_id=str(uuid4()),
                output_type="stdout",
                content=f"chunk {i}",
                sequence=i,
                correlation_id=str(uuid4()),
            )
            await websocket_manager.broadcast(event)

    # Run concurrent broadcasts
    await asyncio.gather(broadcast_messages(10), broadcast_streaming(10))

    # Client should receive all 20 messages
    assert len(client.messages_sent) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
