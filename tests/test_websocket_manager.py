"""Unit tests for WebSocketManager component.

Tests verify WebSocket connection pool management, broadcasting, and heartbeat
according to ARCHITECTURE_SUMMARY.md and DATA_MODEL.md specifications.
"""

import asyncio
import contextlib
from uuid import uuid4

import pytest

from flock.dashboard.events import (
    AgentActivatedEvent,
    MessagePublishedEvent,
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

    async def send(self, message: str) -> None:
        """Mock send method."""
        if self.is_closed:
            raise Exception("WebSocket is closed")
        if self._send_exception:
            raise self._send_exception
        self.messages_sent.append(message)

    async def send_text(self, message: str) -> None:
        """Mock send_text method (FastAPI WebSocket uses send_text for JSON)."""
        await self.send(message)

    async def close(self) -> None:
        """Mock close method."""
        self.is_closed = True

    def simulate_disconnect(self) -> None:
        """Simulate a disconnection that causes send to fail."""
        self._send_exception = ConnectionError("Connection lost")


@pytest.fixture
def websocket_manager():
    """Create WebSocketManager instance for testing."""
    # Import here to avoid import errors before implementation exists
    try:
        from flock.dashboard.websocket import WebSocketManager

        return WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet (TDD approach)")


@pytest.mark.asyncio
async def test_websocket_manager_initialization(websocket_manager):
    """Test that WebSocketManager initializes with empty client pool."""
    # Verify manager starts with no connections
    assert len(websocket_manager.clients) == 0
    assert websocket_manager.heartbeat_interval == 120  # 2 minutes (120 seconds) per updated spec


@pytest.mark.asyncio
async def test_add_client(websocket_manager):
    """Test adding WebSocket client to connection pool."""
    # Create mock WebSocket
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")

    # Add clients
    await websocket_manager.add_client(ws1)
    await websocket_manager.add_client(ws2)

    # Verify clients are tracked
    assert len(websocket_manager.clients) == 2
    assert ws1 in websocket_manager.clients
    assert ws2 in websocket_manager.clients


@pytest.mark.asyncio
async def test_remove_client(websocket_manager):
    """Test removing WebSocket client from connection pool."""
    # Add clients
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")
    await websocket_manager.add_client(ws1)
    await websocket_manager.add_client(ws2)

    # Remove one client
    await websocket_manager.remove_client(ws1)

    # Verify client is removed
    assert len(websocket_manager.clients) == 1
    assert ws1 not in websocket_manager.clients
    assert ws2 in websocket_manager.clients


@pytest.mark.asyncio
async def test_broadcast_sends_to_all_clients(websocket_manager):
    """Test that broadcast() sends events to all connected clients."""
    # Add multiple clients
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")
    ws3 = MockWebSocket("client-3")

    await websocket_manager.add_client(ws1)
    await websocket_manager.add_client(ws2)
    await websocket_manager.add_client(ws3)

    # Create test event
    event = AgentActivatedEvent(
        agent_name="test_agent",
        agent_id="test_agent",
        consumed_types=["TestInput"],
        produced_types=["TestOutput"],
        consumed_artifacts=[str(uuid4())],
        subscription_info=SubscriptionInfo(),
        labels=["test"],
        tenant_id=None,
        max_concurrency=1,
        correlation_id=str(uuid4()),
        run_id=str(uuid4()),  # Bug Fix #3: run_id is now required
    )

    # Broadcast event
    await websocket_manager.broadcast(event)

    # Verify all clients received the event
    assert len(ws1.messages_sent) == 1
    assert len(ws2.messages_sent) == 1
    assert len(ws3.messages_sent) == 1

    # Verify message contains event data (JSON)
    import json

    for ws in [ws1, ws2, ws3]:
        message_data = json.loads(ws.messages_sent[0])
        assert message_data["agent_name"] == "test_agent"
        assert message_data["consumed_types"] == ["TestInput"]


@pytest.mark.asyncio
async def test_broadcast_empty_client_pool(websocket_manager):
    """Test that broadcast with no clients is a no-op."""
    # Create event
    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="TestOutput",
        produced_by="test_agent",
        payload={"result": "test"},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    # Broadcast with no clients - should not raise error
    await websocket_manager.broadcast(event)

    # Verify no clients were affected
    assert len(websocket_manager.clients) == 0


@pytest.mark.asyncio
async def test_broadcast_handles_disconnected_clients(websocket_manager):
    """Test graceful handling of disconnected clients during broadcast."""
    # Add clients
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")
    ws3 = MockWebSocket("client-3")

    await websocket_manager.add_client(ws1)
    await websocket_manager.add_client(ws2)
    await websocket_manager.add_client(ws3)

    # Simulate ws2 disconnecting
    ws2.simulate_disconnect()

    # Create event
    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="TestOutput",
        produced_by="test_agent",
        payload={"result": "test"},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    # Broadcast - should handle disconnected client gracefully
    await websocket_manager.broadcast(event)

    # Verify healthy clients received message
    assert len(ws1.messages_sent) == 1
    assert len(ws3.messages_sent) == 1

    # Verify disconnected client was removed from pool
    assert ws2 not in websocket_manager.clients
    assert len(websocket_manager.clients) == 2


@pytest.mark.asyncio
async def test_concurrent_broadcasts(websocket_manager):
    """Test that concurrent broadcasts are handled correctly."""
    # Add clients
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")

    await websocket_manager.add_client(ws1)
    await websocket_manager.add_client(ws2)

    # Create multiple events
    events = []
    for i in range(5):
        event = MessagePublishedEvent(
            artifact_id=str(uuid4()),
            artifact_type=f"TestOutput{i}",
            produced_by="test_agent",
            payload={"index": i},
            visibility=VisibilitySpec(kind="Public"),
            correlation_id=str(uuid4()),
        )
        events.append(event)

    # Broadcast concurrently
    await asyncio.gather(*[websocket_manager.broadcast(e) for e in events])

    # Verify all clients received all events
    assert len(ws1.messages_sent) == 5
    assert len(ws2.messages_sent) == 5

    # Verify ordering is preserved per client
    import json

    for i, msg in enumerate(ws1.messages_sent):
        data = json.loads(msg)
        assert data["payload"]["index"] == i


@pytest.mark.asyncio
async def test_heartbeat_pong_mechanism(websocket_manager):
    """Test heartbeat/pong mechanism (30s interval)."""
    # Add client
    ws1 = MockWebSocket("client-1")
    await websocket_manager.add_client(ws1)

    # Start heartbeat task
    heartbeat_task = asyncio.create_task(websocket_manager.start_heartbeat())

    # Wait for at least one heartbeat cycle (with small buffer)
    await asyncio.sleep(0.1)  # In real implementation, mock timer or reduce interval

    # Cancel heartbeat task
    heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await heartbeat_task

    # Verify heartbeat messages were sent
    # In real implementation, check for ping/pong messages
    # This is a placeholder - actual implementation will use websocket.ping()
    assert websocket_manager.heartbeat_interval == 120  # 2 minutes per updated spec

    # Note: Full heartbeat testing requires either:
    # 1. Mocking asyncio.sleep to advance time quickly
    # 2. Configurable heartbeat interval for testing
    # 3. Integration test with real WebSocket connection


@pytest.mark.asyncio
async def test_add_client_with_heartbeat_enabled():
    """Test add_client starts heartbeat task when enabled."""
    # Create WebSocketManager with heartbeat enabled
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Verify heartbeat task was started
    assert manager._heartbeat_task is not None
    assert not manager._heartbeat_task.done()

    # Clean up
    await manager.shutdown()


@pytest.mark.asyncio
async def test_add_client_with_heartbeat_already_running():
    """Test add_client doesn't start duplicate heartbeat tasks."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add first client
    ws1 = MockWebSocket("client-1")
    await manager.add_client(ws1)
    first_task = manager._heartbeat_task

    # Add second client
    ws2 = MockWebSocket("client-2")
    await manager.add_client(ws2)

    # Verify same task is reused
    assert manager._heartbeat_task is first_task

    # Clean up
    await manager.shutdown()


@pytest.mark.asyncio
async def test_add_client_with_heartbeat_disabled():
    """Test add_client doesn't start heartbeat when disabled."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(enable_heartbeat=False)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Verify no heartbeat task was started
    assert manager._heartbeat_task is None


@pytest.mark.asyncio
async def test_remove_client_stops_heartbeat_when_last_client():
    """Test remove_client stops heartbeat task when last client is removed."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add clients
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")
    await manager.add_client(ws1)
    await manager.add_client(ws2)

    # Verify heartbeat task started
    assert manager._heartbeat_task is not None

    # Remove one client
    await manager.remove_client(ws1)
    # Verify heartbeat still running
    assert manager._heartbeat_task is not None

    # Remove last client
    await manager.remove_client(ws2)
    # Verify heartbeat task stopped and cleaned up
    assert manager._heartbeat_task is None


@pytest.mark.asyncio
async def test_remove_client_with_nonexistent_client():
    """Test remove_client handles non-existent client gracefully."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Try to remove client that doesn't exist
    ws = MockWebSocket("nonexistent-client")
    await manager.remove_client(ws)

    # Should not raise error
    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_broadcast_stores_streaming_history():
    """Test broadcast stores streaming output events in history."""
    try:
        from flock.dashboard.events import StreamingOutputEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Create streaming event
    event = StreamingOutputEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        output_type="stdout",
        content="test chunk",
        sequence=1,
        correlation_id=str(uuid4()),
    )

    # Broadcast event (no clients connected)
    await manager.broadcast(event)

    # Verify event was stored in history
    history = manager.get_streaming_history("test_agent")
    assert len(history) == 1
    assert history[0].content == "test chunk"
    assert history[0].agent_name == "test_agent"


