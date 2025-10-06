"""Comprehensive test suite for FlockMCPClient."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from anyio import ClosedResourceError
from cachetools import TTLCache
from mcp import (
    ClientSession,
    InitializeResult,
    ListToolsResult,
    McpError,
    ServerCapabilities,
)
from mcp.types import CallToolResult, Implementation, TextContent, Tool

from flock.mcp.client import FlockMCPClient
from flock.mcp.config import (
    FlockMCPCachingConfiguration,
    FlockMCPCallbackConfiguration,
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
    FlockMCPFeatureConfiguration,
)
from flock.mcp.tool import FlockMCPTool
from flock.mcp.types import MCPRoot, StdioServerParameters


class MockFlockMCPClient(FlockMCPClient):
    """Test implementation of FlockMCPClient for testing purposes."""

    async def create_transport(
        self,
        params: StdioServerParameters,
        additional_params: dict[str, object] | None = None,
    ):
        """Mock transport for testing."""
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=(mock_read_stream, mock_write_stream))
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        return mock_cm


@pytest.fixture
def mock_config():
    """Create a mock MCP configuration for testing."""
    return FlockMCPConfiguration(
        name="test_server",
        connection_config=FlockMCPConnectionConfiguration(
            max_retries=3,
            connection_parameters=StdioServerParameters(
                command="test_command",
                args=["arg1", "arg2"],
            ),
            transport_type="stdio",
            mount_points=None,
            read_timeout_seconds=300,
            server_logging_level="error",
        ),
        caching_config=FlockMCPCachingConfiguration(
            tool_cache_max_size=100,
            tool_cache_max_ttl=60,
            tool_result_cache_max_size=1000,
            tool_result_cache_max_ttl=20,
            resource_contents_cache_max_size=10,
            resource_contents_cache_max_ttl=300,
            resource_list_cache_max_size=10,
            resource_list_cache_max_ttl=100,
        ),
        feature_config=FlockMCPFeatureConfiguration(
            tools_enabled=True,
            roots_enabled=True,
            sampling_enabled=True,
            prompts_enabled=True,
            tool_whitelist=None,
        ),
        callback_config=FlockMCPCallbackConfiguration(
            logging_callback=None,
            message_handler=None,
            list_roots_callback=None,
            sampling_callback=None,
        ),
    )


@pytest.fixture
def mcp_client(mock_config):
    """Create a test MCP client instance."""
    return MockFlockMCPClient(config=mock_config)


@pytest.fixture
def mock_client_session():
    """Create a mock ClientSession for testing."""
    session = AsyncMock(spec=ClientSession)
    session.initialize = AsyncMock(
        return_value=InitializeResult(
            protocolVersion="2024-11-05",
            serverInfo=Implementation(name="test_server", version="1.0.0"),
            capabilities=ServerCapabilities(),
        )
    )
    session.list_tools = AsyncMock(
        return_value=ListToolsResult(
            tools=[
                Tool(
                    name="test_tool",
                    description="A test tool",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        )
    )
    session.call_tool = AsyncMock(
        return_value=CallToolResult(content=[TextContent(type="text", text="Test result")])
    )
    session.send_ping = AsyncMock()
    session.send_roots_list_changed = AsyncMock()
    session.set_logging_level = AsyncMock()
    return session


@pytest.fixture
def mcp_client(mock_config):
    """Create a test MCP client instance."""
    return MockFlockMCPClient(config=mock_config)


class TestClientInitialization:
    """Test client initialization and setup."""

    def test_client_initialization_with_defaults(self, mock_config):
        """Test client initialization with default parameters."""
        client = MockFlockMCPClient(config=mock_config)

        assert client.config == mock_config
        assert client.tool_cache is not None
        assert client.tool_result_cache is not None
        assert client.resource_contents_cache is not None
        assert client.resource_list_cache is not None
        assert client.client_session is None
        assert client.connected_server_capabilities is None
        assert client.logging_callback is not None
        assert client.message_handler is not None
        assert client.list_roots_callback is not None
        assert client.sampling_callback is not None

    def test_client_initialization_with_custom_parameters(self, mock_config):
        """Test client initialization with custom parameters."""
        custom_tool_cache = TTLCache(maxsize=50, ttl=30)
        custom_roots = [MCPRoot(uri="file:///test", name="test_root")]

        client = MockFlockMCPClient(
            config=mock_config,
            tool_cache=custom_tool_cache,
            current_roots=custom_roots,
        )

        assert client.tool_cache == custom_tool_cache
        assert client.current_roots == custom_roots

    def test_client_initialization_with_config_roots(self, mock_config):
        """Test client initialization picks up roots from config."""
        config_roots = [MCPRoot(uri="file:///config", name="config_root")]
        mock_config.connection_config.mount_points = config_roots

        client = MockFlockMCPClient(config=mock_config)

        assert client.current_roots == config_roots

    def test_session_proxy_property(self, mcp_client):
        """Test session proxy property."""
        proxy = mcp_client.session
        assert proxy is not None
        assert hasattr(proxy, "_client")
        assert proxy._client == mcp_client


class TestSessionProxy:
    """Test the _SessionProxy auto-reconnect functionality."""

    @pytest.mark.asyncio
    async def test_session_proxy_successful_call(self, mcp_client, mock_client_session):
        """Test successful session proxy call."""
        mcp_client.client_session = mock_client_session

        proxy = mcp_client.session
        result = await proxy.list_tools()

        assert result == mock_client_session.list_tools.return_value
        mock_client_session.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_proxy_with_timeout_retry(self, mcp_client, mock_client_session, mocker):
        """Test session proxy retry on timeout."""
        mcp_client.client_session = mock_client_session

        # Mock timeout error that triggers retry
        import httpx

        timeout_error = McpError(error=MagicMock(code=httpx.codes.REQUEST_TIMEOUT))
        mock_client_session.list_tools.side_effect = timeout_error

        # Mock connection methods
        mcp_client._ensure_connected = AsyncMock()
        mcp_client.disconnect = AsyncMock()
        mcp_client._connect = AsyncMock(return_value=mock_client_session)

        proxy = mcp_client.session

        # Should retry and then return None (when max retries exceeded)
        result = await proxy.list_tools()

        # Verify retry behavior occurred
        assert mcp_client._ensure_connected.call_count >= 2
        assert result is None  # Returns None after max retries exceeded

    @pytest.mark.asyncio
    async def test_session_proxy_with_broken_pipe_error(self, mcp_client, mock_client_session):
        """Test session proxy retry on BrokenPipeError."""
        mcp_client.client_session = mock_client_session

        # Mock BrokenPipeError that triggers retry
        mock_client_session.list_tools.side_effect = BrokenPipeError()

        # Mock connection methods
        mcp_client._ensure_connected = AsyncMock()
        mcp_client.disconnect = AsyncMock()
        mcp_client._connect = AsyncMock(return_value=mock_client_session)

        proxy = mcp_client.session

        # Should retry and then return None (when max retries exceeded)
        result = await proxy.list_tools()

        # Verify retry behavior occurred
        assert mcp_client._ensure_connected.call_count >= 2
        assert result is None  # Returns None after max retries exceeded

    @pytest.mark.asyncio
    async def test_session_proxy_max_retries_exceeded(self, mcp_client, mock_client_session):
        """Test session proxy when max retries are exceeded."""
        mcp_client.client_session = mock_client_session
        mcp_client.config.connection_config.max_retries = 1

        # Mock persistent failure
        mock_client_session.list_tools.side_effect = BrokenPipeError()

        # Mock connection methods
        mcp_client._ensure_connected = AsyncMock()
        mcp_client.disconnect = AsyncMock()
        mcp_client._connect = AsyncMock(side_effect=Exception("Connection failed"))

        proxy = mcp_client.session
        result = await proxy.list_tools()

        assert result is None

    @pytest.mark.asyncio
    async def test_session_proxy_mcp_error_no_retry(self, mcp_client, mock_client_session):
        """Test session proxy doesn't retry on application-level MCP errors."""
        mcp_client.client_session = mock_client_session

        # Mock application-level MCP error (not timeout)
        app_error = McpError(error=MagicMock(code=400))
        mock_client_session.list_tools.side_effect = app_error

        proxy = mcp_client.session
        result = await proxy.list_tools()

        assert result is None
        # Should not retry on application errors
        assert mock_client_session.list_tools.call_count == 1


