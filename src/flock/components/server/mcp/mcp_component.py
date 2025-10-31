"""MCPServerComponent."""

from typing import TYPE_CHECKING

import httpx
from fastapi_mcp import AuthConfig, FastApiMCP
from pydantic import Field

from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.logging.logging import get_logger


logger = get_logger(__name__)

if TYPE_CHECKING:
    from fastapi import FastAPI

    from flock.core.orchestrator import Flock


class MCPServerComponentConfig(ServerComponentConfig):
    """Configuration for MCPServerComponent"""

    enabled: bool = Field(
        default=True,
        description="Enable this component",
    )
    prefix: str = Field(
        default="/api/mcp/plugin/",
        description="Optional Prefix for the routes of the ServerComponent",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="OpenAPI tags to order the endpoints of the ServerComponent.",
    )
    mcp_server_name: str = Field(
        default="Flock MCP",
        description="What name this Flock-MCP server should provide to clients.",
    )
    mcp_server_description: str = Field(
        default="Flock Agent Blackboard MCP",
        description="What this server should identify as to mcp-clients.",
    )
    describe_all_responses: bool = Field(
        default=True,
        description="If the server should include all possible response schemas in tool descriptions",
    )
    describe_full_response_schema: bool = Field(
        default=True,
        description="If the MCP-Server should include the full JSON schema in tool descriptions.",
    )
    included_operations: list[str] = Field(
        default_factory=list,
        description="Which operation_ids to include. operation_ids are assigned to endpoints in the following manner: @app.get('/path/', ..., operation_id='operation_name'). See: https://fastapi-mcp.tadata.com/configurations/tool-naming",
    )
    included_tags: list[str] = Field(
        default_factory=list,
        description="Which tags to include. Tags are assigned to endpoints in the following manner: app.get('/path/', tags=['tag1', 'tag2'])",
    )
    auth_config: AuthConfig | None = Field(
        default=None,
        description="Optional Auth-Config for OAuth authentication. See: https://fastapi-mcp.tadata.com/advanced/auth",
    )
    http_client: httpx.AsyncClient | None = Field(
        default=None,
        description="Optional custom HTTP client to use for API calls to the FastAPI app. Has to be an instance of 'httpx.AsyncClient'.",
    )
    headers: list[str] = Field(
        default=["authorization"],
        description="List of HTTP header names to forward from the incoming MCP requests into each tool invocation. Honly headers in this allowlist will be forwarded. Defaults to ['authorization'].",
    )


class MCPServerComponent(ServerComponent):
    """MCPServerComponent"""

    name: str = Field(default="mcp", description="Name of the ServerComponent")
    priority: int = Field(
        default=1000,
        description="Registration priority. Lower means earlier. Defaults to 1000 to enable core API Routes to be registered first to make them accessible through included_operations & included_tags.",
    )
    config: MCPServerComponentConfig = Field(
        default_factory=MCPServerComponentConfig,
        description="Configuration for the MCPServerComponent.",
    )
    mcp_app: FastApiMCP | None = Field(
        default=None, description="Internal mcp_server instance of the component."
    )
    is_mounted: bool = Field(
        default=False,
        description="Indicates if the internal mcp_server instance has already been mounted.",
    )

    def configure(self, app: "FastAPI", orchestrator: "Flock"):
        if not self.is_mounted and self.mcp_app is None:
            logger.info("MCP-Server has not been mounted yet. Mounting...")
            # the mcp-server has not yet been mounted to the fastapi app
            self.mcp_app = FastApiMCP(
                fastapi=app,
                name=self.config.mcp_server_name,
                description=self.config.mcp_server_description,
                describe_all_responses=self.config.describe_all_responses,
                describe_full_response_schema=self.config.describe_full_response_schema,
                auth_config=self.config.auth_config,
                headers=self.config.headers,
                include_tags=self.config.included_tags,
                include_operations=self.config.included_operations,
            )
            logger.info("MCP-Server has been instantiated.")
            self.mcp_app.mount_http(mount_path=self._join_path(self.config.prefix))
            logger.info("MCP-Server mounted.")
            self.is_mounted = True
        else:
            logger.warning("MCP-Server has been mounted already.")

    def register_routes(self, app: "FastAPI", orchestrator: "Flock"):
        return super().register_routes(app, orchestrator)

    async def on_startup_async(self, orchestrator: "Flock"):
        if self.mcp_app is not None:
            logger.info(
                "Re-Running registration of mcp server to catch endpoints added later."
            )
            self.mcp_app.setup_server()  # re-register the server to catch newly added endpoints

    async def on_shutdown_async(self, orchestrator: "Flock"):
        """No-Op"""

    def get_dependencies(self):
        """No dependencies."""
        return []
