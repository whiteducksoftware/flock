"""Tests for server-specific mount points in agents."""

from unittest.mock import AsyncMock, patch

import pytest

from flock.core import Flock
from flock.mcp import StdioServerParameters


@pytest.fixture
def orchestrator():
    """Create a test orchestrator with MCP servers."""
    flock = Flock(model="openai/gpt-4o-mini")

    # Register test MCP servers
    flock.add_mcp(
        name="filesystem",
        connection_params=StdioServerParameters(command="test", args=[]),
        enable_roots_feature=True,
    )
    flock.add_mcp(
        name="github",
        connection_params=StdioServerParameters(command="test", args=[]),
        enable_roots_feature=True,
    )

    return flock


def test_with_mcps_dict_format(orchestrator):
    """Test .with_mcps() with dict format for server-specific mounts."""
    agent = orchestrator.agent("test_agent").with_mcps({
        "filesystem": {"roots": ["/workspace/src", "/data"]},
        "github": {"roots": ["/workspace/.git"]},
    })

    # Check server names are registered
    assert agent.agent.mcp_server_names == {"filesystem", "github"}

    # Check server-specific mounts
    assert agent.agent.mcp_server_mounts == {
        "filesystem": ["/workspace/src", "/data"],
        "github": ["/workspace/.git"],
    }


def test_with_mcps_list_format(orchestrator):
    """Test .with_mcps() with simple list format (no mounts)."""
    agent = orchestrator.agent("test_agent").with_mcps(["filesystem", "github"])

    # Check server names are registered
    assert agent.agent.mcp_server_names == {"filesystem", "github"}

    # Check no server-specific mounts
    assert agent.agent.mcp_server_mounts == {}


def test_with_mcps_invalid_server(orchestrator):
    """Test .with_mcps() raises error for unregistered server."""
    with pytest.raises(ValueError, match="MCP servers not registered.*invalid_server"):
        orchestrator.agent("test_agent").with_mcps(["invalid_server"])


def test_with_mcps_tool_whitelist(orchestrator):
    """Test .with_mcps() with tool whitelist."""
    agent = orchestrator.agent("test_agent").with_mcps({
        "filesystem": {
            "roots": ["/workspace/src"],
            "tool_whitelist": ["read_file", "write_file"],
        },
    })

    # Check server names are registered
    assert agent.agent.mcp_server_names == {"filesystem"}

    # Check server-specific mounts
    assert agent.agent.mcp_server_mounts == {
        "filesystem": ["/workspace/src"],
    }

    # Check tool whitelist
    assert agent.agent.tool_whitelist == ["read_file", "write_file"]


def test_empty_mounts_in_dict(orchestrator):
    """Test .with_mcps() with empty config for a server (no restrictions)."""
    agent = orchestrator.agent("test_agent").with_mcps({
        "filesystem": {"roots": ["/workspace/src"]},
        "github": {},  # Empty = no restrictions
    })

    assert agent.agent.mcp_server_names == {"filesystem", "github"}
    assert agent.agent.mcp_server_mounts == {
        "filesystem": ["/workspace/src"],
        # github not in mounts dict = no restrictions
    }


@pytest.mark.asyncio
async def test_get_mcp_tools_passes_server_mounts(orchestrator):
    """Test that _get_mcp_tools passes server-specific mounts to manager."""
    from flock.utils.runtime import Context

    agent = orchestrator.agent("test_agent").with_mcps({
        "filesystem": {"roots": ["/workspace/src"]},
        "github": {"roots": ["/workspace/.git"]},
    })

    ctx = Context(
        artifacts=[],
        task_id="test-run-123",
        correlation_id=None,
    )

    # Mock the manager
    with patch.object(orchestrator, "get_mcp_manager") as mock_get_manager:
        mock_manager = AsyncMock()
        mock_manager.get_tools_for_agent.return_value = {}
        mock_get_manager.return_value = mock_manager

        # Call _get_mcp_tools
        await agent.agent._get_mcp_tools(ctx)

        # Verify manager was called with correct server_mounts
        mock_manager.get_tools_for_agent.assert_called_once_with(
            agent_id="test_agent",
            run_id="test-run-123",
            server_names={"filesystem", "github"},
            server_mounts={
                "filesystem": ["/workspace/src"],
                "github": ["/workspace/.git"],
            },
        )


@pytest.mark.asyncio
async def test_manager_passes_server_specific_mounts_to_client(orchestrator):
    """Test that manager passes server-specific mounts to each client."""
    from flock.mcp.manager import FlockMCPClientManager

    # Create manager with test configs
    configs = {
        "filesystem": orchestrator._mcp_configs["filesystem"],
        "github": orchestrator._mcp_configs["github"],
    }
    manager = FlockMCPClientManager(configs)

    server_mounts = {
        "filesystem": ["/workspace/src"],
        "github": ["/workspace/.git"],
    }

    # Mock get_client to track calls
    get_client_calls = []

    async def mock_get_client(server_name, agent_id, run_id, mount_points=None):
        get_client_calls.append({
            "server_name": server_name,
            "mount_points": mount_points,
        })
        # Don't actually connect
        mock_client = AsyncMock()
        mock_client.get_tools = AsyncMock(return_value=[])
        return mock_client

    manager.get_client = mock_get_client

    # Call get_tools_for_agent
    await manager.get_tools_for_agent(
        agent_id="test_agent",
        run_id="test-run",
        server_names={"filesystem", "github"},
        server_mounts=server_mounts,
    )

    # Verify each server got its specific mounts
    filesystem_call = next(
        c for c in get_client_calls if c["server_name"] == "filesystem"
    )
    github_call = next(c for c in get_client_calls if c["server_name"] == "github")

    assert filesystem_call["mount_points"] == ["/workspace/src"]
    assert github_call["mount_points"] == ["/workspace/.git"]