class TestToolOperations:
    """Test tool listing and execution operations."""

    @pytest.mark.asyncio
    async def test_get_tools_enabled(self, mcp_client, mock_client_session):
        """Test getting tools when tools are enabled."""
        mcp_client.client_session = mock_client_session
        mcp_client._ensure_connected = AsyncMock()

        tools = await mcp_client.get_tools(agent_id="test_agent", run_id="test_run")

        assert len(tools) == 1
        assert isinstance(tools[0], FlockMCPTool)
        mock_client_session.list_tools.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_tools_disabled(self, mcp_client):
        """Test getting tools when tools are disabled."""
        mcp_client.config.feature_config.tools_enabled = False

        tools = await mcp_client.get_tools(agent_id="test_agent", run_id="test_run")

        assert tools == []

    @pytest.mark.asyncio
    async def test_get_tools_caching(self, mcp_client, mock_client_session):
        """Test that tools are cached."""
        mcp_client.client_session = mock_client_session
        mcp_client._ensure_connected = AsyncMock()

        # Call twice
        tools1 = await mcp_client.get_tools(agent_id="test_agent", run_id="test_run")
        tools2 = await mcp_client.get_tools(agent_id="test_agent", run_id="test_run")

        # Should only call list_tools once due to caching
        mock_client_session.list_tools.assert_called_once()
        assert tools1 == tools2

    @pytest.mark.asyncio
    async def test_call_tool_success(self, mcp_client, mock_client_session):
        """Test successful tool call."""
        mcp_client.client_session = mock_client_session
        mcp_client._ensure_connected = AsyncMock()

        result = await mcp_client.call_tool(
            agent_id="test_agent",
            run_id="test_run",
            name="test_tool",
            arguments={"param": "value"},
        )

        assert result == mock_client_session.call_tool.return_value
        mock_client_session.call_tool.assert_called_once_with(
            name="test_tool",
            arguments={"param": "value"},
        )

    @pytest.mark.asyncio
    async def test_call_tool_caching(self, mcp_client, mock_client_session):
        """Test that tool results are cached."""
        mcp_client.client_session = mock_client_session
        mcp_client._ensure_connected = AsyncMock()

        # Call twice with same parameters
        result1 = await mcp_client.call_tool(
            agent_id="test_agent",
            run_id="test_run",
            name="test_tool",
            arguments={"param": "value"},
        )
        result2 = await mcp_client.call_tool(
            agent_id="test_agent",
            run_id="test_run",
            name="test_tool",
            arguments={"param": "value"},
        )

        # Should only call call_tool once due to caching
        mock_client_session.call_tool.assert_called_once()
        assert result1 == result2


