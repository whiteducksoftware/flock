import asyncio
from typing import Literal

from pydantic import BaseModel

from flock.mcp import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_tool, flock_type


@flock_tool
def write_file(string: str, file_path: str) -> None:
    with open(file_path, "w") as f:
        f.write(string)


@flock_type
class Url(BaseModel):
    url: str


@flock_type
class WebsiteAnalysis(BaseModel):
    url: str
    title: str
    headings: list[str]
    entities: dict[str, str]
    site_type: Literal["news", "blog", "opinion piece", "tweet"]


flock = Flock(model="openai/gpt-4.1")

flock.add_mcp(
    name="read-website-fast-mcp-server",
    enable_tools_feature=True,
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@just-every/mcp-read-website-fast"],
    ),
)


(
    flock.agent("website_analyzer")
    .description("Analysis of a website and writes a report to report.md")
    .consumes(Url)
    .with_mcps(["read-website-fast-mcp-server"])
    .with_tools([write_file])
    .publishes(WebsiteAnalysis)
)


# 4. Run!
async def main():
    idea = Url(
        url="https://lite.cnn.com/travel/alexander-the-great-macedon-persian-empire-darius/index.html"
    )
    await flock.publish(idea)
    await flock.run_until_idle()
    print("✅ Website analysis report generated!")


asyncio.run(main())
