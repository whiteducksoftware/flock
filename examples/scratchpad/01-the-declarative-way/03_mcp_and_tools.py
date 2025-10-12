"""
🔎 THE WEB RESEARCHER: Tools & MCP Edition
===========================================

You've mastered schemas and types. Now let's give agents SUPERPOWERS:
- @flock_tool: Turn Python functions into agent capabilities
- MCP (Model Context Protocol): Plug in external tools like web search
- Real-world interaction: Search, read, write, not just transform text

🎯 THE QUESTION:
"How do I make agents DO things, not just generate text?"

🎓 THE ANSWER:
Tools and MCPs. Agents can call your Python functions and external services.

⏱️  TIME: 15 minutes
💡 DIFFICULTY: ⭐⭐⭐ Intermediate (but worth it!)

📦 PREREQUISITES:
You'll need these installed for the MCP examples:
- npm (for @just-every/mcp-read-website-fast)
- uvx (for duckduckgo-mcp-server)

If you don't have them, the code will still teach you the concepts!
"""

import asyncio

from pydantic import BaseModel

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_tool, flock_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🛠️ STEP 1: Define Custom Tools with @flock_tool
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# 🎯 KEY CONCEPT: @flock_tool turns regular Python functions into agent tools
# The LLM can CALL these functions when it needs to DO something.


@flock_tool
def write_file(string: str, file_name: str) -> None:
    """
    Writes a file to the .flock/ directory.

    🎓 IMPORTANT: The docstring matters!
    - The LLM reads this to understand what the tool does
    - It will follow the instructions (like "File name must be in all CAPS")
    - Think of it as a mini contract for tool behavior

    Args:
        string: Content to write to the file
        file_name: Name of the file (must be in all CAPS and include today's date)

    Returns:
        None (but creates a file in .flock/)
    """
    from pathlib import Path

    file_path = Path(".flock") / file_name
    directory = file_path.parent

    # Create directory if it doesn't exist
    if directory and not directory.exists():
        directory.mkdir(parents=True)

    with open(file_path, "w") as f:
        f.write(string)

    print(f"✍️  Wrote file: {file_path}")


@flock_tool
def get_current_date() -> str:
    """
    Returns today's date in YYYY-MM-DD format.

    Why make this a tool instead of just using datetime?
    Because the LLM needs to CALL functions - it can't import Python libraries.
    Tools are the bridge between LLM reasoning and real code execution.

    Returns:
        str: Today's date (e.g., "2025-10-08")
    """
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d")


# 💡 WHAT JUST HAPPENED:
# You defined TWO capabilities your agents can use:
# 1. write_file: Agents can save reports, logs, anything
# 2. get_current_date: Agents can get current date for file naming
#
# The LLM will call these when needed. No explicit "if/else" logic required.
# It reads the docstrings and decides WHEN to call them.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📦 STEP 2: Define Types (Same as Before)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


@flock_type
class Task(BaseModel):
    """
    INPUT: A research task description

    Examples:
    - "A review meta overview to the movie 'Dune: Part Two'"
    - "What's happening with quantum computing in 2025?"
    - "Compare the top 5 mechanical keyboards"
    """

    description: str


@flock_type
class Report(BaseModel):
    """
    OUTPUT: A complete research report with sources

    The agent will:
    1. Search the web for relevant info
    2. Read multiple websites
    3. Write a beautifully formatted markdown report
    4. Save it to a file with today's date

    All because the schema + tools define this workflow!
    """

    file_path: str  # Where the report was saved
    title: str  # Report title
    researched_urls: list[str]  # URLs the agent visited
    high_impact_info: dict[str, str]  # Key insights (source → insight)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔌 STEP 3: Add MCPs (Model Context Protocol)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

flock = Flock(model="openai/gpt-4.1")

# 🌐 MCP #1: DuckDuckGo Web Search
# This MCP lets agents search the web (like typing in a search engine)
# Installation: uvx comes with uv (which you already have!)
try:
    flock.add_mcp(
        name="search_web",
        enable_tools_feature=True,  # Give the agent access to search tools
        connection_params=StdioServerParameters(
            command="uvx",
            args=["duckduckgo-mcp-server"],
        ),
    )
    print("✅ Added DuckDuckGo search MCP")
except Exception as e:
    print(f"⚠️  Could not add search MCP (is uvx installed?): {e}")


# 🌐 MCP #2: Website Content Reader
# This MCP lets agents READ website content (like opening pages in a browser)
# Installation: Requires Node.js and npm
try:
    flock.add_mcp(
        name="read-website",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@just-every/mcp-read-website-fast"],
        ),
    )
    print("✅ Added website reader MCP")
except Exception as e:
    print(f"⚠️  Could not add website reader MCP (is npm installed?): {e}")


