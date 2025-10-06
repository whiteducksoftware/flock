"""Real-time dashboard event collection for flock-flow.

Phase 1: Backend event capture system.
Phase 3: WebSocket infrastructure for real-time communication.
"""

from flock_flow.dashboard.collector import DashboardEventCollector
from flock_flow.dashboard.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
)
from flock_flow.dashboard.service import DashboardHTTPService
from flock_flow.dashboard.websocket import WebSocketManager


__all__ = [
    "AgentActivatedEvent",
    "AgentCompletedEvent",
    "AgentErrorEvent",
    "DashboardEventCollector",
    "DashboardHTTPService",
    "MessagePublishedEvent",
    "StreamingOutputEvent",
    "WebSocketManager",
]
