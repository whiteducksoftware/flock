import asyncio

from pydantic import BaseModel, Field

from flock.mcp import StdioServerParameters
from flock import Flock
from flock.registry import flock_tool, flock_type


@flock_tool
def save_research(content: str, filename: str) -> str:
    from pathlib import Path

    path = Path(".flock") / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return str(path)


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
    print(f"⚠️ Could not add search MCP: {e}")

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
    print(f"⚠️ Could not add web reader MCP: {e}")

web_detective = (
    flock.agent("web_detective")
    .description("Research detective who searches and analyzes web content")
    .consumes(ResearchQuery)
    .with_mcps(["search", "web_reader"])
    .with_tools([save_research])
    .publishes(ResearchReport)
)


async def main():
    queries = [
        ResearchQuery(
            topic="Latest developments in quantum computing",
            depth="comprehensive",
            focus_areas=["hardware advances", "software frameworks", "commercial applications"],
        ),
        ResearchQuery(
            topic="Sustainable agriculture technologies 2025",
            depth="overview",
            focus_areas=["vertical farming", "AI crop monitoring", "water conservation"],
        ),
    ]

    for query in queries:
        print(f"🔍 Starting research: {query.topic}")
        await flock.publish(query)

    await flock.run_until_idle()

    reports = await flock.store.get_by_type(ResearchReport)

    for i, report in enumerate(reports):
        print(f"\n📊 RESEARCH REPORT {i + 1}:")
        print(f"   Title: {report.title}")
        print(f"   Summary: {report.summary[:150]}...")
        print(f"   Key Findings: {len(report.key_findings)}")
        print(f"   Sources: {len(report.sources)}")
        print(f"   Confidence: {report.confidence_level:.2f}")
        print(f"   Saved to: {report.file_path}")


if __name__ == "__main__":
    asyncio.run(main())
