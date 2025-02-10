
# Getting into the details with descriptions

In this example, we demonstrate how to use **descriptions** in Flock agents to handle edge cases. The `description` property on the `FlockAgent` class, along with inline field descriptions using `|`, allows you to provide detailed instructions for both input and output, ensuring your agents behave precisely as intended.

---

## Code Example

### 1. Imports and Model Definition

```python
import asyncio

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent

MODEL = "openai/gpt-4o"
```

### 2. Creating the Agent with Descriptions

```python
async def main():
 
    flock = Flock(model=MODEL, local_debug=True)

    # --------------------------------
    # Add descriptions
    # --------------------------------
    # If you NEED your agent to handle edge cases, you can add descriptions to your agents.
    # The description property on the FlockAgent class allows you to add a description to your agent,
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
```

---

## Summary

This example shows how adding **descriptions** to your Flock agents can provide detailed context for handling edge cases. By specifying clear descriptions for both input and output fields, you ensure that your agent operates under well-defined conditions, enhancing its robustness and clarity.
