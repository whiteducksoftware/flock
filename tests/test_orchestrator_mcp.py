"""Test MCP integration with Flock."""

import pytest

from flock.core import Flock
from flock.mcp import StdioServerParameters
from flock.mcp.manager import FlockMCPClientManager


def test_orchestrator_has_mcp_properties():
    """Test orchestrator has MCP-related properties."""
    orch = Flock()
    assert hasattr(orch, "_mcp_configs")
    assert hasattr(orch, "_mcp_manager")
    assert orch._mcp_configs == {}
    assert orch._mcp_manager is None


def test_add_mcp_basic():
    """Test basic MCP server registration."""
    orch = Flock()

    result = orch.add_mcp(
        name="test_server",
        connection_params=StdioServerParameters(command="echo", args=["test"]),
    )

    # Should return self for chaining
    assert result is orch

    # Should store config
    assert "test_server" in orch._mcp_configs
    config = orch._mcp_configs["test_server"]
    assert config.name == "test_server"
    assert config.connection_config.transport_type == "stdio"


def test_add_mcp_duplicate_name_fails():
    """Test that duplicate server names are rejected."""
    orch = Flock()

    orch.add_mcp(
        name="duplicate",
        connection_params=StdioServerParameters(command="echo", args=["1"]),
    )

    with pytest.raises(ValueError, match="already registered"):
        orch.add_mcp(
            name="duplicate",
            connection_params=StdioServerParameters(command="echo", args=["2"]),
        )


def test_add_mcp_with_tool_whitelist():
    """Test MCP registration with tool whitelist."""
    orch = Flock()

    orch.add_mcp(
        name="restricted_server",
        connection_params=StdioServerParameters(command="echo", args=["test"]),
        tool_whitelist=["tool1", "tool2"],
    )

    config = orch._mcp_configs["restricted_server"]
    assert config.feature_config.tool_whitelist == ["tool1", "tool2"]


def test_add_mcp_method_chaining():
    """Test that add_mcp supports method chaining."""
    orch = Flock()

    result = orch.add_mcp(
        name="server1",
        connection_params=StdioServerParameters(command="echo", args=["1"]),
    ).add_mcp(
        name="server2",
        connection_params=StdioServerParameters(command="echo", args=["2"]),
    )

    assert result is orch
    assert "server1" in orch._mcp_configs
    assert "server2" in orch._mcp_configs


def test_get_mcp_manager_lazy_init():
    """Test that MCP manager is lazily initialized."""
    orch = Flock()

    orch.add_mcp(
        name="test_server",
        connection_params=StdioServerParameters(command="echo", args=["test"]),
    )

    # Manager should not exist yet
    assert orch._mcp_manager is None

    # First call creates manager
    manager1 = orch.get_mcp_manager()
    assert isinstance(manager1, FlockMCPClientManager)
    assert orch._mcp_manager is manager1

    # Second call returns same instance
    manager2 = orch.get_mcp_manager()
    assert manager2 is manager1


def test_get_mcp_manager_without_servers_fails():
    """Test that get_mcp_manager fails if no servers registered."""
    orch = Flock()

    with pytest.raises(RuntimeError, match="No MCP servers registered"):
        orch.get_mcp_manager()


@pytest.mark.asyncio
async def test_orchestrator_shutdown_cleans_mcp():
    """Test that orchestrator shutdown cleans up MCP connections."""
    orch = Flock()

    orch.add_mcp(
        name="test_server",
        connection_params=StdioServerParameters(command="echo", args=["test"]),
    )

    # Initialize manager
    orch.get_mcp_manager()
    assert orch._mcp_manager is not None

    # Shutdown should clean up
    await orch.shutdown()
    assert orch._mcp_manager is None
