"""Comprehensive test suite for FlockMCPClientManager.

This module tests the MCP client manager functionality including:
- Manager initialization and configuration
- Server registration and management
- Client lifecycle and connection pooling
- Per-(agent_id, run_id) isolation
- Error handling and graceful degradation
- Multiple server handling
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from flock.mcp.config import (
    FlockMCPConfiguration,
    FlockMCPConnectionConfiguration,
    FlockMCPFeatureConfiguration,
)
from flock.mcp.manager import FlockMCPClientManager
from flock.mcp.tool import FlockMCPTool
from flock.mcp.types import (
    SseServerParameters,
    StdioServerParameters,
    StreamableHttpServerParameters,
)


@pytest.fixture
def mock_connection_config():
    """Create a mock connection configuration."""
    params = StdioServerParameters(command="echo", args=["test"])
    return FlockMCPConnectionConfiguration(
        transport_type="stdio",
        connection_parameters=params,
    )


@pytest.fixture
def mock_feature_config():
    """Create a mock feature configuration."""
    return FlockMCPFeatureConfiguration(
        tools_enabled=True,
        prompts_enabled=True,
        sampling_enabled=True,
    )


@pytest.fixture
def mock_mcp_config(mock_connection_config, mock_feature_config):
    """Create a mock MCP configuration."""
    return FlockMCPConfiguration(
        name="test_server",
        connection_config=mock_connection_config,
        feature_config=mock_feature_config,
    )


@pytest.fixture
def mock_configs(mock_mcp_config):
    """Create a dictionary of mock configurations."""
    return {
        "test_server": mock_mcp_config,
    }


@pytest.fixture
def mock_client():
    """Create a mock MCP client."""
    client = AsyncMock()
    client.disconnect = AsyncMock()
    client.get_tools = AsyncMock(
        return_value=[Mock(spec=FlockMCPTool, name="test_tool", description="Test tool")]
    )
    return client


@pytest.fixture
def manager(mock_configs):
    """Create a manager instance with mock configurations."""
    return FlockMCPClientManager(mock_configs)


class TestFlockMCPClientManager:
    """Test suite for FlockMCPClientManager."""

    def test_manager_initialization(self, mock_configs):
        """Test manager initialization with configurations."""
        manager = FlockMCPClientManager(mock_configs)

        assert manager._configs == mock_configs
        assert manager._pool == {}
        assert isinstance(manager._lock, asyncio.Lock)

    def test_manager_initialization_empty_configs(self):
        """Test manager initialization with empty configurations."""
        manager = FlockMCPClientManager({})

        assert manager._configs == {}
        assert manager._pool == {}
        assert isinstance(manager._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_get_client_server_not_registered(self, manager):
        """Test get_client raises ValueError for unregistered server."""
        with pytest.raises(ValueError, match="MCP server 'unknown' not registered"):
            await manager.get_client("unknown", "agent_1", "run_1")

    @pytest.mark.asyncio
    async def test_get_client_creates_new_client(self, manager, mocker):
        """Test get_client creates a new client when none exists."""
        # Mock the client class based on transport type
        mock_client_class = mocker.patch(
            "flock.mcp.servers.stdio.flock_stdio_server.FlockStdioClient",
            return_value=AsyncMock(),
        )
        mock_client_instance = mock_client_class.return_value
        mock_client_instance._connect = AsyncMock()

        client = await manager.get_client("test_server", "agent_1", "run_1")

        # Verify client was created and connected
        mock_client_class.assert_called_once()
        mock_client_instance._connect.assert_called_once()
        assert client == mock_client_instance

        # Verify client is stored in pool
        key = ("agent_1", "run_1")
        assert key in manager._pool
        assert "test_server" in manager._pool[key]
        assert manager._pool[key]["test_server"] == client

    @pytest.mark.asyncio
    async def test_get_client_returns_existing_client(self, manager, mock_client):
        """Test get_client returns existing client from pool."""
        # Manually add a client to the pool
        key = ("agent_1", "run_1")
        manager._pool[key] = {"test_server": mock_client}

        client = await manager.get_client("test_server", "agent_1", "run_1")

        assert client == mock_client

    @pytest.mark.asyncio
    async def test_get_client_different_transport_types(self, mocker):
        """Test get_client with different transport types."""
        configs = {}

        # Test stdio transport
        stdio_params = StdioServerParameters(command="echo")
        stdio_config = FlockMCPConfiguration(
            name="stdio_server",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="stdio",
                connection_parameters=stdio_params,
            ),
        )
        configs["stdio_server"] = stdio_config

        # Test sse transport
        sse_params = SseServerParameters(url="http://localhost:8080")
        sse_config = FlockMCPConfiguration(
            name="sse_server",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="sse",
                connection_parameters=sse_params,
            ),
        )
        configs["sse_server"] = sse_config

        # Note: Skip websocket transport since it's not properly supported in the current config validation

        # Test streamable_http transport
        http_params = StreamableHttpServerParameters(url="http://localhost:8082")
        http_config = FlockMCPConfiguration(
            name="http_server",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="streamable_http",
                connection_parameters=http_params,
            ),
        )
        configs["http_server"] = http_config

        manager = FlockMCPClientManager(configs)

        # Mock all client classes
        mock_stdio = mocker.patch(
            "flock.mcp.servers.stdio.flock_stdio_server.FlockStdioClient",
            return_value=AsyncMock(),
        )
        mock_sse = mocker.patch(
            "flock.mcp.servers.sse.flock_sse_server.FlockSSEClient", return_value=AsyncMock()
        )
        mock_http = mocker.patch(
            "flock.mcp.servers.streamable_http.flock_streamable_http_server.FlockStreamableHttpClient",
            return_value=AsyncMock(),
        )

        # Mock _connect for all clients
        mock_stdio.return_value._connect = AsyncMock()
        mock_sse.return_value._connect = AsyncMock()
        mock_http.return_value._connect = AsyncMock()

        # Test each transport type
        await manager.get_client("stdio_server", "agent_1", "run_1")
        await manager.get_client("sse_server", "agent_1", "run_1")
        await manager.get_client("http_server", "agent_1", "run_1")

        # Verify correct client classes were instantiated
        mock_stdio.assert_called_once()
        mock_sse.assert_called_once()
        mock_http.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_unsupported_transport_type(self):
        """Test get_client raises ValueError for unsupported transport type."""
        # Use "custom" transport type but the manager will still not handle it
        params = StdioServerParameters(command="echo")
        config = FlockMCPConfiguration(
            name="unsupported_server",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="custom",
                connection_parameters=params,
            ),
        )
        configs = {"unsupported_server": config}
        manager = FlockMCPClientManager(configs)

        with pytest.raises(ValueError, match="Unsupported transport type: custom"):
            await manager.get_client("unsupported_server", "agent_1", "run_1")

    @pytest.mark.asyncio
    async def test_get_tools_for_agent_success(self, manager, mock_client, mocker):
        """Test successful tool retrieval for an agent."""
        # Mock get_client to return our mock client
        mocker.patch.object(manager, "get_client", return_value=mock_client)

        mock_tool = Mock(spec=FlockMCPTool)
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        mock_client.get_tools.return_value = [mock_tool]

        tools = await manager.get_tools_for_agent("agent_1", "run_1", {"test_server"})

        # Verify tool namespacing
        assert "test_server__test_tool" in tools
        assert tools["test_server__test_tool"]["server_name"] == "test_server"
        assert tools["test_server__test_tool"]["original_name"] == "test_tool"
        assert tools["test_server__test_tool"]["tool"] == mock_tool
        assert tools["test_server__test_tool"]["client"] == mock_client

        # Verify get_client was called
        manager.get_client.assert_called_once_with(
            "test_server", "agent_1", "run_1", mount_points=None
        )

    @pytest.mark.asyncio
    async def test_get_tools_for_agent_graceful_degradation(self, manager, mocker):
        """Test graceful degradation when server fails to load tools."""
        # Mock get_client to raise an exception
        mocker.patch.object(manager, "get_client", side_effect=Exception("Connection failed"))

        tools = await manager.get_tools_for_agent("agent_1", "run_1", {"test_server"})

        # Should return empty tools but not raise exception
        assert tools == {}

    @pytest.mark.asyncio
    async def test_get_tools_for_agent_multiple_servers(self, manager, mocker):
        """Test tool retrieval from multiple servers."""
        # Create additional config
        params2 = StdioServerParameters(command="echo", args=["server2"])
        config2 = FlockMCPConfiguration(
            name="test_server2",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="stdio",
                connection_parameters=params2,
            ),
        )
        manager._configs["test_server2"] = config2

        # Create mock clients
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()

        mock_tool1 = Mock(spec=FlockMCPTool)
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        mock_tool2 = Mock(spec=FlockMCPTool)
        mock_tool2.name = "tool2"
        mock_tool2.description = "Tool 2"

        mock_client1.get_tools.return_value = [mock_tool1]
        mock_client2.get_tools.return_value = [mock_tool2]

        # Mock get_client to return different clients
        def mock_get_client(server_name, agent_id, run_id, mount_points=None):
            if server_name == "test_server":
                return mock_client1
            return mock_client2

        mocker.patch.object(manager, "get_client", side_effect=mock_get_client)

        tools = await manager.get_tools_for_agent(
            "agent_1", "run_1", {"test_server", "test_server2"}
        )

        # Verify both tools are namespaced correctly
        assert "test_server__tool1" in tools
        assert "test_server2__tool2" in tools
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_get_tools_for_agent_partial_failure(self, manager, mocker):
        """Test tool retrieval with partial server failures."""
        # Create additional config
        params2 = StdioServerParameters(command="echo", args=["server2"])
        config2 = FlockMCPConfiguration(
            name="test_server2",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="stdio",
                connection_parameters=params2,
            ),
        )
        manager._configs["test_server2"] = config2

        # Create mock clients
        mock_client1 = AsyncMock()
        mock_tool1 = Mock(spec=FlockMCPTool)
        mock_tool1.name = "tool1"
        mock_tool1.description = "Tool 1"
        mock_client1.get_tools.return_value = [mock_tool1]

        # Mock get_client - first succeeds, second fails
        def mock_get_client(server_name, agent_id, run_id, mount_points=None):
            if server_name == "test_server":
                return mock_client1
            raise Exception("Connection failed")

        mocker.patch.object(manager, "get_client", side_effect=mock_get_client)

        tools = await manager.get_tools_for_agent(
            "agent_1", "run_1", {"test_server", "test_server2"}
        )

        # Should only return tools from working server
        assert "test_server__tool1" in tools
        assert len(tools) == 1

    @pytest.mark.asyncio
    async def test_cleanup_run_success(self, manager, mock_client):
        """Test successful cleanup of a run."""
        # Add a client to the pool
        key = ("agent_1", "run_1")
        manager._pool[key] = {"test_server": mock_client}

        await manager.cleanup_run("agent_1", "run_1")

        # Verify client was disconnected and removed from pool
        mock_client.disconnect.assert_called_once()
        assert key not in manager._pool

    @pytest.mark.asyncio
    async def test_cleanup_run_not_exists(self, manager):
        """Test cleanup of a run that doesn't exist."""
        # Should not raise an exception
        await manager.cleanup_run("agent_1", "nonexistent_run")

        # Pool should remain empty
        assert manager._pool == {}

    @pytest.mark.asyncio
    async def test_cleanup_run_disconnect_error(self, manager, mock_client):
        """Test cleanup when client disconnect raises an error."""
        # Add a client to the pool
        key = ("agent_1", "run_1")
        manager._pool[key] = {"test_server": mock_client}

        # Mock disconnect to raise an exception
        mock_client.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))

        # Should not raise an exception
        await manager.cleanup_run("agent_1", "run_1")

        # Should still remove from pool despite error
        assert key not in manager._pool

    @pytest.mark.asyncio
    async def test_cleanup_run_multiple_clients(self, manager):
        """Test cleanup with multiple clients for a run."""
        # Add multiple clients to the pool
        key = ("agent_1", "run_1")
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        manager._pool[key] = {
            "test_server": mock_client1,
            "test_server2": mock_client2,
        }

        await manager.cleanup_run("agent_1", "run_1")

        # Verify all clients were disconnected
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_called_once()
        assert key not in manager._pool

    @pytest.mark.asyncio
    async def test_cleanup_all(self, manager):
        """Test cleanup of all connections."""
        # Add multiple runs with clients
        key1 = ("agent_1", "run_1")
        key2 = ("agent_2", "run_2")
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()
        mock_client3 = AsyncMock()

        manager._pool[key1] = {"test_server": mock_client1}
        manager._pool[key2] = {"test_server": mock_client2, "test_server2": mock_client3}

        await manager.cleanup_all()

        # Verify all clients were disconnected
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_called_once()
        mock_client3.disconnect.assert_called_once()

        # Pool should be empty
        assert manager._pool == {}

    @pytest.mark.asyncio
    async def test_cleanup_all_with_errors(self, manager):
        """Test cleanup all with some disconnect errors."""
        # Add clients with mixed success/failure
        key = ("agent_1", "run_1")
        mock_client1 = AsyncMock()
        mock_client2 = AsyncMock()

        mock_client1.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))

        manager._pool[key] = {
            "test_server": mock_client1,
            "test_server2": mock_client2,
        }

        # Should not raise an exception
        await manager.cleanup_all()

        # Both disconnect methods should be called
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_called_once()

        # Pool should be empty despite errors
        assert manager._pool == {}

    def test_list_servers(self, manager):
        """Test listing registered servers."""
        servers = manager.list_servers()

        assert "test_server" in servers
        assert servers["test_server"]["transport_type"] == "stdio"
        assert servers["test_server"]["tools_enabled"] is True
        assert servers["test_server"]["prompts_enabled"] is True
        assert servers["test_server"]["sampling_enabled"] is True

    def test_list_servers_empty(self):
        """Test listing servers when none are registered."""
        manager = FlockMCPClientManager({})
        servers = manager.list_servers()

        assert servers == {}

    def test_list_servers_multiple(self, mock_connection_config, mock_feature_config):
        """Test listing multiple servers with different configurations."""
        config1 = FlockMCPConfiguration(
            name="server1",
            connection_config=mock_connection_config,
            feature_config=FlockMCPFeatureConfiguration(
                tools_enabled=True,
                prompts_enabled=False,
                sampling_enabled=True,
            ),
        )

        sse_params = SseServerParameters(url="http://localhost:8080")
        config2 = FlockMCPConfiguration(
            name="server2",
            connection_config=FlockMCPConnectionConfiguration(
                transport_type="sse",
                connection_parameters=sse_params,
            ),
            feature_config=FlockMCPFeatureConfiguration(
                tools_enabled=False,
                prompts_enabled=True,
                sampling_enabled=False,
            ),
        )

        configs = {"server1": config1, "server2": config2}
        manager = FlockMCPClientManager(configs)

        servers = manager.list_servers()

        assert len(servers) == 2
        assert "server1" in servers
        assert "server2" in servers
        assert servers["server1"]["transport_type"] == "stdio"
        assert servers["server2"]["transport_type"] == "sse"
        assert servers["server1"]["tools_enabled"] is True
        assert servers["server2"]["tools_enabled"] is False

    @pytest.mark.asyncio
    async def test_per_agent_run_isolation(self, manager, mocker):
        """Test that different agents and runs get isolated clients."""

        # Create unique mock instances for each call
        def create_mock_client(config):
            mock_client = AsyncMock()
            mock_client._connect = AsyncMock()
            return mock_client

        mock_client_class = mocker.patch(
            "flock.mcp.servers.stdio.flock_stdio_server.FlockStdioClient",
            side_effect=create_mock_client,
        )

        # Get clients for different agent/run combinations
        client1 = await manager.get_client("test_server", "agent_1", "run_1")
        client2 = await manager.get_client("test_server", "agent_1", "run_2")
        client3 = await manager.get_client("test_server", "agent_2", "run_1")
        client4 = await manager.get_client("test_server", "agent_1", "run_1")  # Same as client1

        # Verify that separate clients were created for each unique (agent, run) pair
        assert mock_client_class.call_count == 3
        assert client1 == client4  # Same (agent, run) should reuse client
        assert client1 != client2
        assert client1 != client3
        assert client2 != client3

        # Verify pool structure
        assert ("agent_1", "run_1") in manager._pool
        assert ("agent_1", "run_2") in manager._pool
        assert ("agent_2", "run_1") in manager._pool
        assert len(manager._pool) == 3

    @pytest.mark.asyncio
    async def test_concurrent_access(self, manager, mocker):
        """Test concurrent access to manager methods."""
        # Create a single shared mock client
        shared_mock_client = AsyncMock()
        shared_mock_client._connect = AsyncMock()

        mock_client_class = mocker.patch(
            "flock.mcp.servers.stdio.flock_stdio_server.FlockStdioClient",
            return_value=shared_mock_client,
        )

        async def get_client_task():
            return await manager.get_client("test_server", "agent_1", "run_1")

        # Run multiple concurrent requests
        tasks = [get_client_task() for _ in range(5)]
        clients = await asyncio.gather(*tasks)

        # All should get the same client instance
        assert all(client == clients[0] for client in clients)

        # Client should only be created once
        assert mock_client_class.call_count == 1

    @pytest.mark.asyncio
    async def test_lock_contention(self, manager, mocker):
        """Test behavior under lock contention."""

        # Create unique mock instances for each call
        def create_mock_client(config):
            mock_client = AsyncMock()

            # Make _connect slow to simulate contention
            async def slow_connect():
                await asyncio.sleep(0.01)  # Reduced sleep time for faster tests

            mock_client._connect = AsyncMock(side_effect=slow_connect)
            return mock_client

        mock_client_class = mocker.patch(
            "flock.mcp.servers.stdio.flock_stdio_server.FlockStdioClient",
            side_effect=create_mock_client,
        )

        async def get_client_task(agent_id, run_id):
            return await manager.get_client("test_server", agent_id, run_id)

        # Run concurrent requests for different agents/runs
        tasks = [
            get_client_task("agent_1", "run_1"),
            get_client_task("agent_2", "run_1"),
            get_client_task("agent_1", "run_2"),
        ]
        clients = await asyncio.gather(*tasks)

        # Should create 3 separate clients
        assert len(set(clients)) == 3
        assert mock_client_class.call_count == 3
