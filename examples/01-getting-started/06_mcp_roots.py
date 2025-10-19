"""
Getting Started: MCP Roots

This example demonstrates using MCP with the roots feature for filesystem access,
allowing agents to search and analyze files within specified directories.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel

from flock.mcp import StdioServerParameters
from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


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


flock = Flock()

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
    print("✅ Added filesystem MCP with roots feature")
except Exception as e:
    print(f"⚠️  Could not add filesystem MCP (is npm installed?): {e}")

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


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    request = FileSearchRequest(
        filename="README.md",
        analysis_request="Summarize the project's purpose and list the main features",
    )

    print(f"🔎 Looking for: {request.filename}")
    print(f"🎯 Analysis: {request.analysis_request}")
    print(f"🔐 Search scope: {current_dir}\n")

    await flock.publish(request)
    await flock.run_until_idle()

    reports = await flock.store.get_by_type(FileAnalysisReport)
    if reports:
        report = reports[0]
        print("✅ Analysis complete!\n")
        print(f"📄 File: {report.filename}")
        print(f"📍 Location: {report.file_path}")
        print(f"📊 Size: {report.file_size_bytes:,} bytes ({report.line_count:,} lines)")
        print(f"\n📝 Summary:\n{report.content_summary}\n")
        print(f"💡 Key findings ({len(report.key_findings)}):")
        for i, finding in enumerate(report.key_findings, 1):
            print(f"   {i}. {finding}")
    else:
        print("❌ No analysis was generated!")
        print("💡 Make sure the filesystem MCP is installed (see prerequisites)")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())
