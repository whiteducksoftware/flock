import asyncio
from pathlib import Path

from pydantic import BaseModel

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📦 STEP 1: Define Types for Filesystem Operations
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class FileSearchRequest(BaseModel):
    """
    INPUT: A request to find and analyze a specific file

    Examples:
    - "Find README.md and summarize it"
    - "Locate pyproject.toml and extract dependencies"
    - "Find AGENTS.md and count the number of sections"
    """

    filename: str  # Name of file to find (case-insensitive search)
    analysis_request: str = "Summarize the file's content"  # What to do with it


@flock_type
class FileAnalysisReport(BaseModel):
    """
    OUTPUT: A comprehensive analysis of the found file

    The agent will:
    1. Search for the file in mounted directories
    2. Read the file content
    3. Analyze based on the request
    4. Return structured findings
    """

    filename: str  # Actual filename found
    file_path: str  # Full path to the file
    file_size_bytes: int  # Size in bytes
    content_summary: str  # Analysis based on request
    key_findings: list[str]  # Important points discovered
    line_count: int  # Number of lines in file


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔌 STEP 2: Add Filesystem MCP with Roots Feature
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock(model="openai/gpt-4.1")

# Get the current project directory
current_dir = Path.cwd()

print(f"📁 Mounting filesystem at: {current_dir}")
print("🔐 Security: Agent can ONLY access files in this directory\n")

# 🌐 MCP: Filesystem with Roots Feature
# The filesystem MCP provides file operations (read, write, search, list)
# The enable_roots_feature=True activates directory mounting
try:
    flock.add_mcp(
        name="filesystem",
        connection_params=StdioServerParameters(
            command="npx",
            args=[
                "-y",
                "@modelcontextprotocol/server-filesystem",
                str(current_dir),  # Mount this directory
            ],
        ),
        enable_roots_feature=True,  # 🔐 Enable directory mounting (roots)
        enable_tools_feature=True,  # Enable file operations (read, write, etc.)
        tool_whitelist=[            # Prevent all agents that are using this server from modifying files
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
    print("💡 Install with: npm install -g @modelcontextprotocol/server-filesystem")
    print("    Or: Use npx (which auto-installs on first run)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 STEP 3: Create Filesystem Explorer Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
    )  # 🔌 Give agent filesystem access and restrict the tools further
    .publishes(FileAnalysisReport)
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 4: Run the Filesystem Explorer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Let's explore the filesystem! The agent will:
    - Search for the requested file
    - Read its content
    - Analyze based on the request
    - Return structured findings
    """

    # Example 1: Find and summarize README
    request = FileSearchRequest(
        filename="README.md",
        analysis_request="Summarize the project's purpose and list the main features",
    )

    print("🔎 Filesystem Explorer Task")
    print("=" * 60)
    print(f"📄 Looking for: {request.filename}")
    print(f"🎯 Analysis: {request.analysis_request}")
    print(f"🔐 Search scope: {current_dir} (and subdirectories)")
    print("\n⚡ Agent is working...\n")

    # Publish and wait
    await flock.publish(request)
    await flock.run_until_idle()

    # Retrieve the analysis
    reports = await flock.store.get_by_type(FileAnalysisReport)

    if reports:
        report = reports[0]
        print("✅ Analysis complete!\n")
        print(f"📄 File found: {report.filename}")
        print(f"📍 Location: {report.file_path}")
        print(f"📊 Size: {report.file_size_bytes:,} bytes ({report.line_count:,} lines)")
        print(f"\n📝 Summary:\n{report.content_summary}\n")
        print(f"💡 Key findings ({len(report.key_findings)}):")
        for i, finding in enumerate(report.key_findings, 1):
            print(f"   {i}. {finding}")

        print("\n🎉 The agent used the filesystem MCP to:")
        print("   ✓ Search for the file (case-insensitive)")
        print("   ✓ Read the content (within security boundaries)")
        print("   ✓ Extract metadata (size, line count)")
        print("   ✓ Analyze and structure findings")
        print("\n🔐 Security note: Agent could ONLY access files in mounted directory")
    else:
        print("❌ No analysis was generated!")
        print("💡 Check that:")
        print("   - The filesystem MCP is installed (see prerequisites)")
        print("   - The file exists in the current directory")
        print("   - The agent has proper permissions")


if __name__ == "__main__":
    asyncio.run(main())