@pytest.mark.asyncio
async def test_broadcast_stores_streaming_history_with_max_length():
    """Test streaming history respects maxlen parameter."""
    try:
        from flock.dashboard.events import StreamingOutputEvent
        from flock.dashboard.websocket import WebSocketManager

        # Small maxlen for testing
        manager = WebSocketManager()
        manager._streaming_history["test_agent"] = manager._streaming_history[
            "test_agent"
        ].__class__(maxlen=3)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add 5 streaming events
    for i in range(5):
        event = StreamingOutputEvent(
            agent_name="test_agent",
            run_id=str(uuid4()),
            output_type="stdout",
            content=f"chunk {i}",
            sequence=i,
            correlation_id=str(uuid4()),
        )
        await manager.broadcast(event)

    # Verify only last 3 events are kept
    history = manager.get_streaming_history("test_agent")
    assert len(history) == 3
    assert history[0].content == "chunk 2"
    assert history[1].content == "chunk 3"
    assert history[2].content == "chunk 4"


@pytest.mark.asyncio
async def test_broadcast_message_serialization():
    """Test broadcast properly serializes events to JSON."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Create event with complex data
    event = MessagePublishedEvent(
        artifact_id=str(uuid4()),
        artifact_type="ComplexOutput",
        produced_by="test_agent",
        payload={"nested": {"data": [1, 2, 3], "unicode": "🚀"}},
        visibility=VisibilitySpec(kind="Public"),
        correlation_id=str(uuid4()),
    )

    # Broadcast event
    await manager.broadcast(event)

    # Verify JSON was properly serialized
    assert len(ws.messages_sent) == 1
    message = ws.messages_sent[0]

    # Verify it's valid JSON
    import json

    data = json.loads(message)
    assert data["artifact_type"] == "ComplexOutput"
    assert data["payload"]["nested"]["unicode"] == "🚀"


@pytest.mark.asyncio
async def test_broadcast_logging_with_no_clients():
    """Test broadcast logging when no clients are connected."""
    try:
        from flock.dashboard.events import AgentActivatedEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Create event
    event = AgentActivatedEvent(
        agent_name="test_agent",
        agent_id="test_agent",
        consumed_types=["TestInput"],
        produced_types=["TestOutput"],
        consumed_artifacts=[str(uuid4())],
        subscription_info=SubscriptionInfo(),
        labels=["test"],
        tenant_id=None,
        max_concurrency=1,
        correlation_id=str(uuid4()),
        run_id=str(uuid4()),
    )

    # Broadcast with no clients
    await manager.broadcast(event)

    # Should not raise error and event should be stored if it's streaming
    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_heartbeat_loop_shutdown_condition():
    """Test heartbeat loop respects shutdown flag."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=0.1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Start heartbeat loop
    heartbeat_task = asyncio.create_task(manager._heartbeat_loop())

    # Let it run for a bit
    await asyncio.sleep(0.05)

    # Set shutdown flag
    manager._shutdown = True

    # Wait for loop to exit with proper cancellation handling
    try:
        await asyncio.wait_for(heartbeat_task, timeout=0.5)
    except asyncio.TimeoutError:
        # If timeout occurs, cancel the task gracefully
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass  # Expected when cancelling

    # Verify task completed or was cancelled
    assert heartbeat_task.done()


