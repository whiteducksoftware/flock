"""Wrapper Class for a mcp ClientSession Object."""

import asyncio
import random
from abc import ABC, abstractmethod
from asyncio import Lock
from collections.abc import Callable
from contextlib import (
    AsyncExitStack,
    asynccontextmanager,
)
from datetime import timedelta
from typing import (
    Any,
)

import httpx
from anyio import ClosedResourceError
from anyio.streams.memory import (
    MemoryObjectReceiveStream,
    MemoryObjectSendStream,
)
from cachetools import TTLCache, cached
from mcp import (
    ClientSession,
    InitializeResult,
    ListToolsResult,
    McpError,
    ServerCapabilities,
)
from mcp.types import CallToolResult
from opentelemetry import trace
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from flock.core.logging.logging import get_logger
from flock.core.mcp.flock_mcp_tool import FlockMCPTool
from flock.core.mcp.mcp_config import FlockMCPConfiguration
from flock.core.mcp.types.factories import (
    default_flock_mcp_list_roots_callback_factory,
    default_flock_mcp_logging_callback_factory,
    default_flock_mcp_message_handler_callback_factory,
    default_flock_mcp_sampling_callback_factory,
)
from flock.core.mcp.types.types import (
    FlockListRootsMCPCallback,
    FlockLoggingMCPCallback,
    FlockMessageHandlerMCPCallback,
    FlockSamplingMCPCallback,
    MCPRoot,
    ServerParameters,
)
from flock.core.mcp.util.helpers import cache_key_generator

logger = get_logger("mcp.client")
tracer = trace.get_tracer(__name__)

GetSessionIdCallback = Callable[[], str | None]


