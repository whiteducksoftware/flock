
# Random User List Generator with Data Class Integration and Caching

In this example, you'll see a simple Flock agent in action that generates a list of random users. This example demonstrates several cool features:

- **Data Class Integration:** We define a `RandomPerson` dataclass to structure the random user data.
- **Caching:** Enabled caching ensures that if you run the agent with the same input, it will return a cached result—ideal for speeding up repeated requests.
- **Simple Agent Declaration:** Like all Flock agents, this one declares what it needs ("amount_of_people") and what it produces ("random_user_list: list[RandomPerson]") without the hassle of prompt engineering.

In this scenario, our agent ("people_agent") takes the number of people to generate as input and returns a list of randomly generated users. We then print the number of generated users.

Let's see how it's done!

---

## Code Example

### 1. Imports and Data Model

```python
import asyncio
from dataclasses import dataclass
from pprint import pprint
from typing import Literal

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter
from flock.core.tools import basic_tools

# --------------------------------
# Define the data model for a random person
# --------------------------------
@dataclass
class RandomPerson:
    name: str
    age: int
    gender: Literal["female", "male"]
    job: str
    favorite_movie: str  
    short_bio: str
```

### 2. Creating and Running the Agent

```python
async def main():
   
    flock = Flock(local_debug=True)

    # --------------------------------
    # Define the Random User List Agent
    # --------------------------------
    # This agent ("people_agent") is responsible for generating a list of random users.
    # It requires the input "amount_of_people" and produces an output "random_user_list" 
    # which is a list of RandomPerson objects.
    # Caching is enabled so that repeated requests with the same input can return a cached result.
    people_agent = FlockAgent(
        name="people_agent",
        input="amount_of_people",
        output="random_user_list: list[RandomPerson]",
        use_cache=True,
    )
    flock.add_agent(people_agent)

    # --------------------------------
    # Run the agent to generate random users
    # --------------------------------
    # We execute the agent asynchronously, passing in the desired amount of people.
    # The result is a namespace containing the generated random user list.
    result = await flock.run_async(
        start_agent=people_agent,
        input={"amount_of_people": "10"},
    )

    # --------------------------------
    # Process and display the result
    # --------------------------------
    # Here we print the number of users generated to verify our agent's output.
    pprint(len(result.random_user_list))

if __name__ == "__main__":
    # Run the main coroutine using asyncio
    asyncio.run(main())
```

---

## Summary

This example demonstrates a Flock agent that generates a list of random users using a dataclass for structured output and caching for efficient repeated requests. The code is organized into clear sections for data modeling, agent definition, and execution.
