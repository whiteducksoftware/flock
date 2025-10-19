"""Test TypedDict functionality for MCPServerConfig with tool_whitelist."""

import pytest

from flock.core import Flock, MCPServerConfig
from flock.mcp import StdioServerParameters


@pytest.fixture
def orchestrator():
    """Create an orchestrator with test MCP servers."""
    flock = Flock("openai/gpt-4o-mini")
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


def test_new_format_with_tool_whitelist(orchestrator):
    """Test new MCPServerConfig format with tool_whitelist."""
    agent = orchestrator.agent("test_agent").with_mcps({
        "filesystem": {
            "roots": ["/workspace/data"],
            "tool_whitelist": ["read_file", "write_file"],
        },
        "github": {},
    })

    assert agent.agent.mcp_server_names == {"filesystem", "github"}
    assert agent.agent.mcp_server_mounts == {"filesystem": ["/workspace/data"]}
    assert agent.agent.tool_whitelist == ["read_file", "write_file"]


def test_new_format_roots_only(orchestrator):
    """Test new format with only roots (no tool_whitelist)."""
    agent = orchestrator.agent("test_agent").with_mcps({
        "filesystem": {"roots": ["/workspace/src", "/workspace/data"]},
    })

    assert agent.agent.mcp_server_names == {"filesystem"}
    assert agent.agent.mcp_server_mounts == {
        "filesystem": ["/workspace/src", "/workspace/data"]
    }
    assert agent.agent.tool_whitelist is None


def test_new_format_empty_config(orchestrator):
    """Test new format with empty config (no restrictions)."""
    agent = orchestrator.agent("test_agent").with_mcps({"filesystem": {}, "github": {}})

    assert agent.agent.mcp_server_names == {"filesystem", "github"}
    assert agent.agent.mcp_server_mounts == {}
    assert agent.agent.tool_whitelist is None


def test_typeddict_type_hints():
    """Test that TypedDict provides proper type hints."""
    # This test verifies IDE autocomplete would work
    config: MCPServerConfig = {"roots": ["/workspace"], "tool_whitelist": ["read_file"]}

    assert "roots" in config
    assert "tool_whitelist" in config
    assert config["roots"] == ["/workspace"]
    assert config["tool_whitelist"] == ["read_file"]


def test_typeddict_optional_fields():
    """Test that all MCPServerConfig fields are optional."""
    # Empty config is valid
    config1: MCPServerConfig = {}
    assert config1 == {}

    # Only roots
    config2: MCPServerConfig = {"roots": ["/workspace"]}
    assert "roots" in config2
    assert "tool_whitelist" not in config2

    # Only tool_whitelist
    config3: MCPServerConfig = {"tool_whitelist": ["read_file"]}
    assert "tool_whitelist" in config3
    assert "roots" not in config3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
