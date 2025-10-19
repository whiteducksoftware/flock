"""Tests for agent MCP integration."""

from unittest.mock import AsyncMock, Mock

import pytest

from flock.agent.mcp_integration import MCPIntegration
from flock.utils.runtime import Context


@pytest.fixture
def mock_orchestrator():
    """Create mock orchestrator."""
    orchestrator = Mock()
    orchestrator.name = "test_orchestrator"
    return orchestrator


@pytest.fixture
def integration(mock_orchestrator):
    """Create MCPIntegration instance."""
    return MCPIntegration(agent_name="test_agent", orchestrator=mock_orchestrator)


@pytest.fixture
def mock_context():
    """Create mock context."""
    ctx = Mock(spec=Context)
    ctx.task_id = "task-123"
    return ctx


@pytest.fixture
def registered_servers():
    """Create set of registered server names."""
    return {"filesystem", "github", "database"}


def test_configure_servers_with_list(integration, registered_servers):
    """Test configure_servers with simple list of server names."""
    integration.configure_servers(["filesystem", "github"], registered_servers)

    assert integration.mcp_server_names == {"filesystem", "github"}
    assert integration.mcp_server_mounts == {}
    assert integration.tool_whitelist is None


def test_configure_servers_with_dict_no_config(integration, registered_servers):
    """Test configure_servers with dict but no specific config."""
    integration.configure_servers({"filesystem": {}, "github": {}}, registered_servers)

    assert integration.mcp_server_names == {"filesystem", "github"}
    assert integration.mcp_server_mounts == {}
    assert integration.tool_whitelist is None


def test_configure_servers_with_dict_and_roots(integration, registered_servers):
    """Test configure_servers with mount point roots."""
    integration.configure_servers(
        {
            "filesystem": {"roots": ["/workspace/data"]},
            "github": {},
        },
        registered_servers,
    )

    assert integration.mcp_server_names == {"filesystem", "github"}
    assert integration.mcp_server_mounts == {"filesystem": ["/workspace/data"]}
    assert integration.tool_whitelist is None


def test_configure_servers_with_tool_whitelist(integration, registered_servers):
    """Test configure_servers with tool whitelisting."""
    integration.configure_servers(
        {
            "filesystem": {"tool_whitelist": ["read_file", "write_file"]},
        },
        registered_servers,
    )

    assert integration.mcp_server_names == {"filesystem"}
    assert integration.tool_whitelist == ["read_file", "write_file"]


def test_configure_servers_with_multiple_mounts(integration, registered_servers):
    """Test configure_servers with multiple mount points."""
    integration.configure_servers(
        {
            "filesystem": {"roots": ["/workspace/data", "/workspace/logs"]},
        },
        registered_servers,
    )

    assert integration.mcp_server_mounts == {
        "filesystem": ["/workspace/data", "/workspace/logs"]
    }


def test_configure_servers_fails_on_unregistered_server(
    integration, registered_servers
):
    """Test that configure_servers raises ValueError for unregistered servers."""
    with pytest.raises(ValueError, match="MCP servers not registered"):
        integration.configure_servers(["invalid_server"], registered_servers)


def test_configure_servers_fails_on_partially_invalid(integration, registered_servers):
    """Test that configure_servers fails if any server is invalid."""
    with pytest.raises(ValueError, match="invalid_server"):
        integration.configure_servers(
            ["filesystem", "invalid_server"], registered_servers
        )


def test_configure_servers_with_empty_set(integration):
    """Test configure_servers with empty registered servers set."""
    with pytest.raises(ValueError, match="MCP servers not registered"):
        integration.configure_servers(["filesystem"], set())


@pytest.mark.asyncio
async def test_get_mcp_tools_returns_empty_when_no_servers(integration, mock_context):
    """Test that get_mcp_tools returns empty list when no servers configured."""
    integration.mcp_server_names = set()

    tools = await integration.get_mcp_tools(mock_context)

    assert tools == []


@pytest.mark.asyncio
async def test_get_mcp_tools_fetches_from_manager(
    integration, mock_context, mock_orchestrator
):
    """Test that get_mcp_tools fetches tools from MCP manager."""
    # Setup
    integration.mcp_server_names = {"filesystem"}
    mock_manager = Mock()
    mock_orchestrator.get_mcp_manager.return_value = mock_manager

    # Mock tool data
    mock_tool = Mock()
    mock_tool.as_dspy_tool.return_value = Mock(name="mocked_dspy_tool")
    mock_client = Mock()

    tools_dict = {
        "filesystem__read_file": {
            "server_name": "filesystem",
            "tool": mock_tool,
            "client": mock_client,
            "original_name": "read_file",
        }
    }
    mock_manager.get_tools_for_agent = AsyncMock(return_value=tools_dict)

    # Execute
    tools = await integration.get_mcp_tools(mock_context)

    # Verify
    assert len(tools) == 1
    assert tools[0].name == "filesystem__read_file"
    mock_manager.get_tools_for_agent.assert_called_once_with(
        agent_id="test_agent",
        run_id="task-123",
        server_names={"filesystem"},
        server_mounts={},
    )


