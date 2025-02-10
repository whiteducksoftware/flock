"""
Title: Getting into the details with descriptions

Perhaps your co-worker who loves writing blog post long prompts for his agents thought he has found an out:
"Due to my long prompts I can make my agents do anything I want, which is not possible with your little declarative flocky!" he proclaimed.
"What do you do when you need your agents to handle edge cases?" he asked. 

You, being the flocky expert, decided to show him how to use 'descriptions' to make your agents do anything his agents can do and more.
"""

import asyncio

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent


MODEL = "openai/gpt-4o"

async def main():
 
    flock = Flock(model=MODEL, local_debug=True)

    # --------------------------------
    # Add descriptions
    # --------------------------------
    # If you NEED your agent to handle edge cases, you can add descriptions to your agents
    # The desctiption property on the FlockAgent class allows you to add a description to your agent,
    # while with "|" you can specify descriptions of the input and output fields of the agent.
    a_cat_name_agent = FlockAgent(
        name="name_agent", 
        description="Creates five ideas for cute pet names but only for cats and will reject any other animals.",
        input="animal | the animal to create a cute name for", 
        output="""
            cute_name: list[str] | a list of 5 cute names IN ALL CAPS, 
            error_message | an error message if the input is not a cat
        """
    )
    flock.add_agent(a_cat_name_agent)

  
    await flock.run_async(
        start_agent=a_cat_name_agent, 
        input={"animal": "My new dog"}
    )

if __name__ == "__main__":
    asyncio.run(main())
