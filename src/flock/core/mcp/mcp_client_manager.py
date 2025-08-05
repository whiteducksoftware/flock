"""Manages a pool of connections for a particular server."""

import copy
from abc import ABC, abstractmethod
from asyncio import Lock
from typing import Any, Generic, TypeVar

from opentelemetry import trace
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_tool import FlockMCPTool
from flock.core.mcp.mcp_client import (
    FlockMCPClient,
)
from flock.core.mcp.mcp_config import FlockMCPConfiguration

logger = get_logger("mcp.client_manager")
tracer = trace.get_tracer(__name__)

TClient = TypeVar("TClient", bound="FlockMCPClient")


class FlockMCPClientManager(BaseModel, ABC, Generic[TClient]):
    """Handles a Pool of MCPClients of type TClient."""

    client_config: FlockMCPConfiguration = Field(
        ..., description="Configuration for clients."
    )

    lock: Lock = Field(
        default_factory=Lock,
        description="Lock for mutex access.",
        exclude=True,
    )

    clients: dict[str, dict[str, FlockMCPClient]] = Field(
        default_factory=dict,
        exclude=True,
        description="Internal Store for the clients.",
    )

    # --- Pydantic v2 Configuratioin ---
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @abstractmethod
    async def make_client(
        self,
        additional_params: dict[str, Any] | None = None,
    ) -> type[TClient]:
        """Instantiate-but don't connect yet-a fresh client of the concrete subtype."""
        # default implementation
        pass

    async def get_client(
        self,
        agent_id: str,
        run_id: str,
        additional_params: dict[str, Any] | None = None,
    ) -> type[TClient]:
        """Provides a client from the pool."""
        # Attempt to get a client from the client store.
        # clients are stored like this: agent_id -> run_id -> client
        with tracer.start_as_current_span("client_manager.get_client") as span:
            span.set_attribute("agent_id", agent_id)
            span.set_attribute("run_id", run_id)
            async with self.lock:
                try:
                    logger.debug(
                        f"Attempting to get client for server '{self.client_config.name}'"
                    )
                    refresh = False
                    if additional_params:
                        refresh = bool(
                            additional_params.get("refresh_client", False)
                        )
                    client = None
                    run_clients = self.clients.get(agent_id, None)
                    if run_clients is None or refresh:
                        # This means, that across all runs, no agent has ever needed a client.
                        # This also means that we need to create a client.
                        client = await self.make_client(
                            additional_params=copy.deepcopy(additional_params)
                        )
                        # Insert the freshly created client
                        self.clients[agent_id] = {}
                        self.clients[agent_id][run_id] = client

                    else:
                        # This means there is at least one entry for the agent_id available
                        # Now, all we need to do is check if the run_id matches the entrie's run_id
                        client = run_clients.get(run_id, None)
                        if client is None or refresh:
                            # Means no client here with the respective run_id
                            client = await self.make_client(
                                additional_params=copy.deepcopy(
                                    additional_params
                                )
                            )
                            # Insert the freshly created client.
                            self.clients[agent_id][run_id] = client

                    return client
                except Exception as e:
                    # Log the exception and raise it so it becomes visible downstream
                    logger.error(
                        f"Unexpected Exception ocurred while trying to get client for server '{self.client_config.name}' with agent_id: {agent_id} and run_id: {run_id}: {e}"
                    )
                    span.record_exception(e)
                    raise e

    async def call_tool(
        self,
        agent_id: str,
        run_id: str,
        name: str,
        arguments: dict[str, Any],
        additional_params: dict[str, Any] | None = None,
    ) -> Any:
        """Call a tool."""
        with tracer.start_as_current_span("client_manager.call_tool") as span:
            span.set_attribute("agent_id", agent_id)
            span.set_attribute("run_id", run_id)
            span.set_attribute("tool_name", name)
            span.set_attribute("arguments", str(arguments))
            try:
                client = await self.get_client(
                    agent_id=agent_id,
                    run_id=run_id,
                    additional_params=additional_params,
                )
                result = await client.call_tool(
                    agent_id=agent_id,
                    run_id=run_id,
                    name=name,
                    arguments=arguments,
                )
                return result
            except Exception as e:
                logger.error(
                    f"Exception occurred while trying to call tool {name} on server '{self.client_config.name}': {e}"
                )
                span.record_exception(e)
                return None

    async def get_tools(
        self,
        agent_id: str,
        run_id: str,
        additional_params: dict[str, Any] | None = None,
    ) -> list[FlockMCPTool]:
        """Retrieves a list of tools for the agents to act on."""
        with tracer.start_as_current_span("client_manager.get_tools") as span:
            span.set_attribute("agent_id", agent_id)
            span.set_attribute("run_id", run_id)
            try:
                client = await self.get_client(
                    agent_id=agent_id,
                    run_id=run_id,
                    additional_params=additional_params,
                )
                tools: list[FlockMCPTool] = await client.get_tools(
                    agent_id=agent_id, run_id=run_id
                )
                return tools
            except Exception as e:
                logger.error(
                    f"Exception occurred while trying to retrieve Tools for server '{self.client_config.name}' with agent_id: {agent_id} and run_id: {run_id}: {e}"
                )
                span.record_exception(e)
                return []

    async def close_all(self) -> None:
        """Closes all connections in the pool and cancels background tasks."""
        with tracer.start_as_current_span("client_manager.close_all") as span:
            async with self.lock:
                for agent_id, run_dict in self.clients.items():
                    logger.debug(
                        f"Shutting down all clients for agent_id: {agent_id}"
                    )
                    for run_id, client in run_dict.items():
                        logger.debug(
                            f"Shutting down client for agent_id {agent_id} and run_id {run_id}"
                        )
                        try:
                            await client.disconnect()
                        except Exception as e:
                            logger.error(
                                f"Error when trying to disconnect client for server '{self.client_config.name}': {e}"
                            )
                            span.record_exception(e)
                self.clients = {}  # Let the GC take care of the rest.
                logger.info(
                    f"All clients disconnected for server '{self.client_config.name}'"
                )
