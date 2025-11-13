"""MCPServerComponent."""

from typing import TYPE_CHECKING, Literal

import httpx
from fastapi_mcp import AuthConfig, FastApiMCP
from pydantic import Field

from flock.api.websocket import WebSocketManager
from flock.components.server.base import ServerComponent, ServerComponentConfig
from flock.components.server.mcp.default_mcp_endpoints import (
    register_default_get_artifact_by_id_route,
    register_default_get_artifact_schema_route,
    register_default_get_workflow_status_route,
    register_default_invokation_route,
    register_default_list_artifact_type_names_route,
    register_default_list_artifacts_route,
    register_default_list_available_agents_route,
    register_default_publish_artifact_route,
    register_default_summarize_artifacts_route,
    register_default_validate_artifact_schema_route,
)
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
        description="""
        Which operation_ids to include.
        operation_ids are assigned to endpoints in the following manner: @app.get('/path/', ..., operation_id='operation_name').
        See: https://fastapi-mcp.tadata.com/configurations/tool-naming
        """,
    )
    included_tags: list[str] = Field(
        default=[
            "MCP",
        ],
        description="""
        Which tags to include.
        Tags are assigned to endpoints in the following manner: app.get('/path/', tags=['tag1', 'tag2'])
        """,
    )
    auth_config: AuthConfig | None = Field(
        default=None,
        description="""
        Optional Auth-Config for OAuth authentication.
        See: https://fastapi-mcp.tadata.com/advanced/auth
        """,
    )
    http_client: httpx.AsyncClient | None = Field(
        default=None,
        description="""
        Optional custom HTTP client to use for API calls to the FastAPI app.
        Has to be an instance of 'httpx.AsyncClient'.
        """,
    )
    headers: list[str] = Field(
        default=["authorization"],
        description="""
        List of HTTP header names to forward from the incoming MCP requests into each tool invocation.
        Only headers in this allowlist will be forwarded.
        Defaults to ['authorization'].
        """,
    )
    transport: Literal["http", "legacy_sse"] = Field(
        default="http",
        description="""
        Transport to use for the MCP Server.
        Default value (Recommended): 'http':
            This is the recommended transport method as it implements
            the latest MCP Streamable HTTP specification.
            It provides better session management, more robust
            connection handling, and aligns with standard HTTP practices.
        Alternative (Legacy): 'sse':
            SSE (Server-Sent Events) transport is maintained for
            backwards compatibility with older MCP implementations.
        """,
    )
    register_default_tools: bool = Field(
        default=True,
        description="Register the default routes of the Flock-MCP Server.",
    )
    exposed_agents: list[str] = Field(
        default_factory=list,
        description="List of agents that should be exposed via MCP. If ['*'] is being passed, then all agents will be exposed.",
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
    websocket_manager: WebSocketManager | None = Field(
        default=None,
        description="Optional WebSocketManager instance. If not provided, the default Flock global WebSocketManager will be used (recommended).",
    )

    def configure(self, app: "FastAPI", orchestrator: "Flock"):
        default_operations: list[str] = []
        if self.websocket_manager is None:
            self.websocket_manager = WebSocketManager()

        if not self.is_mounted and self.mcp_app is None:
            logger.info("MCP-Server has not been instantiated yet.")
            # the mcp-server has not yet been mounted to the fastapi app
            if self.config.register_default_tools:
                default_operations = [
                    "list_available_agents",  # listing all available agents
                    "invoke_agent",  # invoke an agent directly
                    "get_workflow_status",  # Get the status of a workflow by correlation id
                    "publish_artifact",  # Publish a task to the Blackboard
                    "list_artifacts",  # List all artifacts with a given correlation id
                    "summarize_artifacts",  # summarize all artifacts for a given correlation id
                    "get_artifact",  # Get a specific artifact by correlation id
                    "list_artifact_type_names",  # Get all registered artifact types with their schemas
                    "get_artifact_schema",  # Get specific schema for an artifact
                    "validate_artifact_schema",  # Validate an artifact schema
                ]
            if self.config.included_operations is not None and isinstance(
                self.config.included_operations, list
            ):
                default_operations.extend(self.config.included_operations)
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
        else:
            logger.warning("MCP-Server has been instantiated already.")

    def register_routes(self, app: "FastAPI", orchestrator: "Flock"):
        logger.info("Registering routes.")
        # check if we should register the default routes first, and register them
        if self.config.register_default_tools:
            register_default_invokation_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "invoke_agent"),
                tags=self.config.tags,
                logger=logger,
                operation_id="invoke_agent",
            )
            agents_to_expose = []
            if (
                self.config.exposed_agents is not None
                and len(self.config.exposed_agents) >= 1
            ):
                agents_to_expose = (
                    [agent.name for agent in orchestrator.agents]
                    if self.config.exposed_agents[0] == "*"
                    else self.config.exposed_agents
                )

            register_default_list_available_agents_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "list_agents"),
                tags=self.config.tags,
                logger=logger,
                operation_id="list_available_agents",
                exposed_agents=agents_to_expose,
            )

            register_default_publish_artifact_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "publish_artifact"),
                tags=self.config.tags,
                logger=logger,
                operation_id="publish_artifact",
                websocket_manager=self.websocket_manager
                if self.websocket_manager is not None
                else WebSocketManager(),
            )

            register_default_get_workflow_status_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "get_workflow_status"),
                tags=self.config.tags,
                operation_id="get_workflow_status",
                logger=logger,
            )

            register_default_list_artifacts_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "list_artifacts"),
                tags=self.config.tags,
                operation_id="list_artifacts",
                logger=logger,
            )

            register_default_summarize_artifacts_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "summarize_artifacts"),
                tags=self.config.tags,
                operation_id="summarize_artifacts",
                logger=logger,
            )

            register_default_get_artifact_by_id_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "get_artifact_by_id"),
                tags=self.config.tags,
                operation_id="get_artifact",
                logger=logger,
            )

            register_default_list_artifact_type_names_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "get_artifact_type_names"),
                tags=self.config.tags,
                operation_id="list_artifact_type_names",
                logger=logger,
            )

            register_default_get_artifact_schema_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "get_artifact_schema"),
                tags=self.config.tags,
                operation_id="get_artifact_schema",
                logger=logger,
            )

            register_default_validate_artifact_schema_route(
                app=app,
                orchestrator=orchestrator,
                path=self._join_path(self.config.prefix, "validate_artifact_schema"),
                operation_id="validate_artifact_schema",
                tags=self.config.tags,
                logger=logger,
            )

        # At the end, register the mcp_app
        if not self.is_mounted and self.mcp_app is not None:
            logger.info("Mounting MCP-Server")
            if self.config.transport == "http":
                logger.info("Using StreamableHTTP-Transport Protocol")
                self.mcp_app.mount_http(mount_path=self._join_path(self.config.prefix))
                logger.info(f"Mounted MCP-Server at {self._join_path(self.config.prefix)}")
            elif self.config.transport == "legacy_sse":
                logger.info("Using ServerSentEvents-Transport Protocol")
                self.mcp_app.mount_sse(mount_path=self._join_path(self.config.prefix))
                logger.info(f"Mounted MCP-Server at {self._join_path(self.config.prefix)}")
            else:
                logger.exception(
                    f"Invalid tranport option passed: {self.config.transport}. Valid values are 'http', 'legacy_sse'"
                )
                raise ValueError(
                    f"Invalid transport option passed: {self.config.transport}. Valid values are: 'http', 'legacy_sse'"
                )
            logger.info("MCP-Server mounted")

    async def on_startup_async(self, orchestrator: "Flock"):
        if self.mcp_app is not None:
            logger.info(
                "Re-Running registration of mcp server to catch endpoints added later."
            )
            self.mcp_app.setup_server()  # re-register the server to catch newly added endpoints

    async def on_shutdown_async(self, orchestrator: "Flock"):
        """No-Op"""

    def get_dependencies(self):
        """No dependencies.

        All Endpoints are independently created.
        """
        return []
