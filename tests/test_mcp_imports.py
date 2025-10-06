"""Test that all MCP modules can be imported correctly."""


def test_mcp_types_import():
    """Test MCP types can be imported."""
    from flock.mcp.types import (
        MCPRoot,
        ServerParameters,
        StdioServerParameters,
    )

    assert StdioServerParameters is not None
    assert ServerParameters is not None
    assert MCPRoot is not None


def test_mcp_config_import():
    """Test MCP configuration classes can be imported."""
    from flock.mcp.config import (
        FlockMCPConfiguration,
        FlockMCPConnectionConfiguration,
        FlockMCPFeatureConfiguration,
    )

    assert FlockMCPConfiguration is not None
    assert FlockMCPConnectionConfiguration is not None
    assert FlockMCPFeatureConfiguration is not None


def test_mcp_client_import():
    """Test MCP client can be imported."""
    from flock.mcp.client import FlockMCPClient

    assert FlockMCPClient is not None


def test_mcp_manager_import():
    """Test MCP manager can be imported."""
    from flock.mcp.manager import FlockMCPClientManager

    assert FlockMCPClientManager is not None


def test_mcp_tool_import():
    """Test MCP tool wrapper can be imported."""
    from flock.mcp.tool import FlockMCPTool

    assert FlockMCPTool is not None


def test_mcp_package_import():
    """Test top-level package imports."""
    from flock.mcp import (
        FlockMCPClient,
        FlockMCPClientManager,
        FlockMCPConfiguration,
        StdioServerParameters,
    )

    assert FlockMCPClient is not None
    assert FlockMCPClientManager is not None
    assert FlockMCPConfiguration is not None
    assert StdioServerParameters is not None
