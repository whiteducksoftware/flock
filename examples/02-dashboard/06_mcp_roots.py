import asyncio
from pathlib import Path

from pydantic import BaseModel

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class FileSearchRequest(BaseModel):
    filename: str
    analysis_request: str = "Summarize the file's content"

@flock_type
class FileAnalysisReport(BaseModel):
    filename: str
    file_path: str
    file_size_bytes: int
    content_summary: str
    key_findings: list[str]
    line_count: int

flock = Flock(model="openai/gpt-4.1")

current_dir = Path.cwd()

try:
    flock.add_mcp(
        name="filesystem",
        connection_params=StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(current_dir),
            ],
        ),
        enable_roots_feature=True,
        enable_tools_feature=True,
        tool_whitelist=[
            "read_text_file",
            "read_media_file",
            "read_multiple_files",
            "list_directory",
            "list_directory_with_sizes",
            "search_files",
            "directory_tree",
            "get_file_info",
            "list_allowed_directories",
        ],
    )
    print("[OK] Added filesystem MCP with roots feature")
except Exception as e:
    print(f"[WARNING] Could not add filesystem MCP (is npm installed?): {e}")

(
    flock.agent("filesystem_explorer")
    .description(
        "Expert at finding files, reading content, and performing detailed analysis. "
        "Can search directories, extract metadata, and generate insights from file contents."
    )
    .consumes(FileSearchRequest)
    .with_mcps(
        {
            "filesystem": {
                "tool_whitelist": [
                    "read_text_file",
                    "list_directory",
                    "list_directory_with_sizes",
                    "search_files",
                    "get_file_info",
                    "list_allowed_directories",
                ]
            }
        }
    )
    .publishes(FileAnalysisReport)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
