"""Tests for the ChangelogStreamComponent: SSE, WebSocket, and cursor-based pull API."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from flock.components.server.changelog.changelog_component import (
    ChangelogStreamComponent,
    ChangelogStreamComponentConfig,
)
from flock.components.server.changelog.stream_dispatcher import (
    StreamDispatcher,
    Subscription,
)
from flock.models.changelog import (
    ChangelogEvent,
    ChangelogEventType,
    ChangelogFilter,
    ChangelogQueryResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_store():
    """Mock BlackboardStore with changelog methods."""
    store = AsyncMock()
    store.query_changelog = AsyncMock(return_value=ChangelogQueryResult())
    store.get_changelog_bounds = AsyncMock(return_value=(0, 0))
    return store


@pytest.fixture
def mock_orchestrator(mock_store):
    """Mock Flock orchestrator."""
    orch = MagicMock()
    orch.store = mock_store
    return orch


@pytest.fixture
def app_and_component(mock_orchestrator):
    """Create a FastAPI app with the ChangelogStreamComponent registered."""
    app = FastAPI()
    component = ChangelogStreamComponent()
    component.configure(app, mock_orchestrator)
    component.register_routes(app, mock_orchestrator)
    return app, component, mock_orchestrator


@pytest.fixture
def client(app_and_component):
    """Sync test client."""
    app, _, _ = app_and_component
    return TestClient(app)


# ---------------------------------------------------------------------------
# StreamDispatcher unit tests
# ---------------------------------------------------------------------------


class TestStreamDispatcher:
    """Unit tests for the StreamDispatcher."""

    @pytest.mark.asyncio
    async def test_subscribe_creates_subscription(self):
        dispatcher = StreamDispatcher()
        sub = await dispatcher.subscribe()
        assert sub.id
        assert sub.queue.maxsize == 256
        assert await dispatcher.subscriber_count == 1

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_subscription(self):
        dispatcher = StreamDispatcher()
        sub = await dispatcher.subscribe()
        await dispatcher.unsubscribe(sub.id)
        assert await dispatcher.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_delivers_to_matching_subscribers(self):
        dispatcher = StreamDispatcher()
        # Subscriber with no filter (matches all)
        sub = await dispatcher.subscribe()

        event = ChangelogEvent(
            seq=1,
            event_type=ChangelogEventType.artifact_published,
            artifact_type="TestArtifact",
            produced_by="agent_a",
        )
        dispatcher.publish(event)

        # Allow the create_task to run
        await asyncio.sleep(0.05)

        assert not sub.queue.empty()
        data = sub.queue.get_nowait()
        parsed = json.loads(data)
        assert parsed["event_type"] == "artifact_published"
        assert parsed["produced_by"] == "agent_a"

    @pytest.mark.asyncio
    async def test_publish_respects_filters(self):
        dispatcher = StreamDispatcher()
        # Subscriber only wants artifact_consumed events
        sub = await dispatcher.subscribe(
            filters=ChangelogFilter(event_types={ChangelogEventType.artifact_consumed})
        )

        event = ChangelogEvent(
            seq=1,
            event_type=ChangelogEventType.artifact_published,
            artifact_type="TestArtifact",
        )
        dispatcher.publish(event)
        await asyncio.sleep(0.05)

        # Should NOT have received the event
        assert sub.queue.empty()

    @pytest.mark.asyncio
    async def test_publish_drop_oldest_on_queue_full(self):
        dispatcher = StreamDispatcher()
        sub = await dispatcher.subscribe(queue_maxsize=2)

        # Fill the queue
        for i in range(3):
            event = ChangelogEvent(
                seq=i + 1,
                event_type=ChangelogEventType.artifact_published,
                produced_by=f"agent_{i}",
            )
            dispatcher.publish(event)
            await asyncio.sleep(0.05)

        # Queue should have exactly 2 items (maxsize)
        assert sub.queue.qsize() == 2

        # The oldest event (seq=1) should have been dropped
        first = json.loads(sub.queue.get_nowait())
        assert first["seq"] == 2

    @pytest.mark.asyncio
    async def test_multiple_subscribers_different_filters(self):
        dispatcher = StreamDispatcher()
        sub_all = await dispatcher.subscribe()
        sub_consumed = await dispatcher.subscribe(
            filters=ChangelogFilter(event_types={ChangelogEventType.artifact_consumed})
        )

        event_pub = ChangelogEvent(
            seq=1, event_type=ChangelogEventType.artifact_published
        )
        event_con = ChangelogEvent(
            seq=2, event_type=ChangelogEventType.artifact_consumed
        )

        dispatcher.publish(event_pub)
        dispatcher.publish(event_con)
        await asyncio.sleep(0.05)

        # sub_all gets both
        assert sub_all.queue.qsize() == 2
        # sub_consumed gets only the consumed event
        assert sub_consumed.queue.qsize() == 1
        data = json.loads(sub_consumed.queue.get_nowait())
        assert data["event_type"] == "artifact_consumed"

    @pytest.mark.asyncio
    async def test_shutdown_clears_subscriptions(self):
        dispatcher = StreamDispatcher()
        await dispatcher.subscribe()
        await dispatcher.subscribe()
        assert await dispatcher.subscriber_count == 2

        await dispatcher.shutdown()
        assert await dispatcher.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_never_blocks_caller(self):
        """publish() must return immediately (fire-and-forget)."""
        dispatcher = StreamDispatcher()
        # Create a subscriber with a tiny queue
        await dispatcher.subscribe(queue_maxsize=1)

        event = ChangelogEvent(
            seq=1,
            event_type=ChangelogEventType.artifact_published,
        )

        # publish() should return instantly (non-blocking)
        import time

        start = time.monotonic()
        dispatcher.publish(event)
        elapsed = time.monotonic() - start
        # Must be sub-millisecond (just creates a task)
        assert elapsed < 0.01

    @pytest.mark.asyncio
    async def test_serialized_once_shared_across_queues(self):
        """Event is serialized once and the same string reference is shared."""
        dispatcher = StreamDispatcher()
        sub1 = await dispatcher.subscribe()
        sub2 = await dispatcher.subscribe()

        event = ChangelogEvent(
            seq=1,
            event_type=ChangelogEventType.artifact_published,
            produced_by="shared_test",
        )
        dispatcher.publish(event)
        await asyncio.sleep(0.05)

        data1 = sub1.queue.get_nowait()
        data2 = sub2.queue.get_nowait()
        # Same string content
        assert data1 == data2
        # Same object reference (shared, not copied)
        assert data1 is data2


# ---------------------------------------------------------------------------
# Cursor API tests
# ---------------------------------------------------------------------------


class TestCursorAPI:
    """Tests for GET /api/v1/changelog/events."""

    @pytest.mark.asyncio
    async def test_cursor_returns_events(self, app_and_component):
        app, component, orch = app_and_component

        events = [
            ChangelogEvent(
                seq=1,
                event_type=ChangelogEventType.artifact_published,
                artifact_type="Note",
                produced_by="agent_a",
            ),
            ChangelogEvent(
                seq=2,
                event_type=ChangelogEventType.artifact_consumed,
                artifact_type="Note",
                produced_by="agent_b",
            ),
        ]
        orch.store.query_changelog.return_value = ChangelogQueryResult(
            events=events,
            oldest_available_seq=1,
            latest_seq=2,
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/v1/changelog/events?after=0&limit=10")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["events"]) == 2
        assert body["oldest_available_seq"] == 1
        assert body["latest_seq"] == 2

    @pytest.mark.asyncio
    async def test_cursor_with_type_filter(self, app_and_component):
        app, component, orch = app_and_component

        events = [
            ChangelogEvent(
                seq=3,
                event_type=ChangelogEventType.artifact_published,
                produced_by="agent_x",
            ),
        ]
        orch.store.query_changelog.return_value = ChangelogQueryResult(
            events=events, oldest_available_seq=1, latest_seq=5
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/v1/changelog/events?type=artifact_published"
            )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["events"]) == 1
        # Verify the filter was passed to query_changelog
        call_kwargs = orch.store.query_changelog.call_args.kwargs
        assert call_kwargs["filters"].event_types == {
            ChangelogEventType.artifact_published
        }

    @pytest.mark.asyncio
    async def test_cursor_with_produced_by_filter(self, app_and_component):
        app, component, orch = app_and_component

        orch.store.query_changelog.return_value = ChangelogQueryResult(
            events=[], oldest_available_seq=1, latest_seq=5
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get(
                "/api/v1/changelog/events?produced_by=agent_x"
            )

        assert resp.status_code == 200
        call_kwargs = orch.store.query_changelog.call_args.kwargs
        assert call_kwargs["filters"].produced_by == {"agent_x"}

    @pytest.mark.asyncio
    async def test_cursor_after_beyond_latest_returns_empty(self, app_and_component):
        app, component, orch = app_and_component

        orch.store.query_changelog.return_value = ChangelogQueryResult(
            events=[], oldest_available_seq=1, latest_seq=5
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/v1/changelog/events?after=999")

        assert resp.status_code == 200
        body = resp.json()
        assert body["events"] == []
        assert body["oldest_available_seq"] == 1
        assert body["latest_seq"] == 5

    @pytest.mark.asyncio
    async def test_cursor_invalid_after_returns_400(self, app_and_component):
        app, component, orch = app_and_component

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/v1/changelog/events?after=-1")

        assert resp.status_code == 400
        assert "non-negative" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_cursor_invalid_type_returns_400(self, app_and_component):
        app, component, orch = app_and_component

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/v1/changelog/events?type=bogus_type")

        assert resp.status_code == 400
        assert "Invalid event type" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# SSE endpoint tests (using the internal generator directly)
# ---------------------------------------------------------------------------


class TestSSEEndpoint:
    """Tests for GET /api/v1/changelog/stream.

    SSE long-lived connections are hard to test with httpx, so we test
    the internal generator and subscription behavior directly.
    """

    @pytest.mark.asyncio
    async def test_sse_event_generator_yields_events(self, app_and_component):
        """SSE generator yields events with correct event/data/id fields."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            # Mock request that is never disconnected
            request = MagicMock()
            request.is_disconnected = AsyncMock(return_value=False)

            # Start the generator — it will subscribe internally then wait
            gen = component._sse_event_generator(request, orch, after_seq=0)

            # Advance generator to the subscription point by scheduling it
            # and then publishing. We use a task to drive the generator.
            import flock.components.server.changelog.changelog_component as mod

            original = mod._SSE_KEEPALIVE_SECONDS
            mod._SSE_KEEPALIVE_SECONDS = 0.5  # Short timeout for test

            async def drive_gen():
                return await gen.__anext__()

            task = asyncio.create_task(drive_gen())
            # Wait for the subscription to be set up
            await asyncio.sleep(0.1)

            # Publish an event while the generator is waiting
            event = ChangelogEvent(
                seq=42,
                event_type=ChangelogEventType.artifact_published,
                artifact_type="TestArtifact",
                produced_by="agent_a",
            )
            component.dispatcher.publish(event)

            # Wait for the task to yield
            sse_dict = await asyncio.wait_for(task, timeout=3.0)

            mod._SSE_KEEPALIVE_SECONDS = original

            assert sse_dict["event"] == "artifact_published"
            assert sse_dict["id"] == "42"
            data = json.loads(sse_dict["data"])
            assert data["produced_by"] == "agent_a"
            assert data["artifact_type"] == "TestArtifact"

            await gen.aclose()
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_sse_keepalive_on_idle(self, app_and_component):
        """SSE generator sends keepalive comment when no events arrive."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            request = MagicMock()
            request.is_disconnected = AsyncMock(return_value=False)

            gen = component._sse_event_generator(request, orch, after_seq=0)

            # Don't publish anything — wait for keepalive (15s is too long for
            # a test, so we'll monkeypatch the timeout)
            import flock.components.server.changelog.changelog_component as mod

            original = mod._SSE_KEEPALIVE_SECONDS
            mod._SSE_KEEPALIVE_SECONDS = 0.1  # Speed up for test

            try:
                sse_dict = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
                assert "comment" in sse_dict
                assert sse_dict["comment"] == "keepalive"
            finally:
                mod._SSE_KEEPALIVE_SECONDS = original

            await gen.aclose()
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_sse_reconnection_replays_from_store(self, app_and_component):
        """SSE with after_seq > 0 replays missed events from the store."""
        app, component, orch = app_and_component

        replay_events = [
            ChangelogEvent(
                seq=6,
                event_type=ChangelogEventType.artifact_published,
                produced_by="agent_a",
            ),
            ChangelogEvent(
                seq=7,
                event_type=ChangelogEventType.artifact_consumed,
                produced_by="agent_b",
            ),
        ]
        orch.store.query_changelog.return_value = ChangelogQueryResult(
            events=replay_events,
            oldest_available_seq=1,
            latest_seq=7,
        )
        await component.on_startup_async(orch)

        try:
            request = MagicMock()
            request.is_disconnected = AsyncMock(return_value=False)

            gen = component._sse_event_generator(request, orch, after_seq=5)

            # First two yields should be the replayed events
            sse1 = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
            assert sse1["id"] == "6"
            assert sse1["event"] == "artifact_published"

            sse2 = await asyncio.wait_for(gen.__anext__(), timeout=2.0)
            assert sse2["id"] == "7"
            assert sse2["event"] == "artifact_consumed"

            # Verify store was queried with correct after_seq
            orch.store.query_changelog.assert_called_with(after_seq=5, limit=1000)

            await gen.aclose()
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_sse_client_disconnect_cleans_up(self, app_and_component):
        """SSE generator exits and cleans subscription on client disconnect."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            # Start with connected, then simulate disconnect
            disconnect_after = 0
            call_count = [0]

            async def is_disconnected():
                call_count[0] += 1
                return call_count[0] > 1  # Disconnect after first check

            request = MagicMock()
            request.is_disconnected = is_disconnected

            gen = component._sse_event_generator(request, orch, after_seq=0)

            # Generator should terminate (return) due to disconnect
            items = []
            async for item in gen:
                items.append(item)

            # After generator exits, subscription should be cleaned up
            count = await component.dispatcher.subscriber_count
            assert count == 0
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_sse_slow_consumer_backpressure(self, app_and_component):
        """Slow SSE consumer gets oldest events dropped (QueueFull backpressure)."""
        app, component, orch = app_and_component
        component.config.sse_queue_maxsize = 3
        await component.on_startup_async(orch)

        try:
            # Subscribe directly to test backpressure
            sub = await component.dispatcher.subscribe(queue_maxsize=3)

            # Publish 6 events (queue maxsize is 3)
            for i in range(6):
                event = ChangelogEvent(
                    seq=i + 1,
                    event_type=ChangelogEventType.artifact_published,
                    produced_by=f"agent_{i}",
                )
                component.dispatcher.publish(event)
                await asyncio.sleep(0.02)

            # Queue should have at most 3 events
            assert sub.queue.qsize() == 3

            # The newest events should be retained (4, 5, 6)
            first = json.loads(sub.queue.get_nowait())
            second = json.loads(sub.queue.get_nowait())
            third = json.loads(sub.queue.get_nowait())
            assert first["seq"] == 4
            assert second["seq"] == 5
            assert third["seq"] == 6
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_multiple_sse_clients_different_event_subsets(
        self, app_and_component
    ):
        """Multiple SSE clients with different filters receive different event subsets."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            sub_all = await component.dispatcher.subscribe()
            sub_published = await component.dispatcher.subscribe(
                filters=ChangelogFilter(
                    event_types={ChangelogEventType.artifact_published}
                )
            )
            sub_agent_a = await component.dispatcher.subscribe(
                filters=ChangelogFilter(produced_by={"agent_a"})
            )

            # Publish various events
            ev1 = ChangelogEvent(
                seq=1,
                event_type=ChangelogEventType.artifact_published,
                produced_by="agent_a",
            )
            ev2 = ChangelogEvent(
                seq=2,
                event_type=ChangelogEventType.artifact_consumed,
                produced_by="agent_b",
            )
            ev3 = ChangelogEvent(
                seq=3,
                event_type=ChangelogEventType.artifact_published,
                produced_by="agent_b",
            )

            component.dispatcher.publish(ev1)
            component.dispatcher.publish(ev2)
            component.dispatcher.publish(ev3)
            await asyncio.sleep(0.05)

            # sub_all gets all 3
            assert sub_all.queue.qsize() == 3
            # sub_published gets ev1 and ev3
            assert sub_published.queue.qsize() == 2
            # sub_agent_a gets only ev1
            assert sub_agent_a.queue.qsize() == 1
            data = json.loads(sub_agent_a.queue.get_nowait())
            assert data["seq"] == 1
        finally:
            await component.on_shutdown_async(orch)


# ---------------------------------------------------------------------------
# WebSocket endpoint tests
# ---------------------------------------------------------------------------


class TestWebSocketEndpoint:
    """Tests for WS /ws/changelog."""

    @pytest.mark.asyncio
    async def test_ws_receives_events_with_filter(self, app_and_component):
        """WebSocket endpoint receives initial filter, then pushes matching events only."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            with TestClient(app) as tc:
                with tc.websocket_connect("/ws/changelog") as ws:
                    # Send filter — only want artifact_published
                    ws.send_text(json.dumps({
                        "event_types": ["artifact_published"]
                    }))

                    # Give time for subscription setup
                    await asyncio.sleep(0.1)

                    # Publish a matching event
                    ev_match = ChangelogEvent(
                        seq=10,
                        event_type=ChangelogEventType.artifact_published,
                        produced_by="agent_a",
                    )
                    component.dispatcher.publish(ev_match)

                    # Publish a non-matching event
                    ev_no_match = ChangelogEvent(
                        seq=11,
                        event_type=ChangelogEventType.artifact_consumed,
                        produced_by="agent_b",
                    )
                    component.dispatcher.publish(ev_no_match)

                    await asyncio.sleep(0.1)

                    # Should receive the matching event
                    data = ws.receive_text()
                    parsed = json.loads(data)
                    assert parsed["event_type"] == "artifact_published"
                    assert parsed["seq"] == 10
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_ws_malformed_filter_gets_error_and_disconnect(
        self, app_and_component
    ):
        """WebSocket with malformed filter JSON gets error message and disconnect."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            with TestClient(app) as tc:
                with tc.websocket_connect("/ws/changelog") as ws:
                    # Send invalid JSON
                    ws.send_text("not valid json {{{")
                    await asyncio.sleep(0.1)

                    # Should receive error message
                    data = ws.receive_json()
                    assert "error" in data
                    assert "Invalid filter JSON" in data["error"]
        finally:
            await component.on_shutdown_async(orch)

    @pytest.mark.asyncio
    async def test_ws_disconnect_cleans_up_subscription(self, app_and_component):
        """WebSocket client disconnect cleans up subscription."""
        app, component, orch = app_and_component
        await component.on_startup_async(orch)

        try:
            with TestClient(app) as tc:
                with tc.websocket_connect("/ws/changelog") as ws:
                    # Send empty filter (match all)
                    ws.send_text(json.dumps({}))
                    await asyncio.sleep(0.1)
                    count_during = await component.dispatcher.subscriber_count
                    assert count_during >= 1

            # After disconnect, subscription should be cleaned up
            await asyncio.sleep(0.2)
            count_after = await component.dispatcher.subscriber_count
            assert count_after == 0
        finally:
            await component.on_shutdown_async(orch)


# ---------------------------------------------------------------------------
# Component lifecycle tests
# ---------------------------------------------------------------------------


class TestComponentLifecycle:
    """Tests for ChangelogStreamComponent startup/shutdown."""

    @pytest.mark.asyncio
    async def test_startup_creates_dispatcher(self):
        component = ChangelogStreamComponent()
        orch = MagicMock()
        await component.on_startup_async(orch)
        assert component._dispatcher is not None

    @pytest.mark.asyncio
    async def test_shutdown_cleans_dispatcher(self):
        component = ChangelogStreamComponent()
        orch = MagicMock()
        await component.on_startup_async(orch)
        await component.on_shutdown_async(orch)
        assert component._dispatcher is None

    @pytest.mark.asyncio
    async def test_dispatcher_property_raises_before_startup(self):
        component = ChangelogStreamComponent()
        with pytest.raises(RuntimeError, match="not started"):
            _ = component.dispatcher

    @pytest.mark.asyncio
    async def test_component_priority(self):
        component = ChangelogStreamComponent()
        assert component.priority == 20

    @pytest.mark.asyncio
    async def test_component_name(self):
        component = ChangelogStreamComponent()
        assert component.name == "changelog_stream"

    @pytest.mark.asyncio
    async def test_component_no_dependencies(self):
        component = ChangelogStreamComponent()
        assert component.get_dependencies() == []
