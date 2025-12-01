

from flock import Flock, flock_type
from pydantic import BaseModel, Field
import asyncio



@flock_type
class Prompt(BaseModel):
    prompt: str
    variable_to_value_list: str


class VarList(BaseModel):
    variable: str
    description: str = Field(description="A description of the variable to create a list of values for with potential constraints ond rules")
    values: list[str] = Field(default_factory=list, min_length=10)

flock = Flock("transformers/unsloth/Qwen3-4B-Instruct-2507-bnb-4bit")

z = flock.agent("z").consumes(Prompt).publishes(VarList)

async def main():

    await flock.publish(Prompt(prompt="A __detailed_movie_scene__(a pretty woman as subject) shot by __movie_director__!", variable_to_value_list="__detailed_movie_scene__"))

    await flock.run_until_idle()

    var_lists = await flock.store.get_by_type(VarList)
    if var_lists:
        var_list = var_lists[0]
        print(f"Variable: {var_list.variable}")
        print(f"Description: {var_list.description}")
        print(f"Values: {var_list.values}")

asyncio.run(main())
