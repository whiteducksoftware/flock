

# Celebrity Age Calculator with Themed Output and Tool Integration

In this example, we demonstrate how to build a **Flock agent** that:

- **Applies a custom theme** to the CLI output.
- **Integrates external tools** such as web search and code evaluation.
- **Uses caching** to optimize repeated operations.
- **Declaratively defines** its inputs and outputs for clarity.

The agent calculates the age in days for a given celebrity (in our case, Johnny Depp) and is built following best practices for readability, modularity, and maintainability.

---



## Code Example

### 1. Imports and Initial Configuration

```python
import asyncio
from devtools import debug

# Import Flock components and supporting modules.
from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter
from flock.core.tools import basic_tools

# Define the model to be used (if applicable).
MODEL = "openai/gpt-4o"
```

### 2. Agent Setup and Configuration

```python
async def main():
    # Initialize the output formatter with a custom theme.
    format_options = FormatterOptions(
        ThemedAgentResultFormatter,
        wait_for_input=False,
        settings={"theme": "adventuretime"}
    )
    
    # Create the Flock instance with debugging enabled.
    flock = Flock(local_debug=True, output_formatter=format_options)
    
    # Configure the agent:
    # - 'input': what the agent expects.
    # - 'output': what the agent produces.
    # - 'tools': external functionalities integrated into the agent.
    # - 'use_cache=True': enables caching for repeated inputs.
    agent = FlockAgent(
        name="my_celebrity_age_agent",
        input="a_person",
        output="persons_age_in_days",
        tools=[basic_tools.web_search_tavily, basic_tools.code_eval],
        use_cache=True,
    )
    flock.add_agent(agent)
    
    # Run the agent with the input 'Johnny Depp' to calculate his age in days.
    await flock.run_async(
        start_agent=agent,
        input={"a_person": "Johnny Depp"}
    )

if __name__ == "__main__":
    asyncio.run(main())
```