class FlockMCPClient(BaseModel, ABC):
    """Wrapper for mcp ClientSession.

    Class will attempt to re-establish connection if possible.
    If connection establishment fails after max_retries, then
    `has_error` will be set to true and `error_message` will
    contain the details of the exception.
    """

    # --- Properties ---
    config: FlockMCPConfiguration = Field(
        ..., description="The config for this client instance."
    )

    tool_cache: TTLCache | None = Field(
        default=None,
        exclude=True,
        description="Cache for tools. Excluded from Serialization.",
    )

    tool_result_cache: TTLCache | None = Field(
        default=None,
        exclude=True,
        description="Cache for the result of tool call. Excluded from Serialization.",
    )

    resource_contents_cache: TTLCache | None = Field(
        default=None,
        exclude=True,
        description="Cache for resource contents. Excluded from Serialization.",
    )

    resource_list_cache: TTLCache | None = Field(
        default=None,
        exclude=True,
        description="Cache for Resource Lists. Excluded from Serialization.",
    )

    client_session: ClientSession | None = Field(
        default=None, exclude=True, description="ClientSession Reference."
    )

    connected_server_capabilities: ServerCapabilities | None = Field(
        default=None,
        exclude=True,
        description="Capabilities of the connected server.",
    )

    current_roots: list[MCPRoot] | None = Field(
        default=None, description="Currently used roots of the client."
    )

    lock: Lock = Field(
        default_factory=Lock,
        exclude=True,
        description="Global lock for the client.",
    )

    session_stack: AsyncExitStack = Field(
        default_factory=AsyncExitStack,
        exclude=True,
        description="Internal AsyncExitStack for session.",
    )

    sampling_callback: FlockSamplingMCPCallback | None = Field(
        default=None, description="Sampling Callback."
    )

    list_roots_callback: FlockListRootsMCPCallback | None = Field(
        default=None, description="List Roots Callback."
    )

    logging_callback: FlockLoggingMCPCallback | None = Field(
        default=None, description="Logging Callback."
    )

    message_handler: FlockMessageHandlerMCPCallback | None = Field(
        default=None, description="MessageHandler Callback."
    )

    additional_params: dict[str, Any] | None = Field(
        default=None,
        description="Additional Parameters for connection. Can be modified using server modules.",
    )

    # Auto-reconnect proxy
    class _SessionProxy:
        def __init__(self, client: Any):
            self._client = client

        def __getattr__(self, name: str):
            # return an async function that auto-reconnects, then calls through.
            async def _method(*args, **kwargs):
                with tracer.start_as_current_span(
                    "session_proxy.__getattr__"
                ) as span:
                    client = self._client
                    cfg = client.config
                    max_tries = cfg.connection_config.max_retries or 1
                    base_delay = 0.1
                    span.set_attribute("client.name", client.config.name)
                    span.set_attribute("max_tries", max_tries)

                    for attempt in range(1, max_tries + 2):
                        span.set_attribute("base_delay", base_delay)
                        span.set_attribute("attempt", attempt)
                        await client._ensure_connected()
                        try:
                            # delegate the real session
                            return await getattr(client.client_session, name)(
                                *args, **kwargs
                            )
                        except McpError as e:
                            # only retry on a transport timeout
                            if e.error.code == httpx.codes.REQUEST_TIMEOUT:
                                kind = "timeout"
                            else:
                                # application-level MCP error -> give up immediately
                                logger.error(
                                    f"MCP error in session.{name}: {e.error}"
                                )
                                return None
                        except (BrokenPipeError, ClosedResourceError) as e:
                            kind = type(e).__name__
                            span.record_exception(e)
                        except Exception as e:
                            # anything else is treated as transport failure
                            span.record_exception(e)
                            kind = type(e).__name__

                        # no more retries
                        if attempt > max_tries:
                            logger.error(
                                f"Session.{name} failed after {max_tries} retries ({kind}); giving up."
                            )
                            try:
                                await client.disconnect()
                            except Exception as e:
                                logger.warning(
                                    f"Error tearing down stale session: {e}"
                                )
                                span.record_exception(e)
                            return None

                        # otherwise log + tear down + back off
                        logger.warning(
                            f"Session.{name} attempt {attempt}/{max_tries} failed. ({kind}). Reconnecting."
                        )
                        try:
                            await client.disconnect()
                            await client._connect()
                        except Exception as e:
                            logger.error(f"Reconnect failed: {e}")
                            span.record_exception(e)

                        # Exponential backoff + 10% jitter
                        delay = base_delay ** (2 ** (attempt - 1))
                        delay += random.uniform(0, delay * 0.1)
                        await asyncio.sleep(delay)

            return _method

    def __init__(
        self,
        config: FlockMCPConfiguration,
        lock: Lock | None = None,
        tool_cache: TTLCache | None = None,
        tool_result_cache: TTLCache | None = None,
        resource_contents_cache: TTLCache | None = None,
        resource_list_cache: TTLCache | None = None,
        client_session: ClientSession | None = None,
        connected_server_capabilities: ServerCapabilities | None = None,
        session_stack: AsyncExitStack = AsyncExitStack(),
        sampling_callback: FlockSamplingMCPCallback | None = None,
        list_roots_callback: FlockListRootsMCPCallback | None = None,
        logging_callback: FlockLoggingMCPCallback | None = None,
        message_handler: FlockMessageHandlerMCPCallback | None = None,
        current_roots: list[MCPRoot] | None = None,
        **kwargs,
    ):
        """Init function."""
        lock = lock or Lock()
        super().__init__(
            config=config,
            lock=lock,
            tool_cache=tool_cache,
            tool_result_cache=tool_result_cache,
            resource_contents_cache=resource_contents_cache,
            resource_list_cache=resource_list_cache,
            client_session=client_session,
            connected_server_capabilities=connected_server_capabilities,
            session_stack=session_stack,
            sampling_callback=sampling_callback,
            list_roots_callback=list_roots_callback,
            logging_callback=logging_callback,
            message_handler=message_handler,
            current_roots=current_roots,
            **kwargs,
        )

        # Check if roots are specified in the config:
        if (
            not self.current_roots
            and self.config.connection_config.mount_points
        ):
            # That means that the roots are set in the config
            self.current_roots = self.config.connection_config.mount_points

        if not self.tool_cache:
            self.tool_cache = TTLCache(
                maxsize=self.config.caching_config.tool_cache_max_size,
                ttl=self.config.caching_config.tool_cache_max_ttl,
            )

        # set up the caches
        if not self.tool_result_cache:
            self.tool_result_cache = TTLCache(
                maxsize=self.config.caching_config.tool_result_cache_max_size,
                ttl=self.config.caching_config.tool_result_cache_max_ttl,
            )

        if not self.resource_contents_cache:
            self.resource_contents_cache = TTLCache(
                maxsize=self.config.caching_config.resource_contents_cache_max_size,
                ttl=self.config.caching_config.resource_contents_cache_max_ttl,
            )
        if not self.resource_list_cache:
            self.resource_list_cache = TTLCache(
                maxsize=self.config.caching_config.resource_list_cache_max_size,
                ttl=self.config.caching_config.resource_list_cache_max_ttl,
            )

        # set up callbacks
        if not self.logging_callback:
            if not self.config.callback_config.logging_callback:
                self.logging_callback = (
                    default_flock_mcp_logging_callback_factory(
                        associated_client=self,
                        logger=logger,
                    )
                )
            else:
                self.logging_callback = (
                    self.config.callback_config.logging_callback
                )

        if not self.message_handler:
            if not self.config.callback_config.message_handler:
                self.message_handler = (
                    default_flock_mcp_message_handler_callback_factory(
                        associated_client=self,
                        logger=logger,
                    )
                )
            else:
                self.message_handler = (
                    self.config.callback_config.message_handler
                )

        if not self.list_roots_callback:
            if not self.config.callback_config.list_roots_callback:
                self.list_roots_callback = (
                    default_flock_mcp_list_roots_callback_factory(
                        associated_client=self,
                        logger=logger,
                    )
                )
            else:
                self.list_roots_callback = (
                    self.config.callback_config.list_roots_callback
                )

        if not self.sampling_callback:
            if not self.config.callback_config.sampling_callback:
                self.sampling_callback = (
                    default_flock_mcp_sampling_callback_factory(
                        associated_client=self,
                        logger=logger,
                    )
                )
            else:
                self.sampling_callback = (
                    self.config.callback_config.sampling_callback
                )

    @property
    def session(self) -> _SessionProxy:
        """Always-connected proxy for client_session methods.

        Usage: await self.client_session.call_tool(...), await self.client_session.list_tools(...)
        """
        return self._SessionProxy(self)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="allow",
    )

    # --- Abstract methods / class methods ---
    @abstractmethod
    async def create_transport(
        self,
        params: ServerParameters,
        additional_params: dict[str, Any] | None = None,
    ) -> Any:
        """Given your custom ServerParameters, return an async-contextmgr whose __aenter yields (read_stream, write_stream)."""
        ...

    # --- Public methods ---
    async def get_tools(
        self,
        agent_id: str,
        run_id: str,
    ) -> list[FlockMCPTool]:
        """Gets a list of available tools from the server."""

        @cached(cache=self.tool_cache, key=cache_key_generator)
        async def _get_tools_cached(
            agent_id: str,
            run_id: str,
        ) -> list[FlockMCPTool]:
            if not self.config.feature_config.tools_enabled:
                return []

            async def _get_tools_internal() -> list[FlockMCPTool]:
                # TODO: Crash
                response: ListToolsResult = await self.session.list_tools()
                flock_tools = []

                for tool in response.tools:
                    converted_tool = FlockMCPTool.from_mcp_tool(
                        tool,
                        agent_id=agent_id,
                        run_id=run_id,
                    )
                    if converted_tool:
                        flock_tools.append(converted_tool)
                return flock_tools

            return await _get_tools_internal()

        return await _get_tools_cached(agent_id=agent_id, run_id=run_id)

    async def call_tool(
        self, agent_id: str, run_id: str, name: str, arguments: dict[str, Any]
    ) -> CallToolResult:
        """Call a tool via the MCP Protocol on the client's server."""

        @cached(cache=self.tool_result_cache, key=cache_key_generator)
        async def _call_tool_cached(
            agent_id: str, run_id: str, name: str, arguments: dict[str, Any]
        ) -> CallToolResult:
            async def _call_tool_internal(
                name: str, arguments: dict[str, Any]
            ) -> CallToolResult:
                logger.debug(
                    f"Calling tool '{name}' with arguments {arguments}"
                )
                return await self.session.call_tool(
                    name=name,
                    arguments=arguments,
                )

            return await _call_tool_internal(name=name, arguments=arguments)

        return await _call_tool_cached(
            agent_id=agent_id, run_id=run_id, name=name, arguments=arguments
        )

    async def get_server_name(self) -> str:
        """Return the server_name.

        Uses a lock under the hood.
        """
        async with self.lock:
            return self.config.name

    async def get_roots(self) -> list[MCPRoot] | None:
        """Get the currently set roots of the client.

        Locks under the hood.
        """
        async with self.lock:
            return self.current_roots

    async def set_roots(self, new_roots: list[MCPRoot]) -> None:
        """Set the current roots of the client.

        Locks under the hood.
        """
        async with self.lock:
            self.current_roots = new_roots
            if self.session:
                try:
                    await self.client_session.send_roots_list_changed()
                except McpError as e:
                    logger.warning(f"Send roots list changed: {e}")

    async def invalidate_tool_cache(self) -> None:
        """Invalidate the entries in the tool cache."""
        logger.debug(f"Invalidating tool_cache for server '{self.config.name}'")
        async with self.lock:
            if self.tool_cache:
                self.tool_cache.clear()
                logger.debug(
                    f"Invalidated tool_cache for server '{self.config.name}'"
                )

    async def invalidate_resource_list_cache(self) -> None:
        """Invalidate the entries in the resource list cache."""
        logger.debug(
            f"Invalidating resource_list_cache for server '{self.config.name}'"
        )
        async with self.lock:
            if self.resource_list_cache:
                self.resource_list_cache.clear()
                logger.debug(
                    f"Invalidated resource_list_cache for server '{self.config.name}'"
                )

    async def invalidate_resource_contents_cache(self) -> None:
        """Invalidate the entries in the resource contents cache."""
        logger.debug(
            f"Invalidating resource_contents_cache for server '{self.config.name}'."
        )
        async with self.lock:
            if self.resource_contents_cache:
                self.resource_contents_cache.clear()
                logger.debug(
                    f"Invalidated resource_contents_cache for server '{self.config.name}'"
                )

    async def invalidate_resource_contents_cache_entry(self, key: str) -> None:
        """Invalidate a single entry in the resource contents cache."""
        logger.debug(
            f"Attempting to clear entry with key: {key} from resource_contents_cache for server '{self.config.name}'"
        )
        async with self.lock:
            if self.resource_contents_cache:
                try:
                    self.resource_contents_cache.pop(key, None)
                    logger.debug(
                        f"Cleared entry with key {key} from resource_contents_cache for server '{self.config.name}'"
                    )
                except Exception as e:
                    logger.debug(
                        f"No entry for key {key} found in resource_contents_cache for server '{self.config.name}'. Ignoring. (Exception was: {e})"
                    )
                    return  # do nothing

    async def disconnect(self) -> None:
        """If previously connected via `self._connect()`, tear it down."""
        async with self.lock:
            if self.session_stack:
                # manually __aexit__
                await self.session_stack.aclose()
                self.client_session = None  # remove the reference

    # --- Private Methods ---
    @asynccontextmanager
    async def _safe_transport_ctx(self, cm: Any):
        """Enter the real transport ctxmg, yield its value, but on __aexit__ always swallow all errors."""
        val = await cm.__aenter__()
        try:
            yield val
        finally:
            try:
                await cm.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(
                    f"Suppressed transport-ctx exit error "
                    f"for server '{self.config.name}': {e!r}"
                )

    async def _create_session(self) -> None:
        """Create and hold onto a single ClientSession + ExitStack."""
        logger.debug(f"Creating Client Session for server '{self.config.name}'")
        if self.session_stack:
            await self.session_stack.aclose()
        if self.client_session:
            self.client_session = None
        stack = AsyncExitStack()
        await stack.__aenter__()

        server_params = self.config.connection_config.connection_parameters

        # Single Hook
        transport_ctx = await self.create_transport(
            server_params, self.additional_params
        )
        safe_transport = self._safe_transport_ctx(transport_ctx)
        result = await stack.enter_async_context(safe_transport)

        # support old (read, write) or new (read, write, get_sesssion_id_callback)
        read: MemoryObjectReceiveStream | None = None
        write: MemoryObjectSendStream | None = None
        get_session_id_callback: GetSessionIdCallback | None = None
        if isinstance(result, tuple) and len(result) == 2:
            # old type
            read, write = result
            get_session_id_callback = None
        elif isinstance(result, tuple) and len(result) == 3:
            # new type
            read, write, get_session_id_callback = result
        else:
            raise RuntimeError(
                f"create_transport returned unexpected tuple of {result}"
            )

        if read is None or write is None:
            raise RuntimeError(
                f"create_transport did not create any read or write streams."
            )

        read_timeout = self.config.connection_config.read_timeout_seconds

        if (
            self.additional_params
            and "read_timeout_seconds" in self.additional_params
        ):
            read_timeout = self.additional_params.get(
                "read_timeout_seconds", read_timeout
            )

        timeout_seconds = (
            read_timeout
            if isinstance(read_timeout, timedelta)
            else timedelta(seconds=float(read_timeout))
        )

        # TODO: get_session_id_callback is currently ignored.

        session = await stack.enter_async_context(
            ClientSession(
                read_stream=read,
                write_stream=write,
                read_timeout_seconds=timeout_seconds,
                list_roots_callback=self.list_roots_callback,
                message_handler=self.message_handler,
                sampling_callback=self.sampling_callback,
                logging_callback=self.logging_callback,
            )
        )
        logger.debug(f"Created Client Session for server '{self.config.name}'")
        # store for reuse
        self.session_stack = stack
        self.client_session = session

    async def _connect(self, retries: int | None = None) -> ClientSession:
        """Connect to an MCP Server and set self.client_session to ClientSession.

        Establish the transport and keep it open.
        """
        async with self.lock:
            # if already connected, return it
            if self.client_session:
                logger.debug(
                    f"Client Session for Server '{self.config.name}' exists and is healthy."
                )
                return self.client_session

            else:
                logger.debug(
                    f"Client Session for Server '{self.config.name}' does not exist yet. Connecting..."
                )
                await self._create_session()

            if not self.connected_server_capabilities:
                # This means we never asked the server to initialize the connection.
                await self._perform_initial_handshake()
        return self.client_session

    async def _perform_initial_handshake(self) -> None:
        """Tell the server who we are, what capabilities we have, and what roots we're interested in."""
        # 1) do the LSP-style initialize handshake
        logger.debug(
            f"Performing intialize handshake with server '{self.config.name}'"
        )
        init: InitializeResult = await self.client_session.initialize()

        self.connected_server_capabilities = init

        init_report = f"Server: '{self.config.name}': Protocol-Version: {init.protocolVersion}, Instructions: {init.instructions or 'No specific instructions'}, MCP_Implementation: Name: {init.serverInfo.name}, Version: {init.serverInfo.version}, Capabilities: {init.capabilities}"

        logger.debug(init_report)

        # 2) if we already know our current roots, notify the server
        #    so that it will follow up with a ListRootsRequest
        if self.current_roots and self.config.feature_config.roots_enabled:
            await self.client_session.send_roots_list_changed()

        # 3) Tell the server, what logging level we would like to use
        try:
            await self.client_session.set_logging_level(
                level=self.config.connection_config.server_logging_level
            )
        except McpError as e:
            logger.warning(
                f"Trying to set logging level for server '{self.config.name}' resulted in Exception: {e}"
            )

    async def _ensure_connected(self) -> None:
        # if we've never connected, then connect.
        if not self.client_session:
            await self._connect()
            return

        # otherwise, ping and reconnect on error
        try:
            await self.client_session.send_ping()
        except Exception as e:
            logger.warning(
                f"Session to '{self.config.name}' died, reconnecting. Exception was: {e}"
            )
            await self.disconnect()
            await self._connect()

    async def _get_client_session(self) -> ClientSession | None:
        """Lazily start one session and reuse it forever (until closed)."""
        async with self.lock:
            if self.client_session is None:
                await self._create_session()

        return self.client_session
