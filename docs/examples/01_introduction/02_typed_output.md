
# Advanced Flock Agent with Caching, Type Hints, and Tool Integration

In this example, we'll show you how to build a more advanced Flock system that:

- Uses a custom output formatter (RichTables) for a polished, swaggy display.
- Defines output types using standard Python type hints (including lists and Literals) for structured results.
- Integrates external tools (like a web content scraper) so that agents can perform more complex operations.
- Leverages caching so that if an agent is called with the same input, the cached result is returned—this is particularly useful for expensive operations such as web scraping or during debugging.

The agent takes a URL as input and outputs:

- A title,
- A list of headings,
- A list of dictionaries mapping entities to metadata, and
- A type (limited to one of 'news', 'blog', 'opinion piece', or 'tweet').

After executing the agent, you can work with the result as a real Python object that respects the defined types.

Let's dive in!

---

## Code Example

### 1. Imports and Formatter Setup

```python
import asyncio
from pprint import pprint

from flock.core.flock import Flock
from flock.core.flock_agent import FlockAgent
from flock.core.logging.formatters.base_formatter import FormatterOptions
from flock.core.logging.formatters.rich_formatters import RichTables
from flock.core.logging.formatters.themed_formatter import ThemedAgentResultFormatter
from flock.core.tools import basic_tools
```

### 2. Creating and Running the Agent

```python
async def main():
    # --------------------------------
    # Create the flock
    # --------------------------------
    # Some people need some swag in their output
    # See the formatting examples
    format_options = FormatterOptions(RichTables)
    flock = Flock(local_debug=True, output_formatter=format_options)

    # --------------------------------
    # Create an agent
    # --------------------------------
    # Some additions to example 01:
    # - You can define the output types of the agent with standard python type hints.
    # - You can define the tools the agent can use.
    # - You can define if the agent should use the cache.
    #   Results will get cached and if true and if the input is the same as before,
    #   the agent will return the cached result.
    #   This is useful for expensive operations like web scraping and for debugging.
    agent = FlockAgent(
        name="my_agent",
        input="url",
        output="title, headings: list[str], entities_and_metadata: list[dict[str, str]], type:Literal['news', 'blog', 'opinion piece', 'tweet']",
        tools=[basic_tools.get_web_content_as_markdown],
        use_cache=True,
    )
    flock.add_agent(agent)

    # --------------------------------
    # Run the agent
    # --------------------------------
    # ATTENTION: Big table incoming.
    # It's worth it though!
    result = await flock.run_async(
        start_agent=agent,
        input={"url": "https://lite.cnn.com/travel/alexander-the-great-macedon-persian-empire-darius/index.html"},
    )

    # --------------------------------
    # The result type
    # --------------------------------
    # The result is a real Python object with the types you defined.
    # For example, this works:
    pprint(result.title)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Summary

This example demonstrates an advanced Flock system with a custom output formatter, type hints for structured results, external tool integration, and caching functionality. The code is organized into clear sections for setup, agent creation, and execution. Use this as a template for building robust Flock agents.
