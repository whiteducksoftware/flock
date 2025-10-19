"""
Getting Started: Declarative Pizza Generation

This example demonstrates the core concept of Flock: agents declaring what they
consume and produce, with the orchestrator handling the rest.

🎛️  CONFIGURATION: Set USE_DASHBOARD to switch between CLI and Dashboard modes
"""

import asyncio

from pydantic import BaseModel, Field

from flock import Flock
from flock.registry import flock_type

# ============================================================================
# 🎛️  CONFIGURATION: Switch between CLI and Dashboard modes
# ============================================================================
USE_DASHBOARD = True  # Set to True for dashboard mode, False for CLI mode
# ============================================================================


@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str = Field(
        default="Pizza with pineapple", description="A short description of your dream pizza"
    )


@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]


flock = Flock()

pizza_master = flock.agent("pizza_master").consumes(MyDreamPizza).publishes(Pizza)


async def main_cli():
    """CLI mode: Run agents and display results in terminal"""
    pizza_idea = MyDreamPizza(pizza_idea="pizza with pineapple")
    await flock.publish(pizza_idea)
    await flock.run_until_idle()
    print("✅ Pizza generation complete! Check the dashboard for results.")


async def main_dashboard():
    """Dashboard mode: Serve with interactive web interface"""
    await flock.serve(dashboard=True)


async def main():
    if USE_DASHBOARD:
        await main_dashboard()
    else:
        await main_cli()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
