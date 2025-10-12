import asyncio

from pydantic import BaseModel, Field

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
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

flock = Flock("openai/gpt-4.1")

try:
    flock.add_mcp(
        name="search",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="uvx",
            args=["duckduckgo-mcp-server"],
        ),
    )
    print("[OK] Added search MCP")
except Exception as e:
    print(f"[WARNING] Could not add search MCP: {e}")

try:
    flock.add_mcp(
        name="web_reader",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@just-every/mcp-read-website-fast"],
        ),
    )
    print("[OK] Added web reader MCP")
except Exception as e:
    print(f"[WARNING] Could not add web reader MCP: {e}")

web_detective = (
    flock.agent("web_detective")
    .description("Research detective who searches and analyzes web content")
    .consumes(ResearchQuery)
    .with_mcps(["search", "web_reader"])
    .with_tools([save_research])
    .publishes(ResearchReport)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
