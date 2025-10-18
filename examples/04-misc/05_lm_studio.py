import asyncio

from pydantic import BaseModel

from flock import Flock
from flock.registry import flock_type


@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str


@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]


# Use OPENAI_BASE_URL="http://localhost:1234/v1" in .env to point to LM Studio
flock = Flock("openai/gpt-oss-20b")

pizza_master = flock.agent("pizza_master").consumes(MyDreamPizza).publishes(Pizza)


async def main():
    pizza_idea = MyDreamPizza(pizza_idea="pizza with tartufo")
    await flock.publish(pizza_idea)
    await flock.run_until_idle()


if __name__ == "__main__":
    asyncio.run(main(), debug=True)