class TestRootsOperations:
    """Test roots management operations."""

    @pytest.mark.asyncio
    async def test_get_server_name(self, mcp_client):
        """Test getting server name."""
        name = await mcp_client.get_server_name()
        assert name == mcp_client.config.name

    @pytest.mark.asyncio
    async def test_get_roots(self, mcp_client):
        """Test getting current roots."""
        test_roots = [MCPRoot(uri="file:///test", name="test_root")]
        mcp_client.current_roots = test_roots

        roots = await mcp_client.get_roots()
        assert roots == test_roots

    @pytest.mark.asyncio
    async def test_set_roots(self, mcp_client, mock_client_session):
        """Test setting new roots."""
        mcp_client.client_session = mock_client_session
        new_roots = [MCPRoot(uri="file:///new", name="new_root")]

        await mcp_client.set_roots(new_roots)

        assert mcp_client.current_roots == new_roots
        mock_client_session.send_roots_list_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_roots_with_mcp_error(self, mcp_client, mock_client_session, mocker):
        """Test setting roots with MCP error handling."""
        mcp_client.client_session = mock_client_session
        mock_client_session.send_roots_list_changed.side_effect = McpError(error=MagicMock())

        # Mock logger
        mock_logger = mocker.patch("flock.mcp.client.logger")

        new_roots = [MCPRoot(uri="file:///new", name="new_root")]
        await mcp_client.set_roots(new_roots)

        assert mcp_client.current_roots == new_roots
        mock_logger.warning.assert_called_once()


