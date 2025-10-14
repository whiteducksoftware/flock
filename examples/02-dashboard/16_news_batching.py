import asyncio
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field

from flock.mcp.types.types import StdioServerParameters
from flock.orchestrator import Flock
from flock.registry import flock_type
from flock.subscription import BatchSpec


@flock_type
class Trigger(BaseModel):
    today_date: str = Field(
        default=datetime.now(tz=timezone.utc).strftime("%Y-%m-%d"),
        description="Today's date in YYYY-MM-DD format",
    )


@flock_type
class NewsAnalysis(BaseModel):
    category: str
    key_takeaways: list[str]
    impact_assessment: str


@flock_type
class NewsDigest(BaseModel):
    summary_title: str
    summary_of_all_news: list[str]
    key_takeaways: list[str]


flock = Flock()

flock.add_mcp(
    name="search_web",
    enable_tools_feature=True,
    connection_params=StdioServerParameters(
        command="uvx",
        args=["duckduckgo-mcp-server"],
    ),
)

flock.add_mcp(
    name="web_reader",
    enable_tools_feature=True,
    connection_params=StdioServerParameters(
        command="npx",
        args=["-y", "@just-every/mcp-read-website-fast"],
    ),
)

categories = [
    "world",
    "tech",
    "business",
    "sports",
    "entertainment",
    "science",
    "politics",
    "health",
]

for category in categories:
    (
        flock.agent(f"{category}_analyst")
        .description(
            f"Searches the web for {category} news and provides key takeaways and impact assessment."
        )
        .with_mcps(["search_web", "web_reader"])
        .consumes(Trigger)
        .publishes(NewsAnalysis)
    )


editor = (
    flock.agent("editor")
    .consumes(NewsAnalysis, batch=BatchSpec(size=8, timeout=timedelta(seconds=60)))
    .publishes(NewsDigest)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
