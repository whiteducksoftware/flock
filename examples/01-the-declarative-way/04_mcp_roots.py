"""
🗂️ THE FILESYSTEM EXPLORER: MCP Roots Edition
==============================================

You've learned about MCPs for web search and reading websites.
Now let's explore a powerful security feature: MCP ROOTS.

🎯 THE QUESTION:
"How do I give agents filesystem access without compromising security?"

🎓 THE ANSWER:
MCP Roots let you mount specific directories, giving agents controlled
filesystem access. Think of it like Docker volumes for AI agents.

⏱️  TIME: 10 minutes
💡 DIFFICULTY: ⭐⭐ Intermediate

📦 PREREQUISITES:
- Node.js and npm (for @modelcontextprotocol/server-filesystem)
- Previous knowledge from 03_mcp_and_tools.py

🔐 WHY THIS MATTERS:
Without roots, MCPs can access your entire filesystem - dangerous!
With roots, you control exactly what agents can see and modify.
"""

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


# 💡 WHAT'S NEW:
# These types are richer than the previous example:
# - FileSearchRequest includes analysis instructions
# - FileAnalysisReport captures metadata AND analysis
# This shows how schemas guide what the agent extracts


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔌 STEP 2: Add Filesystem MCP with Roots Feature
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock(model="azure/gpt-4.1-swedencentral")

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


# 💡 WHAT ARE ROOTS?
# Roots are like "mount points" in Docker:
# - You specify which directories the agent can access
# - Everything outside is invisible to the agent
# - Multiple roots can be added for different projects
#
# 🔐 SECURITY BENEFITS:
# Without roots: Agent could read ~/.ssh/, /etc/passwd, your entire drive!
# With roots: Agent only sees what you explicitly mount
#
# This is CRITICAL for production deployments.


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

# 🎉 THE POWER:
# This agent can now:
# 1. Search for files by name (case-insensitive)
# 2. Read file contents (within mounted roots only)
# 3. Extract metadata (size, line count)
# 4. Analyze content based on user instructions
# 5. Return structured findings
#
# All within the security boundary of the mounted directory!


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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 WHAT YOU JUST LEARNED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ✅ MCP Roots Feature
#    - Security boundary for filesystem access
#    - Mount specific directories like Docker volumes
#    - Agent can ONLY see/modify mounted paths
#    - enable_roots_feature=True activates this protection
#
# ✅ Filesystem MCP Capabilities
#    - read_file: Read file contents
#    - write_file: Create/modify files
#    - list_directory: Browse directory structure
#    - search_files: Find files by name/pattern
#    - get_file_info: Extract metadata
#
# ✅ Security Best Practices
#    - Always use roots in production
#    - Mount minimal necessary directories
#    - One root per logical project/workspace
#    - Never mount home directory or system paths
#
# ✅ Rich Schema Design
#    - FileSearchRequest: Guides what to find AND analyze
#    - FileAnalysisReport: Captures metadata + insights
#    - Schema complexity scales with use case
#
# 💡 THE BIG IDEA:
# Roots transform filesystem access from "all or nothing" to "least privilege".
# Your agents get the tools they need, nothing more.
#
# This is how you build production-grade AI systems:
# - Declarative schemas define WHAT to produce
# - MCPs with roots define WHERE agents can operate
# - Security by design, not afterthought
#
# 🚀 REAL-WORLD USE CASES:
# - Code analysis: Mount src/ directory only
# - Documentation: Mount docs/ directory only
# - Data processing: Mount data/ directory only
# - Multi-tenant: Different roots per customer
#
# 🎓 CONGRATULATIONS!
# You now understand:
# 1. Declarative schemas (01_declarative_pizza.py)
# 2. Complex types (02_input_and_output.py)
# 3. Tools + MCPs (03_mcp_and_tools.py)
# 4. Security with MCP Roots (04_mcp_roots.py) ✅
#
# 🚀 NEXT STEPS:
# - Try [05-claudes-workshop/](../05-claudes-workshop/) for progressive lessons
# - Explore [02-the-blackboard/](../02-the-blackboard/) multi-agent workflows
# - Build production systems with secure filesystem access!
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
