"""Tests for Unit 10: External agent status events + dashboard event models.

Verifies that the external agent lifecycle events (spawned, completed, failed)
are correctly modelled, emitted via EventEmitter, and broadcast through
the WebSocketManager.  Also checks that AgentSnapshotRecord carries agent_kind.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from flock.components.server.models.events import (
    ExternalAgentCompletedEvent,
    ExternalAgentFailedEvent,
    ExternalAgentSpawnedEvent,
)
from flock.core.store import AgentSnapshotRecord
from flock.orchestrator.event_emitter import EventEmitter


# ---------------------------------------------------------------------------
# Event model unit tests
# ---------------------------------------------------------------------------


class TestExternalAgentSpawnedEvent:
    """ExternalAgentSpawnedEvent model correctness."""

    def test_type_discriminator(self):
        event = ExternalAgentSpawnedEvent(
            agent_name="translator",
            session_mode="oneshot",
            adapter_type="subprocess",
        )
        assert event.type == "external_agent_spawned"

    def test_all_fields_present(self):
        event = ExternalAgentSpawnedEvent(
            agent_name="translator",
            session_mode="persistent",
            adapter_type="docker",
            trigger_artifact_id="abc-123",
        )
        assert event.agent_name == "translator"
        assert event.session_mode == "persistent"
        assert event.adapter_type == "docker"
        assert event.trigger_artifact_id == "abc-123"
        assert event.timestamp  # auto-populated

    def test_trigger_artifact_id_optional(self):
        event = ExternalAgentSpawnedEvent(
            agent_name="translator",
            session_mode="oneshot",
            adapter_type="subprocess",
        )
        assert event.trigger_artifact_id is None

    def test_serialization_roundtrip(self):
        event = ExternalAgentSpawnedEvent(
            agent_name="agent_a",
            session_mode="oneshot",
            adapter_type="ssh",
            trigger_artifact_id="art-1",
        )
        data = event.model_dump()
        assert data["type"] == "external_agent_spawned"
        assert data["agent_name"] == "agent_a"
        restored = ExternalAgentSpawnedEvent(**data)
        assert restored == event


class TestExternalAgentCompletedEvent:
    """ExternalAgentCompletedEvent model correctness."""

    def test_type_discriminator(self):
        event = ExternalAgentCompletedEvent(agent_name="translator")
        assert event.type == "external_agent_completed"

    def test_defaults(self):
        event = ExternalAgentCompletedEvent(agent_name="translator")
        assert event.session_id is None
        assert event.duration_ms == 0.0

    def test_all_fields(self):
        event = ExternalAgentCompletedEvent(
            agent_name="translator",
            session_id="sess-42",
            duration_ms=1234.5,
        )
        assert event.agent_name == "translator"
        assert event.session_id == "sess-42"
        assert event.duration_ms == 1234.5

    def test_serialization_includes_duration(self):
        event = ExternalAgentCompletedEvent(
            agent_name="translator",
            duration_ms=999.0,
        )
        data = event.model_dump()
        assert data["duration_ms"] == 999.0
        assert data["type"] == "external_agent_completed"


class TestExternalAgentFailedEvent:
    """ExternalAgentFailedEvent model correctness."""

    def test_type_discriminator(self):
        event = ExternalAgentFailedEvent(
            agent_name="translator",
            error="timeout",
        )
        assert event.type == "external_agent_failed"

    def test_all_fields(self):
        event = ExternalAgentFailedEvent(
            agent_name="translator",
            error="process exited with code 1",
            session_id="sess-99",
        )
        assert event.agent_name == "translator"
        assert event.error == "process exited with code 1"
        assert event.session_id == "sess-99"

    def test_session_id_optional(self):
        event = ExternalAgentFailedEvent(
            agent_name="translator",
            error="boom",
        )
        assert event.session_id is None


# ---------------------------------------------------------------------------
# EventEmitter integration tests
# ---------------------------------------------------------------------------


class TestEmitExternalAgentSpawned:
    """EventEmitter.emit_external_agent_spawned broadcasts correctly."""

    @pytest.mark.asyncio
    async def test_broadcasts_correct_event(self):
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        emitter = EventEmitter(websocket_manager=ws)

        await emitter.emit_external_agent_spawned(
            agent_name="translator",
            session_mode="oneshot",
            adapter_type="subprocess",
            trigger_artifact_id="art-77",
        )

        ws.broadcast.assert_called_once()
        event = ws.broadcast.call_args[0][0]
        assert isinstance(event, ExternalAgentSpawnedEvent)
        assert event.agent_name == "translator"
        assert event.session_mode == "oneshot"
        assert event.adapter_type == "subprocess"
        assert event.trigger_artifact_id == "art-77"
        assert event.type == "external_agent_spawned"

    @pytest.mark.asyncio
    async def test_no_op_without_websocket(self):
        """When no WebSocket manager is configured, emit is a silent no-op."""
        emitter = EventEmitter(websocket_manager=None)
        # Should not raise
        await emitter.emit_external_agent_spawned(
            agent_name="translator",
            session_mode="oneshot",
            adapter_type="subprocess",
        )


class TestEmitExternalAgentCompleted:
    """EventEmitter.emit_external_agent_completed broadcasts correctly."""

    @pytest.mark.asyncio
    async def test_broadcasts_with_duration(self):
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        emitter = EventEmitter(websocket_manager=ws)

        await emitter.emit_external_agent_completed(
            agent_name="translator",
            session_id="sess-1",
            duration_ms=500.5,
        )

        ws.broadcast.assert_called_once()
        event = ws.broadcast.call_args[0][0]
        assert isinstance(event, ExternalAgentCompletedEvent)
        assert event.agent_name == "translator"
        assert event.session_id == "sess-1"
        assert event.duration_ms == 500.5

    @pytest.mark.asyncio
    async def test_defaults(self):
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        emitter = EventEmitter(websocket_manager=ws)

        await emitter.emit_external_agent_completed(agent_name="translator")

        event = ws.broadcast.call_args[0][0]
        assert event.session_id is None
        assert event.duration_ms == 0.0

    @pytest.mark.asyncio
    async def test_no_op_without_websocket(self):
        emitter = EventEmitter(websocket_manager=None)
        await emitter.emit_external_agent_completed(
            agent_name="translator",
            duration_ms=100.0,
        )


class TestEmitExternalAgentFailed:
    """EventEmitter.emit_external_agent_failed broadcasts correctly."""

    @pytest.mark.asyncio
    async def test_broadcasts_error_details(self):
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        emitter = EventEmitter(websocket_manager=ws)

        await emitter.emit_external_agent_failed(
            agent_name="translator",
            error="segfault in child process",
            session_id="sess-2",
        )

        ws.broadcast.assert_called_once()
        event = ws.broadcast.call_args[0][0]
        assert isinstance(event, ExternalAgentFailedEvent)
        assert event.agent_name == "translator"
        assert event.error == "segfault in child process"
        assert event.session_id == "sess-2"
        assert event.type == "external_agent_failed"

    @pytest.mark.asyncio
    async def test_no_op_without_websocket(self):
        emitter = EventEmitter(websocket_manager=None)
        await emitter.emit_external_agent_failed(
            agent_name="translator",
            error="boom",
        )


# ---------------------------------------------------------------------------
# AgentSnapshotRecord.agent_kind tests
# ---------------------------------------------------------------------------


class TestAgentSnapshotRecordKind:
    """AgentSnapshotRecord carries agent_kind field."""

    def test_default_is_internal(self):
        now = datetime.now(UTC)
        snap = AgentSnapshotRecord(
            agent_name="test",
            description="d",
            subscriptions=[],
            output_types=[],
            labels=[],
            first_seen=now,
            last_seen=now,
            signature="sig",
        )
        assert snap.agent_kind == "internal"

    def test_external_kind(self):
        now = datetime.now(UTC)
        snap = AgentSnapshotRecord(
            agent_name="ext_agent",
            description="external translator",
            subscriptions=[],
            output_types=[],
            labels=[],
            first_seen=now,
            last_seen=now,
            signature="sig",
            agent_kind="external",
        )
        assert snap.agent_kind == "external"


# ---------------------------------------------------------------------------
# EventEmitter.set_websocket_manager toggling
# ---------------------------------------------------------------------------


class TestEventEmitterToggle:
    """Setting / unsetting the websocket manager toggles emit behaviour."""

    @pytest.mark.asyncio
    async def test_enable_then_disable(self):
        ws = MagicMock()
        ws.broadcast = AsyncMock()
        emitter = EventEmitter(websocket_manager=None)

        # No-op while disabled
        await emitter.emit_external_agent_spawned(
            agent_name="a", session_mode="oneshot", adapter_type="subprocess"
        )
        ws.broadcast.assert_not_called()

        # Enable
        emitter.set_websocket_manager(ws)
        await emitter.emit_external_agent_spawned(
            agent_name="a", session_mode="oneshot", adapter_type="subprocess"
        )
        ws.broadcast.assert_called_once()

        # Disable again
        ws.broadcast.reset_mock()
        emitter.set_websocket_manager(None)
        await emitter.emit_external_agent_spawned(
            agent_name="a", session_mode="oneshot", adapter_type="subprocess"
        )
        ws.broadcast.assert_not_called()
