import asyncio

from pydantic import BaseModel

from flock.orchestrator import Flock
from flock.registry import flock_type


# 1. Define typed artifacts
@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str


@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]


# 2. Create orchestrator
flock = Flock("openai/gpt-4.1")

# 3. Define agent with 0 natural language
pizza_master = flock.agent("pizza_master").consumes(MyDreamPizza).publishes(Pizza)


# 4. Run with unified tracing!
async def main():
    # Option 1: Explicit unified tracing (RECOMMENDED)
    # All operations will be in a single trace called "pizza_workflow"
    async with flock.traced_run("pizza_workflow"):
        pizza_idea = MyDreamPizza(pizza_idea="the ultimate spicy pepperoni pizza")
        await flock.publish(pizza_idea)
        await flock.run_until_idle()
    print("✅ Pizza recipe generated!")

    # Option 2: Without traced_run (old behavior - separate traces)
    # Uncomment to see the difference:
    # pizza_idea = MyDreamPizza(pizza_idea="the ultimate spicy pepperoni pizza")
    # await flock.publish(pizza_idea)  # ← Separate trace
    # await flock.run_until_idle()     # ← Separate trace

    # Bonus: Clear traces for a fresh debug session
    # result = Flock.clear_traces()
    # print(f"🗑️  Cleared {result['deleted_count']} trace spans")


asyncio.run(main(), debug=True)
