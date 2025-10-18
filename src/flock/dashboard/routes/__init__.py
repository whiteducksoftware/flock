"""Dashboard route modules.

Organized route handlers extracted from service.py for better modularity:
- control.py: Control API endpoints (publish, invoke, agents, etc.)
- traces.py: Trace-related endpoints (OpenTelemetry, history, etc.)
- themes.py: Theme management endpoints
- websocket.py: WebSocket and real-time dashboard endpoints
"""

from flock.dashboard.routes.control import register_control_routes
from flock.dashboard.routes.themes import register_theme_routes
from flock.dashboard.routes.traces import register_trace_routes
from flock.dashboard.routes.websocket import register_websocket_routes


__all__ = [
    "register_control_routes",
    "register_theme_routes",
    "register_trace_routes",
    "register_websocket_routes",
]