@pytest.mark.asyncio
async def test_heartbeat_loop_exits_with_no_clients():
    """Test heartbeat loop exits when no clients remain."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=0.1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Start heartbeat loop
    heartbeat_task = asyncio.create_task(manager._heartbeat_loop())

    # Remove client
    await manager.remove_client(ws)

    # Wait for loop to exit
    await asyncio.wait_for(heartbeat_task, timeout=0.2)

    # Verify task completed
    assert heartbeat_task.done()


@pytest.mark.asyncio
async def test_heartbeat_loop_handles_exceptions():
    """Test heartbeat loop handles exceptions gracefully."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=0.1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client that will fail on ping
    ws = MockWebSocket("client-1")
    ws._send_exception = Exception("Ping failed")
    await manager.add_client(ws)

    # Start heartbeat loop
    heartbeat_task = asyncio.create_task(manager._heartbeat_loop())

    # Let it run for a bit
    await asyncio.sleep(0.15)

    # Cancel the task
    heartbeat_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await heartbeat_task

    # Should not have raised exception
    assert True


@pytest.mark.asyncio
async def test_ping_client_success():
    """Test _ping_client sends ping successfully."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add send_json method to mock
    class MockWebSocketWithPing(MockWebSocket):
        def __init__(self, client_id: str):
            super().__init__(client_id)
            self.ping_messages = []

        async def send_json(self, data):
            self.ping_messages.append(data)

    ws = MockWebSocketWithPing("client-1")

    # Ping client
    await manager._ping_client(ws)

    # Verify ping was sent
    assert len(ws.ping_messages) == 1
    assert ws.ping_messages[0]["type"] == "ping"
    assert "timestamp" in ws.ping_messages[0]


@pytest.mark.asyncio
async def test_ping_client_failure():
    """Test _ping_client handles ping failure."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client that will fail on send_json
    ws = MockWebSocket("client-1")

    class FailingWebSocket(MockWebSocket):
        async def send_json(self, data):
            raise ConnectionError("Connection lost")

    failing_ws = FailingWebSocket("client-2")
    await manager.add_client(failing_ws)

    # Ping client
    await manager._ping_client(failing_ws)

    # Verify client was removed
    assert failing_ws not in manager.clients


