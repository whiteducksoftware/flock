"""
Example demonstrating .env file loading in Flock.

This example shows how environment variables are automatically loaded
from .env files when importing or using Flock.
"""

import asyncio
import os

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type


@flock_type
class MyPizzaIdea(BaseModel):
    pizza_idea: str = Field(
        default="Pizza with pineapple",
        description="A short description of your dream pizza",
    )


@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]


# Create Flock instance - will automatically use DEFAULT_MODEL from .env if available
flock = Flock()

pizza_master = flock.agent("pizza_master").consumes(MyPizzaIdea).publishes(Pizza)


async def main():
    """Run the pizza generation example."""
    pizza_idea = MyPizzaIdea(pizza_idea="pizza with pineapple")
    await flock.publish(pizza_idea)
    await flock.run_until_idle()
    
    print("✅ Pizza generation complete!")
    print(f"🔧 Using model: {flock.model}")
    print(f"🔧 API key configured: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
    print(f"🔧 Auto-tracing enabled: {os.getenv('FLOCK_AUTO_TRACE', 'true')}")


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
