"""
MCP Configuration for Spec-Driven Development

This module configures the MCP tools that our orchestrators and specialists need:
- Filesystem MCP for reading/writing code and documentation
- DuckDuckGo MCP for web research
- Website reader MCP for deep content analysis
"""

from pathlib import Path

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock


def configure_mcps(flock: Flock) -> dict[str, bool]:
    """
    Configure all MCP servers for the spec-driven workflow.

    Returns a dict mapping MCP names to whether they were successfully added.
    """
    success_status = {}

    # Get the project root (two levels up from this file)
    project_root = Path.cwd().joinpath(".flock/spec-test")

    # ==========================================================================
    # FILESYSTEM MCP - For reading code and writing documentation
    # ==========================================================================
    try:
        flock.add_mcp(
            name="filesystem",
            connection_params=StdioServerParameters(
                command="npx",
                args=[
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "C:\\workspace\\whiteduck\\flock\\.flock\\spec-test",  # Root access to entire project
                ],
            ),
            enable_roots_feature=True,
            enable_tools_feature=True,
            tool_whitelist=[
                "read_text_file",
                "read_multiple_files",
                "list_directory",
                "list_directory_with_sizes",
                "search_files",
                "directory_tree",
                "get_file_info",
                "list_allowed_directories",
            ],
        )
        print("[OK] Filesystem MCP configured")
        success_status["filesystem"] = True
    except Exception as e:
        print(f"[WARN] Could not add filesystem MCP (is npm installed?): {e}")
        success_status["filesystem"] = False

    # ==========================================================================
    # DUCKDUCKGO MCP - For web research
    # ==========================================================================
    try:
        flock.add_mcp(
            name="search_web",
            enable_tools_feature=True,
            connection_params=StdioServerParameters(
                command="uvx",
                args=["duckduckgo-mcp-server"],
            ),
        )
        print("[OK] DuckDuckGo search MCP configured")
        success_status["search_web"] = True
    except Exception as e:
        print(f"[WARN] Could not add search MCP (is uvx installed?): {e}")
        success_status["search_web"] = False

    # ==========================================================================
    # WEBSITE READER MCP - For deep content analysis
    # ==========================================================================
    try:
        flock.add_mcp(
            name="read_website",
            enable_tools_feature=True,
            connection_params=StdioServerParameters(
                command="npx",
                args=["-y", "@just-every/mcp-read-website-fast"],
            ),
        )
        print("[OK] Website reader MCP configured")
        success_status["read_website"] = True
    except Exception as e:
        print(f"[WARN] Could not add website reader MCP (is npm installed?): {e}")
        success_status["read_website"] = False

    return success_status


def get_mcp_config_for_agent(agent_type: str) -> dict:
    """
    Get MCP configuration for a specific agent type.

    Returns a dict suitable for .with_mcps() based on agent role.
    """
    configs = {
        # Research specialists need web search + website reading
        "research": {
            "mcps": ["search_web", "read_website"],
            "filesystem_tools": ["read_text_file", "list_directory"],
        },

        # Documentation specialists need filesystem read + write
        "documenter": {
            "mcps": ["filesystem"],
            "filesystem_tools": [
                "read_text_file",
                "read_multiple_files",
                "list_directory",
                "get_file_info",
            ],
        },

        # Implementation specialists need full filesystem access
        "implementer": {
            "mcps": ["filesystem"],
            "filesystem_tools": [
                "read_text_file",
                "read_multiple_files",
                "list_directory",
                "search_files",
                "get_file_info",
                "directory_tree",
            ],
        },

        # Reviewers only need read access
        "reviewer": {
            "mcps": ["filesystem"],
            "filesystem_tools": [
                "read_text_file",
                "read_multiple_files",
                "get_file_info",
            ],
        },

        # Validators need read + ability to run commands (via Bash tool)
        "validator": {
            "mcps": ["filesystem"],
            "filesystem_tools": [
                "read_text_file",
                "list_directory",
                "get_file_info",
            ],
        },

        # Analyzers need comprehensive read access
        "analyzer": {
            "mcps": ["filesystem"],
            "filesystem_tools": [
                "read_text_file",
                "read_multiple_files",
                "list_directory",
                "search_files",
                "directory_tree",
                "get_file_info",
            ],
        },

        # Orchestrators need all MCPs
        "orchestrator": {
            "mcps": ["filesystem", "search_web", "read_website"],
            "filesystem_tools": [
                "read_text_file",
                "read_multiple_files",
                "list_directory",
                "search_files",
                "directory_tree",
                "get_file_info",
            ],
        },
    }

    return configs.get(agent_type, {"mcps": [], "filesystem_tools": []})


def format_mcp_config_for_agent(agent_type: str) -> dict:
    """
    Format MCP config for .with_mcps() call.

    Example return value:
    {
        "filesystem": {"tool_whitelist": ["read_text_file", "list_directory"]},
        "search_web": {},
    }
    """
    config = get_mcp_config_for_agent(agent_type)

    result = {}
    for mcp_name in config["mcps"]:
        if mcp_name == "filesystem" and config["filesystem_tools"]:
            result["filesystem"] = {"tool_whitelist": config["filesystem_tools"]}
        else:
            result[mcp_name] = {}

    return result
