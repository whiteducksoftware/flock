"""
Tutorial Example: Creating a agent chain, without agents

also called state machine

In this example, we create a simple two-agent chain:
  1. DoublerAgent: Receives a number ("value") and outputs its double ("doubled").
  2. AdderAgent: Takes the "doubled" value from the previous agent and adds 5 to produce "result".

The special thing about this example is that we don't use any external tools or LLMs.
Instead, we create a simple chain of agents that pass data between each other.

"""

import asyncio
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent

# Define a simple agent that doubles the input value.
class DoublerAgent(FlockAgent):
    async def evaluate(self, inputs: dict[str, any]) -> dict[str, any]:
        # Retrieve the input value (defaulting to 0 if not provided)
        value = inputs.get("value", 0)
        # Return the doubled value
        return {"doubled": value * 2}

# Define another agent that adds 5 to the doubled value.
class AdderAgent(FlockAgent):
    async def evaluate(self, inputs: dict[str, any]) -> dict[str, any]:
        # Retrieve the "doubled" value (defaulting to 0 if not provided)
        doubled = inputs.get("doubled", 0)
        # Return the final result after adding 5
        return {"result": doubled + 5}

async def main():
    # --------------------------------
    # Create the flock
    # --------------------------------
    # Create a Flock instance in local debug mode (no Temporal needed for this simple demo)
    flock = Flock()

    # --------------------------------
    # Create the agents
    # --------------------------------
    # Define the doubler agent:
    doubler = DoublerAgent(
        name="doubler_agent",
        input="value: int | The number to double",
        output="doubled: int | The doubled value",
    )

    # Define the adder agent:
    adder = AdderAgent(
        name="adder_agent",
        input="doubled: int | The doubled value from the previous agent",
        output="result: int | The final result after adding 5",
    )

    # --------------------------------
    # Set up hand-off
    # --------------------------------
    # Link the agents so that the output of doubler is passed to adder automatically.
    doubler.hand_off = adder

    # Register both agents with the flock.
    flock.add_agent(doubler)
    flock.add_agent(adder)

    # --------------------------------
    # Run the agent chain
    # --------------------------------
    # Start the workflow with the doubler agent and provide the initial input.
    result = await flock.run_async(start_agent=doubler, input={"value": 10})
    
    # Print the final result. Expected output: result should be (10*2)+5 = 25.
    print(result)

if __name__ == "__main__":
    asyncio.run(main())
