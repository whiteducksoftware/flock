"""
Getting Started: Web Detective

This example demonstrates multi-agent workflows where agents consume and produce
in a chain, with each agent building on previous results.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock.mcp import StdioServerParameters
from flock import Flock
from flock.registry import flock_tool, flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_tool
def save_research(html: str, file_name: str) -> None:
    """Writes a research report to a html file. Beautifully styled."""
    from pathlib import Path

    file_path = Path(".flock") / file_name
    directory = file_path.parent
    if directory and not directory.exists():
        directory.mkdir(parents=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✍️  Wrote file: {file_path}")


@flock_type
class ResearchQuery(BaseModel):
    topic: str
    depth: str
    focus_areas: list[str]


@flock_type
class ResearchReport(BaseModel):
    title: str
    summary: str
    key_findings: list[str]
    sources: list[str]
    confidence_level: float = Field(ge=0.0, le=1.0)
    file_path: str


flock = Flock()

try:
    flock.add_mcp(
        name="search",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="uvx",
            args=["duckduckgo-mcp-server"],
        ),
    )
    print("✅ Added search MCP")
except Exception as e:
    print(f"⚠️  Could not add search MCP: {e}")

try:
    flock.add_mcp(
        name="web_reader",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@just-every/mcp-read-website-fast"],
        ),
    )
    print("✅ Added web reader MCP")
except Exception as e:
    print(f"⚠️  Could not add web reader MCP: {e}")

web_detective = (
    flock.agent("web_detective")
    .description("Research detective who searches and analyzes web content")
    .consumes(ResearchQuery)
    .with_mcps(["search", "web_reader"])
    .publishes(ResearchReport)
)

web_digger = (
    flock.agent("web_digger")
    .description(
        "Diggs deep into the web to find additional info to extend a research report and saves the final research to a file"
    )
    .consumes(ResearchReport)
    .with_mcps(["search", "web_reader"])
    .with_tools([save_research])
    .publishes(ResearchReport)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    query = ResearchQuery(
        topic="Are blackboard multi agent systems the future of AI?",
        depth="comprehensive and detailed",
        focus_areas=[
            "potential research",
            "novel orchestration possibilities",
            "world changing applications",
        ],
    )

    print(f"🔍 Starting research: {query.topic}\n")

    await flock.publish(query)
    await flock.run_until_idle()

    reports = await flock.store.get_by_type(ResearchReport)

    if reports:
        report = reports[0]
        print("\n📊 RESEARCH REPORT:")
        print(f"   Title: {report.title}")
        print(f"   Summary: {report.summary[:150]}...")
        print(f"   Key Findings: {len(report.key_findings)}")
        print(f"   Sources: {len(report.sources)}")
        print(f"   Confidence: {report.confidence_level:.2f}")
        print(f"   Saved to: {report.file_path}")


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