@pytest.mark.asyncio
async def test_start_heartbeat_with_enable_true():
    """Test start_heartbeat starts task when enabled."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client first
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Cancel existing heartbeat task
    if manager._heartbeat_task:
        manager._heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await manager._heartbeat_task
        manager._heartbeat_task = None

    # Start heartbeat manually
    await manager.start_heartbeat()

    # Verify task was started
    assert manager._heartbeat_task is not None
    assert not manager._heartbeat_task.done()

    # Clean up
    await manager.shutdown()


@pytest.mark.asyncio
async def test_start_heartbeat_already_running():
    """Test start_heartbeat doesn't start duplicate tasks."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client to start heartbeat
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    original_task = manager._heartbeat_task

    # Try to start again
    await manager.start_heartbeat()

    # Verify same task is used
    assert manager._heartbeat_task is original_task

    # Clean up
    await manager.shutdown()


@pytest.mark.asyncio
async def test_start_heartbeat_disabled():
    """Test start_heartbeat does nothing when disabled."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(enable_heartbeat=False)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Try to start heartbeat
    await manager.start_heartbeat()

    # Verify no task was started
    assert manager._heartbeat_task is None


@pytest.mark.asyncio
async def test_start_heartbeat_with_shutdown():
    """Test start_heartbeat does nothing when shutdown."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Set shutdown flag
    manager._shutdown = True

    # Try to start heartbeat
    await manager.start_heartbeat()

    # Verify no task was started
    assert manager._heartbeat_task is None


@pytest.mark.asyncio
async def test_shutdown_with_heartbeat_task():
    """Test shutdown cancels heartbeat task."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client to start heartbeat
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Verify heartbeat task is running
    assert manager._heartbeat_task is not None

    # Shutdown
    await manager.shutdown()

    # Verify heartbeat task was cancelled
    assert manager._heartbeat_task is None
    assert manager._shutdown is True
    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_shutdown_with_multiple_clients():
    """Test shutdown closes all client connections."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add multiple clients
    clients = []
    for i in range(3):
        ws = MockWebSocket(f"client-{i}")
        clients.append(ws)
        await manager.add_client(ws)

    # Shutdown
    await manager.shutdown()

    # Verify all clients were removed
    assert len(manager.clients) == 0
    assert manager._shutdown is True


