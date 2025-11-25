"""
Hackathon Track 10: MCP Filesystem Explorer

🎓 LEARNING OBJECTIVE:
Use the **filesystem MCP server** to explore the local project directory,
read files, and generate structured analysis reports – all within a safe,
whitelisted set of tools.

KEY CONCEPTS:
- Adding the filesystem MCP server with a restricted root
- Using `.with_mcps(...)` and tool whitelists for safety
- Filesystem-backed workflows: FileSearchRequest → FileAnalysisReport
- How roots + whitelists limit what an agent can see and do

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

from flock import Flock
from flock.mcp import StdioServerParameters
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


# ============================================================================
# STEP 1: Define Types
# ============================================================================


@flock_type
class FileSearchRequest(BaseModel):
    """
    A request to find and analyze a file in the current project.

    This is intentionally simple: one filename + a high-level analysis request.
    """

    filename: str = Field(
        description="Name of the file to analyze (e.g. 'README.md' or 'pyproject.toml')"
    )
    analysis_request: str = Field(
        default="Summarize the file's purpose and key sections",
        description="What kind of analysis to perform on the file",
    )


@flock_type
class FileAnalysisReport(BaseModel):
    """Structured analysis of a single file discovered via the filesystem MCP."""

    filename: str
    file_path: str
    file_size_bytes: int
    line_count: int
    content_summary: str = Field(
        description="Short summary of what the file is about"
    )
    key_findings: list[str] = Field(
        description="Important observations, TODOs, or interesting sections"
    )


# ============================================================================
# STEP 2: Create the Orchestrator and Register Filesystem MCP
# ============================================================================
# We will:
# - Use the official filesystem MCP server:
#       npx -y @modelcontextprotocol/server-filesystem <root>
# - Limit it to the CURRENT WORKING DIRECTORY as the root
# - Enable only a safe subset of tools (read/list/search)
#
# If the MCP server/Node is not installed, we log a warning and continue; the
# agent can still do best-effort analysis using just the LLM, but without
# real file contents.
# ============================================================================

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
            "read_multiple_files",
            "list_directory",
            "list_directory_with_sizes",
            "search_files",
            "get_file_info",
            "list_allowed_directories",
        ],
    )
    print(f"✅ Added filesystem MCP with root: {current_dir}")
except Exception as e:  # pragma: no cover - environment dependent
    print(
        f"⚠️  Could not add filesystem MCP "
        f"(is npm + @modelcontextprotocol/server-filesystem installed?): {e}"
    )


# ============================================================================
# STEP 3: Define the Filesystem Explorer Agent
# ============================================================================
# This agent:
# - Consumes FileSearchRequest
# - Uses the filesystem MCP server to:
#     - Locate the requested file
#     - Read its contents
#     - Gather metadata (size, line count)
# - Produces a FileAnalysisReport
# ============================================================================

filesystem_explorer = (
    flock.agent("filesystem_explorer")
    .description(
        "An expert repository explorer that uses the filesystem MCP server to "
        "locate and analyze files in the current project directory. It should:\n"
        "1) Use filesystem tools to search for the requested filename.\n"
        "2) Read the file's content and estimate line count and size.\n"
        "3) Generate a concise summary and bullet list of key findings.\n"
        "Always stay within the allowed root directories and whitelisted tools."
    )
    .consumes(FileSearchRequest)
    .with_mcps(
        {
            "filesystem": {
                "tool_whitelist": [
                    "read_text_file",
                    "read_multiple_files",
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


# ============================================================================
# STEP 4: Run the System (CLI + Dashboard)
# ============================================================================


async def main_cli() -> None:
    """CLI mode: Run the filesystem explorer and display the report."""
    print("=" * 80)
    print("📁 MCP FILESYSTEM EXPLORER - Hackathon Track 10")
    print("=" * 80)
    print()

    request = FileSearchRequest(
        filename="README.md",
        analysis_request="Summarize the project's purpose and list main features",
    )

    print("🔎 File Search Request")
    print("----------------------")
    print(f"Root directory  : {current_dir}")
    print(f"Target filename : {request.filename}")
    print(f"Analysis focus  : {request.analysis_request}")
    print()
    print("⏳ Running filesystem_explorer agent...")
    print()

    await flock.publish(request)
    await flock.run_until_idle()

    reports = await flock.store.get_by_type(FileAnalysisReport)

    if not reports:
        print("❌ No FileAnalysisReport artifacts were generated.")
        print("   - Check filesystem MCP installation messages above.")
        print("   - The agent may be falling back to rough guesses.")
        return

    report = reports[0]

    print("=" * 80)
    print("✅ File Analysis Report")
    print("=" * 80)
    print()
    print(f"📄 File     : {report.filename}")
    print(f"📍 Location : {report.file_path}")
    print(f"📊 Size     : {report.file_size_bytes:,} bytes")
    print(f"📏 Lines    : {report.line_count:,}")
    print()
    print("📝 Summary")
    print("----------")
    print(report.content_summary)
    print()
    print("💡 Key Findings")
    print("---------------")
    for i, finding in enumerate(report.key_findings, start=1):
        print(f"{i:2d}. {finding}")


async def main_dashboard() -> None:
    """Dashboard mode: Serve with interactive web interface."""
    print("🌐 Starting Flock Dashboard for MCP Filesystem Explorer...")
    print("   Visit http://localhost:8344 to:")
    print("   - Publish FileSearchRequest artifacts")
    print("   - Watch the filesystem_explorer agent execute")
    print("   - Inspect FileAnalysisReport artifacts")
    print()
    await flock.serve(dashboard=True)


async def main() -> None:
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main())


# ============================================================================
# 🎓 NOW IT'S YOUR TURN!
# ============================================================================
#
# EXPERIMENT 1: Analyze Different Files
# -------------------------------------
# Change the filename in FileSearchRequest:
#   - "pyproject.toml"
#   - "AGENTS.md"
#   - "docs/architecture.md"
#   - "01-hackathon/README.md"
#
# How do the summary and key findings differ between code, docs, and examples?
#
#
# EXPERIMENT 2: Change the Root Directory
# ---------------------------------------
# Modify `current_dir = Path.cwd()` to a subdirectory:
#   current_dir = Path.cwd() / "examples"
#
# Re-run the example:
#   - Does the report still find the requested file?
#   - What happens if the file is outside the root?
#
# This illustrates how MCP roots constrain what an agent can see.
#
#
# EXPERIMENT 3: Stronger Tool Whitelists
# --------------------------------------
# Reduce the tool whitelist in .with_mcps(...) to only:
#   - "read_text_file"
#   - "search_files"
#
# Does the agent still produce good reports?
# What happens if you remove "search_files" and only allow "read_text_file"?
#
# This shows the tradeoff between capabilities and safety.
#
#
# EXPERIMENT 4: Multi-File Analysis
# ---------------------------------
# Extend FileSearchRequest to include a `pattern` or `directory` field.
# Update the agent description to allow reading multiple files matching
# the pattern and summarizing them together.
#
# For example:
#   - Summarize all `.md` files in `docs/`
#   - Summarize all example scripts in `01-hackathon/`
#
# What new insights can you surface when you look at groups of files?
#
#
# EXPERIMENT 5: Chain Another Agent
# ---------------------------------
# Create a second agent that consumes FileAnalysisReport and produces:
#   - A `RefactorPlan` for code files
#   - A `DocsImprovementPlan` for documentation files
#
# How does chaining change the way you think about filesystem-backed workflows?
#
#
# EXPERIMENT 6: Compare LLM-Only vs MCP-Backed
# --------------------------------------------
# Temporarily break the filesystem MCP (e.g., by changing the command name)
# and run the example:
#   - How different are the reports?
#   - Can you tell when the agent has real file content vs guesses?
#
# This is a good way to reason about **grounding** and **trust** in LLM outputs.
#
# ============================================================================
