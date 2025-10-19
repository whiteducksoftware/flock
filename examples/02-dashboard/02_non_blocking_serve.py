"""Example demonstrating non-blocking serve() for dashboard demos.

This example shows how to use serve(blocking=False) to start the dashboard
server in the background, allowing you to publish messages and run other
logic after the server starts.

This is particularly useful for:
- Demo scripts that need to populate data after starting the dashboard
- Testing scenarios where you want to control execution flow
- Scripts that need to perform setup after the server is running
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str = Field(
        description="A short description of your dream pizza",
    )


@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]


async def main():
    """Main demo showing non-blocking serve usage."""
    # Create orchestrator and agent
    flock = Flock()
    flock.agent("pizza_master").consumes(MyDreamPizza).publishes(Pizza)

    print("🚀 Starting dashboard in background (non-blocking mode)...")

    # Start dashboard in non-blocking mode - returns immediately!
    server_task = await flock.serve(dashboard=True, blocking=False)

    print("✅ Dashboard started! Server is running in the background.")
    print("📊 Dashboard available at: http://localhost:8344")
    print()

    # Now we can publish messages AFTER starting the server!
    print("🍕 Publishing pizza ideas...")

    pizza_ideas = [
        "Classic Margherita with fresh basil",
        "BBQ Chicken with red onions",
        "Vegetarian Supreme with roasted vegetables",
    ]

    for i, idea in enumerate(pizza_ideas, 1):
        print(f"   {i}. {idea}")
        pizza = MyDreamPizza(pizza_idea=idea)
        await flock.publish(pizza)
        await asyncio.sleep(0.5)  # Small delay between publishes

    print()
    print("⏳ Processing pizza orders...")

    # Process all the messages we just published
    await flock.run_until_idle()

    print()
    print("✨ All pizzas created!")
    print("🎯 Dashboard is still running - open http://localhost:8344 to see the results")
    print()
    print("💡 Benefits of non-blocking serve:")
    print("   - Can publish messages after server starts")
    print("   - Dashboard stays alive for inspection")
    print("   - Perfect for demos and testing")
    print()
    print("Press Ctrl+C to stop the server...")

    # Keep server running indefinitely for inspection
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        server_task.cancel()
        try:
            await server_task
        except asyncio.CancelledError:
            pass
        print("✅ Server stopped. Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