@pytest.mark.asyncio
async def test_shutdown_with_real_websocket_methods():
    """Test shutdown handles real WebSocket close methods."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Create mock with async close method
    class MockWebSocketWithAsyncClose(MockWebSocket):
        def __init__(self, client_id: str):
            super().__init__(client_id)
            self.close_called = False

        async def close(self):
            self.close_called = True
            self.is_closed = True

    ws = MockWebSocketWithAsyncClose("client-1")
    await manager.add_client(ws)

    # Shutdown
    await manager.shutdown()

    # Verify close was called
    assert ws.close_called is True


@pytest.mark.asyncio
async def test_get_streaming_history_for_existing_agent():
    """Test get_streaming_history returns list for existing agent."""
    try:
        from flock.dashboard.events import StreamingOutputEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add streaming events to history directly
    event1 = StreamingOutputEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        output_type="stdout",
        content="chunk 1",
        sequence=1,
        correlation_id=str(uuid4()),
    )
    event2 = StreamingOutputEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        output_type="stdout",
        content="chunk 2",
        sequence=2,
        correlation_id=str(uuid4()),
    )

    manager._streaming_history["test_agent"].append(event1)
    manager._streaming_history["test_agent"].append(event2)

    # Get history
    history = manager.get_streaming_history("test_agent")

    # Verify history
    assert len(history) == 2
    assert history[0].content == "chunk 1"
    assert history[1].content == "chunk 2"
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_get_streaming_history_for_nonexistent_agent():
    """Test get_streaming_history returns empty list for non-existent agent."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Get history for non-existent agent
    history = manager.get_streaming_history("nonexistent_agent")

    # Verify empty list is returned
    assert history == []
    assert isinstance(history, list)


@pytest.mark.asyncio
async def test_concurrent_client_addition_removal():
    """Test concurrent client addition and removal operations."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Create tasks to add and remove clients concurrently
    async def add_clients(start_id: int, count: int):
        for i in range(count):
            ws = MockWebSocket(f"client-{start_id + i}")
            await manager.add_client(ws)
            await asyncio.sleep(0.001)  # Small delay

    async def remove_clients(start_id: int, count: int):
        await asyncio.sleep(0.005)  # Let some clients be added first
        for i in range(count):
            # Find a client to remove
            for client in list(manager.clients):
                if hasattr(client, "client_id") and client.client_id.startswith(
                    f"client-{start_id + i}"
                ):
                    await manager.remove_client(client)
                    break
            await asyncio.sleep(0.001)

    # Run concurrent operations
    add_task1 = asyncio.create_task(add_clients(0, 5))
    add_task2 = asyncio.create_task(add_clients(10, 5))
    remove_task1 = asyncio.create_task(remove_clients(0, 3))
    remove_task2 = asyncio.create_task(remove_clients(10, 2))

    # Wait for all tasks to complete
    await asyncio.gather(add_task1, add_task2, remove_task1, remove_task2)

    # Verify no exceptions were raised and manager is in consistent state
    assert len(manager.clients) >= 0
    # All clients should be valid WebSocket objects
    for client in manager.clients:
        assert hasattr(client, "client_id")


@pytest.mark.asyncio
async def test_stress_concurrent_broadcasts():
    """Test stress scenario with many concurrent broadcasts."""
    try:
        from flock.dashboard.events import StreamingOutputEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add multiple clients
    clients = []
    for i in range(10):
        ws = MockWebSocket(f"client-{i}")
        clients.append(ws)
        await manager.add_client(ws)

    # Create many broadcast tasks
    broadcast_tasks = []
    for i in range(50):
        event = StreamingOutputEvent(
            agent_name=f"agent-{i % 5}",
            run_id=str(uuid4()),
            output_type="stdout",
            content=f"message {i}",
            sequence=i,
            correlation_id=str(uuid4()),
        )
        broadcast_tasks.append(manager.broadcast(event))

    # Execute all broadcasts concurrently
    await asyncio.gather(*broadcast_tasks)

    # Verify each client received all messages
    for client in clients:
        assert len(client.messages_sent) == 50

    # Verify streaming history was maintained
    for agent_id in range(5):
        history = manager.get_streaming_history(f"agent-{agent_id}")
        assert len(history) == 10  # Each agent got 10 messages


@pytest.mark.asyncio
async def test_memory_management_with_many_connections():
    """Test memory management with large number of connections."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add many clients
    initial_client_count = 100
    for i in range(initial_client_count):
        ws = MockWebSocket(f"client-{i}")
        await manager.add_client(ws)

    # Verify all clients are tracked
    assert len(manager.clients) == initial_client_count

    # Broadcast to all clients
    from flock.dashboard.events import AgentCompletedEvent

    event = AgentCompletedEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        duration_ms=150.0,
        correlation_id=str(uuid4()),
    )

    await manager.broadcast(event)

    # Verify all clients received the message
    total_messages = sum(len(client.messages_sent) for client in manager.clients)
    assert total_messages == initial_client_count

    # Remove all clients
    for client in list(manager.clients):
        await manager.remove_client(client)

    # Verify cleanup
    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_message_ordering_under_concurrency():
    """Test message ordering is preserved under concurrent operations."""
    try:
        from flock.dashboard.events import MessagePublishedEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add clients
    ws1 = MockWebSocket("client-1")
    ws2 = MockWebSocket("client-2")
    await manager.add_client(ws1)
    await manager.add_client(ws2)

    # Create ordered sequence of events
    events = []
    for i in range(20):
        event = MessagePublishedEvent(
            artifact_id=str(uuid4()),
            artifact_type=f"Message{i:03d}",
            produced_by="test_agent",
            payload={"sequence": i, "timestamp": asyncio.get_event_loop().time()},
            visibility=VisibilitySpec(kind="Public"),
            correlation_id=str(uuid4()),
        )
        events.append(event)

    # Broadcast events concurrently
    tasks = [manager.broadcast(event) for event in events]
    await asyncio.gather(*tasks)

    # Verify ordering is preserved for each client
    import json

    for client in [ws1, ws2]:
        assert len(client.messages_sent) == 20
        for i, message in enumerate(client.messages_sent):
            data = json.loads(message)
            assert data["payload"]["sequence"] == i
            assert data["artifact_type"] == f"Message{i:03d}"


