import asyncio

from pydantic import BaseModel, Field

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_tool, flock_type
from flock.logging.logging import configure_logging

configure_logging(flock_level="DEBUG", external_level="DEBUG")


@flock_tool
def write_report(string: str, file_name: str) -> None:
    """Writes a research report to a markdown file. FILE NAME IN CAPS AND WITH CURRENT DATE."""
    from pathlib import Path
    file_path = Path(".flock") / file_name
    directory = file_path.parent
    if directory and not directory.exists():
        directory.mkdir(parents=True)
    with open(file_path, "w") as f:
        f.write(string)
    print(f"[WRITE] Wrote file: {file_path}")

@flock_tool
def get_current_date() -> str:
    """Returns the current date in YYYY-MM-DD format."""
    from datetime import UTC, datetime
    return datetime.now(UTC).strftime("%Y-%m-%d")

@flock_type
class Task(BaseModel):
    description: str = Field(default="Are blackboard multi agent systems the future of AI?",
                             description="A concise description of the research task")

@flock_type
class Report(BaseModel):
    file_path: str
    title: str
    researched_urls: list[str]
    high_impact_info: dict[str, str]

flock = Flock(model="openai/gpt-4.1")

try:
    flock.add_mcp(
        name="search_web",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="uvx",
            args=["duckduckgo-mcp-server"],
        ),
    )
    print("[OK] Added DuckDuckGo search MCP")
except Exception as e:
    print(f"[WARNING] Could not add search MCP (is uvx installed?): {e}")

try:
    flock.add_mcp(
        name="read-website",
        enable_tools_feature=True,
        connection_params=StdioServerParameters(
            command="npx",
            args=["-y", "@just-every/mcp-read-website-fast"],
        ),
    )
    print("[OK] Added website reader MCP")
except Exception as e:
    print(f"[WARNING] Could not add website reader MCP (is npm installed?): {e}")

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


asyncio.run(flock.serve(dashboard=True), debug=True)

