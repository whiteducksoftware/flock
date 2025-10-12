import asyncio

from pydantic import BaseModel, Field

from flock.orchestrator import Flock
from flock.registry import flock_type


@flock_type
class MyDreamPizza(BaseModel):
    pizza_idea: str = Field(default="Pizza with pineapple",description="A short description of your dream pizza")

@flock_type
class Pizza(BaseModel):
    ingredients: list[str]
    size: str
    crust_type: str
    step_by_step_instructions: list[str]

flock = Flock("openai/gpt-4.1")

pizza_master = (
    flock.agent("pizza_master")
    .consumes(MyDreamPizza)
    .publishes(Pizza)
)

asyncio.run(flock.serve(dashboard=True), debug=True)
