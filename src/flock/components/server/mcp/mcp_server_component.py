"""ServerComponent that allows external Agents to interact with the Flock instance via MCP."""


from typing import TYPE_CHECKING

from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.logging.logging import get_logger


if TYPE_CHECKING:
    from fastapi import FastAPI

    from flock.core import Flock

logger = get_logger(__name__)

class MCPServerComponentConfig(ServerComponentConfig):
    """Configuration-Class for the MCPServerComponent."""
    enabled: bool = Field(
        default=True,
        description="Enable this component. (Default True)"
    )
    prefix: str = Field(
        default="/mcp/",
        description="Optional prefix for the routes of this Component. (Defaults to '/mcp/')"
    )
    tags: list[str] = Field(
        default=["MCP", "Public API"],
        description="OpenAPI tags to order the endpoints of the ServerComponents in SwaggerDoc."
    )
    invokable_agents: list[str] = Field(
        default_factory=list,
        description="The Agents that can be directly invoked via MCP."
    )

class MCPServerComponent(ServerComponent):
    """Component that allows interaction with the Flock orchestrator and its Agents via MCP."""

    name: str = Field(
        default="mcp",
        description="Registration priority."
    )

    config: MCPServerComponentConfig = Field(
        default_factory=MCPServerComponentConfig,
        description="Configuration for ServerComponent."
    )

    priority: int = Field(
        default=9,
        description="Registration priority."
    )

    def configure(self, app: "FastAPI", orchestrator: "Flock"):
        return super().configure(app, orchestrator)

    def register_routes(self, app, orchestrator):
        return super().register_routes(app, orchestrator)

    async def on_startup_async(self, orchestrator: "Flock"):
        return await super().on_startup_async(orchestrator)

    async def on_shutdown_async(self, orchestrator: "Flock"):
        return await super().on_shutdown_async(orchestrator)

    def get_dependencies(self):
        """No dependencies for the MCP module."""
        return []