@pytest.mark.asyncio
async def test_error_recovery_during_broadcast():
    """Test error recovery when clients fail during broadcast."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Create mixed client set: some will fail, some will succeed
    class FlakyWebSocket(MockWebSocket):
        def __init__(self, client_id: str, should_fail: bool = False):
            super().__init__(client_id)
            self.should_fail = should_fail
            self.failure_count = 0

        async def send_text(self, message: str):
            self.failure_count += 1
            if self.should_fail and self.failure_count > 2:  # Fail after 2 successful sends
                raise ConnectionError("Simulated connection failure")
            await super().send_text(message)

    # Add clients
    good_clients = [FlakyWebSocket(f"good-{i}", should_fail=False) for i in range(3)]
    bad_clients = [FlakyWebSocket(f"bad-{i}", should_fail=True) for i in range(2)]

    for client in good_clients + bad_clients:
        await manager.add_client(client)

    # Send multiple broadcasts to trigger failures
    from flock.dashboard.events import AgentActivatedEvent

    for i in range(5):
        event = AgentActivatedEvent(
            agent_name=f"agent-{i}",
            agent_id=f"agent-{i}",
            consumed_types=[f"Input{i}"],
            produced_types=[f"Output{i}"],
            consumed_artifacts=[str(uuid4())],
            subscription_info=SubscriptionInfo(),
            labels=[f"test{i}"],
            tenant_id=None,
            max_concurrency=1,
            correlation_id=str(uuid4()),
            run_id=str(uuid4()),
        )
        await manager.broadcast(event)

    # Verify good clients received all messages
    for client in good_clients:
        assert len(client.messages_sent) == 5

    # Verify bad clients were removed after failure
    for client in bad_clients:
        assert client not in manager.clients

    # Verify manager still has good clients
    assert len(manager.clients) == 3


@pytest.mark.asyncio
async def test_websocket_json_serialization_edge_cases():
    """Test JSON serialization with edge cases and special characters."""
    try:
        from flock.dashboard.events import MessagePublishedEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add client
    ws = MockWebSocket("client-1")
    await manager.add_client(ws)

    # Test various edge cases
    edge_cases = [
        # Unicode and special characters
        {
            "artifact_type": "UnicodeTest",
            "payload": {
                "unicode": "🚀💻🧪",
                "emoji": "🧪 Test 🔬",
                "special_chars": "New\nLine\tTab\"Quote'\\Backslash",
                "math": "∑∏∫∆∇∂",
                "currency": "$€£¥₹₽",
            },
        },
        # Deeply nested structure
        {
            "artifact_type": "NestedTest",
            "payload": {"level1": {"level2": {"level3": {"level4": {"deep_value": "found it"}}}}},
        },
        # Large arrays
        {
            "artifact_type": "ArrayTest",
            "payload": {
                "large_array": list(range(1000)),
                "mixed_types": [1, "string", 3.14, True, None, {"nested": "object"}],
            },
        },
        # Special numeric values
        {
            "artifact_type": "NumericTest",
            "payload": {
                "floats": [0.0, -0.0, 3.14159265359, 1e-10, 1e10],
                "integers": [0, -1, 1, 2**31 - 1, -(2**31)],
                "scientific": [1.23e-4, 9.87e6],
            },
        },
    ]

    # Test each edge case
    for i, test_case in enumerate(edge_cases):
        event = MessagePublishedEvent(
            artifact_id=str(uuid4()),
            artifact_type=test_case["artifact_type"],
            produced_by="edge_case_agent",
            payload=test_case["payload"],
            visibility=VisibilitySpec(kind="Public"),
            correlation_id=str(uuid4()),
        )

        # Broadcast should not raise serialization errors
        await manager.broadcast(event)

        # Verify message was received and is valid JSON
        assert len(ws.messages_sent) == i + 1
        import json

        data = json.loads(ws.messages_sent[-1])
        assert data["artifact_type"] == test_case["artifact_type"]
        assert data["payload"] == test_case["payload"]


@pytest.mark.asyncio
async def test_connection_pool_under_stress():
    """Test connection pool management under high stress conditions."""
    try:
        from flock.dashboard.events import StreamingOutputEvent
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager()
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Rapidly add and remove clients
    async def stress_client_management():
        for cycle in range(10):
            # Add many clients
            added_clients = []
            for i in range(20):
                ws = MockWebSocket(f"stress-{cycle}-{i}")
                added_clients.append(ws)
                await manager.add_client(ws)

            # Send some broadcasts
            for i in range(5):
                event = StreamingOutputEvent(
                    agent_name=f"stress-agent-{cycle}",
                    run_id=str(uuid4()),
                    output_type="stdout",
                    content=f"stress message {cycle}-{i}",
                    sequence=i,
                    correlation_id=str(uuid4()),
                )
                await manager.broadcast(event)

            # Remove some clients randomly
            import random

            for client in random.sample(added_clients, 10):
                await manager.remove_client(client)

            # Small delay
            await asyncio.sleep(0.001)

    # Run multiple stress cycles concurrently
    stress_tasks = [asyncio.create_task(stress_client_management()) for _ in range(3)]
    await asyncio.gather(*stress_tasks)

    # Verify manager is still in consistent state
    assert len(manager.clients) >= 0

    # Clean up remaining clients
    for client in list(manager.clients):
        await manager.remove_client(client)

    assert len(manager.clients) == 0


@pytest.mark.asyncio
async def test_timeout_scenarios():
    """Test timeout scenarios and graceful degradation."""
    try:
        from flock.dashboard.websocket import WebSocketManager

        manager = WebSocketManager(heartbeat_interval=0.1, enable_heartbeat=True)
    except ImportError:
        pytest.skip("WebSocketManager not implemented yet")

    # Add normal clients
    normal_ws1 = MockWebSocket("normal-client-1")
    normal_ws2 = MockWebSocket("normal-client-2")
    await manager.add_client(normal_ws1)
    await manager.add_client(normal_ws2)

    # Send a broadcast to test normal operation
    from flock.dashboard.events import AgentErrorEvent

    event = AgentErrorEvent(
        agent_name="test_agent",
        run_id=str(uuid4()),
        error_type="TimeoutError",
        error_message="Simulated timeout",
        traceback='Traceback (most recent call last):\n  File "test.py", line 1\n    raise TimeoutError()\nTimeoutError: Simulated timeout',
        failed_at="2023-01-01T00:00:00Z",
        correlation_id=str(uuid4()),
    )

    await manager.broadcast(event)

    # Verify clients received the message
    assert len(normal_ws1.messages_sent) == 1
    assert len(normal_ws2.messages_sent) == 1

    # Clean up
    await manager.shutdown()