# 💡 WHAT ARE MCPs?
# Model Context Protocol is a standard way to give LLMs access to external tools.
# Think of them as "plugins" for your agents:
# - search_web: Agent can search DuckDuckGo
# - read-website: Agent can fetch and read webpage content
#
# There are MCPs for:
# - File systems, databases, APIs, Slack, GitHub, etc.
# - Check https://github.com/modelcontextprotocol for more!


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🤖 STEP 4: Create Agent with Tools + MCPs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

(
    flock.agent("web_researcher")
    .description(
        "Researches information on the web and writes a beautifully "
        "formatted markdown report with sources and key insights."
    )
    .consumes(Task)
    # 🔌 Give agent access to MCPs (web search + website reading)
    .with_mcps(["search_web", "read-website"])
    # 🛠️ Give agent access to custom tools (file writing + date)
    .with_tools([write_file, get_current_date])
    .publishes(Report)
)

# 🎉 THE POWER:
# This agent can now:
# 1. Read the Task description
# 2. Search the web with DuckDuckGo MCP
# 3. Read multiple website pages with read-website MCP
# 4. Get today's date with get_current_date tool
# 5. Write a markdown file with write_file tool
# 6. Return a Report with metadata
#
# All declaratively. No step-by-step "first search, then read, then write" logic.
# The LLM figures out the workflow based on the tools available and schema required.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚀 STEP 5: Run the Research Agent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


async def main():
    """
    Let's do some research! The agent will:
    - Search for relevant info
    - Read multiple sources
    - Synthesize findings into a markdown report
    - Save it with today's date in the filename
    """

    # Create a research task
    task = Task(description="A review meta overview of the movie 'Dune: Part Two'")

    print(f"🔎 Research task: {task.description}")
    print("🌐 Web researcher is gathering information...\n")
    print("📡 This will:")
    print("   1. Search DuckDuckGo for relevant articles")
    print("   2. Read top results from multiple sources")
    print("   3. Synthesize findings into a markdown report")
    print("   4. Save it to .flock/ with today's date\n")

    # Publish and wait
    await flock.publish(task)
    await flock.run_until_idle()

    # Retrieve the report
    reports = await flock.store.get_by_type(Report)

    if reports:
        report = reports[0]
        print("✅ Research complete!\n")
        print(f"📄 Report saved to: {report.file_path}")
        print(f"🏷️  Title: {report.title}")
        print(f"🔗 Researched {len(report.researched_urls)} URLs:")
        for url in report.researched_urls[:3]:  # Show first 3
            print(f"   - {url}")
        if len(report.researched_urls) > 3:
            print(f"   ... and {len(report.researched_urls) - 3} more")

        print(f"\n💡 Key insights discovered: {len(report.high_impact_info)}")

        print("\n👉 Check the .flock/ directory for the full markdown report!")
    else:
        print("❌ No report was generated!")
        print("💡 Make sure the MCPs are installed (see prerequisites above)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🎓 WHAT YOU JUST LEARNED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# ✅ @flock_tool Decorator
#    - Turns Python functions into agent capabilities
#    - Docstrings become tool descriptions for the LLM
#    - Agents call them when needed (not explicit if/else)
#
# ✅ MCP Integration
#    - Model Context Protocol = external tool plugins
#    - Add with flock.add_mcp(...)
#    - Enable with .with_mcps([...])
#    - DuckDuckGo search, website reading, databases, APIs, etc.
#
# ✅ Tool Composition
#    - Agents can use MULTIPLE tools in one workflow
#    - Search web → Read pages → Get date → Write file
#    - No explicit orchestration - LLM figures out the sequence
#
# ✅ Real-World Interaction
#    - Not just text transformation anymore
#    - Agents can search, read, write, call APIs
#    - Declarative intent meets executable actions
#
# 💡 THE BIG IDEA:
# Schemas define WHAT to produce.
# Tools define WHAT agents can DO.
# The LLM figures out HOW to use tools to satisfy the schema.
#
# This is the bridge between reasoning and action.
#
# 🎓 YOU'VE COMPLETED THE DECLARATIVE WAY!
#
# You now understand:
# 1. Declarative schemas replace prompts (01_declarative_pizza.py)
# 2. Complex types express business logic (02_input_and_output.py)
# 3. Tools + MCPs enable real-world actions (03_mcp_and_tools.py)
#
# 🚀 NEXT STEPS:
# - Try [05-claudes-workshop/](../05-claudes-workshop/) for 7 progressive lessons ✅
# - Explore [02-the-blackboard/](../02-the-blackboard/) multi-agent workflows 🚧 (coming soon)
# - Build something! The declarative way scales to production.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    asyncio.run(main())
