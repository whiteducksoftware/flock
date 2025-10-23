"""ServerComponent that provides Endpoints for interacting with Agents."""


from pydantic import Field
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.logging.logging import get_logger


logger = get_logger(__name__)

class AgentsComponentConfig(ServerComponentConfig):
    """Configuration class for Agents Component."""
    prefix: str = Field(
        default="/api/v1/agents/",
        description="Optional prefix for Endpoints. Defaults to (and should stay at) '/api/v1/agents/"
    )
    tags: list[str] = Field(
        default=["Agents", "Public API"],
        description="A list of tags for OpenAPI spec."
    )

class AgentsComponent(ServerComponent):
    """ServerComponent that adds Endpoints for interacting with Agents.

    Provided Endpoints:
    - POST /api/v1/agents/{name}/run -> run the agent with agent_name directly
    - GET /api/v1/agents -> Returns a list of all available agents
    - GET /api/v1/agents/{agent_id}/history-summary -> Returns a summary of the history of the agent
    - GET /api/v1/correlations/{correlation_id}/status -> Get the status of a workflow by correlation ID
    """
    name: str = "agents"
    priority: int = Field(
        default=5,
        description="Registration Priority (defaults to 5)"
    )

    def configure(self, app, orchestrator):
        return super().configure(app, orchestrator)

    def register_routes(self, app, orchestrator):
        """Register the routes this component provides."""

    async def on_shutdown_async(self, orchestrator):
        # No-op
        pass

    async def on_startup_async(self, orchestrator):
        # No-op
        pass

    async def get_dependencies(self):
        # No dependencies
        return []
