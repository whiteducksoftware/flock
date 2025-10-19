"""
Getting Started: MCP and Tools

This example demonstrates using Model Context Protocol (MCP) to integrate external
tools like web search and file operations into your agents.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel

from flock.mcp import StdioServerParameters
from flock import Flock
from flock.registry import flock_tool, flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_tool
def write_report(string: str, file_name: str) -> None:
    """Writes a research report to a markdown file. FILE NAME IN CAPS AND WITH CURRENT DATE."""
    from pathlib import Path

    file_path = Path(".flock") / file_name
    directory = file_path.parent
    if directory and not directory.exists():
        directory.mkdir(parents=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(string)
    print(f"✍️  Wrote file: {file_path}")


@flock_tool
def get_current_date() -> str:
    """Returns the current date in YYYY-MM-DD format."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d")


@flock_type
class Task(BaseModel):
    description: str


@flock_type
class Report(BaseModel):
    file_path: str
    title: str
    researched_urls: list[str]
    high_impact_info: dict[str, str]


flock = Flock()

try:
    flock.add_mcp(
        name="search_web",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="uvx",
            args=["duckduckgo-mcp-server"],
        ),
    )
    print("✅ Added DuckDuckGo search MCP")
except Exception as e:
    print(f"⚠️  Could not add search MCP (is uvx installed?): {e}")

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

(
    flock.agent("web_researcher")
    .description(
        "Researches information on the web and writes a beautifully "
        "formatted markdown report with sources and key insights."
    )
    .consumes(Task)
    .with_mcps(["search_web", "read-website"])
    .with_tools([write_report, get_current_date])
    .publishes(Report)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    task = Task(description="Are blackboard multi agent systems the future of AI?")
    print(f"🔍 Research task: {task.description}")
    print("🕵️  Web researcher is gathering information...\n")
    print("📡 This will:")
    print("   1. Search DuckDuckGo for relevant articles")
    print("   2. Read top results from multiple sources")
    print("   3. Synthesize findings into a markdown report")
    print("   4. Save it to .flock/ with today's date\n")
    await flock.publish(task)
    await flock.run_until_idle()
    reports = await flock.store.get_by_type(Report)
    if reports:
        report = reports[0]
        print("✅ Research complete!\n")
        print(f"📄 Report saved to: {report.file_path}")
        print(f"🏷️  Title: {report.title}")
        print(f"🔗 Researched {len(report.researched_urls)} URLs:")
        for url in report.researched_urls[:3]:
            print(f"   - {url}")
        if len(report.researched_urls) > 3:
            print(f"   ... and {len(report.researched_urls) - 3} more")
        print(f"\n💡 Key insights discovered: {len(report.high_impact_info)}")
        print("\n👉 Check the .flock/ directory for the full markdown report!")
    else:
        print("❌ No report was generated!")
        print("💡 Make sure the MCPs are installed (see prerequisites above)")


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
