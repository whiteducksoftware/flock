"""Dashboard ServerComponent - Extends basic functionality with a UI and WebSocket support.

Provides real-time dashboard capabilities by:
1. Mounting WebSocket endpoint at /ws by using WebSocketServerComponent
2. Serving static files for dashboard frontend with StaticFilesComponent
3. Integrating DashboardEventCollector with WebSocketManager
4. Supporting CORS for development mode with CORSComponent
"""


from pydantic import Field
from flock.components.server.agents.agents_component import AgentsServerComponent
from flock.components.server.artifacts.artifacts_component import ArtifactsComponent
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.control.control_routes_component import ControlRoutesComponent
from flock.components.server.cors.cors_component import CORSComponent
from flock.components.server.health.health_component import HealthAndMetricsComponent
from flock.components.server.static_files.static_files import StaticFilesServerComponent
from flock.components.server.themes.themes_component import ThemesComponent
from flock.components.server.traces.trace_component import TracingComponent
from flock.components.server.websocket.websocket_component import WebSocketServerComponent
from flock.logging.logging import get_logger

logger = get_logger(__name__)

class DashboardServerComponentConfig(ServerComponentConfig):
    """Configuration for the Dashboard Component."""

class DashboardServerComponent(ServerComponent):
    """Component with WebSocket support for real-time dashboard.

    Extends Flock Service to add:
    - WebSocket endpoint at /ws (via WebSocketComponent) for real-time event streaming
    - Static File serving (via StaticFilesComponent) for dashboard frontend
    - Integration with DashboardEventCollector
    - Optional CORS middleware for development (via CORSComponent)
    """
    name: str = "dashboard"
    priority: int = Field(
        default=100_000_000,
        description="Registration priority. register fairly late."
    )
    config: DashboardServerComponentConfig = Field(
        default_factory=DashboardServerComponentConfig,
        description="Configuration for Component."
    )

    def configure(self, app, orchestrator):
        return super().configure(app, orchestrator)

    def register_routes(self, app, orchestrator):
        return super().register_routes(app, orchestrator)

    async def on_startup_async(self, orchestrator):
        return await super().on_startup_async(orchestrator)

    async def on_shutdown_async(self, orchestrator):
        return await super().on_shutdown_async(orchestrator)

    def get_dependencies(self) -> list[type[ServerComponent]]:
        # Needs quite a few dependencies
        return [
            AgentsServerComponent,
            HealthAndMetricsComponent,
            WebSocketServerComponent,
            ThemesComponent,
            TracingComponent,
            StaticFilesServerComponent,
            ControlRoutesComponent,
            ArtifactsComponent,
            CORSComponent,
        ]