class TestCacheInvalidation:
    """Test cache invalidation operations."""

    @pytest.mark.asyncio
    async def test_invalidate_tool_cache(self, mcp_client):
        """Test invalidating tool cache."""
        # Add something to cache
        mcp_client.tool_cache["test_key"] = "test_value"

        await mcp_client.invalidate_tool_cache()

        assert len(mcp_client.tool_cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_tool_cache_when_empty(self, mcp_client):
        """Test invalidating empty tool cache."""
        mcp_client.tool_cache = None

        # Should not raise an error
        await mcp_client.invalidate_tool_cache()

    @pytest.mark.asyncio
    async def test_invalidate_resource_list_cache(self, mcp_client):
        """Test invalidating resource list cache."""
        # Add something to cache
        mcp_client.resource_list_cache["test_key"] = "test_value"

        await mcp_client.invalidate_resource_list_cache()

        assert len(mcp_client.resource_list_cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_resource_contents_cache(self, mcp_client):
        """Test invalidating resource contents cache."""
        # Add something to cache
        mcp_client.resource_contents_cache["test_key"] = "test_value"

        await mcp_client.invalidate_resource_contents_cache()

        assert len(mcp_client.resource_contents_cache) == 0

    @pytest.mark.asyncio
    async def test_invalidate_resource_contents_cache_entry(self, mcp_client):
        """Test invalidating specific resource contents cache entry."""
        # Add multiple entries to cache
        mcp_client.resource_contents_cache["key1"] = "value1"
        mcp_client.resource_contents_cache["key2"] = "value2"

        await mcp_client.invalidate_resource_contents_cache_entry("key1")

        assert "key1" not in mcp_client.resource_contents_cache
        assert "key2" in mcp_client.resource_contents_cache

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_cache_entry(self, mcp_client, mocker):
        """Test invalidating non-existent cache entry."""
        # Mock logger
        mock_logger = mocker.patch("flock.mcp.client.logger")

        await mcp_client.invalidate_resource_contents_cache_entry("nonexistent_key")

        # Should log debug message about no entry found
        mock_logger.debug.assert_called()


class TestConnectionManagement:
    """Test connection management operations."""

    @pytest.mark.asyncio
    async def test_disconnect(self, mcp_client):
        """Test disconnection."""
        mock_session_stack = AsyncMock()
        mcp_client.session_stack = mock_session_stack
        mcp_client.client_session = AsyncMock()

        await mcp_client.disconnect()

        mock_session_stack.aclose.assert_called_once()
        assert mcp_client.client_session is None

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, mcp_client, mock_client_session):
        """Test connecting when already connected."""
        mcp_client.client_session = mock_client_session

        result = await mcp_client._connect()

        assert result == mock_client_session

    @pytest.mark.asyncio
    async def test_create_session(self, mcp_client, mocker):
        """Test session creation."""
        # Mock the transport creation
        mock_transport = AsyncMock()
        mock_transport.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_transport.__aexit__ = AsyncMock(return_value=None)
        mcp_client.create_transport = AsyncMock(return_value=mock_transport)

        # Mock ClientSession
        mock_session = AsyncMock()
        mock_client_session_class = mocker.patch("flock.mcp.client.ClientSession")
        mock_client_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        await mcp_client._create_session()

        assert mcp_client.client_session == mock_session
        assert mcp_client.session_stack is not None

    @pytest.mark.asyncio
    async def test_create_session_with_additional_params(self, mcp_client, mocker):
        """Test session creation with additional parameters."""
        mcp_client.additional_params = {"read_timeout_seconds": 30}

        # Mock the transport creation
        mock_transport = AsyncMock()
        mock_transport.__aenter__ = AsyncMock(return_value=(AsyncMock(), AsyncMock()))
        mock_transport.__aexit__ = AsyncMock(return_value=None)
        mcp_client.create_transport = AsyncMock(return_value=mock_transport)

        # Mock ClientSession
        mock_session = AsyncMock()
        mock_client_session_class = mocker.patch("flock.mcp.client.ClientSession")
        mock_client_session_class.return_value.__aenter__ = AsyncMock(return_value=mock_session)

        await mcp_client._create_session()

        # Should use timeout from additional_params
        mock_client_session_class.assert_called_once()
        call_args = mock_client_session_class.call_args
        assert call_args[1]["read_timeout_seconds"] == timedelta(seconds=30)

    @pytest.mark.asyncio
    async def test_perform_initial_handshake(self, mcp_client, mock_client_session):
        """Test initial handshake with server."""
        mcp_client.client_session = mock_client_session
        mcp_client.current_roots = [MCPRoot(uri="file:///test", name="test_root")]

        await mcp_client._perform_initial_handshake()

        mock_client_session.initialize.assert_called_once()
        mock_client_session.send_roots_list_changed.assert_called_once()
        mock_client_session.set_logging_level.assert_called_once()

    @pytest.mark.asyncio
    async def test_perform_initial_handshake_logging_error(
        self, mcp_client, mock_client_session, mocker
    ):
        """Test initial handshake with logging level error."""
        mcp_client.client_session = mock_client_session
        mock_client_session.set_logging_level.side_effect = McpError(error=MagicMock())

        # Mock logger
        mock_logger = mocker.patch("flock.mcp.client.logger")

        await mcp_client._perform_initial_handshake()

        mock_client_session.initialize.assert_called_once()
        mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connected_no_session(self, mcp_client):
        """Test _ensure_connected when no session exists."""
        mcp_client._connect = AsyncMock()

        await mcp_client._ensure_connected()

        mcp_client._connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connected_existing_session_ping_success(
        self, mcp_client, mock_client_session
    ):
        """Test _ensure_connected with existing healthy session."""
        mcp_client.client_session = mock_client_session

        await mcp_client._ensure_connected()

        mock_client_session.send_ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_connected_existing_session_ping_failure(
        self, mcp_client, mock_client_session
    ):
        """Test _ensure_connected with existing session that fails ping."""
        mcp_client.client_session = mock_client_session
        mock_client_session.send_ping.side_effect = Exception("Connection lost")

        mcp_client.disconnect = AsyncMock()
        mcp_client._connect = AsyncMock(return_value=mock_client_session)

        await mcp_client._ensure_connected()

        mock_client_session.send_ping.assert_called_once()
        mcp_client.disconnect.assert_called_once()
        mcp_client._connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_session_lazy_creation(self, mcp_client, mocker):
        """Test lazy client session creation."""
        mcp_client._create_session = AsyncMock()

        session = await mcp_client._get_client_session()

        mcp_client._create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_session_existing(self, mcp_client, mock_client_session):
        """Test getting existing client session."""
        mcp_client.client_session = mock_client_session

        session = await mcp_client._get_client_session()

        assert session == mock_client_session


class TestSafeTransportContext:
    """Test the safe transport context manager."""

    @pytest.mark.asyncio
    async def test_safe_transport_ctx_success(self, mcp_client):
        """Test safe transport context with successful operation."""
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value="test_value")
        mock_cm.__aexit__ = AsyncMock(return_value=None)

        async with mcp_client._safe_transport_ctx(mock_cm) as value:
            assert value == "test_value"

        mock_cm.__aenter__.assert_called_once()
        mock_cm.__aexit__.assert_called_once()

    @pytest.mark.asyncio
    async def test_safe_transport_ctx_exit_error(self, mcp_client, mocker):
        """Test safe transport context with exit error."""
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value="test_value")
        mock_cm.__aexit__ = AsyncMock(side_effect=Exception("Exit error"))

        # Mock logger
        mock_logger = mocker.patch("flock.mcp.client.logger")

        async with mcp_client._safe_transport_ctx(mock_cm) as value:
            assert value == "test_value"

        # Should suppress the error and log it
        mock_logger.debug.assert_called_once()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_model_config(self):
        """Test model configuration."""
        assert FlockMCPClient.model_config.get("arbitrary_types_allowed") is True
        assert FlockMCPClient.model_config.get("extra") == "allow"

    @pytest.mark.asyncio
    async def test_create_transport_unexpected_result(self, mcp_client):
        """Test create_transport with unexpected result format."""
        mock_transport = AsyncMock()
        mock_transport.__aenter__ = AsyncMock(return_value="unexpected_result")
        mcp_client.create_transport = AsyncMock(return_value=mock_transport)

        with pytest.raises(RuntimeError, match="create_transport returned unexpected tuple"):
            await mcp_client._create_session()

    @pytest.mark.asyncio
    async def test_create_transport_missing_streams(self, mcp_client):
        """Test create_transport with missing streams."""
        mock_transport = AsyncMock()
        mock_transport.__aenter__ = AsyncMock(return_value=(None, None))
        mcp_client.create_transport = AsyncMock(return_value=mock_transport)

        with pytest.raises(
            RuntimeError, match="create_transport did not create any read or write streams"
        ):
            await mcp_client._create_session()

    @pytest.mark.asyncio
    async def test_session_proxy_closed_resource_error(self, mcp_client, mock_client_session):
        """Test session proxy with ClosedResourceError."""
        mcp_client.client_session = mock_client_session
        mock_client_session.list_tools.side_effect = ClosedResourceError()

        # Mock connection methods
        mcp_client._ensure_connected = AsyncMock()
        mcp_client.disconnect = AsyncMock()
        mcp_client._connect = AsyncMock(return_value=mock_client_session)

        proxy = mcp_client.session
        result = await proxy.list_tools()

        assert result is None

    @pytest.mark.asyncio
    async def test_connect_without_capabilities(self, mcp_client, mock_client_session):
        """Test _connect when server capabilities are not set."""
        # Don't set client_session initially - let _connect create it
        mcp_client.connected_server_capabilities = None

        # Mock session creation to set the client_session attribute
        async def mock_create_session():
            mcp_client.client_session = mock_client_session

        mcp_client._create_session = mock_create_session
        mcp_client._perform_initial_handshake = AsyncMock()

        result = await mcp_client._connect()

        mcp_client._perform_initial_handshake.assert_called_once()
        assert result == mock_client_session
