"""Example demonstrating MCP root/mount point feature.

This example shows how to mount agents in specific directories,
controlling which filesystem paths MCP servers can access.


CAUTION WHEN USING THE server-filesystem MCP-Server:

Due to the specific implementation of server-filesystem,
ONLY ONE CLIENT (AGENT) CAN SPECIFY ROOTS AT A TIME.

IF MULTIPLE AGENTS ARE ACTING ON THE SAME SERVER INSTANCE,
THEN THEY WILL OVERRIDE EACH OTHER'S MCP-ROOTS


From the Docs: (https://github.com/modelcontextprotocol/servers/blob/main/src/filesystem/README.md)


Roots Protocol Handling (if client supports roots)

On initialization: Server requests roots from client via roots/list
Client responds with its configured roots
Server replaces ALL allowed directories with client's roots
On runtime updates: Client can send notifications/roots/list_changed
Server requests updated roots and replaces allowed directories again
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel

from flock.logging.logging import configure_logging
from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class FileRequest(BaseModel):
    """Request to list files with a specific ending in a directory."""

    path: str
    pattern: str = "*.py"


@flock_type
class FileList(BaseModel):
    """List of files with a specific ending in a directory."""

    path: str
    files: list[str]
    count: int

@flock_type
class FileSummary(BaseModel):
    """A Summary of the contents of the requested files."""

    summary: str


# Create orchestrator
flock = Flock(model="ollama/gpt-oss:latest")

# Register filesystem MCP server with roots feature enabled
# Documentation for server-filesystem: https://github.com/modelcontextprotocol/servers/blob/main/src/filesystem/README.md
# Mount this server on the users $HOME.
home = Path.home()
current_dir = Path.cwd()
flock.add_mcp(
    name="filesystem",
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", f"{home}"],
    ),
    enable_roots_feature=True,
    enable_tools_feature=True,
    # Prevent all agents that are using this server from modifying files.
    # By allowing only the tools that allow an agent to read files but not writing them.
    allow_all_tools=False,
    tool_whitelist=[
        "list_directory",
        "list_directory_with_sizes",
        "read_text_file",
        "read_media_file",
        "read_multiple_files",
        "search_files",
        "directory_tree",
        "get_file_info",
        "list_allowed_directories"
    ]
)

# This Agent is mounted in the current working directory
# And can access all files inside this directory, but cannot
# see anything outside of it.
# All tools it is calling are within the context of the current directory.
(
    flock.agent("filesystem_agent")
    .description("Agent that can investigate the filesystem.")
    .consumes(FileRequest)
    .with_mcps({
        "filesystem": [
            f"{current_dir}" # This will cause the filesystem server to switch to cwd
        ]
    })
    .publishes(FileList)
)

# This Agent can only read all files inside the current directory, but cannot
# see anything outside of it.
# All tools it is calling, are executed within the context of the current directory.
(
    flock.agent("file_reader_agent")
    .description("Agent that can read files in the filesystem. Takes in a list of files, reads them and provides a summary.")
    .consumes(FileList)
    .with_mcps({
        "filesystem": [
            f"{current_dir}" # This will cause the filesystem server to switch to cwd for execution context
        ]
    })
    .publishes(FileSummary)
)




async def main():
    """Run the example."""

    configure_logging(
        flock_level="DEBUG",
        external_level="ERROR",
        specific_levels={
            "dashboard.collector": "INFO",
            "dashboard.websocket": "INFO",
            "dashboard.orchestrator": "INFO",
            "dashboard.agent": "INFO",
        }
    )

    print("🚀 MCP Roots Example - Agent Directory Mounting")
    print("=" * 60)

    await flock.serve(dashboard=True)


if __name__ == "__main__":
    asyncio.run(main())
