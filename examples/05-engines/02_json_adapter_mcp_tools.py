"""
DSPy JSONAdapter with MCP Tools: Native Function Calling

This example demonstrates JSONAdapter's native function calling feature
for better integration with MCP tools.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.engines import DSPyEngine, JSONAdapter
from flock.registry import flock_type


# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class ResearchQuery(BaseModel):
    topic: str = Field(description="Research topic")
    depth: str = Field(
        default="medium", description="Research depth: shallow, medium, deep"
    )


@flock_type
class ResearchReport(BaseModel):
    summary: str = Field(description="Research summary")
    sources: list[str] = Field(description="List of source URLs or file paths")
    findings: list[str] = Field(description="Key findings")


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    flock = Flock()

    # Note: To use MCP tools, you need to register MCP servers first
    # Example:
    # from flock.mcp import StdioServerParameters
    # flock.add_mcp(
    #     name="filesystem",
    #     connection_params=StdioServerParameters(
    #         command="npx",
    #         args=["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]
    #     )
    # )

    # Agent with JSONAdapter + MCP tools
    # JSONAdapter enables native function calling by default
    researcher = (
        flock.agent("researcher")
        .description(
            "Research agent using JSONAdapter with native function calling. "
            "Can use MCP tools for file operations, web searches, etc."
        )
        .consumes(ResearchQuery)
        .publishes(ResearchReport)
        # Uncomment when MCP servers are registered:
        # .with_mcps(["filesystem", "github"])  # MCP tools available
        .with_engines(
            DSPyEngine(
                adapter=JSONAdapter(),  # Native function calling enabled by default
                stream=False,  # Disable streaming for cleaner output
            )
        )
    )

    query = ResearchQuery(
        topic="Python async/await best practices",
        depth="deep",
    )

    print("🔍 Researching with JSONAdapter + MCP tools...")
    print(f"   Topic: {query.topic}")
    print(f"   Depth: {query.depth}\n")
    await flock.publish(query)
    await flock.run_until_idle()

    # Get results
    results = await flock.store.get_by_type(ResearchReport)
    if results:
        result = results[0]
        print(f"✅ Summary: {result.summary}\n")
        print(f"📚 Sources ({len(result.sources)}):")
        for i, source in enumerate(result.sources, 1):
            print(f"   {i}. {source}")
        print(f"\n🔍 Findings ({len(result.findings)}):")
        for i, finding in enumerate(result.findings, 1):
            print(f"   {i}. {finding}")

    print("\n✅ Research complete!")
    print("\n💡 JSONAdapter Benefits:")
    print("   - Native function calling enabled by default")
    print("   - Better integration with MCP tools")
    print("   - More reliable structured output parsing")
    print("   - Uses OpenAI's structured outputs API when supported")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await Flock().serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
