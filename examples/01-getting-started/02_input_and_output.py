"""
Getting Started: Input and Output

This example shows how to create agents that consume input and produce output,
with proper type definitions and documentation.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = False  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class UserRequest(BaseModel):
    message: str
    priority: str = "normal"


@flock_type
class Response(BaseModel):
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str]


flock = Flock()

assistant = (
    flock.agent("assistant")
    .description("Helpful assistant that answers questions with sources")
    .consumes(UserRequest)
    .publishes(Response)
)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    request = UserRequest(
        message="What are the key benefits of async programming?", priority="high"
    )

    print(f"❓ Question: {request.message}")
    print(f"📌 Priority: {request.priority}\n")

    await flock.publish(request)
    await flock.run_until_idle()

    responses = await flock.store.get_by_type(Response)
    if responses:
        response = responses[0]
        print(f"💡 Answer: {response.answer}\n")
        print(f"📊 Confidence: {response.confidence:.2f}")
        print(f"📚 Sources: {len(response.sources)}")
        for i, source in enumerate(response.sources, 1):
            print(f"   {i}. {source}")


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
