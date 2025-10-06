import asyncio

from pydantic import BaseModel, Field

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
pizza_master = (
    flock.agent("pizza_master")
    .consumes(MyDreamPizza)
    .publishes(Pizza)
)


# 4. Run!
async def main():
    pizza_idea = MyDreamPizza(pizza_idea="the ultimate spicy pepperoni pizza")
    await flock.publish(pizza_idea)
    await flock.run_until_idle()
    print("✅ Pizza recipe generated!")


asyncio.run(main(), debug=True)
