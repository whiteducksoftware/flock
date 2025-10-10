"""Real-time dashboard event collection for flock-flow.

Phase 1: Backend event capture system.
Phase 3: WebSocket infrastructure for real-time communication.
"""

from flock.dashboard.collector import DashboardEventCollector
from flock.dashboard.events import (
    AgentActivatedEvent,
    AgentCompletedEvent,
    AgentErrorEvent,
    MessagePublishedEvent,
    StreamingOutputEvent,
)
from flock.dashboard.graph_builder import GraphAssembler
from flock.dashboard.service import DashboardHTTPService
from flock.dashboard.websocket import WebSocketManager


__all__ = [
    "AgentActivatedEvent",
    "AgentCompletedEvent",
    "AgentErrorEvent",
    "DashboardEventCollector",
    "DashboardHTTPService",
    "GraphAssembler",
    "MessagePublishedEvent",
    "StreamingOutputEvent",
    "WebSocketManager",
]
