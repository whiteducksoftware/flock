"""Test MCP integration with Agent."""

import pytest

from flock.core import Flock
from flock.mcp import StdioServerParameters


def test_agent_has_mcp_properties():
    """Test agent has MCP-related properties."""
    orch = Flock()
    agent = orch.agent("test_agent").agent

    assert hasattr(agent, "mcp_server_names")
    assert agent.mcp_server_names == set()


def test_with_mcps_basic():
    """Test basic MCP server assignment to agent."""
    orch = Flock()
    orch.add_mcp(
        name="server1",
        connection_params=StdioServerParameters(command="echo", args=["1"]),
    )

    agent = orch.agent("test_agent").with_mcps(["server1"]).agent

    assert agent.mcp_server_names == {"server1"}


def test_with_mcps_multiple_servers():
    """Test assigning multiple MCP servers to agent."""
    orch = Flock()
    orch.add_mcp(
        name="server1",
        connection_params=StdioServerParameters(command="echo", args=["1"]),
    )
    orch.add_mcp(
        name="server2",
        connection_params=StdioServerParameters(command="echo", args=["2"]),
    )

    agent = orch.agent("test_agent").with_mcps(["server1", "server2"]).agent

    assert agent.mcp_server_names == {"server1", "server2"}


def test_with_mcps_unregistered_server_fails():
    """Test that assigning unregistered server fails."""
    orch = Flock()

    with pytest.raises(ValueError, match="not registered"):
        orch.agent("test_agent").with_mcps(["nonexistent_server"]).agent


def test_with_mcps_method_chaining():
    """Test that with_mcps supports method chaining."""
    orch = Flock()
    orch.add_mcp(
        name="server1",
        connection_params=StdioServerParameters(command="echo", args=["1"]),
    )

    # Should be able to chain with other builder methods
    agent = orch.agent("test_agent").with_mcps(["server1"]).agent

    assert agent.mcp_server_names == {"server1"}


def test_agent_without_mcps():
    """Test that agent works fine without any MCP servers."""
    orch = Flock()

    # Agent without MCP should work normally
    agent = orch.agent("test_agent").agent

    assert agent.mcp_server_names == set()


@pytest.mark.asyncio
async def test_get_mcp_tools_no_servers():
    """Test _get_mcp_tools returns empty list when no servers assigned."""
    orch = Flock()
    agent = orch.agent("test_agent").agent

    # Mock context (adjust based on actual Context structure)
    from unittest.mock import Mock

    ctx = Mock()
    ctx.agent_id = "test_agent"
    ctx.task_id = "test_run"

    tools = await agent._get_mcp_tools(ctx)
    assert tools == []


# Note: Full integration test with actual MCP server will be in Phase 4
