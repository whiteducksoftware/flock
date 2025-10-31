"""ServerComponent used for registering and managing standard health and metrics endpoints."""

from fastapi.responses import PlainTextResponse
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.health.models import HealthResponse


class HealthComponentConfig(ServerComponentConfig):
    """Configuration class for HealthServerComponent."""

    prefix: str | None = Field(
        default=None, description="Optional prefix for all api-endpoints"
    )
    tags: list[str] = Field(
        default=["Health & Metrics"],
        description="A list of tags to pass to the endpoints to be listed under",
    )


class HealthAndMetricsComponent(ServerComponent):
    """ServerComponent that provides health-check and metrics endpoints."""

    name: str = "health"
    config: HealthComponentConfig = Field(
        default_factory=HealthComponentConfig,
        description="Configuration for the health component",
    )
    priority: int = Field(
        default=0,  # registered first
        description="Registration priority. Default = 0",
    )

    def configure(self, app, orchestrator):
        """No-op."""
        return super().configure(app, orchestrator)

    def register_routes(self, app, orchestrator):
        """Adds endpoints to the fastapi-app that allow it to respond to health-checks."""
        prefix = self.config.prefix if self.config.prefix else ""
        health_endpoint_path = self._join_path(prefix, "health")
        metrics_endpoint_path = self._join_path(prefix, "metrics")

        @app.get(health_endpoint_path, tags=self.config.tags)
        async def health() -> HealthResponse:
            """Health Endpoint."""
            return HealthResponse(status="ok")

        @app.get(metrics_endpoint_path, tags=self.config.tags)
        async def metrics() -> PlainTextResponse:
            lines = [
                f"blackboard_{key} {value}"
                for key, value in orchestrator.metrics.items()
            ]
            return PlainTextResponse("\n".join(lines))

    async def on_startup_async(self, orchestrator):
        # No - op
        pass

    async def on_shutdown_async(self, orchestrator):
        # No - op
        pass

    def get_dependencies(self):
        # No dependencies
        return []