@pytest.mark.asyncio
async def test_get_mcp_tools_applies_whitelist(
    integration, mock_context, mock_orchestrator
):
    """Test that get_mcp_tools filters tools by whitelist."""
    # Setup
    integration.mcp_server_names = {"filesystem"}
    integration.tool_whitelist = ["read_file"]  # Only allow read_file
    mock_manager = Mock()
    mock_orchestrator.get_mcp_manager.return_value = mock_manager

    # Mock multiple tools, but only one is whitelisted
    mock_tool1 = Mock()
    mock_tool1.as_dspy_tool.return_value = Mock(name="read_dspy")
    mock_tool2 = Mock()
    mock_tool2.as_dspy_tool.return_value = Mock(name="write_dspy")
    mock_client = Mock()

    tools_dict = {
        "filesystem__read_file": {
            "server_name": "filesystem",
            "tool": mock_tool1,
            "client": mock_client,
            "original_name": "read_file",
        },
        "filesystem__write_file": {
            "server_name": "filesystem",
            "tool": mock_tool2,
            "client": mock_client,
            "original_name": "write_file",
        },
    }
    mock_manager.get_tools_for_agent = AsyncMock(return_value=tools_dict)

    # Execute
    tools = await integration.get_mcp_tools(mock_context)

    # Verify - only read_file should pass whitelist
    assert len(tools) == 1
    assert tools[0].name == "filesystem__read_file"


@pytest.mark.asyncio
async def test_get_mcp_tools_graceful_degradation_on_error(
    integration, mock_context, mock_orchestrator
):
    """Test that get_mcp_tools returns empty list on error (graceful degradation)."""
    # Setup
    integration.mcp_server_names = {"filesystem"}
    mock_manager = Mock()
    mock_orchestrator.get_mcp_manager.return_value = mock_manager
    mock_manager.get_tools_for_agent = AsyncMock(
        side_effect=Exception("MCP connection failed")
    )

    # Execute - should not raise, should return empty
    tools = await integration.get_mcp_tools(mock_context)

    # Verify
    assert tools == []


@pytest.mark.asyncio
async def test_get_mcp_tools_with_server_mounts(
    integration, mock_context, mock_orchestrator
):
    """Test that get_mcp_tools passes server mounts to manager."""
    # Setup
    integration.mcp_server_names = {"filesystem"}
    integration.mcp_server_mounts = {"filesystem": ["/workspace/data"]}
    mock_manager = Mock()
    mock_orchestrator.get_mcp_manager.return_value = mock_manager
    mock_manager.get_tools_for_agent = AsyncMock(return_value={})

    # Execute
    await integration.get_mcp_tools(mock_context)

    # Verify mounts were passed
    mock_manager.get_tools_for_agent.assert_called_once_with(
        agent_id="test_agent",
        run_id="task-123",
        server_names={"filesystem"},
        server_mounts={"filesystem": ["/workspace/data"]},
    )


@pytest.mark.asyncio
async def test_get_mcp_tools_with_empty_whitelist(
    integration, mock_context, mock_orchestrator
):
    """Test that empty whitelist is treated as no filtering."""
    # Setup
    integration.mcp_server_names = {"filesystem"}
    integration.tool_whitelist = []  # Empty whitelist
    mock_manager = Mock()
    mock_orchestrator.get_mcp_manager.return_value = mock_manager

    mock_tool = Mock()
    mock_tool.as_dspy_tool.return_value = Mock(name="dspy_tool")
    mock_client = Mock()

    tools_dict = {
        "filesystem__read_file": {
            "server_name": "filesystem",
            "tool": mock_tool,
            "client": mock_client,
            "original_name": "read_file",
        }
    }
    mock_manager.get_tools_for_agent = AsyncMock(return_value=tools_dict)

    # Execute
    tools = await integration.get_mcp_tools(mock_context)

    # Empty whitelist means no filtering (all tools allowed)
    assert len(tools) == 1


def test_configure_servers_preserves_existing_state(integration, registered_servers):
    """Test that configure_servers properly overwrites state."""
    # First configuration
    integration.configure_servers(["filesystem"], registered_servers)
    assert integration.mcp_server_names == {"filesystem"}

    # Second configuration should overwrite
    integration.configure_servers(["github", "database"], registered_servers)
    assert integration.mcp_server_names == {"github", "database"}
    assert "filesystem" not in integration.mcp_server_names
